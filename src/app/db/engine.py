"""异步引擎。SQLite 内存库用 StaticPool，避免连接丢失。"""

from pathlib import Path

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import Base


def create_engine(database_url: str) -> AsyncEngine:
    _ensure_sqlite_dir(database_url)
    kwargs: dict = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if _is_memory_sqlite(database_url):
            kwargs["poolclass"] = StaticPool
    return create_async_engine(database_url, **kwargs)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _is_memory_sqlite(database_url: str) -> bool:
    database = make_url(database_url).database
    return database in {None, "", ":memory:"}


def _ensure_sqlite_dir(database_url: str) -> None:
    parsed = make_url(database_url)
    if not parsed.drivername.startswith("sqlite"):
        return
    database = parsed.database
    if not database or database == ":memory:":
        return
    Path(database).parent.mkdir(parents=True, exist_ok=True)
