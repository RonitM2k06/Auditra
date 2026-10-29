"""Source-expiry impact: which stored claims, assets and campaigns depend on each evidence source.

Relationships are only reported when a stored record establishes them:
  * confirmed  - a claim check from an asset's latest review run cites a passage of this source
                 (claim_checks.source_document_id); campaigns via campaign_assets membership.
  * historical - the citation exists only in an older run or an older version; shown, never re-verified.
  * possible   - no citation, but the check's stored details name this source as superseded or
                 expired support. The link is by document name only, so it is labelled as such.
Freshness uses only dates stored on the source record. Nothing is inferred from the text.
"""
import json
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend import policies as policy_engine
from backend.models import ContentItem, ContentVersion
from backend.models_r3 import Campaign, CampaignAsset, ClaimCheck, SourceDocument

AFFECTING = {"expired", "review_overdue", "retired"}


def freshness(doc: SourceDocument, today: date) -> Dict[str, Any]:
    if doc.approval_status == "retired":
        return {"status": "retired", "date": doc.expiry_date or doc.review_date or doc.effective_date,
                "reason": "Marked retired in the evidence library."}
    if doc.expiry_date and date.fromisoformat(doc.expiry_date) < today:
        return {"status": "expired", "date": doc.expiry_date, "reason": f"Expiry date {doc.expiry_date} has passed."}
    if doc.review_date and date.fromisoformat(doc.review_date) < today:
        return {"status": "review_overdue", "date": doc.review_date, "reason": f"Review date {doc.review_date} has passed."}
    if doc.expiry_date or doc.review_date:
        nxt = min(d for d in (doc.expiry_date, doc.review_date) if d)
        return {"status": "current", "date": nxt, "reason": f"Valid until at least {nxt}."}
    return {"status": "undated", "date": doc.effective_date,
            "reason": "No expiry or review date is recorded, so freshness cannot be determined."}


def _check_dict(c: ClaimCheck, item: ContentItem, version: ContentVersion, relation: str, basis: str) -> Dict[str, Any]:
    return {"claim_check_id": c.id, "review_run_id": c.review_run_id, "claim_text": c.claim_text, "status": c.status,
            "passage_id": c.passage_id, "passage_text": c.passage_text, "content_id": item.id, "title": item.title,
            "version_number": version.version_number, "relation": relation, "basis": basis,
            "checked_at": c.created_at.isoformat() if c.created_at else None}


def _latest_run_ids(db: Session, items: List[ContentItem]) -> Dict[str, Optional[str]]:
    out = {}
    for it in items:
        v = db.query(ContentVersion).filter(ContentVersion.content_id == it.id, ContentVersion.version_number == it.current_version_number).first()
        run = policy_engine.latest_run_for_version(db, v.id) if v else None
        out[it.id] = run.id if run else None
    return out


def source_impact(db: Session, doc: SourceDocument, today: Optional[date] = None) -> Dict[str, Any]:
    today = today or date.today()
    fresh = freshness(doc, today)
    direct = db.query(ClaimCheck).filter(ClaimCheck.source_document_id == doc.id).all()
    # Possible associations: stored verdict details that name this document without citing it.
    named = [c for c in db.query(ClaimCheck).join(ContentVersion, ClaimCheck.content_version_id == ContentVersion.id)
             .join(ContentItem, ContentVersion.content_id == ContentItem.id)
             .filter(ContentItem.brand_id == doc.brand_id, ClaimCheck.source_document_id.is_(None)).all()
             if doc.name in (c.details_json or "")]

    version_ids = {c.content_version_id for c in direct + named}
    versions = {v.id: v for v in db.query(ContentVersion).filter(ContentVersion.id.in_(version_ids)).all()} if version_ids else {}
    item_ids = {v.content_id for v in versions.values()}
    items = {i.id: i for i in db.query(ContentItem).filter(ContentItem.id.in_(item_ids)).all()} if item_ids else {}
    latest = _latest_run_ids(db, list(items.values()))

    claims, possible = [], []
    for c in direct:
        v = versions.get(c.content_version_id)
        it = items.get(v.content_id) if v else None
        if not it:
            continue
        current = latest.get(it.id) == c.review_run_id
        claims.append(_check_dict(c, it, v, "confirmed" if current else "historical",
                                  "Cited by the latest review of the current version." if current
                                  else f"Cited by an earlier review (v{v.version_number}); not the current assessment."))
    for c in named:
        v = versions.get(c.content_version_id)
        it = items.get(v.content_id) if v else None
        if it and latest.get(it.id) == c.review_run_id:
            possible.append(_check_dict(c, it, v, "possible", "The verdict notes mention this source by name but cite no passage from it."))
    # A check citing another source can still name this one (e.g. "expired_support"); that is also only possible.
    for c in db.query(ClaimCheck).filter(ClaimCheck.source_document_id.isnot(None), ClaimCheck.source_document_id != doc.id,
                                         ClaimCheck.details_json.contains(doc.name)).all():
        v = db.query(ContentVersion).filter(ContentVersion.id == c.content_version_id).first()
        it = db.query(ContentItem).filter(ContentItem.id == v.content_id, ContentItem.brand_id == doc.brand_id).first() if v else None
        if it and _latest_run_ids(db, [it]).get(it.id) == c.review_run_id:
            possible.append(_check_dict(c, it, v, "possible",
                                        "The verdict cites a different source; its notes name this one (for example as expired support)."))

    confirmed_ids = sorted({c["content_id"] for c in claims if c["relation"] == "confirmed"})
    assets = []
    for cid in confirmed_ids:
        it = items[cid]
        assets.append({"content_id": cid, "title": it.title, "status": it.status, "version_number": it.current_version_number,
                       "claims": sum(1 for c in claims if c["content_id"] == cid and c["relation"] == "confirmed"),
                       "approved": it.approved_version_id is not None})
    camp_rows = (db.query(Campaign, CampaignAsset).join(CampaignAsset, CampaignAsset.campaign_id == Campaign.id)
                 .filter(CampaignAsset.content_id.in_(confirmed_ids)).all()) if confirmed_ids else []
    campaigns: Dict[str, Dict[str, Any]] = {}
    for camp, link in camp_rows:
        e = campaigns.setdefault(camp.id, {"id": camp.id, "name": camp.name, "content_ids": [],
                                           "basis": "Contains an asset whose current claims cite this source."})
        e["content_ids"].append(link.content_id)

    notes = []
    if not direct and not possible:
        notes.append("No stored claim check cites this source, so no dependency can be established. "
                     "Content analysed before the source was added is not linked to it.")
    if any(c["relation"] == "historical" for c in claims):
        notes.append("Historical citations come from earlier reviews or versions. They are shown for traceability and are not re-verified.")
    if possible:
        notes.append("Possible associations are matched by document name in stored verdict notes, not by a cited passage.")
    return {
        "id": doc.id, "name": doc.name, "source_identifier": doc.source_identifier, "approval_status": doc.approval_status,
        "effective_date": doc.effective_date, "expiry_date": doc.expiry_date, "review_date": doc.review_date,
        "freshness": fresh, "affects": fresh["status"] in AFFECTING,
        "claims": claims, "possible": possible, "assets": assets, "campaigns": list(campaigns.values()), "notes": notes,
    }


def orphaned_citations(db: Session, brand_id: str) -> List[Dict[str, Any]]:
    """Claim checks whose cited source was deleted: the passage copy survives, the source record does not."""
    rows = (db.query(ClaimCheck, ContentVersion, ContentItem)
            .join(ContentVersion, ClaimCheck.content_version_id == ContentVersion.id)
            .join(ContentItem, ContentVersion.content_id == ContentItem.id)
            .filter(ContentItem.brand_id == brand_id, ClaimCheck.source_document_id.is_(None), ClaimCheck.passage_text.isnot(None)).all())
    latest = _latest_run_ids(db, list({it.id: it for _, _, it in rows}.values()))
    out = []
    for c, v, it in rows:
        if latest.get(it.id) != c.review_run_id:
            continue
        name = (json.loads(c.details_json or "{}").get("source") or {}).get("name")
        out.append({**_check_dict(c, it, v, "missing_source", "The cited source record no longer exists; only the stored passage copy remains."),
                    "source_name": name})
    return out
