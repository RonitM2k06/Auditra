import hashlib
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import policies as policy_engine
from backend.auth import Actor, authorize, authorize_content, current_user
from backend.database import get_db
from backend.models import AuditEvent, Brand, Comment, ContentItem, ContentVersion, Finding, ReviewDecision
from backend.models_r3 import ApprovalPolicy, Publication, User
from backend.routes.content import get_content_item_detail
from backend.schemas import CommentCreate, CommentResponse, ContentItemDetailResponse, ReviewDecisionCreate

router = APIRouter(tags=["Approval Workflow"])

SANDBOX_CHANNEL = "sandbox"


def _current_version(db: Session, item: ContentItem) -> Optional[ContentVersion]:
    return db.query(ContentVersion).filter(
        ContentVersion.content_id == item.id, ContentVersion.version_number == item.current_version_number
    ).first()


def _lock_item(db: Session, content_id: str) -> ContentItem:
    # Row lock on Postgres so concurrent decisions/publishes serialise; SQLite serialises writes itself.
    return db.query(ContentItem).filter(ContentItem.id == content_id).with_for_update().first()


def _audit(db: Session, item: ContentItem, actor: Actor, event_type: str, description: str, **meta) -> None:
    db.add(AuditEvent(
        brand_id=item.brand_id, content_id=item.id, event_type=event_type,
        actor_name=actor.name, actor_role=actor.role_label, description=description,
        event_metadata=json.dumps(meta),
    ))


@router.post("/content/{content_id}/submit", response_model=ContentItemDetailResponse)
def submit_for_review(content_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, actor = authorize_content(db, user, content_id, "content.write")
    item = _lock_item(db, content_id)
    if item.status not in ("draft", "changes_requested", "rejected"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot submit content from status '{item.status}'. Only drafts, rejected items or items with requested changes can be submitted."
        )
    version = _current_version(db, item)
    if not version or not version.body.strip():
        raise HTTPException(status_code=422, detail="There is no content to submit.")

    previous_status = item.status
    item.status = "in_review"
    _audit(db, item, actor, "submitted_for_review",
           f"Submitted version {item.current_version_number} for review ({previous_status} -> in_review).",
           version=item.current_version_number, previous_status=previous_status)
    db.commit()
    return get_content_item_detail(content_id, db)


@router.post("/content/{content_id}/decision", response_model=ContentItemDetailResponse)
def record_review_decision(content_id: str, payload: ReviewDecisionCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, actor = authorize_content(db, user, content_id, "decision.record")
    item = _lock_item(db, content_id)

    decision = payload.decision.lower().strip()
    if decision not in ("approved", "changes_requested", "rejected"):
        raise HTTPException(status_code=422, detail="Decision must be one of: approved, changes_requested, rejected.")
    if item.status != "in_review":
        raise HTTPException(status_code=409, detail=f"Decisions can only be recorded while content is in review (current status: '{item.status}').")

    version = _current_version(db, item)
    if not version:
        raise HTTPException(status_code=409, detail="Cannot record a decision: the current version is missing.")
    if payload.version_number is None and decision == "approved":
        raise HTTPException(status_code=422, detail="Approvals must state the version number that was reviewed.")
    if payload.version_number is not None and payload.version_number != version.version_number:
        raise HTTPException(
            status_code=409,
            detail=f"You reviewed version {payload.version_number}, but the current version is {version.version_number}. Reload and review the latest version."
        )
    note = (payload.comments or "").strip()
    if decision in ("changes_requested", "rejected") and not note:
        raise HTTPException(status_code=422, detail="Add a note explaining what needs to change.")

    if decision == "approved":
        if item.created_by_user_id and item.created_by_user_id == user.id:
            _audit(db, item, actor, "permission_denied", "Blocked self-approval: the author of content cannot approve it.",
                   version=version.version_number)
            db.commit()
            raise HTTPException(status_code=403, detail="You created this content, so you can't approve it. Another reviewer must approve it.")
        if policy_engine.latest_run_for_version(db, version.id) is None:
            raise HTTPException(status_code=409, detail=f"Version {version.version_number} has not been analysed. Run the analysis before approving.")
        duplicate = db.query(ReviewDecision).filter(
            ReviewDecision.content_version_id == version.id, ReviewDecision.decision == "approved",
            ReviewDecision.reviewer_user_id == user.id,
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail=f"You have already approved version {version.version_number}.")

    db.add(ReviewDecision(
        content_id=content_id, content_version_id=version.id, decision=decision,
        reviewer_name=actor.name, reviewer_role=actor.role_label, reviewer_user_id=user.id,
        evidence_confirmed=bool(payload.evidence_confirmed) if decision == "approved" else False,
        comments=note or None,
    ))
    if note:
        db.add(Comment(content_id=content_id, content_version_id=version.id, author_name=actor.name,
                       author_role=actor.role_label, text=f"[{decision.replace('_', ' ').upper()}] {note}"))
    db.flush()

    previous_status = item.status
    if decision == "approved":
        status = policy_engine.evaluate(db, item)
        if status["satisfied"]:
            item.status = "approved"
            item.approved_version_id = version.id
            item.reviewer_id = actor.name
            _audit(db, item, actor, "content_approved",
                   f"Approved version {version.version_number}. All approval requirements are met.",
                   version=version.version_number, previous_status=previous_status,
                   evidence_confirmed=bool(payload.evidence_confirmed), comments=note or None)
        else:
            _audit(db, item, actor, "approval_recorded",
                   f"Recorded an approval on version {version.version_number}; still waiting on: " + " | ".join(status["blocking"]),
                   version=version.version_number, blocking=status["blocking"],
                   evidence_confirmed=bool(payload.evidence_confirmed))
    else:
        item.status = decision
        item.approved_version_id = None
        item.reviewer_id = actor.name
        _audit(db, item, actor, "changes_requested" if decision == "changes_requested" else "content_rejected",
               f"{decision.replace('_', ' ').capitalize()} on version {version.version_number}. Note: {note}",
               version=version.version_number, decision=decision, previous_status=previous_status, comments=note)
    db.commit()
    return get_content_item_detail(content_id, db)


@router.post("/content/{content_id}/comments", response_model=CommentResponse)
def add_comment(content_id: str, payload: CommentCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, actor = authorize_content(db, user, content_id, "comment.write")
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Comment can't be empty.")
    version = _current_version(db, item)
    comment = Comment(content_id=content_id, content_version_id=version.id if version else None,
                      author_name=actor.name, author_role=actor.role_label, text=text)
    db.add(comment)
    db.flush()
    _audit(db, item, actor, "comment_added", f"Commented on version {item.current_version_number}: '{text[:80]}'",
           version=item.current_version_number)
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/content/{content_id}/approval-status")
def approval_status(content_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, _ = authorize_content(db, user, content_id, "workspace.view")
    return policy_engine.evaluate(db, item)


# --- Publishing (local sandbox connector) ---

class PublishRequest(BaseModel):
    version_number: int = Field(..., ge=1)
    channel: str = SANDBOX_CHANNEL


def publication_dict(p: Publication, duplicate: bool = False) -> dict:
    return {
        "id": p.id, "content_id": p.content_id, "content_version_id": p.content_version_id,
        "version_number": p.version_number, "channel": p.channel, "status": p.status,
        "body_sha256": p.body_sha256, "published_by": p.published_by,
        "destination": json.loads(p.export_json).get("destination"),
        "created_at": p.created_at.isoformat() if p.created_at else None, "duplicate": duplicate,
    }


@router.post("/content/{content_id}/publish")
def publish(content_id: str, payload: PublishRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Publishes an approved version to the local sandbox connector (a stored export record, not a live channel)."""
    item, actor = authorize_content(db, user, content_id, "publish")
    if payload.channel != SANDBOX_CHANNEL:
        raise HTTPException(status_code=422, detail="Only the local 'sandbox' connector is available.")
    item = _lock_item(db, content_id)
    version = _current_version(db, item)

    def refuse(reason: str, code: int = 409):
        _audit(db, item, actor, "publish_refused", f"Publishing refused: {reason}",
               requested_version=payload.version_number, channel=payload.channel, reason=reason)
        db.commit()
        raise HTTPException(status_code=code, detail=reason)

    existing = None
    if version and payload.version_number == version.version_number:
        existing = db.query(Publication).filter(
            Publication.content_version_id == version.id, Publication.channel == payload.channel
        ).first()
    if existing:
        _audit(db, item, actor, "publish_duplicate",
               f"Repeated publish request for version {existing.version_number}; returned the existing sandbox record.",
               publication_id=existing.id)
        db.commit()
        return publication_dict(existing, duplicate=True)

    if item.status != "approved":
        refuse(f"Only approved content can be published (current status: {item.status.replace('_', ' ')}).")
    if not version or payload.version_number != version.version_number:
        refuse(f"Version {payload.version_number} is not the current version ({item.current_version_number}). Publish the approved current version.")
    if item.approved_version_id != version.id:
        refuse(f"Version {version.version_number} has not been approved.")
    status = policy_engine.evaluate(db, item)
    if not status["satisfied"]:
        refuse("Approval requirements are no longer met: " + " | ".join(status["blocking"]))

    brand = db.query(Brand).filter(Brand.id == item.brand_id).first()
    sha = hashlib.sha256(version.body.encode("utf-8")).hexdigest()
    approvals = [a for a in status["approvals"]]
    export = {
        "connector": "auditra-local-sandbox",
        "notice": "Sandbox export. Nothing was sent to a third-party channel.",
        "destination": f"sandbox://{brand.slug}/{item.id}/v{version.version_number}",
        "content": {"title": item.title, "content_type": item.content_type, "media_kind": item.media_kind,
                    "version_number": version.version_number, "body": version.body, "body_sha256": sha},
        "approvals": approvals,
        "published_by": actor.name,
    }
    pub = Publication(
        brand_id=item.brand_id, content_id=item.id, content_version_id=version.id,
        version_number=version.version_number, channel=payload.channel, status="published",
        body_sha256=sha, export_json=json.dumps(export), published_by=actor.name,
    )
    db.add(pub)
    try:
        db.flush()
    except IntegrityError:
        # A concurrent request published the same version first.
        db.rollback()
        existing = db.query(Publication).filter(
            Publication.content_version_id == version.id, Publication.channel == payload.channel
        ).first()
        return publication_dict(existing, duplicate=True)
    _audit(db, item, actor, "content_published",
           f"Published version {version.version_number} to the local sandbox ({export['destination']}).",
           version=version.version_number, publication_id=pub.id, body_sha256=sha)
    db.commit()
    db.refresh(pub)
    return publication_dict(pub)


@router.get("/content/{content_id}/publications")
def list_publications(content_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_content(db, user, content_id, "workspace.view")
    pubs = db.query(Publication).filter(Publication.content_id == content_id).order_by(Publication.created_at.desc()).all()
    return [publication_dict(p) for p in pubs]


@router.get("/publications/{publication_id}/export")
def download_export(publication_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    pub = db.query(Publication).filter(Publication.id == publication_id).first()
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    authorize_content(db, user, pub.content_id, "workspace.view")
    return Response(
        content=json.dumps(json.loads(pub.export_json), indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="auditra-sandbox-{pub.id[:8]}-v{pub.version_number}.json"'},
    )


# --- Approval policies (admin) ---

class PolicyIn(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    condition_type: str
    condition_value: str = Field(..., max_length=60)
    required_role: Optional[str] = None
    min_approvals: int = Field(1, ge=1, le=5)
    require_evidence_confirmation: bool = False
    is_active: bool = True


def _validate_policy(p: PolicyIn) -> None:
    if p.condition_type not in policy_engine.CONDITION_TYPES:
        raise HTTPException(status_code=422, detail="condition_type must be severity_at_least, claim_status or finding_category.")
    if p.condition_type == "severity_at_least" and p.condition_value not in policy_engine.SEVERITY_RANK:
        raise HTTPException(status_code=422, detail="Severity must be low, medium, high or critical.")
    if p.condition_type == "claim_status" and p.condition_value not in policy_engine.CLAIM_STATES:
        raise HTTPException(status_code=422, detail="Unknown claim status.")
    if p.required_role not in (None, "reviewer", "admin"):
        raise HTTPException(status_code=422, detail="required_role must be reviewer, admin or empty.")


def policy_dict(p: ApprovalPolicy) -> dict:
    return {
        "id": p.id, "name": p.name, "condition_type": p.condition_type, "condition_value": p.condition_value,
        "description": f"When content has {policy_engine.describe_condition(p.condition_type, p.condition_value)}",
        "required_role": p.required_role, "min_approvals": p.min_approvals,
        "require_evidence_confirmation": p.require_evidence_confirmation, "is_active": p.is_active,
    }


@router.get("/brands/{brand_id}/policies")
def list_policies(brand_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize(db, user, brand_id, "workspace.view")
    return [policy_dict(p) for p in db.query(ApprovalPolicy).filter(ApprovalPolicy.brand_id == brand_id).order_by(ApprovalPolicy.created_at).all()]


@router.post("/brands/{brand_id}/policies", status_code=201)
def create_policy(brand_id: str, payload: PolicyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    actor = authorize(db, user, brand_id, "rules.manage")
    _validate_policy(payload)
    p = ApprovalPolicy(brand_id=brand_id, **payload.model_dump())
    db.add(p)
    db.add(AuditEvent(brand_id=brand_id, event_type="policy_created", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Added approval policy '{p.name}'.", event_metadata=json.dumps(payload.model_dump())))
    db.commit()
    db.refresh(p)
    return policy_dict(p)


@router.put("/brands/{brand_id}/policies/{policy_id}")
def update_policy(brand_id: str, policy_id: str, payload: PolicyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    actor = authorize(db, user, brand_id, "rules.manage")
    _validate_policy(payload)
    p = db.query(ApprovalPolicy).filter(ApprovalPolicy.id == policy_id, ApprovalPolicy.brand_id == brand_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Policy not found")
    for k, v in payload.model_dump().items():
        setattr(p, k, v)
    db.add(AuditEvent(brand_id=brand_id, event_type="policy_updated", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Updated approval policy '{p.name}'.", event_metadata=json.dumps(payload.model_dump())))
    db.commit()
    return policy_dict(p)


@router.delete("/brands/{brand_id}/policies/{policy_id}", status_code=204)
def delete_policy(brand_id: str, policy_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    actor = authorize(db, user, brand_id, "rules.manage")
    p = db.query(ApprovalPolicy).filter(ApprovalPolicy.id == policy_id, ApprovalPolicy.brand_id == brand_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Policy not found")
    name = p.name
    db.delete(p)
    db.add(AuditEvent(brand_id=brand_id, event_type="policy_deleted", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Deleted approval policy '{name}'."))
    db.commit()
    return Response(status_code=204)
