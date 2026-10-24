import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.models import BrandRule, ApprovedClaim
from backend.rule_engine import ComplianceRuleEngine

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c

def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data

def test_deterministic_rule_engine_violations():
    # Setup mock rules
    rules = [
        BrandRule(
            id="rule-1",
            brand_id="b1",
            name="No Guarantees",
            category="prohibited_term",
            description="Never promise guaranteed results.",
            rule_text="Do not guarantee results.",
            match_pattern="guaranteed results",
            suggested_replacement="proven outcomes",
            severity="critical",
            is_active=True
        ),
        BrandRule(
            id="rule-2",
            brand_id="b1",
            name="Preferred: Members",
            category="preferred_term",
            description="Use members instead of users.",
            rule_text="Use members.",
            match_pattern="users",
            suggested_replacement="members",
            severity="medium",
            is_active=True
        ),
        BrandRule(
            id="rule-3",
            brand_id="b1",
            name="Disclaimer required",
            category="required_phrase",
            description="Must include variation disclaimer.",
            rule_text="Results may vary.",
            match_pattern="Results may vary",
            suggested_replacement="\n\nResults may vary.",
            severity="high",
            is_active=True
        )
    ]
    claims = [
        ApprovedClaim(
            id="c1",
            brand_id="b1",
            claim_statement="Northstar accelerates throughput by 34%.",
            topic="Performance",
            evidence_source="Lab benchmark",
            is_active=True
        )
    ]

    engine = ComplianceRuleEngine(rules, claims)
    text = "We offer guaranteed results for all users. Double your performance in seven days!"
    findings = engine.analyze(text)

    categories = [f.category for f in findings]
    assert "prohibited_term" in categories
    assert "preferred_term" in categories
    assert "required_phrase" in categories
    assert "unverified_claim" in categories

def test_deterministic_rule_engine_clean_content():
    rules = [
        BrandRule(
            id="rule-1",
            brand_id="b1",
            name="No Guarantees",
            category="prohibited_term",
            description="Never promise guaranteed results.",
            rule_text="Do not guarantee results.",
            match_pattern="guaranteed results",
            suggested_replacement="proven outcomes",
            severity="critical",
            is_active=True
        )
    ]
    engine = ComplianceRuleEngine(rules, [])
    clean_text = "Northstar offers verified enterprise infrastructure and audited reliability."
    findings = engine.analyze(clean_text)
    assert len(findings) == 0

def test_brands_and_sample_workspace(client):
    # Fetch brands
    resp = client.get("/api/brands")
    assert resp.status_code == 200
    brands = resp.json()
    assert len(brands) > 0
    northstar = next(b for b in brands if b["slug"] == "northstar")
    assert northstar["is_sample"] is True

def test_create_content_takes_brand_from_path(client):
    # The studio posts without brand_id in the body; the URL path identifies the brand.
    brand_id = client.get("/api/brands").json()[0]["id"]
    resp = client.post(f"/api/brands/{brand_id}/content", json={"title": "Path brand", "body": "Hello."})
    assert resp.status_code == 201
    assert resp.json()["brand_id"] == brand_id

def test_content_lifecycle_and_corrections(client):
    # 1. Get Northstar brand
    resp = client.get("/api/brands")
    brand_id = resp.json()[0]["id"]

    # 2. Create new content item
    create_payload = {
        "brand_id": brand_id,
        "title": "Automated Test Post",
        "content_type": "social_post",
        "body": "Northstar guarantees results for every customer. Our users love it.",
        "created_by": "Test Suite"
    }
    create_resp = client.post(f"/api/brands/{brand_id}/content", json=create_payload)
    assert create_resp.status_code == 201
    item = create_resp.json()
    content_id = item["id"]
    assert item["status"] == "draft"
    assert item["current_version_number"] == 1

    # 3. Run compliance review
    review_resp = client.post(f"/api/content/{content_id}/review", json={
        "actor_name": "Test Suite",
        "force_engine": "deterministic"
    })
    assert review_resp.status_code == 200
    run_data = review_resp.json()
    assert run_data["status"] == "completed"
    assert len(run_data["findings"]) > 0

    # Locate finding for "users"
    finding_to_apply = next((f for f in run_data["findings"] if f["matched_text"] == "users"), None)
    assert finding_to_apply is not None

    # 4. Apply targeted correction
    apply_resp = client.post(f"/api/findings/{finding_to_apply['id']}/apply", json={
        "actor_name": "Test Suite",
        "actor_role": "Tester"
    })
    assert apply_resp.status_code == 200
    updated_item = apply_resp.json()
    assert updated_item["current_version_number"] == 2
    assert "members" in updated_item["current_version"]["body"]
    assert "users" not in updated_item["current_version"]["body"]

    # 5. Submit for review (Draft -> In Review)
    submit_resp = client.post(f"/api/content/{content_id}/submit")
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "in_review"

    # 6. Invalid transition test: Cannot transition to invalid state
    bad_decision_resp = client.post(f"/api/content/{content_id}/decision", json={
        "decision": "invalid_status",
        "reviewer_name": "Sarah",
        "reviewer_role": "Reviewer"
    })
    assert bad_decision_resp.status_code == 400

    # 7. Valid approval decision
    approve_resp = client.post(f"/api/content/{content_id}/decision", json={
        "decision": "approved",
        "reviewer_name": "Sarah Chen",
        "reviewer_role": "Senior Reviewer",
        "comments": "Looks compliant and well-structured."
    })
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    # 8. Check audit trail
    audit_resp = client.get(f"/api/brands/{brand_id}/audit?content_id={content_id}")
    assert audit_resp.status_code == 200
    audit_events = audit_resp.json()
    assert len(audit_events) >= 4

def test_dashboard_and_insights_endpoints(client):
    resp = client.get("/api/brands")
    brand_id = resp.json()[0]["id"]

    dash_resp = client.get(f"/api/brands/{brand_id}/dashboard")
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    assert "total_reviews" in dash_data
    assert "severity_distribution" in dash_data
    assert "status_counts" in dash_data

    insights_resp = client.get(f"/api/brands/{brand_id}/insights")
    assert insights_resp.status_code == 200
    insights_data = insights_resp.json()
    assert "most_frequent_categories" in insights_data
    assert "most_triggered_rules" in insights_data
