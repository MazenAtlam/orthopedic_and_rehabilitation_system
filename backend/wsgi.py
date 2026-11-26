"""Entry point used by Flask CLI and gunicorn: ``wsgi:app``."""

from app import create_app

app = create_app()
