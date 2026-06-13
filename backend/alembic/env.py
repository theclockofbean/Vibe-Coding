"""Alembic migration environment.

The database URL is loaded from the project root .env file. Real credentials
must never be stored in alembic.ini or generated migration files.
"""

from logging.config import fileConfig

from sqlalchemy import Connection, Engine, create_engine, pool

from alembic import context
from app.core.config import get_settings
from app.core.database import build_database_url
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Return the application database URL for Alembic.

    Percent characters are escaped because Alembic configuration values use
    ConfigParser interpolation rules.
    """

    url = build_database_url(get_settings()).render_as_string(
        hide_password=False,
    )
    return url.replace("%", "%%")


def configure_context(connection: Connection) -> None:
    """Configure Alembic against an active database connection."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=False,
        version_table="alembic_version",
    )


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""

    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=False,
        version_table="alembic_version",
    )

    with context.begin_transaction():
        context.run_migrations()


def create_migration_engine() -> Engine:
    """Create a migration-only SQLAlchemy engine."""

    settings = get_settings()

    return create_engine(
        build_database_url(settings),
        poolclass=pool.NullPool,
        connect_args={
            "connect_timeout": settings.database_connect_timeout_seconds,
            "sslmode": settings.database_sslmode,
            "options": (
                "-c client_encoding="
                f"{settings.database_client_encoding}"
            ),
        },
    )


def run_migrations_online() -> None:
    """Run migrations using a live PostgreSQL connection."""

    connectable = create_migration_engine()

    try:
        with connectable.connect() as connection:
            configure_context(connection)

            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()