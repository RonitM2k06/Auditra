"""Campaign Risk Radar: one de-duplicated list of what could go wrong in a campaign.

Inputs are records AUDITRA already produces (nothing new is inferred here):
  * open findings from the latest analysis of each asset's *current* version,
  * claim checks from that same analysis,
  * campaign consistency results (cross-asset value mismatches, missing disclosures),
  * approval-policy status of each asset.

Every risk is computed on request, so it reflects the current versions, rules and approvals.

Overall level = the highest severity among the de-duplicated risks. It is a rule, not a probability.
Assets whose current version was never analysed are reported as *unverified*, and the level is then
marked incomplete rather than presented as safe.
"""
import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend import intelligence
from backend import policies as policy_engine
from backend.models import ApprovedClaim, BrandRule, ContentItem, ContentVersion, Finding
from backend.models_r3 import Campaign, CampaignAsset, ClaimCheck

SEV_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
CLAIM_SEVERITY = {"contradicted": "high", "stale": "medium", "needs_review": "medium", "unsupported": "low"}
# Findings that are heuristic estimates rather than exact detections.
HEURISTIC_CATEGORIES = {"visual_contrast", "visual_palette", "visual_logo", "ocr_uncertain", "tone_voice", "unverified_claim"}
ACTIONS = {
    "prohibited_term": "Replace the prohibited wording (use the suggested correction or rewrite the passage).",
    "restricted_claim": "Remove the claim or attach approved evidence and get compliance approval.",
    "preferred_term": "Use the brand's preferred term.",
    "required_phrase": "Add the required disclosure to this asset.",
    "unverified_claim": "Back the claim with an approved source or soften it.",
    "formatting_style": "Adjust formatting to the editorial style.",
    "tone_voice": "Rephrase to match the brand voice.",
    "visual_contrast": "Increase contrast between text and background, then upload a revision.",
    "visual_palette": "Check the colour against the brand palette; revise the creative if it is not intentional.",
    "visual_logo": "Add or correct the brand logo in the creative.",
    "ocr_uncertain": "Check the extracted text against the image before relying on its results.",
}


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def campaign_risk(db: Session, campaign: Campaign) -> Dict[str, Any]:
    rows = (db.query(CampaignAsset, ContentItem).join(ContentItem, ContentItem.id == CampaignAsset.content_id)
            .filter(CampaignAsset.campaign_id == campaign.id).all())
    risks: Dict[str, Dict[str, Any]] = {}
    assets_out: List[Dict[str, Any]] = []
    unverified: List[Dict[str, Any]] = []
    texts: List[Dict[str, Any]] = []

    def add(key: str, risk: Dict[str, Any]) -> None:
        """De-duplicate: the same underlying issue is kept once, with all corroborating sources listed."""
        if key in risks:
            existing = risks[key]
            existing["corroborated_by"] = sorted(set(existing.get("corroborated_by", [])) | {risk["source"]})
            if SEV_RANK[risk["severity"]] > SEV_RANK[existing["severity"]]:
                existing["severity"] = risk["severity"]
            return
        risk["id"] = f"risk-{len(risks) + 1}"
        risks[key] = risk

    for _, item in rows:
        version = db.query(ContentVersion).filter(ContentVersion.content_id == item.id,
                                                  ContentVersion.version_number == item.current_version_number).first()
        if not version:
            continue
        texts.append({"id": item.id, "title": item.title, "text": version.body, "is_brief": False})
        run = policy_engine.latest_run_for_version(db, version.id)
        status = policy_engine.evaluate(db, item)
        assets_out.append({"content_id": item.id, "title": item.title, "status": item.status, "media_kind": item.media_kind,
                           "version_number": version.version_number, "analysed": run is not None,
                           "approval_satisfied": status["satisfied"]})
        if run is None:
            unverified.append({"content_id": item.id, "title": item.title, "version_number": version.version_number,
                               "reason": f"Version {version.version_number} has not been analysed, so its rule, claim and visual risks are unknown."})
            continue

        for f in db.query(Finding).filter(Finding.review_run_id == run.id, Finding.is_applied == False,  # noqa: E712
                                          Finding.is_dismissed == False).all():  # noqa: E712
            if f.category.startswith("claim_"):
                continue  # represented once, by its claim check below
            heuristic = f.category in HEURISTIC_CATEGORIES or f.confidence < 0.8 or f.requires_human_review and f.finding_source == "visual"
            add(f"finding:{item.id}:{f.rule_id or f.category}:{_norm(f.matched_text)}", {
                "severity": f.severity, "kind": "finding", "category": f.category, "source": "analysis",
                "basis": "heuristic" if heuristic else "detected",
                "title": f"{item.title}: {f.category.replace('_', ' ')}",
                "evidence": {"text": None if f.start_offset == f.end_offset and f.category == "required_phrase" else f.matched_text,
                             "explanation": f.explanation, "rule_id": f.rule_id, "source_reference": f.source_reference,
                             "confidence": f.confidence},
                "asset_ids": [item.id], "action": ACTIONS.get(f.category, "Review this finding in the studio."),
                "link": {"page": "studio", "id": item.id, "tab": "findings", "finding_id": f.id},
                "version_number": version.version_number,
            })

        for c in db.query(ClaimCheck).filter(ClaimCheck.review_run_id == run.id).all():
            if c.status == "supported":
                continue
            details = json.loads(c.details_json or "{}")
            src = details.get("source") or {}
            add(f"claim:{item.id}:{_norm(c.claim_text)}", {
                "severity": CLAIM_SEVERITY[c.status], "kind": "claim", "category": f"claim_{c.status}", "source": "claim verification",
                "basis": "detected" if c.status in ("contradicted", "stale") else "heuristic",
                "title": f"{item.title}: claim {c.status.replace('_', ' ')}",
                "evidence": {"text": c.claim_text, "explanation": c.rationale, "passage": c.passage_text,
                             "source_name": src.get("name"), "source_section": src.get("section"),
                             "source_expiry": src.get("expiry_date"), "source_document_id": src.get("document_id")},
                "asset_ids": [item.id],
                "action": {"contradicted": "Correct the figure to match the current source, or update the source if it is wrong.",
                           "stale": "Confirm the figure against a current source before publishing.",
                           "needs_review": "Have a reviewer read the cited passage and decide whether it supports the claim.",
                           "unsupported": "Add an approved source for this claim, or remove it."}[c.status],
                "link": {"page": "studio", "id": item.id, "tab": "claims"},
                "version_number": version.version_number,
            })

        if item.status == "in_review" and not status["satisfied"]:
            add(f"approval:{item.id}", {
                "severity": "medium", "kind": "approval", "category": "approval_pending", "source": "approval policy",
                "basis": "detected", "title": f"{item.title}: approval requirements not met",
                "evidence": {"text": None, "explanation": " | ".join(status["blocking"])},
                "asset_ids": [item.id], "action": "Collect the approvals the policy requires on the current version.",
                "link": {"page": "studio", "id": item.id, "tab": "approval"}, "version_number": version.version_number,
            })
        if item.status == "approved" and (item.approved_version_id != version.id or not status["satisfied"]):
            add(f"approval:{item.id}", {
                "severity": "high", "kind": "approval", "category": "approval_invalid", "source": "approval policy",
                "basis": "detected", "title": f"{item.title}: approval no longer valid",
                "evidence": {"text": None, "explanation": "Marked approved, but the current version no longer meets the approval policy: "
                             + (" | ".join(status["blocking"]) or "the approved version is not the current one.")},
                "asset_ids": [item.id], "action": "Re-review and re-approve the current version before publishing.",
                "link": {"page": "studio", "id": item.id, "tab": "approval"}, "version_number": version.version_number,
            })

    # Cross-asset risks from the consistency graph.
    if campaign.brief:
        texts.insert(0, {"id": "brief", "title": "Approved brief", "text": campaign.brief, "is_brief": True})
    if len([t for t in texts if not t["is_brief"]]) >= 2:
        rules = db.query(BrandRule).filter(BrandRule.brand_id == campaign.brand_id).all()
        claims = db.query(ApprovedClaim).filter(ApprovedClaim.brand_id == campaign.brand_id).all()
        cons = intelligence.campaign_consistency(texts, rules, claims)
        facts = {f["id"]: f for f in cons["facts"]}
        titles = {t["id"]: t["title"] for t in texts}
        for iss in cons["issues"]:
            if iss["kind"] in ("confirmed_mismatch", "uncertain"):
                fact = facts[iss["fact_id"]]
                # One label per distinct value ("Nov 12" and "November 12, 2026" are the same date).
                by_value: Dict[str, str] = {}
                for m in fact["members"]:
                    norm = m["value"][:5] if fact["type"] == "date" else m["value"]
                    by_value.setdefault(norm, m["display"])
                values = sorted(by_value.values())
                add(f"mismatch:{fact['type']}:{'|'.join(values)}", {
                    "severity": "high" if iss["kind"] == "confirmed_mismatch" else "medium", "kind": "conflict",
                    "category": iss["kind"], "source": "consistency graph",
                    "basis": "detected" if iss["kind"] == "confirmed_mismatch" else "heuristic",
                    "title": f"Conflicting {fact['type']} across assets: {' vs '.join(values)}",
                    "evidence": {"text": None, "explanation": iss["explanation"],
                                 "passages": [{"asset": titles.get(m["asset_id"], m["asset_id"]), "asset_id": m["asset_id"],
                                               "value": m["display"], "passage": m["passage"]} for m in fact["members"]]},
                    "asset_ids": [a for a in iss["asset_ids"] if a != "brief"],
                    "action": "Align every asset with the approved brief / current source value.",
                    "link": {"page": "campaigns", "id": campaign.id},
                })
            elif iss["kind"] == "missing_information":
                # Same issue as each asset's own "required disclosure" finding: merge rather than double count.
                for aid in iss["asset_ids"]:
                    add(f"finding:{aid}:{iss['rule_id']}:{_norm('(Missing required disclosure)')}", {
                        "severity": "high", "kind": "finding", "category": "required_phrase", "source": "consistency graph",
                        "basis": "detected", "title": f"{titles.get(aid, aid)}: required disclosure missing",
                        "evidence": {"text": None, "explanation": iss["explanation"], "rule_id": iss["rule_id"]},
                        "asset_ids": [aid], "action": ACTIONS["required_phrase"],
                        "link": {"page": "studio", "id": aid, "tab": "findings"},
                    })

    ordered = sorted(risks.values(), key=lambda r: (-SEV_RANK[r["severity"]], r["kind"], r["title"]))
    counts = {s: sum(1 for r in ordered if r["severity"] == s) for s in ("critical", "high", "medium", "low")}
    top: Optional[str] = next((s for s in ("critical", "high", "medium", "low") if counts[s]), None)
    complete = not unverified and bool(assets_out)
    level = top or ("none_detected" if complete else "unknown")
    explanation = (
        f"Highest severity among {len(ordered)} de-duplicated risk(s) is {top}." if top else
        "No risks were detected in the analysed current versions." if complete else "No analysed assets yet."
    )
    if unverified:
        explanation += f" Incomplete: {len(unverified)} asset(s) have not been analysed, so their risks are unknown."
    return {
        "campaign_id": campaign.id, "name": campaign.name, "level": level, "complete": complete, "explanation": explanation,
        "method": "Level = highest severity of any de-duplicated risk. Severities come from the brand rule, the claim verdict "
                  "(contradicted = high, stale/needs review = medium, no evidence = low), cross-asset conflicts (confirmed = high, "
                  "uncertain = medium) and approval status. 'Heuristic' marks estimates (visual measurements, low-confidence "
                  "results, partial evidence); 'detected' marks exact rule matches, figure conflicts and policy states. "
                  "This is not a probability of harm.",
        "counts": counts, "risks": ordered, "assets": assets_out, "unverified": unverified,
        "basis_counts": {"detected": sum(1 for r in ordered if r["basis"] == "detected"),
                         "heuristic": sum(1 for r in ordered if r["basis"] == "heuristic")},
    }
