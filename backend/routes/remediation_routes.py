import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import remediation
from backend import policies as policy_engine
from backend.auth import authorize_content, current_user
from backend.database import get_db
from backend.models import ApprovedClaim, AuditEvent, Brand, BrandRule, ContentVersion, Finding
from backend.models_r3 import ClaimCheck, User
from backend.review_pipeline import build_index
from backend.routes.content import get_content_item_detail
from backend.schemas import ContentItemDetailResponse

router = APIRouter(tags=["Remediation"])


class FixIn(BaseModel):
    id: str
    replacement: Optional[str] = Field(None, max_length=2000)


class RemediationIn(BaseModel):
    version_number: int = Field(..., ge=1)
    fixes: List[FixIn] = Field(..., min_length=1, max_length=30)
    confirm_factual: bool = False
    note: Optional[str] = Field(None, max_length=500)


def _context(db: Session, item):
    version = db.query(ContentVersion).filter(ContentVersion.content_id == item.id,
                                              ContentVersion.version_number == item.current_version_number).first()
    run = policy_engine.latest_run_for_version(db, version.id) if version else None
    if not run:
        return version, None, []
    findings = db.query(Finding).filter(Finding.review_run_id == run.id).all()
    checks = db.query(ClaimCheck).filter(ClaimCheck.review_run_id == run.id).all()
    return version, run, remediation.suggestions(item, version, findings, checks)


@router.get("/content/{content_id}/remediation")
def list_suggestions(content_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, _ = authorize_content(db, user, content_id, "workspace.view")
    version, run, sugg = _context(db, item)
    return {"version_number": item.current_version_number, "analysed": run is not None, "media_kind": item.media_kind,
            "suggestions": sugg,
            "notice": None if run else "Analyse the current version first; suggestions come from its findings and claim checks."}


def _resolve(db: Session, item, payload: RemediationIn):
    if item.media_kind == "image":
        raise HTTPException(status_code=409, detail="Creatives are fixed by uploading a revised image, not by editing extracted text.")
    if payload.version_number != item.current_version_number:
        raise HTTPException(status_code=409, detail=f"These fixes were prepared for v{payload.version_number}, but the current version is v{item.current_version_number}. Reload.")
    version, run, sugg = _context(db, item)
    if not run:
        raise HTTPException(status_code=409, detail="Analyse the current version before applying fixes.")
    by_id = {s["id"]: s for s in sugg}
    chosen = []
    for f in payload.fixes:
        s = by_id.get(f.id)
        if not s:
            raise HTTPException(status_code=404, detail="A selected suggestion no longer exists. Re-run the analysis.")
        if s["kind"] in ("evidence_needed", "creative"):
            raise HTTPException(status_code=422, detail=f"\"{s['original'][:40]}\" needs evidence or a revised creative, not a text replacement.")
        replacement = f.replacement if f.replacement is not None else s["replacement"]
        if replacement is None or (s["kind"] != "add_disclosure" and not replacement.strip() and replacement != ""):
            raise HTTPException(status_code=422, detail=f"Write a replacement for \"{s['original'][:40]}\".")
        if s["kind"] == "add_disclosure" and f.replacement is not None and f.replacement.strip() != (s["replacement"] or "").strip():
            raise HTTPException(status_code=422, detail="Required disclosures must be added exactly as configured in the rule.")
        chosen.append({**s, "replacement": replacement})
    try:
        new_body, applied = remediation.apply_fixes(version.body, chosen)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not new_body.strip():
        raise HTTPException(status_code=422, detail="These fixes would leave the content empty.")
    return version, new_body, applied


@router.post("/content/{content_id}/remediation/preview")
def preview_fixes(content_id: str, payload: RemediationIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Shows the result of the selected fixes and re-runs rule and claim checks in memory. Nothing is saved."""
    item, _ = authorize_content(db, user, content_id, "content.write")
    version, new_body, _ = _resolve(db, item, payload)
    rules = db.query(BrandRule).filter(BrandRule.brand_id == item.brand_id, BrandRule.is_active == True).all()  # noqa: E712
    claims = db.query(ApprovedClaim).filter(ApprovedClaim.brand_id == item.brand_id, ApprovedClaim.is_active == True).all()  # noqa: E712
    brand = db.query(Brand).filter(Brand.id == item.brand_id).first()
    result = remediation.preview(version.body, new_body, rules, claims, build_index(db, item.brand_id), brand.name)
    result["note"] = "Preview only. Nothing has been saved, and applying creates a new version that must be re-analysed and approved."
    return result


@router.post("/content/{content_id}/remediation/apply", response_model=ContentItemDetailResponse)
def apply_remediation(content_id: str, payload: RemediationIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, actor = authorize_content(db, user, content_id, "content.write")
    version, new_body, applied = _resolve(db, item, payload)
    factual = remediation.factual_change_labels(version.body, new_body)
    if factual and not payload.confirm_factual:
        raise HTTPException(status_code=422, detail=f"These fixes change factual figures or dates ({', '.join(factual)}). Confirm the change against the cited source to apply.")
    n = item.current_version_number + 1
    db.add(ContentVersion(content_id=item.id, version_number=n, body=new_body,
                          change_summary=f"Remediation: {len(applied)} fix(es)" + (f" — {payload.note}" if payload.note else ""),
                          created_by=actor.name))
    for f in applied:
        if f.get("finding_id"):
            rec = db.query(Finding).filter(Finding.id == f["finding_id"]).first()
            if rec:
                rec.is_applied = True
    previous = item.status
    item.current_version_number = n
    if item.status in ("approved", "in_review"):
        item.status = "draft"  # a fixed version must be re-analysed, resubmitted and approved
    item.approved_version_id = None
    db.add(AuditEvent(
        brand_id=item.brand_id, content_id=item.id, event_type="remediation_applied", actor_name=actor.name, actor_role=actor.role_label,
        description=f"Applied {len(applied)} remediation fix(es), creating version {n}."
                    + (f" Factual changes confirmed: {', '.join(factual)}." if factual else "")
                    + (" Approval reset; the new version needs analysis and approval." if previous in ("approved", "in_review") else ""),
        event_metadata=json.dumps({"version": n, "from_version": version.version_number, "previous_status": previous,
                                   "factual_changes": factual,
                                   "fixes": [{"kind": f["kind"], "category": f["category"], "from": f["original"], "to": f["replacement"],
                                              "evidence": (f.get("evidence") or {}).get("source")} for f in applied]}),
    ))
    db.commit()
    return get_content_item_detail(item.id, db)
