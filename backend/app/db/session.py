"""SQLite 引擎与会话工厂。

关键点（单进程多线程：syslog worker / system2 / nightly / uvicorn 线程池）：
- `check_same_thread=False`：允许跨线程使用连接；
- `NullPool`：每线程/会话独立开连接，绝不跨线程共享同一个 Session；
- WAL 由文件头持久化（连接级 pragma 幂等）；foreign_keys 每次连接都开。
"""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.paths import DB_PATH

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
