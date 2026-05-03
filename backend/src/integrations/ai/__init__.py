from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import ProfessorClient

_professor_client: "ProfessorClient | None" = None


def get_professor_client() -> "ProfessorClient":
    global _professor_client
    if _professor_client is None:
        from .client import ProfessorClient
        _professor_client = ProfessorClient()
    return _professor_client


__all__ = ["get_professor_client"]
