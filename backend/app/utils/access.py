"""Re-export of the shared JWT-to-database actor loader."""

from app.auth.access import load_actor

__all__ = ["load_actor"]
