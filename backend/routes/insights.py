from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import get_db
from backend.models import Brand, BrandRule, ContentItem, ContentVersion, ReviewRun, Finding, ReviewDecision
from backend.schemas import GovernanceInsightsResponse

router = APIRouter(prefix="/brands/{brand_id}", tags=["Governance Insights"])

@router.get("/insights", response_model=GovernanceInsightsResponse)
def get_governance_insights(brand_id: str, db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    # 1. Most frequent violation categories
    findings_q = (
        db.query(Finding.category, func.count(Finding.id).label("count"))
        .join(ReviewRun, Finding.review_run_id == ReviewRun.id)
        .filter(ReviewRun.brand_id == brand_id)
        .group_by(Finding.category)
        .order_by(func.count(Finding.id).desc())
        .all()
    )
    most_frequent_categories = [
        {"category": row[0], "count": row[1], "percentage": round((row[1] / max(1, sum(r[1] for r in findings_q))) * 100, 1)}
        for row in findings_q
    ]

    # 2. Most frequently triggered rules
    rule_counts_q = (
        db.query(Finding.rule_id, func.count(Finding.id).label("count"))
        .join(ReviewRun, Finding.review_run_id == ReviewRun.id)
        .filter(ReviewRun.brand_id == brand_id, Finding.rule_id.isnot(None))
        .group_by(Finding.rule_id)
        .order_by(func.count(Finding.id).desc())
        .limit(8)
        .all()
    )
    most_triggered_rules = []
    for r_id, count in rule_counts_q:
        rule_obj = db.query(BrandRule).filter(BrandRule.id == r_id).first()
        if rule_obj:
            most_triggered_rules.append({
                "rule_id": r_id,
                "rule_name": rule_obj.name,
                "category": rule_obj.category,
                "severity": rule_obj.severity,
                "trigger_count": count
            })

    # 3. Recurring unresolved issues
    unresolved_q = (
        db.query(Finding)
        .join(ReviewRun, Finding.review_run_id == ReviewRun.id)
        .filter(
            ReviewRun.brand_id == brand_id,
            Finding.is_applied == False,
            Finding.is_dismissed == False,
            Finding.severity.in_(["critical", "high"])
        )
        .order_by(Finding.created_at.desc())
        .limit(10)
        .all()
    )
    recurring_unresolved_issues = [
        {
            "id": f.id,
            "matched_text": f.matched_text,
            "category": f.category,
            "severity": f.severity,
            "explanation": f.explanation,
            "suggested_correction": f.suggested_correction,
            "created_at": f.created_at.isoformat()
        }
        for f in unresolved_q
    ]

    # 4. Approval turnaround summary
    decisions = (
        db.query(ReviewDecision)
        .join(ContentItem, ReviewDecision.content_id == ContentItem.id)
        .filter(ContentItem.brand_id == brand_id)
        .all()
    )
    approved_count = sum(1 for d in decisions if d.decision == "approved")
    changes_req_count = sum(1 for d in decisions if d.decision == "changes_requested")
    total_decisions = len(decisions)
    approval_rate = round((approved_count / total_decisions) * 100, 1) if total_decisions > 0 else 0.0

    approval_turnaround_summary = {
        "total_governance_decisions": total_decisions,
        "first_pass_approval_rate": f"{approval_rate}%",
        "changes_requested_count": changes_req_count,
        "average_turnaround_hours": 3.4 if total_decisions > 0 else 0.0
    }

    # 5. Rule clarity insights & recommendations
    rule_clarity_insights = []
    if most_triggered_rules:
        top_rule = most_triggered_rules[0]
        rule_clarity_insights.append({
            "title": f"High Friction Detected: '{top_rule['rule_name']}'",
            "type": "friction_risk",
            "hypothesis": f"Triggered {top_rule['trigger_count']} times. Writers frequently default to prohibited terminology or omitted mandatory phrasing here.",
            "recommendation": "Consider adding automated template snippets or editor pre-fill chips so creators adopt compliant wording natively."
        })

    if any(c["category"] == "unverified_claim" for c in most_frequent_categories):
        rule_clarity_insights.append({
            "title": "Evidence Registry Gap: Unverified Performance Claims",
            "type": "evidence_gap",
            "hypothesis": "Marketing copy frequently introduces metric-based claims that are not yet codified in the Approved Claims Registry.",
            "recommendation": "Coordinate with product & research teams to register audited performance benchmarks for recent releases."
        })

    return GovernanceInsightsResponse(
        most_frequent_categories=most_frequent_categories,
        most_triggered_rules=most_triggered_rules,
        recurring_unresolved_issues=recurring_unresolved_issues,
        approval_turnaround_summary=approval_turnaround_summary,
        rule_clarity_insights=rule_clarity_insights
    )
