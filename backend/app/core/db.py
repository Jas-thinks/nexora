from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    kwargs: dict = {}
    if not url.startswith("sqlite"):
        s = get_settings()
        # pre_ping: a connection killed by a Postgres restart / failover is replaced instead of failing a user request.
        kwargs.update(pool_size=s.db_pool_size, max_overflow=s.db_max_overflow, pool_recycle=s.db_pool_recycle_s, pool_pre_ping=True)
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            from sqlalchemy.pool import StaticPool
            kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db
