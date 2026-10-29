"""Source-expiry impact view and governed re-verification."""
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


def _analysed(c, brand_id, body):
    i = c.post(f"/api/brands/{brand_id}/content", json={"title": f"Impact {uuid.uuid4().hex[:6]}", "body": body}).json()["id"]
    assert c.post(f"/api/content/{i}/review", json={}).status_code == 200
    return i


def _impact(c, brand_id):
    return c.get(f"/api/brands/{brand_id}/source-impact").json()


def _src(view, name):
    return next(s for s in view["sources"] if s["name"] == name)


@pytest.fixture(scope="module")
def expired_src(admin, brand_id):
    """A fictional expired source with a claim no other source covers, so citations to it are direct."""
    return _upload(admin, brand_id, "Backup retention memo 2024", "Kestrel backups are retained for 35 days in every region.",
                   effective_date="2024-01-01", expiry_date="2024-12-31")


KESTREL = "Kestrel backups are retained for 35 days in every region."


def _upload(admin, brand_id, name, text, **dates):
    r = admin.post(f"/api/brands/{brand_id}/sources", files={"file": (f"{name}.txt", text.encode(), "text/plain")},
                   data={"name": name, **dates})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_freshness_states(creator, admin, brand_id):
    undated = _upload(admin, brand_id, f"Undated memo {uuid.uuid4().hex[:4]}", "Atlas Pro supports single sign-on for every workspace.")
    v = _impact(creator, brand_id)
    assert _src(v, "Northstar Pricing Sheet 2025")["freshness"]["status"] == "expired"
    assert _src(v, "Northstar Pricing Sheet 2025")["freshness"]["date"] == "2025-12-31"
    assert _src(v, "Northstar Product Fact Sheet 2026")["freshness"]["status"] == "current"
    assert _src(v, "Security & Compliance Overview")["freshness"]["status"] == "review_overdue"
    u = next(s for s in v["sources"] if s["id"] == undated)
    assert u["freshness"]["status"] == "undated" and u["affects"] is False
    assert "cannot be determined" in u["freshness"]["reason"]


def test_confirmed_dependencies_trace_to_assets_and_evidence(creator, brand_id, expired_src):
    cid = _analysed(creator, brand_id, KESTREL + " Northstar is ISO 27001 certified for its managed control plane.")
    v = _impact(creator, brand_id)
    exp = next(s for s in v["sources"] if s["id"] == expired_src)
    assert exp["freshness"]["status"] == "expired" and exp["affects"]
    mine = [c for c in exp["claims"] if c["content_id"] == cid]
    assert mine and all(c["relation"] == "confirmed" and c["passage_text"] and c["claim_check_id"] for c in mine)
    assert any(a["content_id"] == cid for a in exp["assets"])
    sec = _src(v, "Security & Compliance Overview")
    assert any(c["content_id"] == cid and c["relation"] == "confirmed" for c in sec["claims"])


def test_possible_association_is_labelled(creator, brand_id):
    cid = _analysed(creator, brand_id, "Every new Atlas Pro workspace includes a 30-day free trial.")
    exp = _src(_impact(creator, brand_id), "Northstar Pricing Sheet 2025")
    assert not any(c["content_id"] == cid for c in exp["claims"])  # it cites the 2026 fact sheet, not this one
    poss = [c for c in exp["possible"] if c["content_id"] == cid]
    assert poss and poss[0]["relation"] == "possible" and "different source" in poss[0]["basis"]
    assert not any(a["content_id"] == cid for a in exp["assets"])


def test_new_version_turns_citation_historical(creator, brand_id, expired_src):
    cid = _analysed(creator, brand_id, KESTREL)
    creator.put(f"/api/content/{cid}", json={"body": "Atlas Pro has a 14-day free trial."})
    creator.post(f"/api/content/{cid}/review", json={})
    exp = next(s for s in _impact(creator, brand_id)["sources"] if s["id"] == expired_src)
    rel = {c["relation"] for c in exp["claims"] if c["content_id"] == cid}
    assert rel == {"historical"}
    assert not any(a["content_id"] == cid for a in exp["assets"])


def test_campaign_link_is_reported(creator, brand_id, expired_src):
    cid = _analysed(creator, brand_id, KESTREL)
    camp = creator.post(f"/api/brands/{brand_id}/campaigns", json={"name": f"Impact camp {uuid.uuid4().hex[:4]}", "content_ids": [cid]}).json()
    exp = next(s for s in _impact(creator, brand_id)["sources"] if s["id"] == expired_src)
    hit = next(c for c in exp["campaigns"] if c["id"] == camp["id"])
    assert cid in hit["content_ids"] and hit["basis"]


def test_disconnected_source_says_so(creator, admin, brand_id):
    sid = _upload(admin, brand_id, f"Orphan policy {uuid.uuid4().hex[:4]}", "Zebra migration windows close on Fridays.", expiry_date="2024-01-01")
    s = next(x for x in _impact(creator, brand_id)["sources"] if x["id"] == sid)
    assert s["freshness"]["status"] == "expired" and s["claims"] == [] and s["assets"] == []
    assert "No stored claim check cites this source" in s["notes"][0]
    r = admin.post(f"/api/brands/{brand_id}/sources/{sid}/reverify", json={})
    assert r.status_code == 200 and r.json()["results"] == []


def test_deleted_source_reported_as_missing(creator, admin, brand_id):
    text = "Quokka Edge nodes ship with 48 GB of memory."
    sid = _upload(admin, brand_id, f"Hardware note {uuid.uuid4().hex[:4]}", text, expiry_date="2030-01-01")
    cid = _analysed(creator, brand_id, text)
    assert admin.delete(f"/api/brands/{brand_id}/sources/{sid}").status_code == 204
    missing = [m for m in _impact(creator, brand_id)["missing_sources"] if m["content_id"] == cid]
    assert missing and missing[0]["passage_text"] and missing[0]["relation"] == "missing_source"


def test_reverify_runs_checks_without_approving(creator, reviewer, brand_id, expired_src):
    cid = _analysed(creator, brand_id, KESTREL)
    sid = expired_src
    runs_before = len(creator.get(f"/api/content/{cid}/replay").json()["timeline"])
    r = reviewer.post(f"/api/brands/{brand_id}/sources/{sid}/reverify", json={"content_ids": [cid]})
    assert r.status_code == 200, r.text
    res = r.json()["results"]
    assert len(res) == 1 and res[0]["outcome"] == "ok" and res[0]["review_run_id"]
    assert "supported" not in res[0]["after"]  # an expired source never makes the claim supported
    d = creator.get(f"/api/content/{cid}").json()
    assert d["status"] == "draft" and d["approved_version_id"] is None and d["publications"] == []
    assert len(creator.get(f"/api/content/{cid}/replay").json()["timeline"]) == runs_before + 1


def test_reverify_rejects_unrelated_ids(reviewer, creator, brand_id, expired_src):
    sid = expired_src
    other = _analysed(creator, brand_id, "Our members love Atlas Pro.")
    assert reviewer.post(f"/api/brands/{brand_id}/sources/{sid}/reverify", json={"content_ids": [other]}).status_code == 422


def test_partial_failure_and_retry(creator, reviewer, brand_id, monkeypatch, expired_src):
    a = _analysed(creator, brand_id, KESTREL)
    b = _analysed(creator, brand_id, "In every region, " + KESTREL[0].lower() + KESTREL[1:])
    sid = expired_src
    from backend import review_pipeline
    real = review_pipeline.perform_review

    async def flaky(db, item, version, actor, force_engine=None):
        if item.id == b:
            raise RuntimeError("simulated analysis failure")
        return await real(db, item, version, actor, force_engine)

    monkeypatch.setattr(review_pipeline, "perform_review", flaky)
    res = {r["content_id"]: r for r in reviewer.post(f"/api/brands/{brand_id}/sources/{sid}/reverify", json={"content_ids": [a, b]}).json()["results"]}
    assert res[a]["outcome"] == "ok" and res[b]["outcome"] == "failed" and "simulated" in res[b]["error"]
    monkeypatch.setattr(review_pipeline, "perform_review", real)
    retry = reviewer.post(f"/api/brands/{brand_id}/sources/{sid}/reverify", json={"content_ids": [b]}).json()["results"]
    assert retry[0]["outcome"] == "ok"


def test_permissions(creator, brand_id):
    sid = _src(_impact(creator, brand_id), "Northstar Pricing Sheet 2025")["id"]
    assert creator.post(f"/api/brands/{brand_id}/sources/{sid}/reverify", json={}).status_code == 403
    outsider = register_client(f"impact-{uuid.uuid4().hex[:6]}@example.com")
    assert outsider.get(f"/api/brands/{brand_id}/source-impact").status_code == 404
    assert outsider.post(f"/api/brands/{brand_id}/sources/{sid}/reverify", json={}).status_code == 404
    assert make_client().get(f"/api/brands/{brand_id}/source-impact").status_code == 401
