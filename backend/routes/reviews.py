import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth import authorize_content, authorize_finding, current_user
from backend.database import get_db
from backend.models import AuditEvent, ContentVersion, Finding, ReviewRun
from backend.models_r3 import User
from backend.review_pipeline import perform_review
from backend.routes.content import get_content_item_detail, run_to_response
from backend.schemas import ContentItemDetailResponse, FindingApplyRequest, FindingResponse, ReviewRunRequest, ReviewRunResponse

router = APIRouter(tags=["Review & Findings"])


@router.post("/content/{content_id}/review", response_model=ReviewRunResponse)
async def run_content_review(content_id: str, payload: Optional[ReviewRunRequest] = None,
                             user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, actor = authorize_content(db, user, content_id, "content.analyse")
    version = db.query(ContentVersion).filter(
        ContentVersion.content_id == content_id, ContentVersion.version_number == item.current_version_number
    ).first()
    if not version:
        raise HTTPException(status_code=409, detail="No content version available to review")
    if not version.body.strip() and item.media_kind != "image":
        raise HTTPException(status_code=422, detail="There is no text to analyse.")
    run = await perform_review(db, item, version, actor, force_engine=payload.force_engine if payload else None)
    return run_to_response(db, run)


@router.post("/findings/{finding_id}/apply", response_model=ContentItemDetailResponse)
def apply_finding_correction(finding_id: str, payload: FindingApplyRequest,
                             user: User = Depends(current_user), db: Session = Depends(get_db)):
    finding, content_item, actor = authorize_finding(db, user, finding_id, "content.write")
    if content_item.media_kind == "image":
        raise HTTPException(status_code=409, detail="Text in an image can't be corrected in place. Edit the creative and upload a revised version.")
    if finding.is_applied:
        raise HTTPException(status_code=409, detail="This correction has already been applied")
    if finding.is_dismissed:
        raise HTTPException(status_code=409, detail="This finding was dismissed.")

    replacement = payload.custom_replacement if payload.custom_replacement is not None else finding.suggested_correction
    if replacement is None:
        raise HTTPException(status_code=422, detail="No suggested correction available for this finding")
    if len(replacement) > 2000:
        raise HTTPException(status_code=422, detail="Replacement text is too long.")

    current_ver = db.query(ContentVersion).filter(
        ContentVersion.content_id == content_item.id,
        ContentVersion.version_number == content_item.current_version_number
    ).first()
    body = current_ver.body

    if finding.category == "required_phrase":
        if replacement.strip().lower() in body.lower():
            raise HTTPException(status_code=409, detail="The current version already contains this disclosure.")
        updated_body = body.rstrip() + "\n\n" + replacement.strip()
    else:
        target = finding.matched_text
        offset = payload.occurrence_offset
        if offset is not None:
            if offset < 0 or body[offset:offset + len(target)] != target:
                raise HTTPException(status_code=409, detail="The selected text no longer matches the current version. Re-run the review and try again.")
            updated_body = body[:offset] + replacement + body[offset + len(target):]
        else:
            occurrences = body.count(target)
            if occurrences == 0:
                raise HTTPException(status_code=409, detail=f"'{target}' was not found in the current version. It may have already been edited.")
            if occurrences > 1:
                raise HTTPException(status_code=409, detail=f"'{target}' appears {occurrences} times in the current version. Choose which occurrence to replace.")
            updated_body = body.replace(target, replacement, 1)

    new_version_num = content_item.current_version_number + 1
    db.add(ContentVersion(
        content_id=content_item.id, version_number=new_version_num, body=updated_body,
        change_summary=f"Applied correction for '{finding.category}': '{finding.matched_text[:60]}' -> '{replacement[:60]}'",
        created_by=actor.name,
    ))
    content_item.current_version_number = new_version_num
    finding.is_applied = True
    if content_item.status == "approved":
        content_item.status = "draft"
    content_item.approved_version_id = None

    db.add(AuditEvent(
        brand_id=content_item.brand_id, content_id=content_item.id, event_type="correction_applied",
        actor_name=actor.name, actor_role=actor.role_label,
        description=f"Applied targeted correction: replaced '{finding.matched_text[:80]}' with '{replacement[:80]}'. Created version {new_version_num}.",
        event_metadata=json.dumps({"finding_id": finding.id, "rule_id": finding.rule_id, "from": finding.matched_text,
                                   "to": replacement, "version": new_version_num}),
    ))
    db.commit()
    return get_content_item_detail(content_item.id, db)


@router.post("/findings/{finding_id}/dismiss", response_model=FindingResponse)
def dismiss_finding(finding_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    finding, content_item, actor = authorize_finding(db, user, finding_id, "finding.dismiss")
    if finding.is_dismissed:
        return FindingResponse.model_validate(finding)
    finding.is_dismissed = True
    db.add(AuditEvent(
        brand_id=content_item.brand_id, content_id=content_item.id, event_type="finding_dismissed",
        actor_name=actor.name, actor_role=actor.role_label,
        description=f"Dismissed finding: '{finding.matched_text[:80]}' ({finding.explanation[:60]}).",
        event_metadata=json.dumps({"finding_id": finding.id, "category": finding.category, "severity": finding.severity}),
    ))
    db.commit()
    db.refresh(finding)
    return FindingResponse.model_validate(finding)
