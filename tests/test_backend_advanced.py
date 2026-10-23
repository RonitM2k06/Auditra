import io
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.models import BrandRule, ApprovedClaim
from backend.rule_engine import ComplianceRuleEngine

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c

def test_guideline_upload_parsing(client):
    resp = client.get("/api/brands")
    brand_id = resp.json()[0]["id"]

    guideline_content = """# Northstar Marketing Policy Addendum
Prohibited: 100% uptime guaranteed
Use: client partner instead of user
Do not use: secret hack
"""
    file_bytes = io.BytesIO(guideline_content.encode("utf-8"))
    upload_resp = client.post(
        f"/api/brands/{brand_id}/rules/upload-guidelines",
        files={"file": ("addendum.md", file_bytes, "text/markdown")}
    )
    assert upload_resp.status_code == 200
    data = upload_resp.json()
    assert data["rules_extracted"] >= 2

def test_claims_crud(client):
    resp = client.get("/api/brands")
    brand_id = resp.json()[0]["id"]

    # 1. List claims
    claims_resp = client.get(f"/api/brands/{brand_id}/claims")
    assert claims_resp.status_code == 200
    initial_count = len(claims_resp.json())

    # 2. Create claim
    new_claim = {
        "claim_statement": "Northstar reduces cloud infrastructure idle spend by 28%.",
        "topic": "Cost Optimization",
        "evidence_source": "FinOps Consortium Audit 2026",
        "verification_date": "2026-09-01",
        "is_active": True
    }
    create_resp = client.post(f"/api/brands/{brand_id}/claims", json=new_claim)
    assert create_resp.status_code == 201
    claim_id = create_resp.json()["id"]

    # 3. Verify in list
    claims_resp2 = client.get(f"/api/brands/{brand_id}/claims")
    assert len(claims_resp2.json()) == initial_count + 1

    # 4. Delete claim
    del_resp = client.delete(f"/api/brands/{brand_id}/claims/{claim_id}")
    assert del_resp.status_code == 204

def test_state_machine_strict_enforcement(client):
    resp = client.get("/api/brands")
    brand_id = resp.json()[0]["id"]

    # Create draft
    item_resp = client.post(f"/api/brands/{brand_id}/content", json={
        "brand_id": brand_id,
        "title": "State Transition Guardrail Test",
        "content_type": "advertisement",
        "body": "Compliant content for our cloud members.",
        "created_by": "Compliance Lead"
    })
    item_id = item_resp.json()["id"]

    # Attempt to directly approve a draft without submitting for review: should be rejected
    direct_approve = client.post(f"/api/content/{item_id}/decision", json={
        "decision": "approved",
        "reviewer_name": "Auditor",
        "reviewer_role": "Reviewer"
    })
    assert direct_approve.status_code == 400
    assert "Illegal state transition" in direct_approve.json()["detail"]

    # Transition Draft -> In Review
    submit = client.post(f"/api/content/{item_id}/submit")
    assert submit.status_code == 200
    assert submit.json()["status"] == "in_review"

    # In Review -> Changes Requested
    req_changes = client.post(f"/api/content/{item_id}/decision", json={
        "decision": "changes_requested",
        "reviewer_name": "Auditor",
        "reviewer_role": "Reviewer",
        "comments": "Please refine the intro paragraph."
    })
    assert req_changes.status_code == 200
    assert req_changes.json()["status"] == "changes_requested"

    # Resubmit Changes Requested -> In Review
    resubmit = client.post(f"/api/content/{item_id}/submit")
    assert resubmit.status_code == 200
    assert resubmit.json()["status"] == "in_review"

    # In Review -> Approved
    approve = client.post(f"/api/content/{item_id}/decision", json={
        "decision": "approved",
        "reviewer_name": "Auditor",
        "reviewer_role": "Reviewer",
        "comments": "Approved after review."
    })
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"
