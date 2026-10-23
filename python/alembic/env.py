"""How Alembic connects. The app passes its own connection in (see ``app/db/session.py``); the
``alembic`` command line connects to DATABASE_URL instead."""
from alembic import context

from app.core.config import get_settings
from app.db.models import Base
from app.db.session import make_engine

target_metadata = Base.metadata


def run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    with make_engine(get_settings().database_url).begin() as conn:
        run(conn)
