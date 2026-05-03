from os import getenv


def _env(name: str, default: str | None = None) -> str | None:
    value = getenv(name)
    if value is None or value == "": return default
    return value


def _required_env(name: str) -> str:
    value = _env(name)
    if value is None: raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _int_env(name: str, default: int | None = None) -> int:
    value = _env(name)
    if value is None:
        if default is None: raise RuntimeError(f"Missing required environment variable: {name}")
        return default
    return int(value)


def _float_env(name: str, default: float) -> float:
    value = _env(name)
    if value is None: return default
    return float(value)


def _csv_env(name: str, default: str = "") -> list[str]:
    raw = _env(name, default) or ""
    return [chunk.strip() for chunk in raw.split(",") if chunk.strip()]


def _bool_env(name: str, default: bool = False) -> bool:
    value = _env(name)
    if value is None: return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
