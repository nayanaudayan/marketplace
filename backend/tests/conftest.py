import os
import tempfile

# Must be set before the app is imported. Uses a dedicated database so dev data is never touched.
TEST_DB = "marketplace_test"
BASE_URL = os.environ.get("TEST_DATABASE_SERVER", "postgresql+psycopg://marketplace:marketplace@localhost:5433")
os.environ["DATABASE_URL"] = f"{BASE_URL}/{TEST_DB}"
os.environ["CELERY_EAGER"] = "true"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["ENVIRONMENT"] = "test"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="marketplace-test-uploads-")
os.environ["MAX_UPLOAD_MB"] = "1"
os.environ["SPEC_CATALOG_TTL_SECONDS"] = "0"
os.environ["REDIS_URL"] = "redis://127.0.0.1:6399/0"  # nothing listens here: exercises the no-Redis fallbacks

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


def _ensure_database() -> None:
    admin = create_engine(f"{BASE_URL}/postgres", isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        if not conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": TEST_DB}):
            conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    admin.dispose()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


@pytest.fixture(scope="session", autouse=True)
def _schema():
    _ensure_database()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_db():
    yield
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session
