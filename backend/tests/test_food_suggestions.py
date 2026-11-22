import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.app.services.ai.chat_interactive import build_ai_chat_output_schema
from src.app.services.ai.companion.food_suggestions import FoodSuggestion, MealSuggestionContext, next_meal_context, suggestion_errors
from src.app.services.ai.companion import recipe_images


def nutrition(kcal=1200):
    return {"kcal": kcal, "protein": 90, "fat": 40, "carbs": 120}


def test_next_meal_budget_uses_local_time_and_logged_groups_not_preview_limits():
    snapshot = {"as_of": "2026-11-21T06:00:00+00:00", "timezone": "Europe/Moscow", "remaining_nutrition": nutrition()}
    context = next_meal_context(snapshot)
    assert context.meal_type == "breakfast" and context.meals_left == 3 and context.budget.kcal == 400
    snapshot["confirmed_food_today"] = [{"data": {"meal_type": "breakfast"}}, *[{"data": {"meal_type": "extra"}} for _ in range(100)]]
    context = next_meal_context(snapshot)
    assert context.meal_type == "lunch" and context.meals_left == 2 and context.budget.kcal == 600
    # Unlogged breakfast is not treated as a future meal in the evening.
    snapshot["as_of"] = "2026-11-21T17:00:00+00:00"
    context = next_meal_context(snapshot)
    assert context.meal_type == "dinner" and context.meals_left == 1 and context.budget.kcal == 1200
    snapshot["confirmed_food_today"].append({"occurred_at": "2026-11-21T15:00:00+00:00", "data": {}})
    assert next_meal_context(snapshot).meal_type == "extra"
    snapshot["remaining_nutrition"] = None
    assert next_meal_context(snapshot).budget is None
    snapshot["remaining_nutrition"] = nutrition(0)
    assert next_meal_context(snapshot).budget.kcal == 0


def recipe(**changes):
    return FoodSuggestion.model_validate({"name": "Chicken and rice", "description": "Balanced meal", "portion": "One bowl", "nutrition": {"kcal": 440, "protein": 30, "fat": 12, "carbs": 53}, "minutes": 25, "ingredients": ["Chicken 120 g", "Rice 60 g"], "steps": ["Cook rice", "Cook chicken and serve"], "image_query": "chicken rice", **changes})


def test_recipe_schema_is_only_exposed_for_selection_and_validates_portions():
    assert "nutrition_suggestions" not in build_ai_chat_output_schema(include_companion=True, dialogue=True)["properties"]
    schema = build_ai_chat_output_schema(include_companion=True, dialogue=True, nutrition_suggestions=True)
    assert "nutrition_suggestions" in schema["required"]
    context = MealSuggestionContext(meal_type="lunch", meals_left=2, budget=nutrition(600))
    output = SimpleNamespace(nutrition_suggestions=[recipe(), recipe(name="Second bowl")])
    assert suggestion_errors(output, context) == []
    output.nutrition_suggestions = [recipe()]
    assert suggestion_errors(output, context)
    output.nutrition_suggestions = [recipe(), recipe(nutrition=nutrition(1500))]
    assert "portions" in suggestion_errors(output, context)[0]["message"]
    output.nutrition_suggestions = [recipe(), recipe(nutrition={"kcal": 440, "protein": 2, "fat": 2, "carbs": 2})]
    assert "macros" in suggestion_errors(output, context)[0]["message"]
    with pytest.raises(ValueError):
        recipe(image_query="https://example.com/private-profile")


def commons_page(**changes):
    return {"imageinfo": [{"mime": "image/jpeg", "thumburl": "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/Dish.jpg?utm_source=x", "descriptionurl": "https://commons.wikimedia.org/wiki/File:Dish.jpg", "extmetadata": {"Artist": {"value": '<a href="https://example.com">Jane &amp; Joe</a>'}, "LicenseShortName": {"value": "CC BY-SA 4.0"}}, **changes}]}


def test_photo_metadata_retains_credit_and_rejects_unsupported_licenses_or_hosts():
    image = recipe_images.commons_image(commons_page())
    assert image.author == "Jane & Joe" and image.license == "CC BY-SA 4.0"
    assert "?" not in image.url
    for change in [
        {"thumburl": "https://attacker.example/photo.jpg"}, {"thumburl": "https://upload.wikimedia.org.evil.test/wikipedia/commons/x.jpg"},
        {"descriptionurl": "https://example.com"}, {"mime": "image/svg+xml"},
        {"extmetadata": {"LicenseShortName": {"value": "All rights reserved"}}},
    ]:
        assert recipe_images.commons_image(commons_page(**change)) is None


def test_public_photo_search_is_bounded_cached_and_fails_without_losing_recipes(monkeypatch):
    recipe_images._cache.clear()
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"query": {"pages": {"1": commons_page()}}})
    get = AsyncMock(return_value=response)
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
    Client.get = get
    monkeypatch.setattr(recipe_images.httpx, "AsyncClient", Client)
    async def scenario():
        assert await recipe_images.find_recipe_candidates("chicken rice") != []
        assert await recipe_images.find_recipe_candidates("chicken rice") != []
        assert await recipe_images.find_recipe_candidates("https://private") == []
    asyncio.run(scenario())
    assert get.await_count == 1
    assert get.call_args.kwargs["params"]["gsrsearch"] == "chicken rice filetype:bitmap"
    assert get.call_args.kwargs["params"]["gsrlimit"] == 8
    recipe_images._cache.clear()
    get.reset_mock()
    response.json = lambda: {}
    assert asyncio.run(recipe_images.find_recipe_candidates("grilled chicken rice broccoli")) == []
    assert get.await_count == 2
    assert get.call_args_list[0].kwargs["params"]["gsrsearch"] == "grilled chicken rice broccoli filetype:bitmap"
    assert get.call_args.kwargs["params"]["gsrsearch"] == "(grilled OR chicken OR rice OR broccoli) filetype:bitmap"
    recipe_images._cache.clear()
    get.side_effect = recipe_images.httpx.ConnectError("Offline")
    assert asyncio.run(recipe_images.find_recipe_candidates("rice bowl")) == []


def test_empty_full_dish_search_retries_all_terms_and_still_returns_only_candidates(monkeypatch):
    recipe_images._cache.clear()
    empty = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {})
    found = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"query": {"pages": {"1": commons_page()}}})
    get = AsyncMock(side_effect=[empty, found])
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
    Client.get = get
    monkeypatch.setattr(recipe_images.httpx, "AsyncClient", Client)
    result = asyncio.run(recipe_images.find_recipe_candidates("grilled chicken with rice broccoli"))
    assert len(result) == 1 and isinstance(result[0], recipe_images.RecipePhotoCandidate)
    assert get.await_count == 2
    assert get.call_args.kwargs["params"]["gsrsearch"] == "(grilled OR chicken OR rice OR broccoli) filetype:bitmap"
    assert get.call_args.kwargs["params"]["gsrnamespace"] == 6
