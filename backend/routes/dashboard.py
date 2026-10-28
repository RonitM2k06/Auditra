import json
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.auth import authorize, current_user
from backend.models_r3 import User
from backend.models import Brand, ContentItem, ContentVersion, ReviewRun, Finding, AuditEvent
from backend.schemas import DashboardStatsResponse, ContentItemResponse, AuditEventResponse

router = APIRouter(prefix="/brands/{brand_id}", tags=["Dashboard"])

@router.get("/dashboard", response_model=DashboardStatsResponse)
def get_dashboard_metrics(brand_id: str, user: User = Depends(current_user),
    db: Session = Depends(get_db)):
    actor = authorize(db, user, brand_id, "workspace.view")
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    items = db.query(ContentItem).filter(ContentItem.brand_id == brand_id).all()
    total_reviews = len(items)

    status_counts = {"draft": 0, "in_review": 0, "changes_requested": 0, "approved": 0, "rejected": 0}
    for item in items:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1

    awaiting_approval = status_counts.get("in_review", 0)
    approved_reviews = status_counts.get("approved", 0)

    # Calculate unresolved high/critical issues and severity distribution from latest reviews
    severity_distribution = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    category_distribution = {}
    items_with_high_risk = 0

    for item in items:
        # Find current version
        current_ver = db.query(ContentVersion).filter(
            ContentVersion.content_id == item.id,
            ContentVersion.version_number == item.current_version_number
        ).first()

        if current_ver:
            latest_run = db.query(ReviewRun).filter(ReviewRun.content_version_id == current_ver.id).order_by(ReviewRun.created_at.desc()).first()
            if latest_run:
                # Get active findings (not applied, not dismissed)
                active_findings = db.query(Finding).filter(
                    Finding.review_run_id == latest_run.id,
                    Finding.is_applied == False,
                    Finding.is_dismissed == False
                ).all()

                has_critical_or_high = False
                for f in active_findings:
                    s = f.severity.lower()
                    severity_distribution[s] = severity_distribution.get(s, 0) + 1
                    category_distribution[f.category] = category_distribution.get(f.category, 0) + 1
                    if s in ("critical", "high"):
                        has_critical_or_high = True

                if has_critical_or_high:
                    items_with_high_risk += 1

    # Recent reviews
    recent_items = db.query(ContentItem).filter(ContentItem.brand_id == brand_id).order_by(ContentItem.updated_at.desc()).limit(6).all()
    recent_reviews = [
        ContentItemResponse(
            id=item.id,
            brand_id=item.brand_id,
            title=item.title,
            content_type=item.content_type,
            status=item.status,
            current_version_number=item.current_version_number,
            created_by=item.created_by,
            reviewer_id=item.reviewer_id,
            created_at=item.created_at,
            updated_at=item.updated_at
        )
        for item in recent_items
    ]

    # Recent activity
    recent_audit = db.query(AuditEvent).filter(AuditEvent.brand_id == brand_id).order_by(AuditEvent.created_at.desc()).limit(8).all()
    recent_activity = []
    for ae in recent_audit:
        meta_dict = None
        if ae.event_metadata:
            try:
                meta_dict = json.loads(ae.event_metadata)
            except Exception:
                meta_dict = {}
        recent_activity.append(
            AuditEventResponse(
                id=ae.id,
                brand_id=ae.brand_id,
                content_id=ae.content_id,
                event_type=ae.event_type,
                actor_name=ae.actor_name,
                actor_role=ae.actor_role,
                description=ae.description,
                event_metadata=meta_dict,
                created_at=ae.created_at
            )
        )

    return DashboardStatsResponse(
        total_reviews=total_reviews,
        awaiting_approval=awaiting_approval,
        high_severity_issues=items_with_high_risk,
        approved_reviews=approved_reviews,
        status_counts=status_counts,
        severity_distribution=severity_distribution,
        category_distribution=category_distribution,
        recent_reviews=recent_reviews,
        recent_activity=recent_activity
    )
