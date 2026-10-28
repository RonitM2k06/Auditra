import json
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import intelligence as intel
from backend import policies as policy_engine
from backend.auth import authorize, authorize_content, current_user
from backend.database import get_db
from backend.models import ApprovedClaim, AuditEvent, Brand, BrandRule, ContentItem, ContentVersion, Finding, ReviewDecision, ReviewRun
from backend.models_r3 import ApprovalPolicy, BrandLogo, Campaign, CampaignAsset, ClaimCheck, Publication, RuleSnapshot, SourceDocument, User
from backend.review_pipeline import brand_palette
from backend.risk import campaign_risk as compute_campaign_risk

router = APIRouter(tags=["Brand intelligence"])


class Change(BaseModel):
    op: str
    rule_id: Optional[str] = None
    rule: Optional[Dict[str, Any]] = None


class SimulationIn(BaseModel):
    changes: List[Change] = Field(..., min_length=1, max_length=20)


def _rules_claims(db: Session, brand_id: str):
    rules = db.query(BrandRule).filter(BrandRule.brand_id == brand_id).all()
    claims = db.query(ApprovedClaim).filter(ApprovedClaim.brand_id == brand_id).all()
    return rules, claims


def _current_versions(db: Session, brand_id: str):
    items = db.query(ContentItem).filter(ContentItem.brand_id == brand_id).all()
    out = []
    for it in items:
        v = db.query(ContentVersion).filter(ContentVersion.content_id == it.id, ContentVersion.version_number == it.current_version_number).first()
        if v:
            out.append((it, v))
    return out


@router.get("/brands/{brand_id}/dna")
def get_brand_dna(brand_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize(db, user, brand_id, "workspace.view")
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    rules, claims = _rules_claims(db, brand_id)
    counts: Dict[str, int] = {}
    for (cat,) in db.query(Finding.category).join(ReviewRun, ReviewRun.id == Finding.review_run_id).filter(ReviewRun.brand_id == brand_id).all():
        counts[cat] = counts.get(cat, 0) + 1
    result = intel.brand_dna(
        rules, claims, db.query(SourceDocument).filter(SourceDocument.brand_id == brand_id).all(),
        db.query(ApprovalPolicy).filter(ApprovalPolicy.brand_id == brand_id).all(), brand_palette(brand),
        db.query(BrandLogo).filter(BrandLogo.brand_id == brand_id).first() is not None, counts, date.today().isoformat(),
    )
    result["rules"] = {r.id: {"name": r.name, "category": r.category, "pattern": r.match_pattern, "severity": r.severity} for r in rules}
    return result


def simulate(db: Session, brand_id: str, changes: List[Change], only: Optional[List] = None) -> Dict[str, Any]:
    rules, claims = _rules_claims(db, brand_id)
    try:
        proposed = intel.apply_changes(rules, [c.model_dump() for c in changes])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    current = [intel.copy_rule(r) for r in rules]
    policies = db.query(ApprovalPolicy).filter(ApprovalPolicy.brand_id == brand_id).all()
    items_out = []
    for it, v in (only or _current_versions(db, brand_id)):
        before = intel.run_rules(v.body, current, claims)
        after = intel.run_rules(v.body, proposed, claims)
        d = intel.diff_findings(before, after)
        run = policy_engine.latest_run_for_version(db, v.id)
        checks = db.query(ClaimCheck).filter(ClaimCheck.review_run_id == run.id).all() if run else []
        to_ns = lambda fs: [type("F", (), f) for f in fs]  # noqa: E731
        pol_before = {t["policy"].name for t in policy_engine.triggered_policies(policies, to_ns(before), checks)}
        pol_after = {t["policy"].name for t in policy_engine.triggered_policies(policies, to_ns(after), checks)}
        items_out.append({
            "content_id": it.id, "title": it.title, "status": it.status, "version_number": v.version_number,
            "media_kind": it.media_kind, "findings_before": len(before), "findings_after": len(after), **d,
            "policies_added": sorted(pol_after - pol_before), "policies_removed": sorted(pol_before - pol_after),
            "approval_at_risk": it.status == "approved" and bool(pol_after - pol_before),
        })
    before_c = {(c["kind"], tuple(sorted(c["rule_ids"]))) for c in intel.detect_contradictions(current, claims)}
    after_contra = intel.detect_contradictions(proposed, claims)
    return {
        "items": items_out,
        "affected_items": sum(1 for i in items_out if i["gained"] or i["lost"] or i["severity_changed"]),
        "new_contradictions": [c for c in after_contra if (c["kind"], tuple(sorted(c["rule_ids"]))) not in before_c],
        "note": "Simulation only. The active rulebook, content, findings and approvals were not changed.",
    }


@router.post("/brands/{brand_id}/simulate")
def simulate_rule_change(brand_id: str, payload: SimulationIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize(db, user, brand_id, "simulate")
    return simulate(db, brand_id, payload.changes)


# --- Campaigns ---

class CampaignIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    brief: Optional[str] = Field(None, max_length=20000)
    content_ids: List[str] = Field(default_factory=list, max_length=30)


def _campaign(db: Session, user: User, campaign_id: str, perm: str):
    c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    actor = authorize(db, user, c.brand_id, perm)
    return c, actor


def _campaign_dict(db: Session, c: Campaign) -> Dict[str, Any]:
    rows = db.query(CampaignAsset, ContentItem).join(ContentItem, ContentItem.id == CampaignAsset.content_id).filter(CampaignAsset.campaign_id == c.id).all()
    return {"id": c.id, "name": c.name, "brief": c.brief, "created_by": c.created_by,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "assets": [{"content_id": it.id, "title": it.title, "content_type": it.content_type, "status": it.status,
                        "media_kind": it.media_kind, "version_number": it.current_version_number} for _, it in rows]}


def _set_assets(db: Session, c: Campaign, content_ids: List[str]):
    valid = {i for (i,) in db.query(ContentItem.id).filter(ContentItem.brand_id == c.brand_id, ContentItem.id.in_(content_ids or [""])).all()}
    bad = set(content_ids) - valid
    if bad:
        raise HTTPException(status_code=422, detail="Some selected content does not belong to this workspace.")
    db.query(CampaignAsset).filter(CampaignAsset.campaign_id == c.id).delete()
    for cid in dict.fromkeys(content_ids):
        db.add(CampaignAsset(campaign_id=c.id, content_id=cid))


@router.get("/brands/{brand_id}/campaigns")
def list_campaigns(brand_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize(db, user, brand_id, "workspace.view")
    return [_campaign_dict(db, c) for c in db.query(Campaign).filter(Campaign.brand_id == brand_id).order_by(Campaign.created_at.desc()).all()]


@router.post("/brands/{brand_id}/campaigns", status_code=201)
def create_campaign(brand_id: str, payload: CampaignIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    actor = authorize(db, user, brand_id, "campaign.manage")
    c = Campaign(brand_id=brand_id, name=payload.name.strip(), brief=(payload.brief or "").strip() or None, created_by=actor.name)
    db.add(c)
    db.flush()
    _set_assets(db, c, payload.content_ids)
    db.add(AuditEvent(brand_id=brand_id, event_type="campaign_created", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Created campaign '{c.name}' with {len(payload.content_ids)} asset(s)."))
    db.commit()
    return _campaign_dict(db, c)


@router.put("/campaigns/{campaign_id}")
def update_campaign(campaign_id: str, payload: CampaignIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c, actor = _campaign(db, user, campaign_id, "campaign.manage")
    c.name, c.brief = payload.name.strip(), (payload.brief or "").strip() or None
    _set_assets(db, c, payload.content_ids)
    db.add(AuditEvent(brand_id=c.brand_id, event_type="campaign_updated", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Updated campaign '{c.name}' ({len(payload.content_ids)} asset(s))."))
    db.commit()
    return _campaign_dict(db, c)


@router.delete("/campaigns/{campaign_id}", status_code=204)
def delete_campaign(campaign_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c, actor = _campaign(db, user, campaign_id, "campaign.manage")
    db.add(AuditEvent(brand_id=c.brand_id, event_type="campaign_deleted", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Deleted campaign '{c.name}'. Its content items were kept."))
    db.delete(c)
    db.commit()


@router.get("/campaigns/{campaign_id}/consistency")
def campaign_consistency(campaign_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c, _ = _campaign(db, user, campaign_id, "workspace.view")
    info = _campaign_dict(db, c)
    assets = []
    if c.brief:
        assets.append({"id": "brief", "title": "Approved campaign brief", "text": c.brief, "is_brief": True})
    for a in info["assets"]:
        v = db.query(ContentVersion).filter(ContentVersion.content_id == a["content_id"], ContentVersion.version_number == a["version_number"]).first()
        if v:
            assets.append({"id": a["content_id"], "title": a["title"], "text": v.body, "is_brief": False})
    rules, claims = _rules_claims(db, c.brand_id)
    if len([a for a in assets if not a["is_brief"]]) < 2:
        return {**info, "facts": [], "issues": [], "counts": {}, "asset_texts": {a["id"]: a["text"] for a in assets},
                "notice": "Add at least two assets to compare them."}
    result = intel.campaign_consistency(assets, rules, claims)
    return {**info, **result, "asset_texts": {a["id"]: a["text"] for a in assets}}


@router.get("/campaigns/{campaign_id}/risk")
def campaign_risk(campaign_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Campaign Risk Radar, computed from current versions, rules and approvals on every request."""
    c, _ = _campaign(db, user, campaign_id, "workspace.view")
    return compute_campaign_risk(db, c)


# --- Decision replay ---

def _run_findings(db: Session, run: Optional[ReviewRun]) -> List[Dict[str, Any]]:
    if not run:
        return []
    return [{"id": f.id, "rule_id": f.rule_id, "category": f.category, "severity": f.severity, "matched_text": f.matched_text,
             "start_offset": f.start_offset, "explanation": f.explanation, "source_reference": f.source_reference,
             "is_applied": f.is_applied, "is_dismissed": f.is_dismissed}
            for f in db.query(Finding).filter(Finding.review_run_id == run.id).all()]


def _snapshot(db: Session, run: Optional[ReviewRun]):
    snap = db.query(RuleSnapshot).filter(RuleSnapshot.review_run_id == run.id).first() if run else None
    return json.loads(snap.rules_json) if snap else None, snap


@router.get("/content/{content_id}/replay")
def replay(content_id: str, from_version: Optional[int] = None, to_version: Optional[int] = None,
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, _ = authorize_content(db, user, content_id, "workspace.view")
    versions = {v.version_number: v for v in db.query(ContentVersion).filter(ContentVersion.content_id == content_id).all()}
    b = to_version or item.current_version_number
    a = from_version or max(1, b - 1)
    if a not in versions or b not in versions:
        raise HTTPException(status_code=404, detail="Version not found")
    va, vb = versions[a], versions[b]
    ra, rb = policy_engine.latest_run_for_version(db, va.id), policy_engine.latest_run_for_version(db, vb.id)
    sa, snap_a = _snapshot(db, ra)
    sb, snap_b = _snapshot(db, rb)
    events = db.query(AuditEvent).filter(AuditEvent.content_id == content_id).order_by(AuditEvent.created_at.asc()).all()
    decisions = db.query(ReviewDecision).filter(ReviewDecision.content_id == content_id).order_by(ReviewDecision.created_at.asc()).all()
    vid_num = {v.id: n for n, v in versions.items()}
    return {
        "content_id": content_id, "title": item.title, "media_kind": item.media_kind,
        "versions": [{"version_number": n, "created_by": v.created_by, "change_summary": v.change_summary,
                      "created_at": v.created_at.isoformat() if v.created_at else None,
                      "reviewed": policy_engine.latest_run_for_version(db, v.id) is not None} for n, v in sorted(versions.items())],
        "from_version": a, "to_version": b,
        "diff": intel.text_diff(va.body, vb.body),
        "findings": intel.compare_runs(_run_findings(db, ra), _run_findings(db, rb)),
        "review_runs": {"from": ra.created_at.isoformat() if ra else None, "to": rb.created_at.isoformat() if rb else None},
        "rulebook": {
            "from_snapshot": snap_a is not None, "to_snapshot": snap_b is not None,
            "diff": intel.diff_rule_snapshots(sa, sb),
            "note": None if (snap_a and snap_b) else "Rulebook snapshots are recorded for reviews run after the Round 3 upgrade; "
                                                     "older runs have no stored rule state, so it is not reconstructed.",
        },
        "decisions": [{"decision": d.decision, "reviewer": d.reviewer_name, "role": d.reviewer_role, "version_number": vid_num.get(d.content_version_id),
                       "evidence_confirmed": bool(d.evidence_confirmed), "comments": d.comments,
                       "created_at": d.created_at.isoformat() if d.created_at else None} for d in decisions],
        "timeline": [{"event_type": e.event_type, "actor_name": e.actor_name, "actor_role": e.actor_role, "description": e.description,
                      "version": (json.loads(e.event_metadata or "{}") or {}).get("version"),
                      "created_at": e.created_at.isoformat() if e.created_at else None} for e in events],
        "publications": [{"version_number": p.version_number, "channel": p.channel, "created_at": p.created_at.isoformat() if p.created_at else None}
                         for p in db.query(Publication).filter(Publication.content_id == content_id).all()],
        "integrity_note": "Events come from AUDITRA's audit table. It is an append-only application log, not a tamper-proof ledger.",
    }


@router.post("/content/{content_id}/versions/{version_number}/counterfactual")
def counterfactual(content_id: str, version_number: int, payload: SimulationIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, _ = authorize_content(db, user, content_id, "simulate")
    v = db.query(ContentVersion).filter(ContentVersion.content_id == content_id, ContentVersion.version_number == version_number).first()
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    result = simulate(db, item.brand_id, payload.changes, only=[(item, v)])
    return {**result["items"][0], "new_contradictions": result["new_contradictions"], "note": result["note"]}
