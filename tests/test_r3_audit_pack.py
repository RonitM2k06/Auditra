"""Campaign audit pack: PDF/JSON consistency, hash chain, tamper detection, limitations, permissions."""
import copy
import io
import json
import uuid

import pytest
from pypdf import PdfReader

from backend import audit_pack
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


def _campaign(creator, brand_id, content_ids):
    r = creator.post(f"/api/brands/{brand_id}/campaigns", json={"name": f"Pack {uuid.uuid4().hex[:6]}", "content_ids": content_ids})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _approved_asset(creator, reviewer, brand_id, body="Atlas Pro is available from November 12, 2026 for our members."):
    cid = creator.post(f"/api/brands/{brand_id}/content", json={"title": f"Pack asset {uuid.uuid4().hex[:5]}", "body": body}).json()["id"]
    creator.post(f"/api/content/{cid}/review", json={})
    creator.post(f"/api/content/{cid}/submit")
    assert reviewer.post(f"/api/content/{cid}/decision", json={"decision": "approved", "version_number": 1}).json()["status"] == "approved"
    reviewer.post(f"/api/content/{cid}/publish", json={"version_number": 1, "channel": "sandbox"})
    return cid


def _export(reviewer, camp):
    r = reviewer.post(f"/api/campaigns/{camp}/audit-packs")
    assert r.status_code == 201, r.text
    s = r.json()
    manifest = reviewer.get(s["json_url"]).json()
    pdf = reviewer.get(s["pdf_url"])
    assert pdf.headers["content-type"] == "application/pdf"
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    return s, manifest, text


def _flat(text):
    return "".join(text.split())


def test_pdf_and_json_come_from_one_snapshot(creator, reviewer, brand_id):
    cid = _approved_asset(creator, reviewer, brand_id)
    camp = _campaign(creator, brand_id, [cid])
    s, m, text = _export(reviewer, camp)
    assert audit_pack.verify_manifest(m)["valid"]
    assert m["manifest_sha256"] == s["manifest_sha256"] and m["integrity"]["final_chain_hash"] == s["final_chain_hash"]
    flat = _flat(text)
    for value in (m["manifest_sha256"], m["integrity"]["final_chain_hash"], m["export"]["id"], cid):
        assert value in flat
    a = m["assets"][0]
    assert a["versions"][0]["text"] and a["versions"][0]["review_runs"][0]["claims"]
    assert a["decisions"][0]["reviewer_name"] == "Sarah Chen" and a["decisions"][0]["version_number"] == 1
    assert a["publications"] and any(x["event_type"] == "content_published" for x in a["publish_attempts"])
    supported = [c for c in a["versions"][0]["review_runs"][0]["claims"] if c["status"] == "supported"]
    assert supported and supported[0]["passage_text"] and _flat(supported[0]["passage_text"])[:30] in flat
    # Every chained event shows up in the PDF table by id.
    assert all(e["event"]["id"] in flat for e in m["audit_events"]["chain"])
    assert m["integrity"]["digitally_signed"] is False and "not digitally signed" in text


def test_chain_scheme_is_reproducible(creator, reviewer, brand_id):
    camp = _campaign(creator, brand_id, [_approved_asset(creator, reviewer, brand_id)])
    _, m, _ = _export(reviewer, camp)
    prev = "0" * 64
    import hashlib
    for e in m["audit_events"]["chain"]:
        canon = json.dumps(e["event"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        h = hashlib.sha256((prev + "\n" + canon).encode("utf-8")).hexdigest()
        assert e["prev_hash"] == prev and e["hash"] == h
        prev = h
    assert m["integrity"]["final_chain_hash"] == prev
    times = [e["event"]["created_at"] for e in m["audit_events"]["chain"]]
    assert times == sorted(times)


def test_first_export_is_not_called_fully_verified(creator, reviewer, brand_id):
    camp = _campaign(creator, brand_id, [_approved_asset(creator, reviewer, brand_id)])
    s, m, _ = _export(reviewer, camp)
    assert s["verification"] == "pass_unanchored"
    assert any(c["check"] == "matches_previous_export" and c["result"] == "not_available" for c in m["integrity"]["checks"])
    s2, m2, _ = _export(reviewer, camp)
    assert s2["verification"] == "pass"


def test_tampered_manifest_is_detected(creator, reviewer, brand_id):
    camp = _campaign(creator, brand_id, [_approved_asset(creator, reviewer, brand_id)])
    _, m, _ = _export(reviewer, camp)
    edited = copy.deepcopy(m)
    edited["audit_events"]["chain"][1]["event"]["description"] = "Something else happened."
    res = audit_pack.verify_manifest(edited)
    assert not res["valid"] and any("event 1" in p for p in res["problems"])
    dropped = copy.deepcopy(m)
    del dropped["audit_events"]["chain"][0]
    assert not audit_pack.verify_manifest(dropped)["valid"]  # broken link
    relabel = copy.deepcopy(m)
    relabel["assets"][0]["status"] = "rejected"
    assert any("manifest_sha256" in p for p in audit_pack.verify_manifest(relabel)["problems"])


def _db():
    from backend.database import SessionLocal
    return SessionLocal()


def test_tampered_stored_event_fails_next_export(creator, reviewer, brand_id):
    cid = _approved_asset(creator, reviewer, brand_id)
    camp = _campaign(creator, brand_id, [cid])
    _export(reviewer, camp)
    from backend.models import AuditEvent
    db = _db()
    try:
        ev = db.query(AuditEvent).filter(AuditEvent.content_id == cid, AuditEvent.event_type == "content_approved").first()
        ev.description = "Approved by someone else."
        db.commit()
        target = ev.id
    finally:
        db.close()
    s, m, text = _export(reviewer, camp)
    assert s["verification"] == "fail"
    chk = next(c for c in m["integrity"]["checks"] if c["check"] == "matches_previous_export")
    assert target in chk["changed_event_ids"] and "fail" in text


def test_deleted_event_fails_next_export(creator, reviewer, brand_id):
    cid = _approved_asset(creator, reviewer, brand_id)
    camp = _campaign(creator, brand_id, [cid])
    _export(reviewer, camp)
    from backend.models import AuditEvent
    db = _db()
    try:
        ev = db.query(AuditEvent).filter(AuditEvent.content_id == cid, AuditEvent.event_type == "submitted_for_review").first()
        target = ev.id
        db.delete(ev)
        db.commit()
    finally:
        db.close()
    s, m, _ = _export(reviewer, camp)
    chk = next(c for c in m["integrity"]["checks"] if c["check"] == "matches_previous_export")
    assert s["verification"] == "fail" and target in chk["missing_event_ids"]


def test_malformed_event_is_disclosed(creator, reviewer, brand_id):
    cid = _approved_asset(creator, reviewer, brand_id)
    from backend.models import AuditEvent
    db = _db()
    try:
        db.add(AuditEvent(brand_id=brand_id, content_id=cid, event_type="legacy_note", description="Imported note", event_metadata="{not json"))
        db.commit()
    finally:
        db.close()
    s, m, _ = _export(reviewer, _campaign(creator, brand_id, [cid]))
    assert s["verification"] == "incomplete"
    bad = next(e for e in m["audit_events"]["chain"] if e["event"]["event_type"] == "legacy_note")
    assert bad["event"]["metadata"] == {"_unparsed": "{not json"}
    assert any("malformed" in x for x in m["limitations"])
    assert audit_pack.verify_manifest(m)["valid"]  # disclosed, still hashed consistently


def test_empty_campaign(creator, reviewer, brand_id):
    s, m, text = _export(reviewer, _campaign(creator, brand_id, []))
    assert m["assets"] == [] and m["audit_events"]["count"] == 0
    assert m["integrity"]["final_chain_hash"] == "0" * 64
    assert any("no assets" in x for x in m["limitations"]) and "No audit events" in text


def test_missing_evidence_is_listed(creator, reviewer, brand_id):
    cid = creator.post(f"/api/brands/{brand_id}/content", json={"title": "Never analysed", "body": "Atlas Pro for members."}).json()["id"]
    _, m, _ = _export(reviewer, _campaign(creator, brand_id, [cid]))
    lim = " ".join(m["limitations"])
    assert "never analysed" in lim and "no approval decisions" in lim
    assert m["assets"][0]["versions"][0]["review_runs"] == []


def test_special_characters_are_escaped(creator, reviewer, brand_id):
    body = 'Members <b>love</b> Atlas & "Pro" <script>alert(1)</script> café — ünïcödé \x07bell'
    cid = creator.post(f"/api/brands/{brand_id}/content", json={"title": "<i>Tricky</i> & co", "body": body}).json()["id"]
    s, m, text = _export(reviewer, _campaign(creator, brand_id, [cid]))
    assert m["assets"][0]["versions"][0]["text"] == body  # JSON keeps the stored text exactly
    assert "<script>alert(1)</script>" in text and "<i>Tricky</i> & co" in text  # rendered literally, not as markup
    assert "\x07" not in text
    assert audit_pack.safe("<a href='x'>&") == "&lt;a href='x'&gt;&amp;"


def test_no_secrets_in_manifest(creator, reviewer, brand_id):
    _, m, text = _export(reviewer, _campaign(creator, brand_id, [_approved_asset(creator, reviewer, brand_id)]))
    raw = json.dumps(m).lower()
    for needle in ("password", "token_hash", "auditra_session", "api_key", "secret"):
        assert needle not in raw and needle not in text.lower()


def test_permissions(creator, reviewer, brand_id):
    camp = _campaign(creator, brand_id, [])
    assert creator.post(f"/api/campaigns/{camp}/audit-packs").status_code == 403  # creators cannot export
    s = reviewer.post(f"/api/campaigns/{camp}/audit-packs").json()
    assert creator.get(s["json_url"]).status_code == 403 and creator.get(s["pdf_url"]).status_code == 403
    outsider = register_client(f"pack-{uuid.uuid4().hex[:6]}@example.com")
    assert outsider.post(f"/api/campaigns/{camp}/audit-packs").status_code == 404
    assert outsider.get(s["pdf_url"]).status_code == 404 and outsider.get(s["json_url"]).status_code == 404
    assert make_client().get(s["json_url"]).status_code == 401
