"""Authentication, authorisation, approval-policy and publishing safety tests."""
import uuid

import pytest

from tests.conftest import make_client, register_client


@pytest.fixture(scope="module")
def creator():
    return make_client("creator")


@pytest.fixture(scope="module")
def reviewer():
    return make_client("reviewer")


@pytest.fixture(scope="module")
def admin():
    return make_client("admin")


@pytest.fixture(scope="module")
def brand_id(creator):
    return next(b["id"] for b in creator.get("/api/brands").json() if b["slug"] == "northstar")


def _new_item(c, brand_id, body="Discover how Northstar members streamline cloud governance with automated policy guardrails."):
    r = c.post(f"/api/brands/{brand_id}/content", json={"title": f"Test {uuid.uuid4().hex[:6]}", "content_type": "email", "body": body})
    assert r.status_code == 201, r.text
    return r.json()


# --- Authentication ---

def test_anonymous_requests_are_rejected(brand_id):
    anon = make_client()
    for path in ["/api/brands", f"/api/brands/{brand_id}/rules", f"/api/brands/{brand_id}/content",
                 f"/api/brands/{brand_id}/audit", f"/api/brands/{brand_id}/dna", f"/api/brands/{brand_id}/sources"]:
        assert anon.get(path).status_code == 401, path
    assert anon.post(f"/api/brands/{brand_id}/content", json={"title": "x", "body": "y"}).status_code == 401
    assert anon.get("/api/health").status_code == 200


def test_state_changing_calls_need_csrf_header(brand_id):
    from fastapi.testclient import TestClient
    from backend.main import app
    raw = TestClient(app)
    r = raw.post("/api/auth/demo", json={"persona": "creator"})
    assert r.status_code == 403


def test_register_login_logout_and_session_invalidation():
    email = f"judge-{uuid.uuid4().hex[:6]}@example.com"
    c = register_client(email)
    me = c.get("/api/auth/me").json()
    assert me["email"] == email and me["memberships"] == []
    assert c.cookies.get("auditra_session")
    token = c.cookies.get("auditra_session")
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/auth/me").status_code == 401
    # The old cookie value is revoked server-side, not only deleted client-side.
    c.cookies.set("auditra_session", token)
    assert c.get("/api/auth/me").status_code == 401
    bad = make_client().post("/api/auth/login", json={"email": email, "password": "wrong-password-123"})
    assert bad.status_code == 401
    good = make_client()
    assert good.post("/api/auth/login", json={"email": email, "password": "correct-horse-battery"}).status_code == 200


def test_password_rules_and_duplicates():
    c = make_client()
    assert c.post("/api/auth/register", json={"email": "short@example.com", "password": "abc", "display_name": "Al"}).status_code == 422
    assert c.post("/api/auth/register", json={"email": "not-an-email", "password": "long-enough-pw", "display_name": "Al"}).status_code == 422
    assert c.post("/api/auth/register", json={"email": "x@northstar.demo", "password": "long-enough-pw", "display_name": "Al"}).status_code == 422
    email = f"dup-{uuid.uuid4().hex[:6]}@example.com"
    register_client(email)
    assert make_client().post("/api/auth/register", json={"email": email, "password": "long-enough-pw", "display_name": "Al"}).status_code == 409


def test_passwords_are_hashed():
    from backend.database import SessionLocal
    from backend.models_r3 import User
    email = f"hash-{uuid.uuid4().hex[:6]}@example.com"
    register_client(email)
    db = SessionLocal()
    u = db.query(User).filter(User.email == email).first()
    assert u.password_hash.startswith("pbkdf2_sha256$") and "correct-horse" not in u.password_hash
    db.close()


def test_demo_personas_cannot_use_password_login():
    r = make_client().post("/api/auth/login", json={"email": "sarah.chen@northstar.demo", "password": ""})
    assert r.status_code in (401, 422)


# --- Authorisation ---

def test_creator_cannot_do_admin_actions(creator, brand_id):
    assert creator.post(f"/api/brands/{brand_id}/rules", json={
        "name": "Blocked rule", "category": "prohibited_term", "description": "x", "rule_text": "x", "match_pattern": "x", "severity": "low"
    }).status_code == 403
    assert creator.post(f"/api/brands/{brand_id}/policies", json={"name": "abc", "condition_type": "severity_at_least", "condition_value": "low"}).status_code == 403
    assert creator.post("/api/brands/sample/reset").status_code == 403
    assert creator.post(f"/api/brands/{brand_id}/members", json={"email": "a@b.co", "role": "admin"}).status_code == 403


def test_permission_failures_are_audited(creator, admin, brand_id):
    creator.delete(f"/api/brands/{brand_id}/rules/does-not-matter")
    events = admin.get(f"/api/brands/{brand_id}/audit?event_type=permission_denied").json()
    assert any("rules.manage" in e["description"] for e in events)


def test_reviewer_cannot_edit_or_create_content(reviewer, creator, brand_id):
    item = _new_item(creator, brand_id)
    assert reviewer.put(f"/api/content/{item['id']}", json={"body": "edited"}).status_code == 403
    assert reviewer.post(f"/api/brands/{brand_id}/content", json={"title": "x", "body": "y"}).status_code == 403
    assert creator.post(f"/api/content/{item['id']}/submit").status_code == 200
    assert creator.post(f"/api/content/{item['id']}/decision", json={"decision": "approved", "version_number": 1}).status_code == 403


def test_cross_workspace_access_is_blocked(brand_id, creator):
    outsider = register_client(f"outsider-{uuid.uuid4().hex[:6]}@example.com", name="Outsider")
    own = outsider.post("/api/brands", json={"name": f"Outsider Co {uuid.uuid4().hex[:4]}", "industry": "Retail"})
    assert own.status_code == 201
    assert [b["id"] for b in outsider.get("/api/brands").json()] == [own.json()["id"]]
    item = _new_item(creator, brand_id)
    for path in [f"/api/brands/{brand_id}", f"/api/brands/{brand_id}/rules", f"/api/content/{item['id']}",
                 f"/api/brands/{brand_id}/audit", f"/api/content/{item['id']}/replay"]:
        assert outsider.get(path).status_code == 404, path
    assert outsider.post(f"/api/content/{item['id']}/review", json={}).status_code == 404
    # The Northstar creator cannot see the outsider's workspace either.
    assert creator.get(f"/api/brands/{own.json()['id']}/rules").status_code == 404


def test_invalid_ids_and_malformed_requests(creator, brand_id):
    assert creator.get("/api/content/not-a-real-id").status_code == 404
    assert creator.post("/api/findings/nope/apply", json={}).status_code == 404
    r = creator.post(f"/api/brands/{brand_id}/content", content=b"{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert creator.post(f"/api/brands/{brand_id}/content", json={"title": "No body"}).status_code == 422
    assert creator.post(f"/api/brands/{brand_id}/content", json={"title": "Blank", "body": "   \n "}).status_code == 422
    assert creator.post(f"/api/brands/{brand_id}/content", json={"title": "Huge", "body": "a" * 60000}).status_code == 422


# --- Approval policies and version binding ---

def test_self_approval_stale_versions_and_duplicates(creator, reviewer, admin, brand_id):
    item = _new_item(creator, brand_id)
    cid = item["id"]
    creator.post(f"/api/content/{cid}/submit")
    # Not analysed yet
    assert reviewer.post(f"/api/content/{cid}/decision", json={"decision": "approved", "version_number": 1}).status_code == 409
    creator.post(f"/api/content/{cid}/review", json={})
    # Missing version / stale version
    assert reviewer.post(f"/api/content/{cid}/decision", json={"decision": "approved"}).status_code == 422
    assert reviewer.post(f"/api/content/{cid}/decision", json={"decision": "approved", "version_number": 99}).status_code == 409
    # Notes required for changes
    assert reviewer.post(f"/api/content/{cid}/decision", json={"decision": "rejected", "version_number": 1}).status_code == 422
    ok = reviewer.post(f"/api/content/{cid}/decision", json={"decision": "approved", "version_number": 1})
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    # Decision on an approved item is an invalid state transition
    assert admin.post(f"/api/content/{cid}/decision", json={"decision": "approved", "version_number": 1}).status_code == 409


def test_duplicate_approval_by_same_reviewer_is_refused(creator, reviewer, brand_id):
    item = _new_item(creator, brand_id, body="Northstar guarantees results for every customer.")  # critical -> 2 approvers
    cid = item["id"]
    creator.post(f"/api/content/{cid}/review", json={})
    creator.post(f"/api/content/{cid}/submit")
    first = reviewer.post(f"/api/content/{cid}/decision", json={"decision": "approved", "version_number": 1, "evidence_confirmed": True})
    assert first.status_code == 200 and first.json()["status"] == "in_review"
    assert any("two approvers" in b for b in first.json()["approval_status"]["blocking"])
    again = reviewer.post(f"/api/content/{cid}/decision", json={"decision": "approved", "version_number": 1})
    assert again.status_code == 409


def test_critical_policy_needs_two_distinct_approvers(creator, reviewer, admin, brand_id):
    item = _new_item(creator, brand_id, body="Northstar guarantees results for every customer.")
    cid = item["id"]
    creator.post(f"/api/content/{cid}/review", json={})
    creator.post(f"/api/content/{cid}/submit")
    reviewer.post(f"/api/content/{cid}/decision", json={"decision": "approved", "version_number": 1})
    done = admin.post(f"/api/content/{cid}/decision", json={"decision": "approved", "version_number": 1})
    assert done.status_code == 200 and done.json()["status"] == "approved"
    assert done.json()["approved_version_id"] == done.json()["current_version"]["id"]


def test_contradicted_claim_requires_evidence_confirmation(creator, reviewer, admin, brand_id):
    item = _new_item(creator, brand_id, body="Pricing starts at $59 per member per month for Atlas Pro.")
    cid = item["id"]
    creator.post(f"/api/content/{cid}/review", json={})
    detail = creator.get(f"/api/content/{cid}").json()
    assert any(c["status"] == "contradicted" for c in detail["claim_checks"])
    creator.post(f"/api/content/{cid}/submit")
    r = reviewer.post(f"/api/content/{cid}/decision", json={"decision": "approved", "version_number": 1, "evidence_confirmed": False})
    assert r.json()["status"] == "in_review"
    assert any("evidence" in b for b in r.json()["approval_status"]["blocking"])
    r2 = admin.post(f"/api/content/{cid}/decision", json={"decision": "approved", "version_number": 1, "evidence_confirmed": True})
    assert r2.json()["status"] == "approved"


def test_editing_invalidates_approval(creator, reviewer, brand_id):
    item = _new_item(creator, brand_id)
    cid = item["id"]
    creator.post(f"/api/content/{cid}/review", json={})
    creator.post(f"/api/content/{cid}/submit")
    reviewer.post(f"/api/content/{cid}/decision", json={"decision": "approved", "version_number": 1})
    edited = creator.put(f"/api/content/{cid}", json={"body": "Discover how Northstar members automate governance."}).json()
    assert edited["status"] == "draft" and edited["approved_version_id"] is None


# --- Publishing ---

def test_publishing_guard(creator, reviewer, admin, brand_id):
    item = _new_item(creator, brand_id)
    cid = item["id"]
    # Draft
    assert reviewer.post(f"/api/content/{cid}/publish", json={"version_number": 1}).status_code == 409
    # Creator lacks publish permission
    assert creator.post(f"/api/content/{cid}/publish", json={"version_number": 1}).status_code == 403
    creator.post(f"/api/content/{cid}/review", json={})
    creator.post(f"/api/content/{cid}/submit")
    reviewer.post(f"/api/content/{cid}/decision", json={"decision": "approved", "version_number": 1})
    # Wrong / unknown channel and stale version number
    assert reviewer.post(f"/api/content/{cid}/publish", json={"version_number": 1, "channel": "twitter"}).status_code == 422
    assert reviewer.post(f"/api/content/{cid}/publish", json={"version_number": 2}).status_code == 409
    first = reviewer.post(f"/api/content/{cid}/publish", json={"version_number": 1})
    assert first.status_code == 200 and first.json()["duplicate"] is False
    assert first.json()["destination"].startswith("sandbox://")
    dup = admin.post(f"/api/content/{cid}/publish", json={"version_number": 1})
    assert dup.status_code == 200 and dup.json()["duplicate"] is True and dup.json()["id"] == first.json()["id"]
    assert len(reviewer.get(f"/api/content/{cid}/publications").json()) == 1
    export = reviewer.get(f"/api/publications/{first.json()['id']}/export")
    assert export.status_code == 200 and export.json()["connector"] == "auditra-local-sandbox"
    # After an edit, the old approved version can no longer be published.
    creator.put(f"/api/content/{cid}", json={"body": "Northstar members get automated guardrails."})
    assert reviewer.post(f"/api/content/{cid}/publish", json={"version_number": 1}).status_code == 409
    assert reviewer.post(f"/api/content/{cid}/publish", json={"version_number": 2}).status_code == 409
    events = [e["event_type"] for e in admin.get(f"/api/brands/{brand_id}/audit?content_id={cid}").json()]
    assert "content_published" in events and "publish_refused" in events and "publish_duplicate" in events


def test_rejected_content_cannot_be_published(creator, reviewer, brand_id):
    item = _new_item(creator, brand_id)
    cid = item["id"]
    creator.post(f"/api/content/{cid}/review", json={})
    creator.post(f"/api/content/{cid}/submit")
    reviewer.post(f"/api/content/{cid}/decision", json={"decision": "rejected", "version_number": 1, "comments": "Off brand."})
    assert reviewer.post(f"/api/content/{cid}/publish", json={"version_number": 1}).status_code == 409


def test_seeded_approved_item_is_publishable(reviewer, brand_id):
    items = reviewer.get(f"/api/brands/{brand_id}/content?status=approved").json()
    seeded = next(i for i in items if i["title"].startswith("Apex FinTech"))
    r = reviewer.post(f"/api/content/{seeded['id']}/publish", json={"version_number": seeded["current_version_number"]})
    assert r.status_code == 200


def test_policy_crud_validation(admin, brand_id):
    bad = admin.post(f"/api/brands/{brand_id}/policies", json={"name": "Bad", "condition_type": "nonsense", "condition_value": "x"})
    assert bad.status_code == 422
    ok = admin.post(f"/api/brands/{brand_id}/policies", json={"name": "Low severity test", "condition_type": "severity_at_least",
                                                               "condition_value": "high", "min_approvals": 1, "is_active": False})
    assert ok.status_code == 201
    assert admin.delete(f"/api/brands/{brand_id}/policies/{ok.json()['id']}").status_code == 204


def test_last_admin_cannot_be_removed(admin, brand_id):
    members = admin.get(f"/api/brands/{brand_id}/members").json()
    morgan = next(m for m in members if m["role"] == "admin")
    assert admin.delete(f"/api/brands/{brand_id}/members/{morgan['user_id']}").status_code == 409
