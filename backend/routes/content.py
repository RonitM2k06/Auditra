import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import policies as policy_engine
from backend.models_r3 import ClaimCheck, ImageAsset, Publication
from backend.auth import authorize, authorize_content, current_user
from backend.models_r3 import User
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
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
):
    actor = authorize(db, user, brand_id, "workspace.view")
    query = db.query(ContentItem).filter(ContentItem.brand_id == brand_id)
    if status:
        query = query.filter(ContentItem.status == status)
    if content_type:
        query = query.filter(ContentItem.content_type == content_type)
    return query.order_by(ContentItem.updated_at.desc()).all()

@router.post("/brands/{brand_id}/content", response_model=ContentItemDetailResponse, status_code=status.HTTP_201_CREATED)
def create_content_item(brand_id: str, payload: ContentItemCreate, user: User = Depends(current_user),
    db: Session = Depends(get_db)):
    actor = authorize(db, user, brand_id, "content.write")
    if not payload.body.strip() or not payload.title.strip():
        raise HTTPException(status_code=422, detail="Title and content can't be empty.")

    item = ContentItem(
        brand_id=brand_id,
        title=payload.title,
        content_type=payload.content_type,
        status="draft",
        current_version_number=1,
        created_by=actor.name,
        created_by_user_id=user.id,
        media_kind="text",
    )
    db.add(item)
    db.flush()

    v1 = ContentVersion(
        content_id=item.id,
        version_number=1,
        body=payload.body,
        change_summary="Initial draft",
        created_by=actor.name
    )
    db.add(v1)
    db.flush()

    db.add(AuditEvent(
        brand_id=brand_id,
        content_id=item.id,
        event_type="draft_created",
        actor_name=actor.name,
        actor_role=actor.role_label,
        description=f"Created content draft '{item.title}' (version 1).",
        event_metadata=json.dumps({"version": 1})
    ))
    db.commit()
    db.refresh(item)

    return get_content_item_detail(item.id, db)

@router.get("/content/{content_id}", response_model=ContentItemDetailResponse)
def read_content_item(content_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_content(db, user, content_id, "workspace.view")
    return get_content_item_detail(content_id, db)


def claim_checks_for_run(db: Session, run_id: str) -> List[dict]:
    rows = db.query(ClaimCheck).filter(ClaimCheck.review_run_id == run_id).order_by(ClaimCheck.start_offset).all()
    out = []
    for c in rows:
        details = json.loads(c.details_json or "{}")
        out.append({
            "id": c.id, "claim_text": c.claim_text, "start_offset": c.start_offset, "end_offset": c.end_offset,
            "status": c.status, "rationale": c.rationale, "retrieval_score": c.retrieval_score, "coverage": c.coverage,
            "passage_id": c.passage_id, "passage_text": c.passage_text, "source": details.pop("source", None),
            "details": details, "content_version_id": c.content_version_id,
        })
    return out


def publication_summary(p) -> dict:
    return {"id": p.id, "version_number": p.version_number, "channel": p.channel, "status": p.status,
            "published_by": p.published_by, "created_at": p.created_at.isoformat() if p.created_at else None,
            "destination": json.loads(p.export_json).get("destination")}


def image_meta(db: Session, version) -> Optional[dict]:
    asset = db.query(ImageAsset).filter(ImageAsset.content_version_id == version.id).first()
    if not asset:
        return None
    return {
        "version_number": version.version_number, "width": asset.width, "height": asset.height,
        "mime_type": asset.mime_type, "byte_size": asset.byte_size, "sha256": asset.sha256,
        "url": f"/api/content/{version.content_id}/versions/{version.version_number}/image",
        "ocr": json.loads(asset.ocr_json or "{}"), "visual": json.loads(asset.visual_json or "{}"),
    }


def run_to_response(db: Session, run) -> ReviewRunResponse:
    findings = db.query(Finding).filter(Finding.review_run_id == run.id).all()
    return ReviewRunResponse(
        id=run.id, content_id=run.content_id, content_version_id=run.content_version_id, brand_id=run.brand_id,
        engine_type=run.engine_type, ai_status=run.ai_status, status=run.status, risk_score=run.risk_score,
        summary=run.summary, severity_counts=json.loads(run.severity_counts or "{}"),
        category_breakdown=json.loads(run.category_breakdown or "{}"), created_at=run.created_at,
        findings=[FindingResponse.model_validate(f) for f in findings],
    )


def get_content_item_detail(content_id: str, db: Session):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")

    versions = db.query(ContentVersion).filter(ContentVersion.content_id == content_id).order_by(ContentVersion.version_number.desc()).all()
    current_ver = next((v for v in versions if v.version_number == item.current_version_number), versions[0] if versions else None)

    latest_review = None
    run = None
    if current_ver:
        # Return the most recent review for the item, even if it was run on an
        # earlier version; clients compare content_version_id to detect staleness.
        run = db.query(ReviewRun).filter(ReviewRun.content_id == content_id).order_by(ReviewRun.created_at.desc()).first()
        if run:
            latest_review = run_to_response(db, run)

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
        media_kind=item.media_kind or "text",
        approved_version_id=item.approved_version_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
        claim_checks=claim_checks_for_run(db, run.id) if run else [],
        approval_status=policy_engine.evaluate(db, item),
        publications=[publication_summary(p) for p in db.query(Publication).filter(Publication.content_id == item.id).order_by(Publication.created_at.desc()).all()],
        image=image_meta(db, current_ver) if current_ver and item.media_kind == "image" else None,
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
                reviewer_user_id=d.reviewer_user_id,
                evidence_confirmed=bool(d.evidence_confirmed),
                comments=d.comments,
                created_at=d.created_at
            )
            for d in decisions
        ]
    )

@router.put("/content/{content_id}", response_model=ContentItemDetailResponse)
def update_content_item(content_id: str, payload: ContentItemUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, actor = authorize_content(db, user, content_id, "content.write")
    if payload.body is not None and item.media_kind == "image":
        raise HTTPException(status_code=409, detail="Text extracted from a creative can't be edited directly. Upload a revised image instead.")
    if payload.body is not None and not payload.body.strip():
        raise HTTPException(status_code=422, detail="Content can't be empty.")

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
            created_by=actor.name
        )
        db.add(new_version)
        item.current_version_number = new_version_num

        # Any new version invalidates an approval: approvals are bound to the version reviewed.
        if item.status == "approved":
            item.status = "draft"
        item.approved_version_id = None

        db.add(AuditEvent(
            brand_id=item.brand_id,
            content_id=content_id,
            event_type="content_edited",
            actor_name=actor.name,
            actor_role=actor.role_label,
            description=f"Saved revised content (version {new_version_num}).",
            event_metadata=json.dumps({"version": new_version_num, "summary": new_version.change_summary})
        ))

    db.commit()
    db.refresh(item)
    return get_content_item_detail(content_id, db)

@router.delete("/content/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_content_item(content_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, actor = authorize_content(db, user, content_id, "content.delete")

    title = item.title
    brand_id = item.brand_id
    db.delete(item)
    db.add(AuditEvent(
        brand_id=brand_id,
        content_id=None,
        event_type="content_deleted",
        actor_name=actor.name,
        actor_role=actor.role_label,
        description=f"Deleted content item '{title}'."
    ))
    db.commit()
    return None
