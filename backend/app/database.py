"""Database engine and session management."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL

# SQLite needs check_same_thread=False for FastAPI
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

# Enable foreign keys + WAL for SQLite
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        # WAL：读写并发，多人同时使用时避免整库加锁互相阻塞
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            # NORMAL 在 WAL 下兼顾性能与安全（崩溃最多丢失最后一个检查点后的事务）
            cursor.execute("PRAGMA synchronous=NORMAL")
            # 队列忙等 5 秒，避免偶发写入直接抛 database is locked
            cursor.execute("PRAGMA busy_timeout=5000")
        except Exception:
            pass
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
