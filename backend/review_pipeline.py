"""One review run: rule engine, optional AI step, OCR region mapping, visual checks and claim verification."""
import io
import json
import re
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from PIL import Image
from sqlalchemy.orm import Session

from backend import evidence, vision
from backend.ai_service import AIService
from backend.auth import Actor
from backend.models import ApprovedClaim, AuditEvent, Brand, BrandRule, ContentItem, ContentVersion, Finding, ReviewRun
from backend.models_r3 import (
    ApprovalPolicy, BrandLogo, ClaimCheck, ImageAsset, RuleSnapshot, SourceDocument, SourcePassage,
)
from backend.rule_engine import ComplianceRuleEngine

RULE_FIELDS = ("id", "name", "category", "description", "rule_text", "match_pattern",
               "suggested_replacement", "severity", "is_active", "source_reference")


def rule_to_dict(r) -> Dict[str, Any]:
    return {k: getattr(r, k) for k in RULE_FIELDS}


def brand_palette(brand: Brand) -> List[str]:
    palette = [c for c in (brand.primary_color, brand.secondary_color) if c]
    try:
        palette += [c for c in json.loads(brand.palette_json or "[]") if isinstance(c, str)]
    except ValueError:
        pass
    seen, out = set(), []
    for c in palette:
        if c.upper() not in seen:
            seen.add(c.upper())
            out.append(c.upper())
    return out


def load_logo(db: Session, brand_id: str) -> Optional[Image.Image]:
    rec = db.query(BrandLogo).filter(BrandLogo.brand_id == brand_id).first()
    return Image.open(io.BytesIO(rec.data)).convert("RGB") if rec else None


def build_index(db: Session, brand_id: str) -> evidence.BM25Index:
    rows = (
        db.query(SourcePassage, SourceDocument)
        .join(SourceDocument, SourceDocument.id == SourcePassage.document_id)
        .filter(SourceDocument.brand_id == brand_id, SourceDocument.approval_status == "approved")
        .all()
    )
    return evidence.BM25Index([
        evidence.IndexedPassage(
            id=p.id, text=p.text, section=p.section, page=p.page, document_id=d.id, document_name=d.name,
            source_identifier=d.source_identifier, effective_date=d.effective_date, expiry_date=d.expiry_date,
            review_date=d.review_date,
        )
        for p, d in rows
    ])


def verify_text(text: str, index: evidence.BM25Index, today: Optional[date] = None) -> List[Dict[str, Any]]:
    out = []
    for claim in evidence.extract_claims(text):
        v = evidence.verify_claim(claim.text, index, today=today)
        p = v.passage
        out.append({
            "claim_text": claim.text, "start_offset": claim.start, "end_offset": claim.end, "status": v.status,
            "rationale": v.rationale, "retrieval_score": round(v.score, 3), "coverage": round(v.coverage, 3),
            "passage_id": p.id if p else None, "source_document_id": p.document_id if p else None,
            "passage_text": p.text if p else None, "details": v.details,
            "source": None if not p else {
                "document_id": p.document_id, "name": p.document_name, "source_identifier": p.source_identifier,
                "section": p.section, "page": p.page, "effective_date": p.effective_date,
                "expiry_date": p.expiry_date, "review_date": p.review_date,
            },
        })
    return out


def compute_findings(text: str, rules: Sequence[Any], claims: Sequence[Any], brand_name: str = "") -> List[Dict[str, Any]]:
    """Pure: deterministic findings for a text and rulebook (used by reviews and simulations)."""
    allowed = set(re.findall(r"[A-Za-z]{4,}", brand_name or ""))  # a brand's own name in capitals (e.g. a logo) is not shouting
    return [f.to_dict() for f in ComplianceRuleEngine(list(rules), list(claims), allowed).analyze(text)]


def _image_for_version(db: Session, version_id: str) -> Optional[ImageAsset]:
    return db.query(ImageAsset).filter(ImageAsset.content_version_id == version_id).first()


async def perform_review(db: Session, item: ContentItem, version: ContentVersion, actor: Actor,
                         force_engine: Optional[str] = None) -> ReviewRun:
    brand = db.query(Brand).filter(Brand.id == item.brand_id).first()
    rules = db.query(BrandRule).filter(BrandRule.brand_id == item.brand_id, BrandRule.is_active == True).all()  # noqa: E712
    claims = db.query(ApprovedClaim).filter(ApprovedClaim.brand_id == item.brand_id, ApprovedClaim.is_active == True).all()  # noqa: E712
    body = version.body or ""
    asset = _image_for_version(db, version.id) if item.media_kind == "image" else None
    ocr = json.loads(asset.ocr_json) if asset else None

    combined = compute_findings(body, rules, claims, brand.name if brand else "")
    if asset:
        for f in combined:
            f["finding_source"] = "ocr_rule"
            if f["category"] != "required_phrase":
                f["region_json"] = json.dumps(vision.regions_for_span(ocr, f["start_offset"], f["end_offset"]))

    ai_status, engine_type = "fallback_rule_based", "deterministic"
    if not asset and force_engine != "deterministic" and AIService.is_configured():
        ai_res = await AIService.analyze_content(text=body, brand_name=brand.name if brand else "Brand", rules=rules, approved_claims=claims)
        ai_status = ai_res.get("ai_status", "fallback_rule_based")
        if ai_status == "configured":
            engine_type = "hybrid_ai"
            spans = {(f["start_offset"], f["end_offset"], f["matched_text"]) for f in combined}
            for af in ai_res.get("findings", []):
                if (af["start_offset"], af["end_offset"], af["matched_text"]) not in spans:
                    combined.append(af)

    visual = None
    if asset:
        engine_type = "multimodal"
        ai_status = "skipped"
        img = Image.open(io.BytesIO(asset.data)).convert("RGB")
        visual = vision.analyse_visuals(img, ocr, brand_palette(brand), load_logo(db, item.brand_id))
        asset.visual_json = json.dumps(visual)
        combined.extend(vision.visual_findings(visual, ocr))

    # Claim verification against approved sources.
    # OCR line breaks are layout, not sentence ends; replacing them keeps character offsets intact.
    checks = verify_text(body.replace("\n", " ") if asset else body, build_index(db, item.brand_id))
    for c in checks:
        if c["status"] in ("contradicted", "stale"):
            src = c["source"] or {}
            region = json.dumps(vision.regions_for_span(ocr, c["start_offset"], c["end_offset"])) if ocr else None
            combined.append({
                "rule_id": None, "category": f"claim_{c['status']}",
                "severity": "high" if c["status"] == "contradicted" else "medium",
                "matched_text": c["claim_text"], "start_offset": c["start_offset"], "end_offset": c["end_offset"],
                "explanation": c["rationale"],
                "source_reference": f"{src.get('name')}" + (f" · {src['section']}" if src.get("section") else "") + (f" · p.{src['page']}" if src.get("page") else ""),
                "suggested_correction": None, "confidence": 0.75, "requires_human_review": True,
                "finding_source": "evidence", "region_json": region,
            })

    sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    cat_breakdown: Dict[str, int] = {}
    for f in combined:
        sev_counts[f["severity"]] = sev_counts.get(f["severity"], 0) + 1
        cat_breakdown[f["category"]] = cat_breakdown.get(f["category"], 0) + 1
    risk_score = min(100, sev_counts["critical"] * 35 + sev_counts["high"] * 20 + sev_counts["medium"] * 10 + sev_counts["low"] * 3)
    claim_counts: Dict[str, int] = {}
    for c in checks:
        claim_counts[c["status"]] = claim_counts.get(c["status"], 0) + 1

    run = ReviewRun(
        content_id=item.id, content_version_id=version.id, brand_id=item.brand_id, engine_type=engine_type,
        ai_status=ai_status, status="completed", risk_score=risk_score,
        summary=(f"{len(combined)} finding(s): {sev_counts['critical']} critical, {sev_counts['high']} high. "
                 f"{len(checks)} claim(s) checked against approved sources."),
        severity_counts=json.dumps(sev_counts), category_breakdown=json.dumps(cat_breakdown),
    )
    db.add(run)
    db.flush()

    for f in combined:
        db.add(Finding(
            review_run_id=run.id, content_version_id=version.id, rule_id=f.get("rule_id"),
            category=f.get("category", "tone_voice"), severity=f.get("severity", "medium"),
            matched_text=f.get("matched_text", ""), start_offset=f.get("start_offset", 0), end_offset=f.get("end_offset", 0),
            explanation=f.get("explanation", ""), source_reference=f.get("source_reference"),
            suggested_correction=f.get("suggested_correction"), confidence=f.get("confidence", 1.0),
            requires_human_review=f.get("requires_human_review", False),
            finding_source=f.get("finding_source", "deterministic"), region_json=f.get("region_json"),
        ))
    for c in checks:
        db.add(ClaimCheck(
            review_run_id=run.id, content_version_id=version.id, claim_text=c["claim_text"],
            start_offset=c["start_offset"], end_offset=c["end_offset"], status=c["status"],
            passage_id=c["passage_id"], source_document_id=c["source_document_id"], passage_text=c["passage_text"],
            retrieval_score=c["retrieval_score"], coverage=c["coverage"], rationale=c["rationale"],
            details_json=json.dumps({**c["details"], "source": c["source"]}),
        ))

    # Snapshot the rulebook, policies and sources used, so Decision Replay can show them later.
    policies = db.query(ApprovalPolicy).filter(ApprovalPolicy.brand_id == item.brand_id).all()
    docs = db.query(SourceDocument).filter(SourceDocument.brand_id == item.brand_id).all()
    db.add(RuleSnapshot(
        review_run_id=run.id,
        rules_json=json.dumps([rule_to_dict(r) for r in rules]),
        policies_json=json.dumps([{"id": p.id, "name": p.name, "condition_type": p.condition_type,
                                   "condition_value": p.condition_value, "required_role": p.required_role,
                                   "min_approvals": p.min_approvals, "require_evidence_confirmation": p.require_evidence_confirmation,
                                   "is_active": p.is_active} for p in policies]),
        sources_json=json.dumps([{"id": d.id, "name": d.name, "approval_status": d.approval_status,
                                  "effective_date": d.effective_date, "expiry_date": d.expiry_date} for d in docs]),
    ))

    db.add(AuditEvent(
        brand_id=item.brand_id, content_id=item.id, event_type="analysis_run",
        actor_name=actor.name, actor_role=actor.role_label,
        description=(f"Analysed version {version.version_number}"
                     f"{' (image creative)' if asset else ''}: {len(combined)} findings, risk score {risk_score}, "
                     f"{len(checks)} claims checked."),
        event_metadata=json.dumps({"version": version.version_number, "engine": engine_type, "ai_status": ai_status,
                                   "risk_score": risk_score, "findings_count": len(combined), "claims": claim_counts}),
    ))
    db.commit()
    db.refresh(run)
    return run
