import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from openai import APIConnectionError

from src.app.services.ai.companion import recipe_photo_selection as photos
from src.app.services.ai.companion.food_suggestions import RecipeImage
from src.app.services.ai.companion.recipe_images import RecipePhotoCandidate
from src.app.services.ai.companion.recipe_images import MAX_PHOTO_BYTES, load_recipe_photo
from src.integrations.ai.client import ProfessorClient
from src.integrations.ai.enums import BotModel


def recipe(**changes):
    return SimpleNamespace(**{"name": "Chicken and rice", "image_query": "grilled chicken rice", "ingredients": ["Chicken 120 g", "Rice 60 g"], "steps": ["Grill chicken", "Cook rice and serve together"], **changes})


def candidate(name):
    return RecipePhotoCandidate(title=name, image=RecipeImage(url=f"https://thumb.wikimedia.org/wikipedia/commons/{name}.jpg", source_url=f"https://commons.wikimedia.org/wiki/File:{name}.jpg", author="Photographer", license="CC0"))


@pytest.fixture(autouse=True)
def clear_photo_cache(monkeypatch):
    photos._verified.clear()
    monkeypatch.setattr(photos, "load_recipe_photo", AsyncMock(return_value=("image/jpeg", b"\xff\xd8\xff")))


def provider(matches):
    return SimpleNamespace(inspect_images=AsyncMock(return_value={"structured_output": {"matches": matches}, "input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 30}))


def test_visual_match_can_skip_the_first_search_result_and_caches_full_recipe(monkeypatch):
    wrong, right = candidate("Chicken_potatoes"), candidate("Chicken_rice")
    search = AsyncMock(return_value=[wrong, right]); monkeypatch.setattr(photos, "find_recipe_candidates", search)
    client = provider([{"recipe_id": 0, "candidate_id": 1, "matches": True, "confidence": 0.97}])
    async def run():
        result, usage = await photos.select_recipe_photos([recipe()], client=client, bot_model=BotModel.FREE, resource_recorder=None)
        assert result == [right.image] and usage["input_tokens"] == 100
        cached, usage = await photos.select_recipe_photos([recipe()], client=client, bot_model=BotModel.FREE, resource_recorder=None)
        assert cached == [right.image] and usage == {}
        assert client.inspect_images.await_count == 1
        # Same query with a different side/preparation must be checked again.
        await photos.select_recipe_photos([recipe(ingredients=["Chicken 120 g", "Potatoes 100 g"])], client=client, bot_model=BotModel.FREE, resource_recorder=None)
        assert client.inspect_images.await_count == 2
    asyncio.run(run())
    request = client.inspect_images.call_args.kwargs
    assert request["image_contents"] == [("image/jpeg", b"\xff\xd8\xff")] * 2
    assert "potatoes" in request["instructions"] and "Never approve a photo based only on its title" in request["instructions"]
    assert "ingredients" in json.loads(request["input_text"])[0]


@pytest.mark.parametrize("match", [
    {"recipe_id": 0, "candidate_id": 0, "matches": False, "confidence": 1},
    {"recipe_id": 0, "candidate_id": 0, "matches": True, "confidence": 0.7},
    {"recipe_id": 0, "candidate_id": None, "matches": False, "confidence": 1},
    {"recipe_id": 0, "candidate_id": 11, "matches": True, "confidence": 1},
])
def test_unmatched_uncertain_or_invented_candidates_never_fall_back_to_first_photo(monkeypatch, match):
    monkeypatch.setattr(photos, "find_recipe_candidates", AsyncMock(return_value=[candidate("Unrelated")]))
    result, usage = asyncio.run(photos.select_recipe_photos([recipe()], client=provider([match]), bot_model=BotModel.FREE, resource_recorder=None))
    assert result == [None] and usage["input_tokens"] == 100


def test_candidate_must_belong_to_its_recipe_and_photos_are_not_repeated(monkeypatch):
    chicken, soup = candidate("Chicken"), candidate("Soup")
    monkeypatch.setattr(photos, "find_recipe_candidates", AsyncMock(side_effect=[[chicken], [soup]]))
    client = provider([{"recipe_id": 0, "candidate_id": 1, "matches": True, "confidence": 1}, {"recipe_id": 1, "candidate_id": 1, "matches": True, "confidence": 1}])
    result, _ = asyncio.run(photos.select_recipe_photos([recipe(), recipe(name="Soup")], client=client, bot_model=BotModel.FREE, resource_recorder=None))
    assert result == [None, soup.image]


def test_failed_download_is_removed_before_candidate_numbers_are_assigned(monkeypatch):
    wrong, right = candidate("Unavailable"), candidate("Chicken_rice")
    monkeypatch.setattr(photos, "find_recipe_candidates", AsyncMock(return_value=[wrong, right]))
    monkeypatch.setattr(photos, "load_recipe_photo", AsyncMock(side_effect=[None, ("image/jpeg", b"\xff\xd8\xff")]))
    client = provider([{"recipe_id": 0, "candidate_id": 0, "matches": True, "confidence": 1}])
    result, _ = asyncio.run(photos.select_recipe_photos([recipe()], client=client, bot_model=BotModel.FREE, resource_recorder=None))
    assert result == [right.image]
    data = json.loads(client.inspect_images.call_args.kwargs["input_text"])
    assert data[0]["candidates"] == [{"candidate_id": 0, "title": "Chicken_rice"}]


def test_downloads_accept_only_bounded_images_from_the_public_photo_host():
    requested = []
    def transport(request):
        requested.append(str(request.url))
        path = request.url.path
        if path.endswith("Redirect.jpg"):
            return httpx.Response(302, headers={"Location": "http://169.254.169.254/private"})
        if path.endswith("Html.jpg"):
            return httpx.Response(200, content=b"<html>not a photograph</html>")
        if path.endswith("Large.jpg"):
            return httpx.Response(200, headers={"content-length": "1"}, content=b"x" * (MAX_PHOTO_BYTES + 1))
        return httpx.Response(200, content=b"\xff\xd8\xffJPEG")
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            assert await load_recipe_photo(candidate("Chicken").image.url, client=client) == ("image/jpeg", b"\xff\xd8\xffJPEG")
            for name in ("Redirect", "Html", "Large"):
                assert await load_recipe_photo(candidate(name).image.url, client=client) is None
            assert await load_recipe_photo("http://localhost/private", client=client) is None
            assert await load_recipe_photo("https://upload.wikimedia.org.evil.test/wikipedia/commons/x.jpg", client=client) is None
    asyncio.run(run())
    assert len(requested) == 4


def test_missing_search_and_unavailable_inspection_leave_recipes_without_unverified_images(monkeypatch):
    search = AsyncMock(return_value=[]); monkeypatch.setattr(photos, "find_recipe_candidates", search)
    client = provider([])
    result, usage = asyncio.run(photos.select_recipe_photos([recipe()], client=client, bot_model=BotModel.FREE, resource_recorder=None))
    assert result == [None] and usage == {}
    client.inspect_images.assert_not_awaited()
    search.return_value = [candidate("Chicken")]
    client.inspect_images.side_effect = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    result, usage = asyncio.run(photos.select_recipe_photos([recipe()], client=client, bot_model=BotModel.FREE, resource_recorder=None))
    assert result == [None] and usage == {}
    client.inspect_images.side_effect = HTTPException(409, "Consent revoked")
    with pytest.raises(HTTPException):
        asyncio.run(photos.select_recipe_photos([recipe()], client=client, bot_model=BotModel.FREE, resource_recorder=None))


def test_photo_inspection_is_stateless_has_no_tools_and_reports_actual_usage(monkeypatch):
    async def run():
        client = ProfessorClient(api_key="test-key", proxy_url=None)
        response = SimpleNamespace(id="resp_photo", model="gpt-5.6-sol", output_text='{"matches":[]}', usage=SimpleNamespace(input_tokens=120, input_tokens_details=SimpleNamespace(cached_tokens=30), output_tokens=15))
        create, recorded = AsyncMock(return_value=response), AsyncMock()
        options = {}
        def with_options(**kwargs):
            options.update(kwargs)
            return SimpleNamespace(responses=SimpleNamespace(create=create))
        monkeypatch.setattr(client, "with_options", with_options)
        try:
            result = await client.inspect_images(input_text="Public recipe data", instructions="Match photographs", image_contents=[("image/jpeg", b"\xff\xd8\xff")], output_schema=photos.PhotoSelection.model_json_schema(), bot_model=BotModel.FREE, resource_recorder=recorded)
            request = create.call_args.kwargs
            assert request["store"] is False and request["tools"] == []
            assert "conversation" not in request and "companion_context" not in request
            assert request["input"][0]["content"][-1]["detail"] == "low"
            assert options == {"max_retries": 0, "timeout": 40}
            assert result["input_tokens"] == 120 and result["cached_input_tokens"] == 30 and result["output_tokens"] == 15
            recorded.assert_awaited_once_with("response", "resp_photo")
            for contents in [[("text/html", b"not a photo")], [("image/jpeg", b"")], [("image/jpeg", b"x")] * 13]:
                with pytest.raises(ValueError):
                    await client.inspect_images(input_text="Recipe", instructions="Check", image_contents=contents, output_schema={}, bot_model=BotModel.FREE)
            assert create.await_count == 1
        finally:
            await client.aclose()
    asyncio.run(run())


def test_real_sdk_request_options_work_with_the_application_client():
    captured = []
    def transport(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "resp_photo", "object": "response", "created_at": 1, "status": "completed", "model": "gpt-5.6-sol", "output": [{"id": "msg_photo", "type": "message", "status": "completed", "role": "assistant", "content": [{"type": "output_text", "text": '{"matches":[]}', "annotations": []}]}], "usage": {"input_tokens": 40, "input_tokens_details": {"cached_tokens": 0}, "output_tokens": 5}})
    async def run():
        client = ProfessorClient(api_key="test-key", proxy_url=None, http_client=httpx.AsyncClient(transport=httpx.MockTransport(transport)))
        try:
            result = await client.inspect_images(input_text="Recipe", instructions="Inspect photos", image_contents=[("image/jpeg", b"\xff\xd8\xff")], output_schema=photos.PhotoSelection.model_json_schema(), bot_model=BotModel.FREE)
            assert result["structured_output"] == {"matches": []}
            assert result["input_tokens"] == 40
        finally:
            await client.aclose()
    asyncio.run(run())
    assert captured[0]["store"] is False and captured[0]["tools"] == []
