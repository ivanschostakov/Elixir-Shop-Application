from pathlib import Path


INSTRUCTIONS = Path(__file__).parents[1] / "src/integrations/ai/instructions"


def test_mentor_protocols_do_not_authorize_prescribing():
    for name in ("companion.txt", "companion-dialogue.txt"):
        prompt = (INSTRUCTIONS / name).read_text()
        assert "специалист" in prompt
        assert "не меняй дозировку" in prompt or "не меняй медицинскую схему" in prompt
        assert "latest_weight" in prompt
        assert "не подменяй расчёт своими числами" in prompt or "не выдумывай дневную норму" in prompt
        assert "можешь подобрать препарат" not in prompt
        assert "дай в assistant_text конкретную рекомендацию" not in prompt


def test_course_recommendations_are_historical_only():
    prompt = (INSTRUCTIONS / "companion-dialogue.txt").read_text()
    assert "только при переносе готовой пользовательской схемы" in prompt
    assert "Исторические записи с source=ai_recommended_plan" in prompt
    assert "не являются разрешением создать новую рекомендацию" in prompt


def test_telegram_reminders_are_opt_in_and_timezone_is_not_invented():
    prompt = (INSTRUCTIONS / "companion-telegram.txt").read_text()
    assert "только по включённым пользователем настройкам" in prompt
    assert "Не утверждай, что пояс получен с телефона" in prompt


def test_app_profile_requires_telegram_fields_and_keeps_phone_timezone_automatic():
    for name in ("companion.txt", "companion-dialogue.txt"):
        prompt = (INSTRUCTIONS / name).read_text()
        required = prompt.split("четыре шага — ", 1)[1].split(".", 1)[0]
        for field in ("goal", "age", "sex", "height_cm", "latest_weight", "activity"):
            assert f"({field})" in required
        assert "Целевой вес (target_weight_kg), предпочтения (preferences) и ограничения (restrictions) необязательны" in prompt
        assert "по кнопке «Открыть наставника»" in prompt
        assert "Не собирай эти данные вопросами в чате" in prompt
        assert "без вопроса и подтверждения" in prompt
