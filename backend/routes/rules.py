import io
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Brand, BrandRule, ApprovedClaim, AuditEvent
from backend.schemas import (
    BrandRuleCreate, BrandRuleUpdate, BrandRuleResponse,
    ApprovedClaimCreate, ApprovedClaimResponse
)

router = APIRouter(prefix="/brands/{brand_id}", tags=["Brand Rules"])

@router.get("/rules", response_model=List[BrandRuleResponse])
def get_rules(
    brand_id: str,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(BrandRule).filter(BrandRule.brand_id == brand_id)
    if category:
        query = query.filter(BrandRule.category == category)
    if severity:
        query = query.filter(BrandRule.severity == severity)
    if is_active is not None:
        query = query.filter(BrandRule.is_active == is_active)
    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            (BrandRule.name.ilike(search_fmt)) |
            (BrandRule.description.ilike(search_fmt)) |
            (BrandRule.match_pattern.ilike(search_fmt)) |
            (BrandRule.source_reference.ilike(search_fmt))
        )
    return query.order_by(BrandRule.created_at.desc()).all()

@router.post("/rules", response_model=BrandRuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(brand_id: str, payload: BrandRuleCreate, db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    rule = BrandRule(
        brand_id=brand_id,
        name=payload.name,
        category=payload.category,
        description=payload.description,
        rule_text=payload.rule_text,
        match_pattern=payload.match_pattern,
        suggested_replacement=payload.suggested_replacement,
        severity=payload.severity,
        is_active=payload.is_active,
        source_reference=payload.source_reference
    )
    db.add(rule)
    db.flush()

    db.add(AuditEvent(
        brand_id=brand_id,
        event_type="rule_created",
        actor_name="Brand Manager",
        actor_role="Brand Governance Lead",
        description=f"Added brand rule: '{rule.name}' ({rule.category})."
    ))
    db.commit()
    db.refresh(rule)
    return rule

@router.put("/rules/{rule_id}", response_model=BrandRuleResponse)
def update_rule(brand_id: str, rule_id: str, payload: BrandRuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(BrandRule).filter(BrandRule.id == rule_id, BrandRule.brand_id == brand_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)

    db.add(AuditEvent(
        brand_id=brand_id,
        event_type="rule_updated",
        actor_name="Brand Manager",
        actor_role="Brand Governance Lead",
        description=f"Updated rule: '{rule.name}'."
    ))
    db.commit()
    db.refresh(rule)
    return rule

@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(brand_id: str, rule_id: str, db: Session = Depends(get_db)):
    rule = db.query(BrandRule).filter(BrandRule.id == rule_id, BrandRule.brand_id == brand_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule_name = rule.name
    db.delete(rule)
    db.add(AuditEvent(
        brand_id=brand_id,
        event_type="rule_deleted",
        actor_name="Brand Manager",
        actor_role="Brand Governance Lead",
        description=f"Deleted rule: '{rule_name}'."
    ))
    db.commit()
    return None

@router.post("/rules/upload-guidelines")
async def upload_guidelines(
    brand_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Ingests text or markdown guideline document and automatically generates structured rules.
    """
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    content_bytes = await file.read()
    filename = file.filename or "guideline.txt"

    # Enforce safe text decoding
    try:
        text_content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text_content = content_bytes.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="Unable to parse document. Please upload UTF-8 plain text or Markdown.")

    lines = [line.strip() for line in text_content.splitlines() if line.strip()]
    created_rules = []

    # Simple deterministic heuristic parser for bullet points or sections
    for line in lines:
        if line.lower().startswith("do not use:") or line.lower().startswith("prohibited:"):
            phrase = line.split(":", 1)[1].strip()
            if phrase:
                r = BrandRule(
                    brand_id=brand_id,
                    name=f"Prohibited: {phrase[:40]}",
                    category="prohibited_term",
                    description=f"Imported from guideline: {line}",
                    rule_text=f"Do not use '{phrase}'",
                    match_pattern=phrase,
                    severity="high",
                    source_reference=f"Document: {filename}",
                    is_active=True
                )
                db.add(r)
                created_rules.append(r)
        elif "instead of" in line.lower() or "use" in line.lower() and "prefer" in line.lower():
            r = BrandRule(
                brand_id=brand_id,
                name=f"Terminology: {line[:40]}",
                category="preferred_term",
                description=line,
                rule_text=line,
                match_pattern=None,
                severity="medium",
                source_reference=f"Document: {filename}",
                is_active=True
            )
            db.add(r)
            created_rules.append(r)

    # If no structured bullets matched, create a general tone rule representing the guideline
    if not created_rules and len(text_content) > 20:
        r = BrandRule(
            brand_id=brand_id,
            name=f"Guideline Ingestion: {filename[:40]}",
            category="tone_voice",
            description=f"Imported guideline content: {text_content[:200]}...",
            rule_text=text_content[:500],
            severity="medium",
            source_reference=f"Document: {filename}",
            is_active=True
        )
        db.add(r)
        created_rules.append(r)

    db.add(AuditEvent(
        brand_id=brand_id,
        event_type="guideline_uploaded",
        actor_name="Brand Manager",
        actor_role="Brand Governance Lead",
        description=f"Uploaded and parsed guideline file '{filename}', extracting {len(created_rules)} rules."
    ))
    db.commit()

    return {
        "filename": filename,
        "rules_extracted": len(created_rules),
        "message": f"Successfully ingested {len(created_rules)} brand rules from {filename}."
    }

# --- Claims ---
@router.get("/claims", response_model=List[ApprovedClaimResponse])
def get_approved_claims(brand_id: str, db: Session = Depends(get_db)):
    return db.query(ApprovedClaim).filter(ApprovedClaim.brand_id == brand_id).order_by(ApprovedClaim.created_at.desc()).all()

@router.post("/claims", response_model=ApprovedClaimResponse, status_code=status.HTTP_201_CREATED)
def create_approved_claim(brand_id: str, payload: ApprovedClaimCreate, db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    claim = ApprovedClaim(
        brand_id=brand_id,
        claim_statement=payload.claim_statement,
        topic=payload.topic,
        evidence_source=payload.evidence_source,
        verification_date=payload.verification_date,
        is_active=payload.is_active
    )
    db.add(claim)
    db.flush()

    db.add(AuditEvent(
        brand_id=brand_id,
        event_type="claim_created",
        actor_name="Legal & Compliance",
        actor_role="Compliance Officer",
        description=f"Registered verified claim: '{claim.claim_statement[:60]}...' backed by {claim.evidence_source}."
    ))
    db.commit()
    db.refresh(claim)
    return claim

@router.delete("/claims/{claim_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_approved_claim(brand_id: str, claim_id: str, db: Session = Depends(get_db)):
    claim = db.query(ApprovedClaim).filter(ApprovedClaim.id == claim_id, ApprovedClaim.brand_id == brand_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    db.delete(claim)
    db.commit()
    return None
