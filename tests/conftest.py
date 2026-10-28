import os
import tempfile

# Point the app at a throwaway database before backend modules are imported,
# so test runs never write fixtures into the demo workspace in auditra.db.
_db_dir = tempfile.mkdtemp(prefix="auditra-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_db_dir, 'test.db')}"
os.environ["AUDITRA_DEMO_LOGIN"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

CLIENT_HEADER = {"X-Auditra-Client": "web"}


def make_client(persona=None) -> TestClient:
    """A TestClient that sends the CSRF header and, optionally, is signed in as a demo persona."""
    from backend.main import app
    c = TestClient(app, headers=CLIENT_HEADER)
    c.__enter__()
    if persona:
        r = c.post("/api/auth/demo", json={"persona": persona})
        assert r.status_code == 200, r.text
    return c


def register_client(email: str, name: str = "Test Person", password: str = "correct-horse-battery") -> TestClient:
    c = make_client()
    r = c.post("/api/auth/register", json={"email": email, "password": password, "display_name": name})
    assert r.status_code == 201, r.text
    return c
