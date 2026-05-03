from .client import ProfessorClient

professor_client = ProfessorClient()

def get_professor_client() -> ProfessorClient: return professor_client

__all__ = ["professor_client", "get_professor_client", "ProfessorClient"]