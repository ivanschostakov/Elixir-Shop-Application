from .env import _bool_env, _env

# Release gates: no production health workflow is enabled by a migration alone.
AI_COMPANION_ENABLED = _bool_env("AI_COMPANION_ENABLED", False)
AI_COMPANION_CONSENT_VERSION = _env("AI_COMPANION_CONSENT_VERSION", "companion-v1")
AI_COMPANION_NUTRITION_RULES_JSON = _env("AI_COMPANION_NUTRITION_RULES_JSON", "")
