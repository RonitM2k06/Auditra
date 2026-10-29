"""What-If Brand Policy Simulator: governed rule-change proposals.

Proposal -> stored simulation (with a fingerprint of the rulebook it ran against) -> a different
admin activates or rejects it with explicit confirmation. Activation is refused if the rulebook
changed after the simulation, so nobody approves a change based on stale results.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import intelligence as intel
from backend.auth import authorize, current_user
from backend.database import get_db
from backend.models import AuditEvent, BrandRule
from backend.models_r3 import RuleProposal, User
from backend.routes.intel import Change, simulate

router = APIRouter(tags=["Policy simulator"])


def rulebook_fingerprint(db: Session, brand_id: str) -> str:
    rules = db.query(BrandRule).filter(BrandRule.brand_id == brand_id).order_by(BrandRule.id).all()
    payload = json.dumps([[getattr(r, f) for f in intel.RULE_FIELDS] for r in rules], default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _summary(sim: dict) -> dict:
    items = sim["items"]
    flips = lambda a, b: [i["title"] for i in items if i["outcome_before"] == a and i["outcome_after"] == b]  # noqa: E731
    return {
        "assets_evaluated": len(items),
        "affected": sim["affected_items"],
        "new_failures": [i["title"] for i in items if i["outcome_after"] == "fail" and i["outcome_before"] != "fail"],
        "newly_passing": [i["title"] for i in items if i["outcome_after"] == "pass" and i["outcome_before"] != "pass"],
        "new_reviews": flips("pass", "review"),
        "approvals_at_risk": [i["title"] for i in items if i["approval_at_risk"]],
        "new_contradictions": len(sim["new_contradictions"]),
    }


def _dict(p: RuleProposal, db: Session) -> dict:
    sim = json.loads(p.simulation_json)
    return {
        "id": p.id, "title": p.title, "rationale": p.rationale, "status": p.status,
        "changes": json.loads(p.changes_json), "simulation": sim, "summary": _summary(sim),
        "proposed_by": p.proposed_by, "proposed_by_user_id": p.proposed_by_user_id,
        "decided_by": p.decided_by, "decision_note": p.decision_note,
        "simulated_at": p.simulated_at.isoformat() if p.simulated_at else None,
        "decided_at": p.decided_at.isoformat() if p.decided_at else None,
        "simulation_is_current": p.status != "proposed" or p.rulebook_fingerprint == rulebook_fingerprint(db, p.brand_id),
        "scope_note": "Evaluated: rule checks on the current version of every content item in this workspace. "
                      "Claim verification and visual checks are not affected by rule text and were not re-run. "
                      "Earlier versions and content outside this workspace were not evaluated.",
    }


class ProposalIn(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    rationale: Optional[str] = Field(None, max_length=2000)
    changes: List[Change] = Field(..., min_length=1, max_length=20)


class DecisionIn(BaseModel):
    decision: str = Field(..., pattern="^(activate|reject)$")
    confirm: bool = False
    note: Optional[str] = Field(None, max_length=1000)


def _get(db: Session, user: User, proposal_id: str, perm: str):
    p = db.query(RuleProposal).filter(RuleProposal.id == proposal_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    actor = authorize(db, user, p.brand_id, perm)
    return p, actor


@router.get("/brands/{brand_id}/rule-proposals")
def list_proposals(brand_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize(db, user, brand_id, "workspace.view")
    rows = db.query(RuleProposal).filter(RuleProposal.brand_id == brand_id).order_by(RuleProposal.created_at.desc()).all()
    return [_dict(p, db) for p in rows]


@router.post("/brands/{brand_id}/rule-proposals", status_code=201)
def create_proposal(brand_id: str, payload: ProposalIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    actor = authorize(db, user, brand_id, "simulate")
    sim = simulate(db, brand_id, payload.changes)
    p = RuleProposal(brand_id=brand_id, title=payload.title.strip(), rationale=(payload.rationale or "").strip() or None,
                     changes_json=json.dumps([c.model_dump() for c in payload.changes]), simulation_json=json.dumps(sim),
                     rulebook_fingerprint=rulebook_fingerprint(db, brand_id), proposed_by=actor.name, proposed_by_user_id=user.id)
    db.add(p)
    db.flush()
    s = _summary(sim)
    db.add(AuditEvent(brand_id=brand_id, event_type="rule_change_proposed", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Proposed rule change '{p.title}' (simulated on {s['assets_evaluated']} items: "
                                  f"{len(s['new_failures'])} new failure(s), {len(s['newly_passing'])} newly passing). Active rules unchanged.",
                      event_metadata=json.dumps({"proposal_id": p.id, "changes": json.loads(p.changes_json), "summary": s})))
    db.commit()
    return _dict(p, db)


@router.post("/rule-proposals/{proposal_id}/rerun")
def rerun_proposal(proposal_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p, actor = _get(db, user, proposal_id, "simulate")
    if p.status != "proposed":
        raise HTTPException(status_code=409, detail=f"This proposal was already {p.status}.")
    sim = simulate(db, p.brand_id, [Change(**c) for c in json.loads(p.changes_json)])
    p.simulation_json = json.dumps(sim)
    p.rulebook_fingerprint = rulebook_fingerprint(db, p.brand_id)
    p.simulated_at = datetime.now(timezone.utc)
    db.add(AuditEvent(brand_id=p.brand_id, event_type="rule_change_resimulated", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Re-ran the simulation for proposal '{p.title}'.", event_metadata=json.dumps({"proposal_id": p.id, "summary": _summary(sim)})))
    db.commit()
    return _dict(p, db)


@router.post("/rule-proposals/{proposal_id}/decision")
def decide_proposal(proposal_id: str, payload: DecisionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p, actor = _get(db, user, proposal_id, "rules.manage")
    if p.status != "proposed":
        raise HTTPException(status_code=409, detail=f"This proposal was already {p.status}.")
    if payload.decision == "reject":
        if not (payload.note or "").strip():
            raise HTTPException(status_code=422, detail="Say why the proposal is rejected.")
    else:
        if not payload.confirm:
            raise HTTPException(status_code=422, detail="Activation changes the live rulebook. Confirm explicitly to proceed.")
        if p.proposed_by_user_id == user.id:
            raise HTTPException(status_code=403, detail="A different admin must activate a proposal you created.")
        if p.rulebook_fingerprint != rulebook_fingerprint(db, p.brand_id):
            raise HTTPException(status_code=409, detail="The rulebook changed after this simulation. Re-run the simulation and review the new results first.")
        rules = {r.id: r for r in db.query(BrandRule).filter(BrandRule.brand_id == p.brand_id).all()}
        applied = []
        for ch in json.loads(p.changes_json):
            op, rid, data = ch["op"], ch.get("rule_id"), ch.get("rule") or {}
            if op == "add":
                fields = {k: v for k, v in data.items() if k in intel.RULE_FIELDS and k != "id"}
                r = BrandRule(brand_id=p.brand_id, name=fields.get("name") or "Rule from proposal",
                              category=fields["category"], description=fields.get("description") or p.title,
                              rule_text=fields.get("rule_text") or fields.get("match_pattern"), match_pattern=fields.get("match_pattern"),
                              suggested_replacement=fields.get("suggested_replacement"), severity=fields.get("severity", "medium"),
                              source_reference=fields.get("source_reference") or f"Proposal: {p.title}", is_active=True)
                db.add(r)
                applied.append(f"added '{r.name}'")
                continue
            r = rules.get(rid)
            if not r:
                raise HTTPException(status_code=409, detail="A rule in this proposal no longer exists. Re-run the simulation.")
            if op == "disable":
                r.is_active = False
            elif op == "enable":
                r.is_active = True
            elif op == "delete":
                db.delete(r)
            elif op == "update":
                for k, v in data.items():
                    if k in intel.RULE_FIELDS and k != "id":
                        setattr(r, k, v)
            applied.append(f"{op} '{r.name}'")
    p.status = "activated" if payload.decision == "activate" else "rejected"
    p.decided_by = actor.name
    p.decision_note = (payload.note or "").strip() or None
    p.decided_at = datetime.now(timezone.utc)
    db.add(AuditEvent(
        brand_id=p.brand_id, event_type="rule_change_activated" if p.status == "activated" else "rule_change_rejected",
        actor_name=actor.name, actor_role=actor.role_label,
        description=(f"Activated rule change '{p.title}' proposed by {p.proposed_by}: {', '.join(applied)}. "
                     "Existing analyses keep their recorded rulebook snapshot; re-run analyses to apply the new rules."
                     if p.status == "activated" else f"Rejected rule change '{p.title}': {p.decision_note}"),
        event_metadata=json.dumps({"proposal_id": p.id, "note": p.decision_note}),
    ))
    db.commit()
    return _dict(p, db)
