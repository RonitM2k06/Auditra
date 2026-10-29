"""Smart remediation: suggestions, preview, factual guard, approval reset, permissions."""
import uuid

import pytest

from tests.conftest import make_client


@pytest.fixture(scope="module")
def creator():
    return make_client("creator")


@pytest.fixture(scope="module")
def reviewer():
    return make_client("reviewer")


@pytest.fixture(scope="module")
def brand_id(creator):
    return next(b["id"] for b in creator.get("/api/brands").json() if b["slug"] == "northstar")


def _item(c, brand_id, body):
    i = c.post(f"/api/brands/{brand_id}/content", json={"title": f"Fix {uuid.uuid4().hex[:5]}", "body": body}).json()["id"]
    c.post(f"/api/content/{i}/review", json={})
    return i


def _sugg(c, i):
    return c.get(f"/api/content/{i}/remediation").json()


def test_requires_analysis_first(creator, brand_id):
    i = creator.post(f"/api/brands/{brand_id}/content", json={"title": "x", "body": "Our users love it."}).json()["id"]
    s = _sugg(creator, i)
    assert s["analysed"] is False and s["suggestions"] == [] and s["notice"]


def test_suggestion_kinds(creator, brand_id):
    i = _item(creator, brand_id, "Our users love Atlas Pro. Pricing starts at $59 per member per month. Northstar is the fastest cloud in the world.")
    kinds = {s["kind"] for s in _sugg(creator, i)["suggestions"]}
    assert {"wording", "add_disclosure", "factual", "evidence_needed"} <= kinds
    fact = next(s for s in _sugg(creator, i)["suggestions"] if s["kind"] == "factual" and "$59" in s["original"])
    assert "$49" in fact["replacement"] and fact["requires_confirmation"] and fact["evidence"]["passage"]
    ev = next(s for s in _sugg(creator, i)["suggestions"] if s["kind"] == "evidence_needed")
    assert ev["replacement"] is None  # no invented correction


def test_preview_does_not_save_and_rechecks(creator, brand_id):
    i = _item(creator, brand_id, "Our users love Atlas Pro.")
    s = _sugg(creator, i)["suggestions"]
    fixes = [{"id": x["id"]} for x in s if x["kind"] in ("wording", "add_disclosure")]
    pv = creator.post(f"/api/content/{i}/remediation/preview", json={"version_number": 1, "fixes": fixes}).json()
    assert "members" in pv["after_body"] and "Results may vary" in pv["after_body"]
    assert pv["findings_after"] < pv["findings_before"] and pv["resolved"]
    assert any(d["op"] == "insert" for d in pv["diff"])
    assert creator.get(f"/api/content/{i}").json()["current_version_number"] == 1


def test_apply_creates_version_and_resets_approval(creator, reviewer, brand_id):
    i = _item(creator, brand_id, "Discover how Northstar users streamline governance.")
    creator.post(f"/api/content/{i}/submit")
    assert reviewer.post(f"/api/content/{i}/decision", json={"decision": "approved", "version_number": 1}).json()["status"] == "approved"
    s = _sugg(creator, i)["suggestions"]
    wording = [{"id": x["id"]} for x in s if x["kind"] == "wording"]
    d = creator.post(f"/api/content/{i}/remediation/apply", json={"version_number": 1, "fixes": wording}).json()
    assert d["current_version_number"] == 2 and d["status"] == "draft" and d["approved_version_id"] is None
    assert d["versions"][-1]["body"] == "Discover how Northstar users streamline governance."  # original preserved
    assert reviewer.post(f"/api/content/{i}/publish", json={"version_number": 2}).status_code == 409
    events = [e["event_type"] for e in creator.get(f"/api/brands/{brand_id}/audit?content_id={i}").json()]
    assert "remediation_applied" in events


def test_factual_changes_need_confirmation(creator, brand_id):
    i = _item(creator, brand_id, "Pricing starts at $59 per member per month for Atlas Pro.")
    fact = next(x for x in _sugg(creator, i)["suggestions"] if x["kind"] == "factual")
    body = {"version_number": 1, "fixes": [{"id": fact["id"]}]}
    r = creator.post(f"/api/content/{i}/remediation/apply", json=body)
    assert r.status_code == 422 and "$59" in r.json()["detail"]
    ok = creator.post(f"/api/content/{i}/remediation/apply", json={**body, "confirm_factual": True})
    assert ok.status_code == 200 and "$49" in ok.json()["current_version"]["body"]


def test_custom_wording_that_changes_a_figure_is_guarded(creator, brand_id):
    i = _item(creator, brand_id, "Our users get 14 regions.")
    w = next(x for x in _sugg(creator, i)["suggestions"] if x["kind"] == "wording")
    r = creator.post(f"/api/content/{i}/remediation/apply", json={"version_number": 1, "fixes": [{"id": w["id"], "replacement": "members in 20 regions"}]})
    assert r.status_code == 422


def test_guards(creator, reviewer, brand_id):
    i = _item(creator, brand_id, "Our users love it. Northstar is the fastest cloud in the world.")
    s = _sugg(creator, i)["suggestions"]
    ev = next(x for x in s if x["kind"] == "evidence_needed")
    w = next(x for x in s if x["kind"] == "wording")
    assert creator.post(f"/api/content/{i}/remediation/apply", json={"version_number": 1, "fixes": [{"id": ev["id"], "replacement": "x"}]}).status_code == 422
    assert creator.post(f"/api/content/{i}/remediation/apply", json={"version_number": 9, "fixes": [{"id": w["id"]}]}).status_code == 409
    assert reviewer.post(f"/api/content/{i}/remediation/apply", json={"version_number": 1, "fixes": [{"id": w["id"]}]}).status_code == 403
    assert creator.post(f"/api/content/{i}/remediation/preview", json={"version_number": 1, "fixes": [{"id": "f:nope"}]}).status_code == 404
    d = s[0]
    disc = next((x for x in s if x["kind"] == "add_disclosure"), None)
    if disc:
        r = creator.post(f"/api/content/{i}/remediation/apply", json={"version_number": 1, "fixes": [{"id": disc["id"], "replacement": "Results vary."}]})
        assert r.status_code == 422
    assert make_client().get(f"/api/content/{i}/remediation").status_code == 401
    assert d


def test_image_items_cannot_be_text_fixed(creator, brand_id):
    items = creator.get(f"/api/brands/{brand_id}/content").json()
    img = next(x for x in items if x["media_kind"] == "image" and x["title"].startswith("Migration promo"))
    creator.post(f"/api/content/{img['id']}/review", json={})
    s = _sugg(creator, img["id"])["suggestions"]
    assert s and all(x["kind"] in ("creative", "evidence_needed") for x in s)
    assert creator.post(f"/api/content/{img['id']}/remediation/apply",
                        json={"version_number": img["current_version_number"], "fixes": [{"id": s[0]["id"]}]}).status_code == 409
