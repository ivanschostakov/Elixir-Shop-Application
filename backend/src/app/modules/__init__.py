"""Application module packages.

Routers are imported directly by ``src.app.router``. Keeping this package
initializer light avoids circular imports when background workers import schema
modules without booting the whole FastAPI router tree.
"""

__all__: list[str] = []
