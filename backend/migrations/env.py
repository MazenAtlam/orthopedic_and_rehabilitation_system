import os

from alembic import context
from sqlalchemy import create_engine, pool

from app import normalize_database_url
from app.models.schema_v1 import metadata


def migrate():
    url = normalize_database_url(os.environ["DATABASE_URL"])
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


migrate()
