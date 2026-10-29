"""Governance Coverage Map: 'not checked' is never reported as 'passed'."""
import uuid

import pytest

from tests.conftest import make_client, register_client


@pytest.fixture(scope="module")
def creator():
    return make_client("creator")


@pytest.fixture(scope="module")
def brand_id(creator):
    return next(b["id"] for b in creator.get("/api/brands").json() if b["slug"] == "northstar")


def _cov(c, brand_id):
    r = c.get(f"/api/brands/{brand_id}/coverage")
    assert r.status_code == 200, r.text
    return r.json()


def test_unanalysed_assets_are_not_checked_and_coverage_incomplete(creator, brand_id):
    i = creator.post(f"/api/brands/{brand_id}/content", json={"title": f"Cov {uuid.uuid4().hex[:4]}", "body": "Our users love it."}).json()["id"]
    cov = _cov(creator, brand_id)
    assert cov["complete"] is False and "not the same as 'passed'" in cov["statement"]
    for p in cov["policies"]:
        cell = p["cells"][i]
        assert cell["state"] in ("not_checked", "n/a"), (p["name"], cell)


def test_states_after_analysis(creator, brand_id):
    i = creator.post(f"/api/brands/{brand_id}/content", json={"title": f"Cov {uuid.uuid4().hex[:4]}",
                                                               "body": "Our users love Atlas Pro. Pricing starts at $59 per member per month."}).json()["id"]
    creator.post(f"/api/content/{i}/review", json={})
    cov = _cov(creator, brand_id)
    by_name = {p["name"]: p for p in cov["policies"]}
    members = next(p for p in cov["policies"] if p["category"] == "preferred_term" and "Members" in p["name"])
    assert members["cells"][i]["state"] == "violated" and members["cells"][i]["finding_id"]
    guarantee = next(p for p in cov["policies"] if p["category"] == "prohibited_term" and p["active"])
    assert guarantee["cells"][i]["state"] == "passed"
    assert by_name["Claims must be backed by approved evidence"]["cells"][i]["state"] == "violated"
    assert by_name["Text must meet WCAG AA contrast"]["cells"][i]["state"] == "n/a"


def test_flags_conflicts_and_expired_sources(creator, brand_id):
    cov = _cov(creator, brand_id)
    legacy = next(p for p in cov["policies"] if "demo conflict" in p["name"])
    assert "conflicting rule" in legacy["flags"] and legacy["conflicts"]
    claims = cov["policies"][0]
    assert any("expired source" in f for f in claims["flags"])
    assert any("not in the evidence library" in f for p in cov["policies"] for f in p["flags"])


def test_rule_added_after_analysis_is_not_checked(creator, brand_id):
    admin = make_client("admin")
    i = creator.post(f"/api/brands/{brand_id}/content", json={"title": f"Cov {uuid.uuid4().hex[:4]}", "body": "Northstar members get guardrails."}).json()["id"]
    creator.post(f"/api/content/{i}/review", json={})
    rule = admin.post(f"/api/brands/{brand_id}/rules", json={"name": f"New {uuid.uuid4().hex[:4]}", "category": "prohibited_term", "description": "x",
                                                             "rule_text": "x", "match_pattern": "guardrails", "severity": "low"}).json()
    cell = next(p for p in _cov(creator, brand_id)["policies"] if p["id"] == rule["id"])["cells"][i]
    assert cell["state"] == "not_checked" and "did not exist" in cell["reason"]


def test_coverage_access(creator, brand_id):
    assert make_client().get(f"/api/brands/{brand_id}/coverage").status_code == 401
    assert register_client(f"cov-{uuid.uuid4().hex[:6]}@example.com").get(f"/api/brands/{brand_id}/coverage").status_code == 404
