"""Multimodal review, evidence verification, Brand DNA, simulation, campaigns and replay."""
import io
import os
from datetime import date

import pytest
from PIL import Image

from backend import evidence, intelligence, vision
from tests.conftest import make_client

SAMPLES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples")


@pytest.fixture(scope="module")
def creator():
    return make_client("creator")


@pytest.fixture(scope="module")
def admin():
    return make_client("admin")


@pytest.fixture(scope="module")
def brand_id(creator):
    return next(b["id"] for b in creator.get("/api/brands").json() if b["slug"] == "northstar")


def _png(size=(400, 300), color="white") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def _sample(name) -> bytes:
    with open(os.path.join(SAMPLES, "creatives", name), "rb") as fh:
        return fh.read()


# --- Image intake validation ---

@pytest.mark.parametrize("data,fragment", [
    (b"", "empty"),
    (b"GIF89a" + b"0" * 100, "Unsupported"),
    (b"\x89PNG\r\n\x1a\n" + b"garbage" * 20, "corrupt"),
    (_png((20, 20)), "outside the supported range"),
])
def test_image_validation_rejects_bad_files(data, fragment):
    with pytest.raises(vision.ImageValidationError) as exc:
        vision.validate_image(data)
    assert fragment in str(exc.value)


def test_image_validation_ignores_filename_and_mime(creator, brand_id):
    # A text file renamed to .png with an image MIME type is still rejected by content.
    r = creator.post(f"/api/brands/{brand_id}/creatives", data={"title": "Fake"},
                     files={"file": ("../../etc/passwd.png", b"not an image at all", "image/png")})
    assert r.status_code == 422


def test_oversized_upload_rejected(creator, brand_id):
    r = creator.post(f"/api/brands/{brand_id}/creatives", data={"title": "Big"},
                     files={"file": ("big.png", b"\x89PNG\r\n\x1a\n" + b"0" * (vision.MAX_IMAGE_BYTES + 10), "image/png")})
    assert r.status_code == 413


def test_creative_upload_ocr_rules_and_visual_checks(creator, admin, brand_id):
    r = creator.post(f"/api/brands/{brand_id}/creatives", data={"title": "Violations creative", "content_type": "social_post"},
                     files={"file": ("promo.png", _sample("02-violations-guarantee.png"), "image/png")})
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["media_kind"] == "image"
    ocr = item["image"]["ocr"]
    assert ocr["status"] == "ok" and len(ocr["lines"]) >= 3
    assert "guarantees results" in item["current_version"]["body"].lower()
    run = creator.post(f"/api/content/{item['id']}/review", json={}).json()
    cats = {f["category"] for f in run["findings"]}
    assert {"prohibited_term", "visual_contrast", "visual_logo"} <= cats
    prohibited = next(f for f in run["findings"] if f["category"] == "prohibited_term")
    assert prohibited["finding_source"] == "ocr_rule" and prohibited["region_json"]
    contrast = next(f for f in run["findings"] if f["category"] == "visual_contrast")
    assert "Ask your account team" in contrast["matched_text"]
    # Image text cannot be edited in place
    assert creator.post(f"/api/findings/{prohibited['id']}/apply", json={}).status_code == 409
    assert creator.put(f"/api/content/{item['id']}", json={"body": "x"}).status_code == 409
    img = creator.get(f"/api/content/{item['id']}/versions/1/image")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    # Revised creative creates version 2; identical re-upload is refused
    again = creator.post(f"/api/content/{item['id']}/creative", files={"file": ("p.png", _sample("02-violations-guarantee.png"), "image/png")})
    assert again.status_code == 409
    v2 = creator.post(f"/api/content/{item['id']}/creative", files={"file": ("p.png", _sample("01-compliant-atlas.png"), "image/png")})
    assert v2.status_code == 200 and v2.json()["current_version_number"] == 2


def test_compliant_creative_has_no_rule_violations(creator, brand_id):
    r = creator.post(f"/api/brands/{brand_id}/creatives", data={"title": "Compliant"},
                     files={"file": ("ok.png", _sample("01-compliant-atlas.png"), "image/png")}).json()
    run = creator.post(f"/api/content/{r['id']}/review", json={}).json()
    serious = [f for f in run["findings"] if f["severity"] in ("critical", "high")]
    assert serious == []
    logo = creator.get(f"/api/content/{r['id']}").json()["image"]["visual"]["logo"]
    assert logo["status"] == "match"


def test_contrast_math():
    assert round(vision.contrast_ratio((0, 0, 0), (255, 255, 255)), 1) == 21.0
    assert round(vision.contrast_ratio((119, 119, 119), (255, 255, 255)), 2) == 4.48


def test_palette_delta_e_flags_off_brand_colour():
    img = Image.new("RGB", (200, 200), "#0F9D91")
    img.paste(Image.new("RGB", (200, 80), "#F26B1D"), (0, 120))
    res = vision.check_palette(img, ["#0F9D91", "#101B2D"])
    assert any(c["hex"].startswith("#F") and not c["on_palette"] for c in res["colours"])
    assert res["off_palette"]


# --- Evidence ingestion and verification ---

def _index(passages):
    return evidence.BM25Index([evidence.IndexedPassage(id=f"p{i}", text=t, section=None, page=None, document_id=f"d{i}",
                                                       document_name=n, source_identifier=None, effective_date=None,
                                                       expiry_date=exp, review_date=None)
                               for i, (t, n, exp) in enumerate(passages)])


IDX = [
    ("Northstar maintains a 99.995% uptime SLA backed by multi-region automated failover.", "Fact sheet", "2027-01-01"),
    ("Atlas Pro costs $49 per member per month, billed annually.", "Fact sheet", "2027-01-01"),
    ("Atlas Pro costs $59 per member per month, billed annually.", "Old pricing", "2025-12-31"),
    ("Northstar is not HIPAA certified.", "Security", None),
    ("Northstar is SOC 2 Type II certified.", "Security", "2025-06-30"),
]


@pytest.mark.parametrize("claim,expected", [
    ("Northstar maintains a 99.995% uptime SLA.", "supported"),
    ("Northstar maintains a 99.9% uptime SLA.", "contradicted"),
    ("Atlas Pro costs $59 per member per month.", "contradicted"),
    ("Atlas Pro costs $49 per member per month.", "supported"),
    ("Northstar is the fastest cloud in the world.", "unsupported"),
    ("Northstar is HIPAA certified.", "needs_review"),
    ("Northstar is SOC 2 Type II certified.", "stale"),
    ("Northstar guarantees 99.995% uptime.", "needs_review"),
])
def test_claim_verification_cases(claim, expected):
    v = evidence.verify_claim(claim, _index(IDX), today=date(2026, 10, 29))
    assert v.status == expected, (claim, v.status, v.rationale)
    if v.status != "unsupported":
        assert v.passage is not None and v.passage.text in [t for t, _, _ in IDX]


def test_never_verified_without_evidence():
    v = evidence.verify_claim("Northstar reduces costs by 40%.", _index([]), today=date(2026, 10, 29))
    assert v.status == "unsupported" and v.passage is None


def test_source_upload_validation_and_metadata(admin, creator, brand_id):
    bad = admin.post(f"/api/brands/{brand_id}/sources", files={"file": ("x.exe", b"MZ\x00\x00", "application/octet-stream")})
    assert bad.status_code == 422
    empty = admin.post(f"/api/brands/{brand_id}/sources", files={"file": ("e.txt", b"", "text/plain")})
    assert empty.status_code == 422
    bad_date = admin.post(f"/api/brands/{brand_id}/sources", data={"expiry_date": "next year"},
                          files={"file": ("a.md", b"# A\n\nNorthstar supports 14 regions.", "text/markdown")})
    assert bad_date.status_code == 422
    ok = admin.post(f"/api/brands/{brand_id}/sources", data={"name": "Regions note"},
                    files={"file": ("a.md", b"# Regions\n\nNorthstar Cloud runs in 14 regions.", "text/markdown")})
    assert ok.status_code == 201
    doc = ok.json()
    assert doc["expiry_date"] is None and doc["effective_date"] is None  # never invented
    assert creator.post(f"/api/brands/{brand_id}/sources", files={"file": ("a.txt", b"hello world text", "text/plain")}).status_code == 403
    detail = creator.get(f"/api/brands/{brand_id}/sources/{doc['id']}").json()
    assert detail["passages"][0]["section"] == "Regions"
    hits = creator.post(f"/api/brands/{brand_id}/evidence/search", json={"text": "how many regions"}).json()
    assert hits and "14 regions" in hits[0]["text"]
    admin.delete(f"/api/brands/{brand_id}/sources/{doc['id']}")


def test_pdf_ingestion():
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "Northstar Cloud is available in 14 regions worldwide.")
    c.showPage()
    c.save()
    passages = evidence.extract_pdf(buf.getvalue())
    assert passages and passages[0]["page"] == 1 and "14 regions" in passages[0]["text"]
    with pytest.raises(ValueError):
        evidence.extract_pdf(b"%PDF-1.4 broken")


def test_claim_checks_persist_with_review(creator, brand_id):
    items = creator.get(f"/api/brands/{brand_id}/content").json()
    landing = next(i for i in items if "landing page" in i["title"])
    creator.post(f"/api/content/{landing['id']}/review", json={})
    checks = creator.get(f"/api/content/{landing['id']}").json()["claim_checks"]
    by_status = {c["status"] for c in checks}
    assert "contradicted" in by_status and "supported" in by_status
    for c in checks:
        if c["passage_id"]:
            assert c["source"]["name"] and c["passage_text"]


# --- Brand DNA, contradictions, simulation ---

def test_brand_dna_is_derived_from_records(creator, brand_id):
    dna = creator.get(f"/api/brands/{brand_id}/dna").json()
    keys = {d["key"] for d in dna["dimensions"]}
    assert {"tone", "terminology", "prohibited", "disclosures", "claims", "evidence", "visual", "governance"} <= keys
    rule_ids = set(dna["rules"])
    for d in dna["dimensions"]:
        for it in d["items"]:
            if "rule_id" in it:
                assert it["rule_id"] in rule_ids
    assert any(c["certainty"] == "definite" for c in dna["contradictions"])


def test_contradiction_detector_cases():
    from types import SimpleNamespace as R
    rules = [
        R(id="a", name="No guarantee", category="prohibited_term", match_pattern="guaranteed", rule_text="", suggested_replacement="proven", severity="high", is_active=True),
        R(id="b", name="Disclaimer", category="required_phrase", match_pattern="Results are not guaranteed", rule_text="", suggested_replacement=None, severity="high", is_active=True),
        R(id="c", name="Members", category="preferred_term", match_pattern="users", rule_text="", suggested_replacement="members", severity="low", is_active=True),
        R(id="d", name="Clients", category="preferred_term", match_pattern="users", rule_text="", suggested_replacement="clients", severity="low", is_active=True),
    ]
    kinds = {c["kind"] for c in intelligence.detect_contradictions(rules)}
    assert {"required_contains_prohibited", "conflicting_replacements"} <= kinds


def test_simulation_does_not_change_active_data(admin, creator, brand_id):
    before_rules = admin.get(f"/api/brands/{brand_id}/rules").json()
    before_audit = len(admin.get(f"/api/brands/{brand_id}/audit?limit=500").json())
    target = next(r for r in before_rules if r["match_pattern"] == "guarantees results")
    sim = admin.post(f"/api/brands/{brand_id}/simulate", json={"changes": [
        {"op": "disable", "rule_id": target["id"]},
        {"op": "add", "rule": {"name": "No 'today'", "category": "prohibited_term", "match_pattern": "today", "severity": "high"}},
    ]})
    assert sim.status_code == 200, sim.text
    data = sim.json()
    assert data["affected_items"] >= 1
    assert any(f["matched_text"].lower() == "today" for i in data["items"] for f in i["gained"])
    assert any(f.get("rule_id") == target["id"] for i in data["items"] for f in i["lost"])
    assert admin.get(f"/api/brands/{brand_id}/rules").json() == before_rules
    assert len(admin.get(f"/api/brands/{brand_id}/audit?limit=500").json()) == before_audit
    assert creator.post(f"/api/brands/{brand_id}/simulate", json={"changes": [{"op": "disable", "rule_id": target["id"]}]}).status_code == 403
    assert admin.post(f"/api/brands/{brand_id}/simulate", json={"changes": [{"op": "disable", "rule_id": "nope"}]}).status_code == 422


# --- Campaign consistency ---

def test_campaign_consistency_on_seed(creator, brand_id):
    camp = creator.get(f"/api/brands/{brand_id}/campaigns").json()[0]
    res = creator.get(f"/api/campaigns/{camp['id']}/consistency").json()
    kinds = {i["kind"] for i in res["issues"]}
    assert {"confirmed_mismatch", "missing_information", "rule_conflict"} <= kinds
    price = next(f for f in res["facts"] if f["type"] == "price")
    assert price["status"] == "confirmed_mismatch"
    assert {m["display"] for m in price["members"]} == {"$49", "$59"}
    for m in price["members"]:
        assert m["display"] in m["passage"]
    trial = next(f for f in res["facts"] if "trial" in f["label"])
    assert trial["status"] == "consistent"


def test_unrelated_numbers_are_not_called_contradictions():
    assets = [
        {"id": "a", "title": "A", "text": "Our team has grown to 40 engineers in Berlin.", "is_brief": False},
        {"id": "b", "title": "B", "text": "Storage plans start at 50 GB per workspace.", "is_brief": False},
    ]
    res = intelligence.campaign_consistency(assets, [], [])
    assert not [i for i in res["issues"] if i["kind"] == "confirmed_mismatch"]


def test_campaign_crud_and_empty_state(creator, brand_id):
    r = creator.post(f"/api/brands/{brand_id}/campaigns", json={"name": "Empty campaign", "content_ids": []})
    assert r.status_code == 201
    cons = creator.get(f"/api/campaigns/{r.json()['id']}/consistency").json()
    assert cons["issues"] == [] and "at least two" in cons["notice"]
    assert creator.post(f"/api/brands/{brand_id}/campaigns", json={"name": "Bad", "content_ids": ["foreign-id"]}).status_code == 422
    assert creator.delete(f"/api/campaigns/{r.json()['id']}").status_code == 204


# --- Decision replay ---

def test_replay_diff_findings_and_counterfactual(creator, admin, brand_id):
    item = creator.post(f"/api/brands/{brand_id}/content", json={"title": "Replay", "body": "Our users love Northstar. It guarantees results for every team."}).json()
    cid = item["id"]
    run1 = creator.post(f"/api/content/{cid}/review", json={}).json()
    users_f = next(f for f in run1["findings"] if f["category"] == "preferred_term")
    creator.post(f"/api/findings/{users_f['id']}/apply", json={})
    creator.post(f"/api/content/{cid}/review", json={})
    rep = creator.get(f"/api/content/{cid}/replay?from_version=1&to_version=2").json()
    assert any(d["op"] == "insert" and "members" in d["text"] for d in rep["diff"])
    assert any(f["matched_text"].lower() == "users" for f in rep["findings"]["resolved"])
    assert rep["findings"]["persisted"]
    assert rep["rulebook"]["from_snapshot"] and rep["rulebook"]["to_snapshot"]
    assert [e["event_type"] for e in rep["timeline"]][:1] == ["draft_created"]
    target = next(r for r in admin.get(f"/api/brands/{brand_id}/rules").json() if r["match_pattern"] == "guarantees results")
    cf = admin.post(f"/api/content/{cid}/versions/2/counterfactual", json={"changes": [{"op": "disable", "rule_id": target["id"]}]}).json()
    assert any(f.get("rule_id") == target["id"] for f in cf["lost"])
    # Nothing changed for real
    assert creator.get(f"/api/content/{cid}").json()["current_version_number"] == 2


def test_replay_reports_missing_historical_snapshot(creator, brand_id):
    items = creator.get(f"/api/brands/{brand_id}/content").json()
    seeded = next(i for i in items if i["title"].startswith("Apex FinTech"))
    rep = creator.get(f"/api/content/{seeded['id']}/replay").json()
    assert rep["rulebook"]["note"] and rep["rulebook"]["diff"] is None


# --- Edge cases ---

def test_review_on_empty_workspace_and_whitespace(creator):
    own = creator.post("/api/brands", json={"name": "Empty Workspace", "industry": "Tech"})
    assert own.status_code == 201
    bid = own.json()["id"]
    assert creator.get(f"/api/brands/{bid}/content").json() == []
    assert creator.get(f"/api/brands/{bid}/dna").json()["summary"]["dimensions_missing"] >= 6
    assert creator.get(f"/api/brands/{bid}/campaigns").json() == []
    assert creator.post(f"/api/brands/{bid}/evidence/verify", json={"text": "Northstar is the fastest cloud platform on the market."}).json()[0]["status"] == "unsupported"
