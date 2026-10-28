import hashlib
import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import evidence
from backend.auth import authorize, current_user
from backend.database import get_db
from backend.models import AuditEvent
from backend.models_r3 import SourceDocument, SourcePassage, User
from backend.review_pipeline import build_index, verify_text

router = APIRouter(prefix="/brands/{brand_id}", tags=["Evidence sources"])

STATUSES = {"approved", "pending", "retired"}


def doc_dict(d: SourceDocument, passages: int) -> dict:
    return {
        "id": d.id, "name": d.name, "source_identifier": d.source_identifier, "file_format": d.file_format,
        "effective_date": d.effective_date, "expiry_date": d.expiry_date, "review_date": d.review_date,
        "approval_status": d.approval_status, "sha256": d.sha256, "char_count": d.char_count,
        "uploaded_by": d.uploaded_by, "created_at": d.created_at.isoformat() if d.created_at else None,
        "passage_count": passages,
    }


def ingest_document(db: Session, brand_id: str, filename: str, data: bytes, *, name: Optional[str], source_identifier: Optional[str],
                    effective_date: Optional[str], expiry_date: Optional[str], review_date: Optional[str],
                    approval_status: str, uploaded_by: str) -> SourceDocument:
    """Validates and stores a source document and its passages. Raises ValueError with a user-facing message."""
    if not data:
        raise ValueError("The file is empty.")
    if len(data) > evidence.MAX_SOURCE_BYTES:
        raise ValueError("Source documents are limited to 2 MB.")
    fmt = evidence.detect_format(filename, data)
    if fmt == "pdf":
        passages = evidence.extract_pdf(data)
    else:
        passages = evidence.split_passages(evidence.decode_text(data), fmt)
    if not passages:
        raise ValueError("No readable text was found in the document.")
    eff, exp, rev = (evidence.parse_iso_date(effective_date), evidence.parse_iso_date(expiry_date),
                     evidence.parse_iso_date(review_date))
    if eff and exp and exp < eff:
        raise ValueError("The expiry date is before the effective date.")
    if approval_status not in STATUSES:
        raise ValueError("Approval status must be approved, pending or retired.")
    safe_name = (name or os.path.basename(filename.replace("\\", "/")) or "Untitled source").strip()[:255]
    doc = SourceDocument(
        brand_id=brand_id, name=safe_name, source_identifier=(source_identifier or None) and source_identifier.strip()[:120],
        file_format=fmt, effective_date=eff, expiry_date=exp, review_date=rev, approval_status=approval_status,
        sha256=hashlib.sha256(data).hexdigest(), char_count=sum(len(p["text"]) for p in passages), uploaded_by=uploaded_by,
    )
    db.add(doc)
    db.flush()
    for i, p in enumerate(passages):
        db.add(SourcePassage(document_id=doc.id, ordinal=i, section=p.get("section"), page=p.get("page"), text=p["text"]))
    return doc


@router.get("/sources")
def list_sources(brand_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize(db, user, brand_id, "workspace.view")
    docs = db.query(SourceDocument).filter(SourceDocument.brand_id == brand_id).order_by(SourceDocument.created_at.desc()).all()
    counts = {d.id: db.query(SourcePassage).filter(SourcePassage.document_id == d.id).count() for d in docs}
    return [doc_dict(d, counts[d.id]) for d in docs]


@router.get("/sources/{doc_id}")
def get_source(brand_id: str, doc_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize(db, user, brand_id, "workspace.view")
    d = db.query(SourceDocument).filter(SourceDocument.id == doc_id, SourceDocument.brand_id == brand_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Source not found")
    return {**doc_dict(d, len(d.passages)),
            "passages": [{"id": p.id, "ordinal": p.ordinal, "section": p.section, "page": p.page, "text": p.text} for p in d.passages]}


@router.post("/sources", status_code=201)
async def upload_source(
    brand_id: str,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None, max_length=255),
    source_identifier: Optional[str] = Form(None, max_length=120),
    effective_date: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    review_date: Optional[str] = Form(None),
    approval_status: str = Form("approved"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    actor = authorize(db, user, brand_id, "rules.manage")
    data = await file.read(evidence.MAX_SOURCE_BYTES + 1)
    try:
        doc = ingest_document(db, brand_id, file.filename or "source.txt", data, name=name, source_identifier=source_identifier,
                              effective_date=effective_date, expiry_date=expiry_date, review_date=review_date,
                              approval_status=approval_status, uploaded_by=actor.name)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    db.add(AuditEvent(brand_id=brand_id, event_type="source_added", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Added evidence source '{doc.name}' ({doc.file_format}, {len(doc.passages)} passages, {doc.approval_status}).",
                      event_metadata=json.dumps({"document_id": doc.id, "sha256": doc.sha256})))
    db.commit()
    return doc_dict(doc, len(doc.passages))


class SourceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    source_identifier: Optional[str] = Field(None, max_length=120)
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    review_date: Optional[str] = None
    approval_status: Optional[str] = None


@router.put("/sources/{doc_id}")
def update_source(brand_id: str, doc_id: str, payload: SourceUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    actor = authorize(db, user, brand_id, "rules.manage")
    d = db.query(SourceDocument).filter(SourceDocument.id == doc_id, SourceDocument.brand_id == brand_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Source not found")
    changes = payload.model_dump(exclude_unset=True)
    try:
        for key in ("effective_date", "expiry_date", "review_date"):
            if key in changes:
                changes[key] = evidence.parse_iso_date(changes[key])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if "approval_status" in changes and changes["approval_status"] not in STATUSES:
        raise HTTPException(status_code=422, detail="Approval status must be approved, pending or retired.")
    for k, v in changes.items():
        setattr(d, k, v)
    db.add(AuditEvent(brand_id=brand_id, event_type="source_updated", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Updated evidence source '{d.name}'.", event_metadata=json.dumps(changes)))
    db.commit()
    return doc_dict(d, len(d.passages))


@router.delete("/sources/{doc_id}", status_code=204)
def delete_source(brand_id: str, doc_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    actor = authorize(db, user, brand_id, "rules.manage")
    d = db.query(SourceDocument).filter(SourceDocument.id == doc_id, SourceDocument.brand_id == brand_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Source not found")
    name = d.name
    db.delete(d)  # past claim checks keep their own copy of the cited passage text
    db.add(AuditEvent(brand_id=brand_id, event_type="source_deleted", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Deleted evidence source '{name}'."))
    db.commit()
    return Response(status_code=204)


class TextIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)


@router.post("/evidence/search")
def search_evidence(brand_id: str, payload: TextIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Retrieval only: the top passages for a query, with BM25 scores. Nothing is stored."""
    authorize(db, user, brand_id, "workspace.view")
    hits = build_index(db, brand_id).search(payload.text, top_k=5)
    return [{"passage_id": p.id, "text": p.text, "score": round(s, 3), "document_id": p.document_id, "document": p.document_name,
             "section": p.section, "page": p.page, "expiry_date": p.expiry_date} for p, s in hits]


@router.post("/evidence/verify")
def verify_claims(brand_id: str, payload: TextIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Extracts candidate claims from the text and classifies each against approved sources. Nothing is stored."""
    authorize(db, user, brand_id, "workspace.view")
    if not payload.text.strip():
        raise HTTPException(status_code=422, detail="Enter some text to check.")
    return verify_text(payload.text, build_index(db, brand_id))
