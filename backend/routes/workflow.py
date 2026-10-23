import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import ContentItem, ContentVersion, ReviewDecision, Comment, AuditEvent
from backend.schemas import (
    ReviewDecisionCreate, ReviewDecisionResponse,
    CommentCreate, CommentResponse, ContentItemDetailResponse
)
from backend.routes.content import get_content_item_detail

router = APIRouter(tags=["Approval Workflow"])

# Allowed state transitions
VALID_TRANSITIONS = {
    "draft": ["in_review"],
    "in_review": ["changes_requested", "approved", "rejected", "draft"],
    "changes_requested": ["in_review", "draft"],
    "approved": ["draft", "in_review"],
    "rejected": ["draft", "in_review"]
}

@router.post("/content/{content_id}/submit", response_model=ContentItemDetailResponse)
def submit_for_review(
    content_id: str,
    actor_name: str = "Creator",
    actor_role: str = "Content Creator",
    db: Session = Depends(get_db)
):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")

    if item.status not in ("draft", "changes_requested", "rejected"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit content from current status '{item.status}'. Only drafts, rejected, or items with requested changes can be submitted."
        )

    previous_status = item.status
    item.status = "in_review"

    db.add(AuditEvent(
        brand_id=item.brand_id,
        content_id=item.id,
        event_type="submitted_for_review",
        actor_name=actor_name,
        actor_role=actor_role,
        description=f"Submitted version {item.current_version_number} to human governance review queue (transitioned from {previous_status} -> in_review).",
        event_metadata=json.dumps({"version": item.current_version_number, "previous_status": previous_status})
    ))

    db.commit()
    db.refresh(item)
    return get_content_item_detail(content_id, db)

@router.post("/content/{content_id}/decision", response_model=ContentItemDetailResponse)
def record_review_decision(
    content_id: str,
    payload: ReviewDecisionCreate,
    db: Session = Depends(get_db)
):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")

    decision = payload.decision.lower().strip()
    if decision not in ("approved", "changes_requested", "rejected"):
        raise HTTPException(
            status_code=400,
            detail="Invalid decision. Must be one of: 'approved', 'changes_requested', 'rejected'."
        )

    # Validate transition from current status
    allowed_next = VALID_TRANSITIONS.get(item.status, [])
    if decision not in allowed_next:
        raise HTTPException(
            status_code=400,
            detail=f"Illegal state transition: Cannot change status from '{item.status}' to '{decision}'. Allowed next states: {allowed_next}."
        )

    # Get current version
    current_ver = db.query(ContentVersion).filter(
        ContentVersion.content_id == content_id,
        ContentVersion.version_number == item.current_version_number
    ).first()
    if not current_ver:
        raise HTTPException(status_code=400, detail="Cannot record decision: current version not found")

    previous_status = item.status
    item.status = decision
    item.reviewer_id = f"{payload.reviewer_name} ({payload.reviewer_role})"

    # Record decision entity
    dec_record = ReviewDecision(
        content_id=content_id,
        content_version_id=current_ver.id,
        decision=decision,
        reviewer_name=payload.reviewer_name,
        reviewer_role=payload.reviewer_role,
        comments=payload.comments
    )
    db.add(dec_record)

    # If reviewer left a comment, also add to comments thread
    if payload.comments and payload.comments.strip():
        db.add(Comment(
            content_id=content_id,
            content_version_id=current_ver.id,
            author_name=payload.reviewer_name,
            author_role=payload.reviewer_role,
            text=f"[{decision.replace('_', ' ').upper()}] {payload.comments.strip()}"
        ))

    event_type_map = {
        "approved": "content_approved",
        "changes_requested": "changes_requested",
        "rejected": "content_rejected"
    }

    db.add(AuditEvent(
        brand_id=item.brand_id,
        content_id=content_id,
        event_type=event_type_map.get(decision, "decision_recorded"),
        actor_name=payload.reviewer_name,
        actor_role=payload.reviewer_role,
        description=f"Reviewer decision: {decision.replace('_', ' ').upper()} on version {item.current_version_number}." + (f" Note: {payload.comments}" if payload.comments else ""),
        event_metadata=json.dumps({
            "version": item.current_version_number,
            "decision": decision,
            "previous_status": previous_status,
            "comments": payload.comments
        })
    ))

    db.commit()
    db.refresh(item)
    return get_content_item_detail(content_id, db)

@router.post("/content/{content_id}/comments", response_model=CommentResponse)
def add_comment(
    content_id: str,
    payload: CommentCreate,
    db: Session = Depends(get_db)
):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")

    current_ver = db.query(ContentVersion).filter(
        ContentVersion.content_id == content_id,
        ContentVersion.version_number == item.current_version_number
    ).first()

    comment = Comment(
        content_id=content_id,
        content_version_id=current_ver.id if current_ver else None,
        author_name=payload.author_name,
        author_role=payload.author_role,
        text=payload.text
    )
    db.add(comment)
    db.flush()

    db.add(AuditEvent(
        brand_id=item.brand_id,
        content_id=content_id,
        event_type="comment_added",
        actor_name=payload.author_name,
        actor_role=payload.author_role,
        description=f"Added comment on version {item.current_version_number}: '{payload.text[:80]}...'",
        event_metadata=json.dumps({"version": item.current_version_number})
    ))

    db.commit()
    db.refresh(comment)
    return comment
