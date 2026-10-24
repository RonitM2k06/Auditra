import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Brand, ContentItem, ContentVersion, ReviewRun, Finding, Comment, ReviewDecision, AuditEvent
from backend.schemas import (
    ContentItemCreate, ContentItemUpdate, ContentItemResponse, ContentItemDetailResponse,
    ContentVersionResponse, ReviewRunResponse, FindingResponse, CommentResponse, ReviewDecisionResponse
)

router = APIRouter(tags=["Content Items"])

@router.get("/brands/{brand_id}/content", response_model=List[ContentItemResponse])
def get_brand_content_items(
    brand_id: str,
    status: Optional[str] = None,
    content_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(ContentItem).filter(ContentItem.brand_id == brand_id)
    if status:
        query = query.filter(ContentItem.status == status)
    if content_type:
        query = query.filter(ContentItem.content_type == content_type)
    return query.order_by(ContentItem.updated_at.desc()).all()

@router.post("/brands/{brand_id}/content", response_model=ContentItemDetailResponse, status_code=status.HTTP_201_CREATED)
def create_content_item(brand_id: str, payload: ContentItemCreate, db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    item = ContentItem(
        brand_id=brand_id,
        title=payload.title,
        content_type=payload.content_type,
        status="draft",
        current_version_number=1,
        created_by=payload.created_by
    )
    db.add(item)
    db.flush()

    v1 = ContentVersion(
        content_id=item.id,
        version_number=1,
        body=payload.body,
        change_summary="Initial draft",
        created_by=payload.created_by
    )
    db.add(v1)
    db.flush()

    db.add(AuditEvent(
        brand_id=brand_id,
        content_id=item.id,
        event_type="draft_created",
        actor_name=payload.created_by,
        actor_role="Creator",
        description=f"Created content draft '{item.title}' (version 1).",
        event_metadata=json.dumps({"version": 1})
    ))
    db.commit()
    db.refresh(item)

    return get_content_item_detail(item.id, db)

@router.get("/content/{content_id}", response_model=ContentItemDetailResponse)
def get_content_item_detail(content_id: str, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")

    versions = db.query(ContentVersion).filter(ContentVersion.content_id == content_id).order_by(ContentVersion.version_number.desc()).all()
    current_ver = next((v for v in versions if v.version_number == item.current_version_number), versions[0] if versions else None)

    latest_review = None
    if current_ver:
        # Return the most recent review for the item, even if it was run on an
        # earlier version; clients compare content_version_id to detect staleness.
        run = db.query(ReviewRun).filter(ReviewRun.content_id == content_id).order_by(ReviewRun.created_at.desc()).first()
        if run:
            findings_recs = db.query(Finding).filter(Finding.review_run_id == run.id).all()
            findings_data = [
                FindingResponse(
                    id=f.id,
                    review_run_id=f.review_run_id,
                    content_version_id=f.content_version_id,
                    rule_id=f.rule_id,
                    category=f.category,
                    severity=f.severity,
                    matched_text=f.matched_text,
                    start_offset=f.start_offset,
                    end_offset=f.end_offset,
                    explanation=f.explanation,
                    source_reference=f.source_reference,
                    suggested_correction=f.suggested_correction,
                    confidence=f.confidence,
                    requires_human_review=f.requires_human_review,
                    is_applied=f.is_applied,
                    is_dismissed=f.is_dismissed,
                    finding_source=f.finding_source,
                    created_at=f.created_at
                )
                for f in findings_recs
            ]
            latest_review = ReviewRunResponse(
                id=run.id,
                content_id=run.content_id,
                content_version_id=run.content_version_id,
                brand_id=run.brand_id,
                engine_type=run.engine_type,
                ai_status=run.ai_status,
                status=run.status,
                risk_score=run.risk_score,
                summary=run.summary,
                severity_counts=json.loads(run.severity_counts or "{}"),
                category_breakdown=json.loads(run.category_breakdown or "{}"),
                created_at=run.created_at,
                findings=findings_data
            )

    comments = db.query(Comment).filter(Comment.content_id == content_id).order_by(Comment.created_at.asc()).all()
    decisions = db.query(ReviewDecision).filter(ReviewDecision.content_id == content_id).order_by(ReviewDecision.created_at.desc()).all()

    return ContentItemDetailResponse(
        id=item.id,
        brand_id=item.brand_id,
        title=item.title,
        content_type=item.content_type,
        status=item.status,
        current_version_number=item.current_version_number,
        created_by=item.created_by,
        reviewer_id=item.reviewer_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
        versions=[
            ContentVersionResponse(
                id=v.id,
                content_id=v.content_id,
                version_number=v.version_number,
                body=v.body,
                change_summary=v.change_summary,
                created_by=v.created_by,
                created_at=v.created_at
            )
            for v in versions
        ],
        current_version=ContentVersionResponse(
            id=current_ver.id,
            content_id=current_ver.content_id,
            version_number=current_ver.version_number,
            body=current_ver.body,
            change_summary=current_ver.change_summary,
            created_by=current_ver.created_by,
            created_at=current_ver.created_at
        ) if current_ver else None,
        latest_review=latest_review,
        comments=[
            CommentResponse(
                id=c.id,
                content_id=c.content_id,
                content_version_id=c.content_version_id,
                author_name=c.author_name,
                author_role=c.author_role,
                text=c.text,
                created_at=c.created_at
            )
            for c in comments
        ],
        decisions=[
            ReviewDecisionResponse(
                id=d.id,
                content_id=d.content_id,
                content_version_id=d.content_version_id,
                decision=d.decision,
                reviewer_name=d.reviewer_name,
                reviewer_role=d.reviewer_role,
                comments=d.comments,
                created_at=d.created_at
            )
            for d in decisions
        ]
    )

@router.put("/content/{content_id}", response_model=ContentItemDetailResponse)
def update_content_item(content_id: str, payload: ContentItemUpdate, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")

    if payload.title:
        item.title = payload.title
    if payload.content_type:
        item.content_type = payload.content_type

    # Get current version
    current_ver = db.query(ContentVersion).filter(
        ContentVersion.content_id == content_id,
        ContentVersion.version_number == item.current_version_number
    ).first()

    body_changed = payload.body is not None and (current_ver is None or current_ver.body != payload.body)

    if body_changed:
        new_version_num = item.current_version_number + 1
        new_version = ContentVersion(
            content_id=content_id,
            version_number=new_version_num,
            body=payload.body,
            change_summary=payload.change_summary or f"Manual revision {new_version_num}",
            created_by=payload.actor_name
        )
        db.add(new_version)
        item.current_version_number = new_version_num

        # If it was approved, modifying content invalidates approval back to draft
        if item.status == "approved":
            item.status = "draft"

        db.add(AuditEvent(
            brand_id=item.brand_id,
            content_id=content_id,
            event_type="content_edited",
            actor_name=payload.actor_name,
            actor_role=payload.actor_role,
            description=f"Saved revised content (version {new_version_num}).",
            event_metadata=json.dumps({"version": new_version_num, "summary": new_version.change_summary})
        ))

    db.commit()
    db.refresh(item)
    return get_content_item_detail(content_id, db)

@router.delete("/content/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_content_item(content_id: str, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")

    title = item.title
    brand_id = item.brand_id
    db.delete(item)
    db.add(AuditEvent(
        brand_id=brand_id,
        content_id=None,
        event_type="content_deleted",
        actor_name="Administrator",
        actor_role="Admin",
        description=f"Deleted content item '{title}'."
    ))
    db.commit()
    return None
