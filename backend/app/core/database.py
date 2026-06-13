"""SQLAlchemy database engine and session infrastructure.

This module creates the synchronous PostgreSQL engine and session factory.
Creating the engine does not establish a database connection until the first
database operation is executed.

Application services are responsible for explicitly committing transactions.
The FastAPI dependency rolls back failed transactions and always closes the
session.
"""

from collections.abc import Generator
from functools import lru_cache
from typing import Final

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings

DATABASE_DRIVER: Final[str] = "postgresql+psycopg"

DEFAULT_POOL_SIZE: Final[int] = 5
DEFAULT_MAX_OVERFLOW: Final[int] = 10
DEFAULT_POOL_TIMEOUT_SECONDS: Final[int] = 30
DEFAULT_POOL_RECYCLE_SECONDS: Final[int] = 1800


def build_database_url(settings: Settings | None = None) -> URL:
    """Build a PostgreSQL URL without manually concatenating credentials.

    ``URL.create`` safely handles passwords containing reserved URL
    characters. Callers must not render the returned URL with its password
    visible.
    """

    active_settings = settings or get_settings()

    return URL.create(
        drivername=DATABASE_DRIVER,
        username=active_settings.database_user,
        password=active_settings.database_password.get_secret_value(),
        host=active_settings.database_host,
        port=active_settings.database_port,
        database=active_settings.database_name,
    )


def get_safe_database_url(settings: Settings | None = None) -> str:
    """Return a database URL with the password hidden."""

    return build_database_url(settings).render_as_string(
        hide_password=True,
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine.

    The engine is created lazily and cached. No physical PostgreSQL connection
    is opened until a query or connection operation is performed.
    """

    settings = get_settings()

    return create_engine(
        build_database_url(settings),
        pool_pre_ping=True,
        pool_size=DEFAULT_POOL_SIZE,
        max_overflow=DEFAULT_MAX_OVERFLOW,
        pool_timeout=DEFAULT_POOL_TIMEOUT_SECONDS,
        pool_recycle=DEFAULT_POOL_RECYCLE_SECONDS,
        connect_args={
            "connect_timeout": settings.database_connect_timeout_seconds,
            "sslmode": settings.database_sslmode,
            "options": (
                "-c client_encoding="
                f"{settings.database_client_encoding}"
            ),
        },
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Return the process-wide SQLAlchemy session factory."""

    return sessionmaker(
        bind=get_engine(),
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )


def get_db_session() -> Generator[Session, None, None]:
    """Yield one SQLAlchemy session for a FastAPI request.

    This dependency intentionally does not commit automatically. Business
    services must explicitly call ``session.commit()`` after successful write
    operations.
    """

    session = get_session_factory()()

    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_connection() -> dict[str, str]:
    """Run a read-only query and return non-sensitive connection metadata."""

    query = text(
        """
        SELECT
            current_database(),
            current_user,
            current_setting('server_encoding'),
            current_setting('client_encoding'),
            current_setting('TimeZone')
        """
    )

    with get_engine().connect() as connection:
        row = connection.execute(query).one()

    return {
        "database": str(row[0]),
        "user": str(row[1]),
        "server_encoding": str(row[2]),
        "client_encoding": str(row[3]),
        "timezone": str(row[4]),
    }


def dispose_database_engine() -> None:
    """Dispose pooled connections and clear cached database objects."""

    get_session_factory.cache_clear()

    engine = get_engine()
    engine.dispose()

    get_engine.cache_clear()


__all__ = [
    "DATABASE_DRIVER",
    "build_database_url",
    "check_database_connection",
    "dispose_database_engine",
    "get_db_session",
    "get_engine",
    "get_safe_database_url",
    "get_session_factory",
]