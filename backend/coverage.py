"""Governance Coverage Map: which policies are enforced by which checks, backed by which sources,
and what their status is on every asset's current version.

Cell states per (policy, asset):
  violated     an open finding for this policy on the latest analysis of the current version
  passed       the current version was analysed with this policy active and produced no open finding
  not_checked  the current version was never analysed, or was analysed before this policy existed/was active
  n/a          the check does not apply to the asset (e.g. visual checks on text content)
"""
import json
from datetime import date
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from backend import intelligence
from backend import policies as policy_engine
from backend.models import ApprovedClaim, BrandRule, ContentItem, ContentVersion, Finding
from backend.models_r3 import ApprovalPolicy, BrandLogo, ClaimCheck, RuleSnapshot, SourceDocument

CHECK_FOR_CATEGORY = {
    "prohibited_term": "Rule engine: phrase match (text and OCR text)",
    "restricted_claim": "Rule engine: phrase match (text and OCR text)",
    "preferred_term": "Rule engine: term match with replacement (text and OCR text)",
    "required_phrase": "Rule engine: presence check (text and OCR text)",
    "tone_voice": "Rule engine: phrase match",
    "formatting_style": "Rule engine: built-in style checks",
}


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def coverage_map(db: Session, brand_id: str) -> Dict[str, Any]:
    today = date.today().isoformat()
    rules = db.query(BrandRule).filter(BrandRule.brand_id == brand_id).all()
    claims = db.query(ApprovedClaim).filter(ApprovedClaim.brand_id == brand_id).all()
    docs = db.query(SourceDocument).filter(SourceDocument.brand_id == brand_id).all()
    approved_docs = [d for d in docs if d.approval_status == "approved"]
    has_logo = db.query(BrandLogo).filter(BrandLogo.brand_id == brand_id).first() is not None
    conflicts = intelligence.detect_contradictions(rules, claims)
    conflict_rules: Dict[str, List[str]] = {}
    for c in conflicts:
        for rid in c["rule_ids"]:
            conflict_rules.setdefault(rid, []).append(f"{c['certainty']}: {c['title']}")

    # Assets and the latest analysis of each current version.
    assets, runs = [], {}
    for it in db.query(ContentItem).filter(ContentItem.brand_id == brand_id).order_by(ContentItem.title).all():
        v = db.query(ContentVersion).filter(ContentVersion.content_id == it.id, ContentVersion.version_number == it.current_version_number).first()
        run = policy_engine.latest_run_for_version(db, v.id) if v else None
        snap = db.query(RuleSnapshot).filter(RuleSnapshot.review_run_id == run.id).first() if run else None
        snap_rules = {r["id"]: r for r in json.loads(snap.rules_json)} if snap else None
        open_findings = db.query(Finding).filter(Finding.review_run_id == run.id, Finding.is_applied == False,  # noqa: E712
                                                 Finding.is_dismissed == False).all() if run else []  # noqa: E712
        checks = db.query(ClaimCheck).filter(ClaimCheck.review_run_id == run.id).all() if run else []
        runs[it.id] = {"run": run, "snapshot": snap_rules, "findings": open_findings, "claims": checks}
        assets.append({"content_id": it.id, "title": it.title, "media_kind": it.media_kind, "status": it.status,
                       "version_number": it.current_version_number, "analysed": run is not None,
                       "analysed_at": run.created_at.isoformat() if run else None})

    def cell_for_rule(rule, asset) -> Dict[str, Any]:
        info = runs[asset["content_id"]]
        if not info["run"]:
            return {"state": "not_checked", "reason": f"v{asset['version_number']} not analysed"}
        snap = info["snapshot"]
        # Only claim "passed" when we know this rule was active when the analysis ran.
        if snap is None:
            return {"state": "not_checked", "reason": "analysed before rule snapshots were recorded; cannot confirm this rule ran"}
        snap_rule = snap.get(rule.id)
        if not snap_rule:
            return {"state": "not_checked", "reason": "rule did not exist when this version was analysed"}
        if not snap_rule.get("is_active"):
            return {"state": "not_checked", "reason": "rule was inactive when this version was analysed"}
        hits = [f for f in info["findings"] if f.rule_id == rule.id]
        if hits:
            return {"state": "violated", "reason": hits[0].matched_text[:80], "finding_id": hits[0].id}
        return {"state": "passed", "reason": "no finding on the latest analysis"}

    policies_out: List[Dict[str, Any]] = []
    for r in sorted(rules, key=lambda r: (not r.is_active, r.category, r.name)):
        pattern = (r.match_pattern or "").strip()
        has_check = r.is_active and (bool(pattern) or r.category in ("required_phrase", "formatting_style"))
        cited = (r.source_reference or "").strip()
        cited_doc = next((d for d in docs if d.name and (d.name.lower() in cited.lower() or (d.source_identifier and d.source_identifier.lower() in cited.lower()))), None)
        flags = []
        if not r.is_active:
            flags.append("inactive")
        if r.is_active and not has_check:
            flags.append("no implemented check (no match pattern)")
        if not cited:
            flags.append("no cited source")
        elif not cited_doc:
            flags.append("cited source is not in the evidence library")
        elif cited_doc.expiry_date and cited_doc.expiry_date < today:
            flags.append(f"cited source expired {cited_doc.expiry_date}")
        if r.id in conflict_rules:
            flags.append("conflicting rule")
        cells = {a["content_id"]: (cell_for_rule(r, a) if r.is_active and has_check else {"state": "not_checked", "reason": "no active check"}) for a in assets}
        policies_out.append({
            "id": r.id, "kind": "rule", "name": r.name, "category": r.category, "severity": r.severity, "active": r.is_active,
            "check": CHECK_FOR_CATEGORY.get(r.category, "Rule engine") if has_check else None,
            "source": {"cited": cited or None, "document_id": cited_doc.id if cited_doc else None,
                       "document": cited_doc.name if cited_doc else None,
                       "effective_date": cited_doc.effective_date if cited_doc else None,
                       "expiry_date": cited_doc.expiry_date if cited_doc else None},
            "conflicts": conflict_rules.get(r.id, []), "flags": flags, "cells": cells,
        })

    # Claim verification as a governance control backed by the evidence library.
    claim_cells = {}
    for a in assets:
        info = runs[a["content_id"]]
        if not info["run"]:
            claim_cells[a["content_id"]] = {"state": "not_checked", "reason": f"v{a['version_number']} not analysed"}
            continue
        if info["snapshot"] is None:
            # Analyses recorded before Round 3 never ran claim verification.
            claim_cells[a["content_id"]] = {"state": "not_checked", "reason": "analysed before claim verification was recorded; re-run the analysis"}
            continue
        bad = [c for c in info["claims"] if c.status in ("contradicted", "stale")]
        unsure = [c for c in info["claims"] if c.status in ("needs_review", "unsupported")]
        if bad:
            claim_cells[a["content_id"]] = {"state": "violated", "reason": f"{bad[0].status}: {bad[0].claim_text[:70]}"}
        elif unsure:
            claim_cells[a["content_id"]] = {"state": "review", "reason": f"{len(unsure)} claim(s) without clear evidence"}
        else:
            claim_cells[a["content_id"]] = {"state": "passed", "reason": f"{len(info['claims'])} claim(s) supported" if info["claims"] else "no checkable claims"}
    expired = [d.name for d in approved_docs if d.expiry_date and d.expiry_date < today]
    overdue = [d.name for d in approved_docs if d.review_date and d.review_date < today]
    claim_flags = ([] if approved_docs else ["no approved evidence sources"]) + [f"expired source: {n}" for n in expired] + [f"review overdue: {n}" for n in overdue]
    policies_out.insert(0, {
        "id": "control:claims", "kind": "control", "name": "Claims must be backed by approved evidence", "category": "claim_verification",
        "severity": "high", "active": True, "check": "Evidence retrieval + claim verification",
        "source": {"cited": f"{len(approved_docs)} approved source(s)", "documents": [{"id": d.id, "name": d.name, "effective_date": d.effective_date,
                   "expiry_date": d.expiry_date, "review_date": d.review_date, "updated": d.created_at.isoformat() if d.created_at else None} for d in approved_docs]},
        "conflicts": [], "flags": claim_flags, "cells": claim_cells,
    })

    # Visual identity controls apply to creatives only.
    for key, name, cat, ok in (("control:contrast", "Text must meet WCAG AA contrast", "visual_contrast", True),
                               ("control:logo", "Creatives must show the reference logo", "visual_logo", has_logo)):
        cells = {}
        for a in assets:
            info = runs[a["content_id"]]
            if a["media_kind"] != "image":
                cells[a["content_id"]] = {"state": "n/a", "reason": "text content"}
            elif not ok:
                cells[a["content_id"]] = {"state": "not_checked", "reason": "no reference logo configured"}
            elif not info["run"]:
                cells[a["content_id"]] = {"state": "not_checked", "reason": f"v{a['version_number']} not analysed"}
            else:
                hit = next((f for f in info["findings"] if f.category == cat), None)
                cells[a["content_id"]] = {"state": "violated", "reason": hit.matched_text[:70]} if hit else {"state": "passed", "reason": "no finding"}
        policies_out.insert(1, {"id": key, "kind": "control", "name": name, "category": cat, "severity": "medium", "active": True,
                                "check": "Pixel measurement on creatives", "source": {"cited": "WCAG 2.2 SC 1.4.3" if cat == "visual_contrast" else ("Workspace reference logo" if has_logo else None)},
                                "conflicts": [], "flags": [] if ok else ["no reference logo configured"], "cells": cells})

    approval_policies = db.query(ApprovalPolicy).filter(ApprovalPolicy.brand_id == brand_id).all()
    counts = {"violated": 0, "passed": 0, "not_checked": 0, "review": 0, "n/a": 0}
    for p in policies_out:
        for c in p["cells"].values():
            counts[c["state"]] += 1
    unanalysed = [a["title"] for a in assets if not a["analysed"]]
    flagged = [p["name"] for p in policies_out if p["flags"] and p["active"]]
    complete = not unanalysed and counts["not_checked"] == 0
    return {
        "policies": policies_out, "assets": assets, "counts": counts,
        "approval_policies": [{"name": p.name, "active": p.is_active, "condition": f"{p.condition_type} = {p.condition_value}"} for p in approval_policies],
        "unanalysed_assets": unanalysed, "flagged_policies": flagged, "complete": complete,
        "statement": ("Every active policy was checked on every applicable asset's current version." if complete else
                      f"Coverage is incomplete: {counts['not_checked']} policy/asset combinations are not checked"
                      + (f" ({len(unanalysed)} asset(s) never analysed)" if unanalysed else "") + ". 'Not checked' is not the same as 'passed'."),
    }
