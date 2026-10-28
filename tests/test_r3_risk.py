"""Campaign Risk Radar: aggregation, de-duplication, recomputation and access control."""
import uuid

import pytest

from tests.conftest import make_client, register_client


@pytest.fixture(scope="module")
def creator():
    return make_client("creator")


@pytest.fixture(scope="module")
def brand_id(creator):
    return next(b["id"] for b in creator.get("/api/brands").json() if b["slug"] == "northstar")


def _campaign(c, brand_id, bodies, brief=None):
    ids = []
    for b in bodies:
        ids.append(c.post(f"/api/brands/{brand_id}/content", json={"title": f"Risk {uuid.uuid4().hex[:5]}", "body": b}).json()["id"])
    camp = c.post(f"/api/brands/{brand_id}/campaigns", json={"name": f"Risk test {uuid.uuid4().hex[:4]}", "brief": brief, "content_ids": ids}).json()
    return camp["id"], ids


def test_unanalysed_assets_make_radar_incomplete(creator, brand_id):
    cid, ids = _campaign(creator, brand_id, ["Atlas Pro costs $49 per member per month.", "Atlas Pro costs $59 per member per month."])
    r = creator.get(f"/api/campaigns/{cid}/risk").json()
    assert r["complete"] is False and len(r["unverified"]) == 2
    assert "Incomplete" in r["explanation"]
    # Cross-asset conflict is still detected without analysis (computed from current text).
    assert any(x["kind"] == "conflict" for x in r["risks"])


def test_risks_link_to_evidence_and_dedupe(creator, brand_id):
    disclaimer = "Disclaimer: Results may vary based on client workload and infrastructure configurations."
    cid, ids = _campaign(creator, brand_id, [
        "Atlas Pro costs $49 per member per month. " + disclaimer,
        "Atlas Pro costs $59 per member per month. Northstar guarantees results for every team.",
    ])
    for i in ids:
        creator.post(f"/api/content/{i}/review", json={})
    r = creator.get(f"/api/campaigns/{cid}/risk").json()
    assert r["complete"] is True
    assert r["level"] == "critical"
    keys = [(x["kind"], tuple(x["asset_ids"]), x["category"], (x["evidence"].get("text") or "").lower()) for x in r["risks"]]
    assert len(keys) == len(set(keys)), "same underlying issue counted twice"
    # The missing disclosure is reported once for the second asset, corroborated by both the analysis and the graph.
    missing = [x for x in r["risks"] if x["category"] == "required_phrase" and x["asset_ids"] == [ids[1]]]
    assert len(missing) == 1 and missing[0].get("corroborated_by")
    # The contradicted $59 claim appears as a claim risk, not also as a separate claim finding.
    claim = [x for x in r["risks"] if x["kind"] == "claim" and "$59" in (x["evidence"]["text"] or "")]
    assert len(claim) == 1 and claim[0]["evidence"]["source_name"] and claim[0]["link"]["tab"] == "claims"
    assert not [x for x in r["risks"] if x["category"].startswith("claim_") and x["kind"] == "finding"]
    conflict = next(x for x in r["risks"] if x["kind"] == "conflict")
    assert {p["value"] for p in conflict["evidence"]["passages"]} == {"$49", "$59"}
    assert sum(r["counts"].values()) == len(r["risks"])
    assert r["basis_counts"]["detected"] + r["basis_counts"]["heuristic"] == len(r["risks"])


def test_risk_recalculates_after_edit(creator, brand_id):
    cid, ids = _campaign(creator, brand_id, ["Northstar guarantees results for every team.", "Northstar members get policy guardrails."])
    for i in ids:
        creator.post(f"/api/content/{i}/review", json={})
    assert creator.get(f"/api/campaigns/{cid}/risk").json()["counts"]["critical"] == 1
    creator.put(f"/api/content/{ids[0]}", json={"body": "Northstar delivers proven performance gains for every team."})
    after = creator.get(f"/api/campaigns/{cid}/risk").json()
    assert after["complete"] is False  # the new version is unanalysed, so it is not called safe
    creator.post(f"/api/content/{ids[0]}/review", json={})
    assert creator.get(f"/api/campaigns/{cid}/risk").json()["counts"]["critical"] == 0


def test_approval_pending_is_a_risk(creator, brand_id):
    cid, ids = _campaign(creator, brand_id, ["Northstar guarantees results for every team.", "Northstar members get policy guardrails."])
    for i in ids:
        creator.post(f"/api/content/{i}/review", json={})
    creator.post(f"/api/content/{ids[0]}/submit")
    r = creator.get(f"/api/campaigns/{cid}/risk").json()
    assert any(x["category"] == "approval_pending" and x["link"]["tab"] == "approval" for x in r["risks"])


def test_risk_requires_membership(creator, brand_id):
    cid, _ = _campaign(creator, brand_id, ["a b c d e", "f g h i j"])
    assert make_client().get(f"/api/campaigns/{cid}/risk").status_code == 401
    outsider = register_client(f"risk-{uuid.uuid4().hex[:6]}@example.com")
    assert outsider.get(f"/api/campaigns/{cid}/risk").status_code == 404
    assert creator.get("/api/campaigns/nope/risk").status_code == 404
