"""Guided judge tour: the full story through the real endpoints, fixture recovery, and guards."""
import pytest

from tests.conftest import make_client, register_client


@pytest.fixture(scope="module")
def creator():
    return make_client("creator")


@pytest.fixture(scope="module")
def reviewer():
    return make_client("reviewer")


@pytest.fixture(scope="module")
def brand_id(creator):
    return next(b["id"] for b in creator.get("/api/brands").json() if b["slug"] == "northstar")


def _run_story(creator, reviewer, brand_id):
    status = creator.get(f"/api/brands/{brand_id}/tour").json()
    if not status["ready"]:
        status = creator.post(f"/api/brands/{brand_id}/tour/copy").json()
    assert status["ready"], status
    cid, camp = status["asset"]["id"], status["campaign"]["id"]

    # Step 2: analyse, then the campaign Risk Radar shows the stored contradictions for this asset.
    assert creator.post(f"/api/content/{cid}/review", json={}).status_code == 200
    risk = creator.get(f"/api/campaigns/{camp}/risk").json()
    mine = [r for r in risk["risks"] if cid in r["asset_ids"] and r["category"] == "claim_contradicted"]
    assert len(mine) == 2

    # Step 3: Fix tab, factual fixes need explicit confirmation.
    sugg = creator.get(f"/api/content/{cid}/remediation").json()["suggestions"]
    fixes = [{"id": s["id"]} for s in sugg if s["kind"] == "factual"]
    assert len(fixes) == 2
    assert not any(s["replacement"] for s in sugg if s["kind"] == "evidence_needed")  # HIPAA: no invented fix
    r = creator.post(f"/api/content/{cid}/remediation/apply", json={"version_number": 1, "fixes": fixes})
    assert r.status_code == 422
    r = creator.post(f"/api/content/{cid}/remediation/apply", json={"version_number": 1, "fixes": fixes, "confirm_factual": True})
    assert r.status_code == 200 and r.json()["current_version_number"] == 2

    # Step 4: re-check v2; the contradictions are gone, the unsupported claim is still flagged.
    creator.post(f"/api/content/{cid}/review", json={})
    d = creator.get(f"/api/content/{cid}").json()
    statuses = {c["status"] for c in d["claim_checks"]}
    assert "contradicted" not in statuses and "needs_review" in statuses
    assert creator.post(f"/api/content/{cid}/submit").status_code == 200

    # Step 5: the author cannot approve; the reviewer persona can.
    return cid, d


def test_full_story(creator, reviewer, brand_id):
    cid, d = _run_story(creator, reviewer, brand_id)
    # Alex is the author and a creator: blocked by role. Approval needs a different, permitted person.
    assert creator.post(f"/api/content/{cid}/decision", json={"decision": "approved", "version_number": 2}).status_code == 403
    r = reviewer.post(f"/api/content/{cid}/decision", json={"decision": "approved", "version_number": 2})
    assert r.status_code == 200 and r.json()["status"] == "approved"

    # Step 6: Decision Replay shows the stored versions, finding changes and the approval event.
    rp = creator.get(f"/api/content/{cid}/replay").json()
    assert [v["version_number"] for v in rp["versions"]] == [1, 2]
    assert rp["decisions"][-1]["decision"] == "approved" and rp["decisions"][-1]["version_number"] == 2
    kinds = [e["event_type"] for e in rp["timeline"]]
    assert "remediation_applied" in kinds and "content_approved" in kinds

    # The asset is used now, so the tour reports it and offers a labelled copy (restart path).
    st = creator.get(f"/api/brands/{brand_id}/tour").json()
    assert st["ready"] is False and st["problem"] == "asset_used" and "tour copy" in st["message"]
    again = creator.post(f"/api/brands/{brand_id}/tour/copy")
    assert again.status_code == 201 and again.json()["ready"] and again.json()["asset"]["kind"] == "tour_copy"
    # A second request reuses the untouched copy instead of creating another.
    assert creator.post(f"/api/brands/{brand_id}/tour/copy").json()["asset"]["id"] == again.json()["asset"]["id"]
    # The used asset is untouched by the restart.
    assert creator.get(f"/api/content/{cid}").json()["status"] == "approved"


def test_restart_runs_story_again_on_copy(creator, reviewer, brand_id):
    cid, _ = _run_story(creator, reviewer, brand_id)
    assert reviewer.post(f"/api/content/{cid}/decision", json={"decision": "approved", "version_number": 2}).json()["status"] == "approved"


def test_reviewer_cannot_create_copy(reviewer, brand_id):
    assert reviewer.post(f"/api/brands/{brand_id}/tour/copy").status_code == 403


def test_outsider_and_other_workspace(brand_id):
    outsider = register_client("tour-outsider@example.com")
    assert outsider.get(f"/api/brands/{brand_id}/tour").status_code == 404
    assert outsider.post(f"/api/brands/{brand_id}/tour/copy").status_code == 404
    own = outsider.post("/api/brands", json={"name": "Tour Outsider Co", "industry": "Retail"})
    assert own.status_code in (200, 201), own.text
    assert outsider.get(f"/api/brands/{own.json()['id']}/tour").status_code == 404  # tour only runs on demo data


def test_missing_campaign_explains_recovery(creator, brand_id):
    from backend.database import SessionLocal
    from backend.models_r3 import Campaign
    db = SessionLocal()
    try:
        c = db.query(Campaign).filter(Campaign.brand_id == brand_id, Campaign.name == "Atlas Pro launch").first()
        c.name = "Atlas Pro launch (renamed in test)"
        db.commit()
        st = creator.get(f"/api/brands/{brand_id}/tour").json()
        assert st["ready"] is False and st["problem"] == "missing_campaign" and "Reset demo workspace" in st["message"]
        assert creator.post(f"/api/brands/{brand_id}/tour/copy").status_code == 409
    finally:
        c.name = "Atlas Pro launch"
        db.commit()
        db.close()


def test_unauthenticated():
    anon = make_client()
    assert anon.get("/api/brands/x/tour").status_code == 401
