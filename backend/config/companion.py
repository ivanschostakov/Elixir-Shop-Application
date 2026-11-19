from .env import _bool_env, _env

# Fixed release behavior, never selected through environment variables.
AI_COMPANION_ENABLED = True
AI_COMPANION_DIALOGUE_ENABLED = True
AI_COMPANION_CONSENT_VERSION = "companion-v1"

# Dedicated Telegram bot bridge. Native attestation requirements remain unchanged.
TELEGRAM_AI_BRIDGE_ENABLED = _bool_env("TELEGRAM_AI_BRIDGE_ENABLED", False)
TELEGRAM_AI_BRIDGE_SECRET = _env("TELEGRAM_AI_BRIDGE_SECRET", "")
