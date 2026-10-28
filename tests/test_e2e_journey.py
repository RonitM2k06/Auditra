import pytest
from fastapi.testclient import TestClient
from tests.conftest import make_client
from backend.main import app
from backend.database import SessionLocal
from backend.models import ContentItem, AuditEvent

def test_complete_judge_end_to_end_journey():
    """
    Executes the exact 12-step master judge workflow specified in Section 19.3 & Section 22.
    """
    with make_client("admin") as client:
        # Step 1 & 2: Open app & verify brand workspace exists
        brands_resp = client.get("/api/brands")
        assert brands_resp.status_code == 200
        brands = brands_resp.json()
        assert len(brands) > 0
        brand = next((b for b in brands if b["slug"] == "northstar"), brands[0])
        brand_id = brand["id"]

        # Step 3: Check configured rules
        rules_resp = client.get(f"/api/brands/{brand_id}/rules")
        assert rules_resp.status_code == 200
        rules = rules_resp.json()
        assert len(rules) >= 5
        # Verify prohibited phrase rule exists
        guarantee_rule = next((r for r in rules if "guarantees results" in (r.get("match_pattern") or "").lower()), None)
        assert guarantee_rule is not None, "Prohibited phrase rule must be configured"

        # Step 4: Submit content containing known violations
        # Section 22 exact test copy:
        # "Northstar guarantees results for every customer. Our users will double their performance in seven days. Join today."
        sample_copy = "Northstar guarantees results for every customer. Our users will double their performance in seven days. Join today."
        create_payload = {
            "brand_id": brand_id,
            "title": "E2E Judge Verification Campaign",
            "content_type": "social_post",
            "body": sample_copy,
            "created_by": "Alex Rivers (Creator)"
        }
        create_resp = client.post(f"/api/brands/{brand_id}/content", json=create_payload)
        assert create_resp.status_code == 201
        content_item = create_resp.json()
        content_id = content_item["id"]
        assert content_item["status"] == "draft"
        assert content_item["current_version_number"] == 1

        # Step 5: Run compliance review
        review_resp = client.post(f"/api/content/{content_id}/review", json={
            "actor_name": "Alex Rivers",
            "actor_role": "Content Creator",
            "force_engine": "deterministic"
        })
        assert review_resp.status_code == 200
        review_run = review_resp.json()
        assert review_run["status"] == "completed"

        # Step 6: Verify findings & rule citations
        findings = review_run["findings"]
        assert len(findings) >= 3, f"Expected at least 3 findings, got {len(findings)}"

        # Check prohibited phrase finding
        prohibited_finding = next((f for f in findings if f["matched_text"] == "guarantees results"), None)
        assert prohibited_finding is not None
        assert prohibited_finding["category"] == "prohibited_term"
        assert prohibited_finding["severity"] == "critical"
        assert "Northstar Legal Governance Standard" in (prohibited_finding["source_reference"] or "")

        # Check terminology finding
        term_finding = next((f for f in findings if f["matched_text"] == "users"), None)
        assert term_finding is not None
        assert term_finding["category"] == "preferred_term"
        assert term_finding["suggested_correction"] == "members"

        # Check unverified claim finding
        claim_finding = next((f for f in findings if "double" in f["matched_text"].lower()), None)
        assert claim_finding is not None
        assert claim_finding["requires_human_review"] is True

        # Step 7: Apply targeted correction on terminology ("users" -> "members")
        apply_resp = client.post(f"/api/findings/{term_finding['id']}/apply", json={
            "actor_name": "Alex Rivers",
            "actor_role": "Content Creator"
        })
        assert apply_resp.status_code == 200
        revised_item = apply_resp.json()
        assert revised_item["current_version_number"] == 2
        assert "members" in revised_item["current_version"]["body"]
        assert "users" not in revised_item["current_version"]["body"]

        # Step 8: Re-run analysis on revised content
        re_review_resp = client.post(f"/api/content/{content_id}/review", json={
            "actor_name": "Alex Rivers",
            "force_engine": "deterministic"
        })
        assert re_review_resp.status_code == 200
        re_findings = re_review_resp.json()["findings"]
        # Terminology violation is resolved in new version!
        assert not any(f["matched_text"] == "users" for f in re_findings)

        # Step 9: Submit content for human review (Draft -> In Review)
        submit_resp = client.post(f"/api/content/{content_id}/submit", params={
            "actor_name": "Alex Rivers",
            "actor_role": "Content Creator"
        })
        assert submit_resp.status_code == 200
        assert submit_resp.json()["status"] == "in_review"

        # Step 10: Perform reviewer action (Comment + Review Decision)
        comment_resp = client.post(f"/api/content/{content_id}/comments", json={
            "author_name": "Sarah Chen",
            "author_role": "Brand Compliance Lead",
            "text": "Reviewed and verified revision. Approved for omni-channel release."
        })
        assert comment_resp.status_code == 200

        reviewer = make_client("reviewer")
        decision_resp = reviewer.post(f"/api/content/{content_id}/decision", json={
            "version_number": client.get(f"/api/content/{content_id}").json()["current_version_number"], "evidence_confirmed": True,
            "decision": "approved",
            "reviewer_name": "Sarah Chen",
            "reviewer_role": "Brand Compliance Lead",
            "comments": "Final copy certified against Northstar governance policy."
        })
        assert decision_resp.status_code == 200
        # Approved outright, or held in review by a triggered approval policy that names what is missing.
        _st = decision_resp.json()
        assert _st["status"] == "approved" or (_st["status"] == "in_review" and _st["approval_status"]["blocking"])

        # Step 11: Verify audit trail
        audit_resp = client.get(f"/api/brands/{brand_id}/audit?content_id={content_id}")
        assert audit_resp.status_code == 200
        audit_events = audit_resp.json()
        event_types = [e["event_type"] for e in audit_events]
        assert "draft_created" in event_types
        assert "correction_applied" in event_types
        assert "submitted_for_review" in event_types
        assert "comment_added" in event_types
        assert "content_approved" in event_types or "approval_recorded" in event_types

        # Step 12: Verify persistent database state across new session
        detail_resp = client.get(f"/api/content/{content_id}")
        assert detail_resp.status_code == 200
        persisted = detail_resp.json()
        assert persisted["status"] in ("approved", "in_review")
        assert persisted["current_version_number"] == 2
        assert len(persisted["decisions"]) >= 1
        assert persisted["decisions"][0]["decision"] == "approved"
        assert persisted["decisions"][0]["reviewer_name"] == "Sarah Chen"
