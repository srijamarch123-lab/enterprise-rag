from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config.settings import get_settings

settings = get_settings()

db_url = settings.database_url
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine_args = {}
if "sqlite" in db_url:
    engine_args["connect_args"] = {"check_same_thread": False}
else:
    import os
    engine_args["pool_size"] = int(os.environ.get("DB_POOL_SIZE", "10"))
    engine_args["max_overflow"] = int(os.environ.get("DB_MAX_OVERFLOW", "20"))
    engine_args["pool_recycle"] = int(os.environ.get("DB_POOL_RECYCLE", "1800"))
    engine_args["pool_pre_ping"] = True

engine = create_engine(db_url, **engine_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401 — registers all models
    Base.metadata.create_all(bind=engine)
    # Check if chunks table has parent_text column, if not add it dynamically
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("chunks")]
        if "parent_text" not in columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE chunks ADD COLUMN parent_text TEXT"))
                conn.commit()
    except Exception:
        pass

    # Check if users table has department column, if not add it dynamically
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        user_columns = [c["name"] for c in inspector.get_columns("users")]
        if "department" not in user_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN department VARCHAR(100)"))
                conn.commit()
    except Exception:
        pass
