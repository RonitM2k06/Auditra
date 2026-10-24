import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import (
    ContentItem, ContentVersion, BrandRule, ApprovedClaim,
    ReviewRun, Finding, AuditEvent
)
from backend.schemas import (
    ReviewRunRequest, ReviewRunResponse, FindingResponse,
    FindingApplyRequest, ContentItemDetailResponse
)
from backend.rule_engine import ComplianceRuleEngine
from backend.ai_service import AIService
from backend.routes.content import get_content_item_detail

router = APIRouter(tags=["Review & Findings"])

@router.post("/content/{content_id}/review", response_model=ReviewRunResponse)
async def run_content_review(
    content_id: str,
    payload: Optional[ReviewRunRequest] = None,
    db: Session = Depends(get_db)
):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")

    current_ver = db.query(ContentVersion).filter(
        ContentVersion.content_id == content_id,
        ContentVersion.version_number == item.current_version_number
    ).first()
    if not current_ver:
        raise HTTPException(status_code=400, detail="No content version available to review")

    rules = db.query(BrandRule).filter(BrandRule.brand_id == item.brand_id, BrandRule.is_active == True).all()
    claims = db.query(ApprovedClaim).filter(ApprovedClaim.brand_id == item.brand_id, ApprovedClaim.is_active == True).all()

    # 1. Deterministic Analysis
    engine = ComplianceRuleEngine(rules, claims)
    deterministic_findings = engine.analyze(current_ver.body)

    # 2. AI-Assisted Analysis (if configured and not explicitly forced deterministic)
    ai_status = "fallback_rule_based"
    engine_type = "deterministic"
    ai_findings_raw = []

    force_engine = payload.force_engine if payload else None
    if force_engine != "deterministic" and AIService.is_configured():
        ai_res = await AIService.analyze_content(
            text=current_ver.body,
            brand_name=item.brand.name if item.brand else "Brand",
            rules=rules,
            approved_claims=claims
        )
        ai_status = ai_res.get("ai_status", "fallback_rule_based")
        if ai_status == "configured":
            engine_type = "hybrid_ai"
            ai_findings_raw = ai_res.get("findings", [])

    # Combine findings (avoid duplicating identical text matches)
    combined_findings = []
    # Add deterministic findings
    matched_spans = set()
    for df in deterministic_findings:
        matched_spans.add((df.start_offset, df.end_offset, df.matched_text))
        combined_findings.append({
            "rule_id": df.rule_id,
            "category": df.category,
            "severity": df.severity,
            "matched_text": df.matched_text,
            "start_offset": df.start_offset,
            "end_offset": df.end_offset,
            "explanation": df.explanation,
            "source_reference": df.source_reference,
            "suggested_correction": df.suggested_correction,
            "confidence": df.confidence,
            "requires_human_review": df.requires_human_review,
            "finding_source": df.finding_source
        })

    # Add AI findings if not overlapping exact span
    for af in ai_findings_raw:
        span_key = (af["start_offset"], af["end_offset"], af["matched_text"])
        if span_key not in matched_spans:
            matched_spans.add(span_key)
            combined_findings.append(af)

    # Calculate severity counts and risk score
    sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    cat_breakdown = {}
    for f in combined_findings:
        sev = f["severity"].lower()
        sev_counts[sev] = sev_counts.get(sev, 0) + 1
        cat = f["category"]
        cat_breakdown[cat] = cat_breakdown.get(cat, 0) + 1

    risk_score = min(100, (
        sev_counts.get("critical", 0) * 35 +
        sev_counts.get("high", 0) * 20 +
        sev_counts.get("medium", 0) * 10 +
        sev_counts.get("low", 0) * 3
    ))

    summary = (
        f"Compliance scan completed via {engine_type.replace('_', ' ').title()} Engine. "
        f"Flagged {len(combined_findings)} finding(s): {sev_counts['critical']} critical, "
        f"{sev_counts['high']} high risk. Risk score: {risk_score}/100."
    )

    run = ReviewRun(
        content_id=content_id,
        content_version_id=current_ver.id,
        brand_id=item.brand_id,
        engine_type=engine_type,
        ai_status=ai_status,
        status="completed",
        risk_score=risk_score,
        summary=summary,
        severity_counts=json.dumps(sev_counts),
        category_breakdown=json.dumps(cat_breakdown)
    )
    db.add(run)
    db.flush()

    findings_records = []
    for f in combined_findings:
        finding = Finding(
            review_run_id=run.id,
            content_version_id=current_ver.id,
            rule_id=f.get("rule_id"),
            category=f.get("category", "tone_voice"),
            severity=f.get("severity", "medium"),
            matched_text=f.get("matched_text", ""),
            start_offset=f.get("start_offset", 0),
            end_offset=f.get("end_offset", 0),
            explanation=f.get("explanation", ""),
            source_reference=f.get("source_reference"),
            suggested_correction=f.get("suggested_correction"),
            confidence=f.get("confidence", 1.0),
            requires_human_review=f.get("requires_human_review", False),
            finding_source=f.get("finding_source", "deterministic")
        )
        db.add(finding)
        findings_records.append(finding)

    actor_name = payload.actor_name if payload else "Creator"
    actor_role = payload.actor_role if payload else "Content Creator"
    db.add(AuditEvent(
        brand_id=item.brand_id,
        content_id=content_id,
        event_type="analysis_run",
        actor_name=actor_name,
        actor_role=actor_role,
        description=f"Executed compliance analysis on version {current_ver.version_number} ({len(findings_records)} findings, risk score {risk_score}).",
        event_metadata=json.dumps({
            "version": current_ver.version_number,
            "engine": engine_type,
            "ai_status": ai_status,
            "risk_score": risk_score,
            "findings_count": len(findings_records)
        })
    ))

    db.commit()
    db.refresh(run)

    return ReviewRunResponse(
        id=run.id,
        content_id=run.content_id,
        content_version_id=run.content_version_id,
        brand_id=run.brand_id,
        engine_type=run.engine_type,
        ai_status=run.ai_status,
        status=run.status,
        risk_score=run.risk_score,
        summary=run.summary,
        severity_counts=sev_counts,
        category_breakdown=cat_breakdown,
        created_at=run.created_at,
        findings=[
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
            for f in findings_records
        ]
    )

@router.post("/findings/{finding_id}/apply", response_model=ContentItemDetailResponse)
def apply_finding_correction(
    finding_id: str,
    payload: FindingApplyRequest,
    db: Session = Depends(get_db)
):
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    if finding.is_applied:
        raise HTTPException(status_code=400, detail="This correction has already been applied")

    replacement = payload.custom_replacement if payload.custom_replacement is not None else finding.suggested_correction
    if replacement is None:
        raise HTTPException(status_code=400, detail="No suggested correction available for this finding")

    # Get associated content version
    version = db.query(ContentVersion).filter(ContentVersion.id == finding.content_version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Associated content version not found")

    content_item = db.query(ContentItem).filter(ContentItem.id == version.content_id).first()
    if not content_item:
        raise HTTPException(status_code=404, detail="Content item not found")

    # Get the latest current version
    current_ver = db.query(ContentVersion).filter(
        ContentVersion.content_id == content_item.id,
        ContentVersion.version_number == content_item.current_version_number
    ).first()

    body = current_ver.body

    # Apply replacement
    if finding.category == "required_phrase":
        # Append the required disclosure
        updated_body = body.rstrip() + ("\n\n" if not replacement.startswith("\n") else "") + replacement.strip()
    else:
        target = finding.matched_text
        offset = payload.occurrence_offset
        if offset is not None:
            # Caller identified the exact occurrence; verify it still matches.
            if offset < 0 or body[offset:offset + len(target)] != target:
                raise HTTPException(
                    status_code=409,
                    detail="The selected text no longer matches the current version. Re-run the review and try again."
                )
            updated_body = body[:offset] + replacement + body[offset + len(target):]
        else:
            occurrences = body.count(target)
            if occurrences == 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"'{target}' was not found in the current version. It may have already been edited."
                )
            if occurrences > 1:
                raise HTTPException(
                    status_code=409,
                    detail=f"'{target}' appears {occurrences} times in the current version. Choose which occurrence to replace."
                )
            updated_body = body.replace(target, replacement, 1)

    # Create new content version
    new_version_num = content_item.current_version_number + 1
    new_version = ContentVersion(
        content_id=content_item.id,
        version_number=new_version_num,
        body=updated_body,
        change_summary=f"Applied correction for '{finding.category}': '{finding.matched_text}' -> '{replacement}'",
        created_by=payload.actor_name
    )
    db.add(new_version)
    content_item.current_version_number = new_version_num
    finding.is_applied = True

    # If it was approved, reset status to draft/in_review
    if content_item.status == "approved":
        content_item.status = "draft"

    db.add(AuditEvent(
        brand_id=content_item.brand_id,
        content_id=content_item.id,
        event_type="correction_applied",
        actor_name=payload.actor_name,
        actor_role=payload.actor_role,
        description=f"Applied targeted correction: replaced '{finding.matched_text}' with '{replacement}'. Created version {new_version_num}.",
        event_metadata=json.dumps({
            "finding_id": finding.id,
            "rule_id": finding.rule_id,
            "from": finding.matched_text,
            "to": replacement,
            "version": new_version_num
        })
    ))

    db.commit()
    db.refresh(content_item)

    return get_content_item_detail(content_item.id, db)

@router.post("/findings/{finding_id}/dismiss", response_model=FindingResponse)
def dismiss_finding(
    finding_id: str,
    actor_name: str = "Reviewer",
    actor_role: str = "Content Reviewer",
    db: Session = Depends(get_db)
):
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    finding.is_dismissed = True

    version = db.query(ContentVersion).filter(ContentVersion.id == finding.content_version_id).first()
    content_id = version.content_id if version else None
    content_item = db.query(ContentItem).filter(ContentItem.id == content_id).first() if content_id else None

    if content_item:
        db.add(AuditEvent(
            brand_id=content_item.brand_id,
            content_id=content_item.id,
            event_type="finding_dismissed",
            actor_name=actor_name,
            actor_role=actor_role,
            description=f"Dismissed finding: '{finding.matched_text}' ({finding.explanation[:60]}).",
            event_metadata=json.dumps({"finding_id": finding.id})
        ))

    db.commit()
    db.refresh(finding)

    return FindingResponse(
        id=finding.id,
        review_run_id=finding.review_run_id,
        content_version_id=finding.content_version_id,
        rule_id=finding.rule_id,
        category=finding.category,
        severity=finding.severity,
        matched_text=finding.matched_text,
        start_offset=finding.start_offset,
        end_offset=finding.end_offset,
        explanation=finding.explanation,
        source_reference=finding.source_reference,
        suggested_correction=finding.suggested_correction,
        confidence=finding.confidence,
        requires_human_review=finding.requires_human_review,
        is_applied=finding.is_applied,
        is_dismissed=finding.is_dismissed,
        finding_source=finding.finding_source,
        created_at=finding.created_at
    )
