import os

os.environ["CODEMIND_DATABASE_URL"] = os.environ.get("NEXORA_TEST_DB", "sqlite:///:memory:")  # set NEXORA_TEST_DB=postgresql+psycopg://... to run on Postgres
os.environ["CODEMIND_AUTH_RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ["CODEMIND_WORKER_ENABLED"] = "false"
os.environ["CODEMIND_EXPERIMENT_HOLDOUT_FRACTION"] = "0.0"  # experiment tests set their own fraction

import pytest
from fastapi.testclient import TestClient

from app.core import db as dbmod
from app.core.ratelimit import limiter
from app.main import create_app
from app.models import User  # noqa: F401  (register models)


@pytest.fixture()
def client():
    dbmod.Base.metadata.drop_all(dbmod.engine)
    dbmod.Base.metadata.create_all(dbmod.engine)
    limiter.hits.clear()
    from app.core import cache
    cache.clear_local()  # the cache is process-wide; every test starts with a fresh DB so it must start cold
    return TestClient(create_app())


def register(client, email="a@example.com", pw="correct-horse-battery"):
    r = client.post("/auth/register", json={"email": email, "display_name": "A", "password": pw})
    assert r.status_code == 201, r.text
    return r.json()


def auth(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}
