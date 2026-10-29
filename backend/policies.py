"""Approval policy evaluation.

A version is approved only when:
  * it is the item's current version and it has a completed review run,
  * at least one reviewer/admin has approved that exact version, and
  * every active policy triggered by the version's open findings or claim checks is satisfied
    by approvals recorded against that same version.

Approvals from earlier versions never count, so editing content cannot ride on an old approval.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models import ContentItem, ContentVersion, Finding, ReviewDecision, ReviewRun
from backend.models_r3 import ApprovalPolicy, ClaimCheck, Membership

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
CONDITION_TYPES = {"severity_at_least", "claim_status", "finding_category"}
CLAIM_STATES = {"supported", "unsupported", "contradicted", "stale", "needs_review"}


def describe_condition(condition_type: str, value: str) -> str:
    if condition_type == "severity_at_least":
        return f"an open finding of {value} severity or higher"
    if condition_type == "claim_status":
        return f"a claim classified as '{value.replace('_', ' ')}'"
    return f"an open '{value.replace('_', ' ')}' finding"


def latest_run_for_version(db: Session, version_id: str) -> Optional[ReviewRun]:
    return (
        db.query(ReviewRun).filter(ReviewRun.content_version_id == version_id)
        .order_by(ReviewRun.created_at.desc()).first()
    )


def triggered_policies(policies: List[Any], open_findings: List[Any], claim_checks: List[Any]) -> List[Dict[str, Any]]:
    """Pure function (also used by simulations): which policies the given evidence triggers."""
    triggered = []
    for p in policies:
        if not p.is_active:
            continue
        reasons: List[str] = []
        if p.condition_type == "severity_at_least":
            threshold = SEVERITY_RANK.get(p.condition_value, 5)
            reasons = [f"{f.severity} · {f.matched_text[:60]}" for f in open_findings if SEVERITY_RANK.get(f.severity, 0) >= threshold]
        elif p.condition_type == "claim_status":
            reasons = [f"{c.status} · {c.claim_text[:60]}" for c in claim_checks if c.status == p.condition_value]
        elif p.condition_type == "finding_category":
            reasons = [f"{f.category} · {f.matched_text[:60]}" for f in open_findings if f.category == p.condition_value]
        if reasons:
            triggered.append({"policy": p, "reasons": reasons})
    return triggered


def evaluate(db: Session, item: ContentItem) -> Dict[str, Any]:
    version = db.query(ContentVersion).filter(
        ContentVersion.content_id == item.id, ContentVersion.version_number == item.current_version_number
    ).first()
    result: Dict[str, Any] = {
        "version_number": item.current_version_number,
        "reviewed": False,
        "review_is_current": False,
        "approvals": [],
        "requirements": [],
        "satisfied": False,
        "blocking": [],
    }
    if not version:
        result["blocking"].append("No current version.")
        return result

    run = latest_run_for_version(db, version.id)
    result["reviewed"] = run is not None
    result["review_is_current"] = run is not None
    open_findings = []
    checks = []
    if run:
        open_findings = db.query(Finding).filter(
            Finding.review_run_id == run.id, Finding.is_applied == False, Finding.is_dismissed == False  # noqa: E712
        ).all()
        checks = db.query(ClaimCheck).filter(ClaimCheck.review_run_id == run.id).all()

    approvals = db.query(ReviewDecision).filter(
        ReviewDecision.content_version_id == version.id, ReviewDecision.decision == "approved"
    ).order_by(ReviewDecision.created_at.asc()).all()
    roles = {
        m.user_id: m.role
        for m in db.query(Membership).filter(Membership.brand_id == item.brand_id).all()
    }
    approval_rows = [{
        "reviewer_name": a.reviewer_name,
        "reviewer_user_id": a.reviewer_user_id,
        "role": roles.get(a.reviewer_user_id, "unknown"),
        "evidence_confirmed": bool(a.evidence_confirmed),
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a in approvals]
    result["approvals"] = approval_rows

    requirements = [{
        "name": "Baseline: one approval from a reviewer or admin on this version",
        "trigger": None,
        "reasons": [],
        "required_role": None,
        "min_approvals": 1,
        "require_evidence_confirmation": False,
    }]
    policies = db.query(ApprovalPolicy).filter(ApprovalPolicy.brand_id == item.brand_id).all()
    for t in triggered_policies(policies, open_findings, checks):
        p = t["policy"]
        requirements.append({
            "name": p.name,
            "policy_id": p.id,
            "trigger": describe_condition(p.condition_type, p.condition_value),
            "reasons": t["reasons"][:5],
            "required_role": p.required_role,
            "min_approvals": p.min_approvals,
            "require_evidence_confirmation": p.require_evidence_confirmation,
        })

    all_ok = run is not None
    if run is None:
        result["blocking"].append(f"Version {version.version_number} has not been analysed yet.")
    for req in requirements:
        eligible = [a for a in approval_rows if a["role"] in ("reviewer", "admin")]
        if req["required_role"]:
            role_ok = any(a["role"] == req["required_role"] for a in eligible)
        else:
            role_ok = True
        evidence_ok = (not req["require_evidence_confirmation"]) or any(a["evidence_confirmed"] for a in eligible)
        count_ok = len({a["reviewer_user_id"] for a in eligible}) >= req["min_approvals"]
        req["met"] = role_ok and evidence_ok and count_ok
        missing = []
        if not count_ok:
            missing.append(f"needs {req['min_approvals']} distinct approver(s), has {len({a['reviewer_user_id'] for a in eligible})}")
        if not role_ok:
            missing.append(f"needs an approval from a {req['required_role']}")
        if not evidence_ok:
            missing.append("needs an approver to confirm the claim evidence was reviewed")
        req["missing"] = missing
        if not req["met"]:
            all_ok = False
            result["blocking"].append(f"{req['name']}: " + "; ".join(missing))
    result["requirements"] = requirements
    result["satisfied"] = all_ok
    return result
