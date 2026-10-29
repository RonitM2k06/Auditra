"""What-If policy simulator: proposals never touch live rules until a separate admin confirms."""
import uuid

import pytest

from tests.conftest import make_client


@pytest.fixture(scope="module")
def reviewer():
    return make_client("reviewer")


@pytest.fixture(scope="module")
def admin():
    return make_client("admin")


@pytest.fixture(scope="module")
def creator():
    return make_client("creator")


@pytest.fixture(scope="module")
def brand_id(admin):
    return next(b["id"] for b in admin.get("/api/brands").json() if b["slug"] == "northstar")


def _propose(c, brand_id, phrase=None):
    phrase = phrase or f"zz{uuid.uuid4().hex[:6]}"
    return c.post(f"/api/brands/{brand_id}/rule-proposals", json={
        "title": f"Ban '{phrase}'", "rationale": "Legal asked for it",
        "changes": [{"op": "add", "rule": {"name": f"No {phrase}", "category": "prohibited_term", "match_pattern": phrase, "severity": "high"}}],
    })


def test_proposal_simulates_without_changing_rules(reviewer, admin, creator, brand_id):
    creator.post(f"/api/brands/{brand_id}/content", json={"title": "Trial copy", "body": "Start your free trial today with Northstar. Disclaimer: Results may vary based on client workload and infrastructure configurations."})
    before = admin.get(f"/api/brands/{brand_id}/rules").json()
    r = _propose(reviewer, brand_id, "free trial")
    assert r.status_code == 201, r.text
    p = r.json()
    assert admin.get(f"/api/brands/{brand_id}/rules").json() == before
    assert p["status"] == "proposed" and p["simulation_is_current"]
    item = next(i for i in p["simulation"]["items"] if i["title"] == "Trial copy")
    assert item["outcome_before"] == "pass" and item["outcome_after"] == "fail"
    assert "No free trial" in item["responsible_rules"]
    assert "Trial copy" in p["summary"]["new_failures"]
    assert "not evaluated" in p["scope_note"]
    events = [e["event_type"] for e in admin.get(f"/api/brands/{brand_id}/audit?limit=500").json()]
    assert "rule_change_proposed" in events


def test_permissions_and_separation_of_duties(reviewer, admin, creator, brand_id):
    assert _propose(creator, brand_id).status_code == 403
    p = _propose(reviewer, brand_id).json()
    assert reviewer.post(f"/api/rule-proposals/{p['id']}/decision", json={"decision": "activate", "confirm": True}).status_code == 403
    own = _propose(admin, brand_id).json()
    assert admin.post(f"/api/rule-proposals/{own['id']}/decision", json={"decision": "activate", "confirm": True}).status_code == 403


def test_activation_requires_confirmation_and_fresh_simulation(reviewer, admin, brand_id):
    p = _propose(reviewer, brand_id).json()
    assert admin.post(f"/api/rule-proposals/{p['id']}/decision", json={"decision": "activate"}).status_code == 422
    # Change the live rulebook after the simulation -> activation refused until re-simulated.
    rule = admin.get(f"/api/brands/{brand_id}/rules").json()[0]
    admin.put(f"/api/brands/{brand_id}/rules/{rule['id']}", json={"description": rule["description"] + " "})
    stale = admin.post(f"/api/rule-proposals/{p['id']}/decision", json={"decision": "activate", "confirm": True})
    assert stale.status_code == 409
    assert admin.get(f"/api/brands/{brand_id}/rule-proposals").json()[0]["simulation_is_current"] is False
    assert reviewer.post(f"/api/rule-proposals/{p['id']}/rerun").status_code == 200
    ok = admin.post(f"/api/rule-proposals/{p['id']}/decision", json={"decision": "activate", "confirm": True, "note": "Approved by legal"})
    assert ok.status_code == 200 and ok.json()["status"] == "activated"
    names = [r["name"] for r in admin.get(f"/api/brands/{brand_id}/rules").json()]
    assert p["changes"][0]["rule"]["name"] in names
    assert admin.post(f"/api/rule-proposals/{p['id']}/decision", json={"decision": "reject", "note": "x"}).status_code == 409
    events = [e["event_type"] for e in admin.get(f"/api/brands/{brand_id}/audit?limit=500").json()]
    assert "rule_change_activated" in events


def test_reject_needs_reason(reviewer, admin, brand_id):
    p = _propose(reviewer, brand_id).json()
    assert admin.post(f"/api/rule-proposals/{p['id']}/decision", json={"decision": "reject"}).status_code == 422
    r = admin.post(f"/api/rule-proposals/{p['id']}/decision", json={"decision": "reject", "note": "Too broad"})
    assert r.json()["status"] == "rejected"


def test_invalid_change_is_rejected(reviewer, brand_id):
    r = reviewer.post(f"/api/brands/{brand_id}/rule-proposals", json={"title": "Bad change", "changes": [{"op": "disable", "rule_id": "nope"}]})
    assert r.status_code == 422
    assert make_client().get(f"/api/brands/{brand_id}/rule-proposals").status_code == 401
