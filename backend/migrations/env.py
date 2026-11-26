import os

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import normalize_database_url
from app.models import Base

target_metadata = Base.metadata


def migrate() -> None:
    url = normalize_database_url(os.environ["DATABASE_URL"])
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


migrate()
