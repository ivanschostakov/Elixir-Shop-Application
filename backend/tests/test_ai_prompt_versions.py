import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.integrations.ai.client import ProfessorClient
from src.integrations.ai.enums import BotModel


@pytest.mark.parametrize("model,role", [
    (BotModel.FREE, "Ты — *Профессор медицины*."),
    (BotModel.PREMIUM, "Ты — УНИКАЛЬНЕЙШЕЙ СИЛЫ *Профессор медицины*."),
])
def test_ordinary_chat_uses_the_restored_tier_prompt(model, role, monkeypatch, tmp_path):
    instructions_dir = Path(__file__).parents[1] / "src/integrations/ai/instructions"
    expected = (instructions_dir / f"{model.value}.txt").read_text(encoding="utf-8")
    other_model = BotModel.PREMIUM if model == BotModel.FREE else BotModel.FREE
    other = (instructions_dir / f"{other_model.value}.txt").read_text(encoding="utf-8")
    create = AsyncMock(return_value=SimpleNamespace(id="resp_test"))
    client = SimpleNamespace(
        responses=SimpleNamespace(create=create),
        _resolve_model_name=ProfessorClient._resolve_model_name,
        _load_instructions=ProfessorClient._load_instructions,
        _build_reasoning_payload=ProfessorClient._build_reasoning_payload,
    )
    monkeypatch.chdir(tmp_path)

    asyncio.run(ProfessorClient._create_v2_response(
        client, model=model, conversation_id="conv_test", input_payload="Hello", tools=[],
    ))

    payload = create.call_args.kwargs
    assert payload["instructions"] == expected
    assert payload["instructions"] != other
    assert role in payload["instructions"]
    assert "### SECURITY / DEFENSE BLOCK" in payload["instructions"]
    assert payload["model"] == "gpt-5.6-sol"
    assert payload["reasoning"] == ProfessorClient._build_reasoning_payload(model)
    assert payload["conversation"] == {"id": "conv_test"}
