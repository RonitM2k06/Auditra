"""Campaign audit pack: a JSON manifest and a PDF report built from one data snapshot.

Integrity scheme (also embedded in every manifest under integrity.scheme)
  1. Events: every audit_events row whose content_id is an asset of the campaign.
  2. Order: ascending (created_at, id).
  3. Canonical form of one event: the JSON object
        {"actor_name", "actor_role", "brand_id", "content_id", "created_at", "description", "event_type", "id", "metadata"}
     serialised with keys sorted, separators (",", ":"), no ASCII escaping, encoded as UTF-8.
     created_at is UTC "YYYY-MM-DDTHH:MM:SS.ffffffZ" (null if missing). metadata is the parsed
     event_metadata JSON; if it is not valid JSON it is {"_unparsed": "<raw text>"} and the event is
     reported as malformed.
  4. Chain: prev_0 = 64 zeros; hash_i = SHA-256(prev_i + "\n" + canonical_i) as lowercase hex, prev_(i+1) = hash_i.
     final_chain_hash = hash of the last event (or 64 zeros when there are none).
  5. manifest_sha256 = SHA-256 of the manifest serialised the same way with "manifest_sha256" removed.

What this does and does not show
  * Recomputing the chain detects any edit, insertion, removal or reordering of events in a copy of the
    manifest, relative to its final_chain_hash.
  * Each export stores its per-event hashes. The next export compares against them, which detects stored
    events that changed or disappeared between exports.
  * It is not a digital signature. It does not prove who wrote the events, gives no non-repudiation, and
    cannot detect a privileged operator who rewrites both the events and the stored anchors.
"""
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

from sqlalchemy.orm import Session

from backend import policies as policy_engine
from backend.models import AuditEvent, Brand, BrandRule, ContentItem, ContentVersion, Finding, ReviewDecision, ReviewRun
from backend.models_r3 import AuditPackExport, Campaign, CampaignAsset, ClaimCheck, ImageAsset, Publication, SourceDocument

GENESIS = "0" * 64
SCHEMA = "auditra.audit-pack/1"
EVENT_FIELDS = ("actor_name", "actor_role", "brand_id", "content_id", "created_at", "description", "event_type", "id", "metadata")
SCHEME_DOC = {
    "event_selection": "audit_events rows whose content_id is an asset of the campaign",
    "ordering": "ascending (created_at, id)",
    "canonical_event": "JSON object with keys " + ", ".join(EVENT_FIELDS) + "; sort_keys=True, separators=(',', ':'), "
                       "ensure_ascii=False, UTF-8. created_at = UTC 'YYYY-MM-DDTHH:MM:SS.ffffffZ' or null. "
                       "metadata = parsed event_metadata JSON, or {'_unparsed': raw} when it is not valid JSON.",
    "chain": "prev_0 = '0'*64; hash_i = sha256((prev_i + '\\n' + canonical_i).encode('utf-8')).hexdigest(); prev_(i+1) = hash_i",
    "final_chain_hash": "hash of the last event, or '0'*64 when there are no events",
    "manifest_sha256": "sha256 of the manifest canonicalised the same way, with the 'manifest_sha256' key removed",
    "not_a_signature": "A hash chain is not a digital signature. It gives no authenticity or non-repudiation guarantee and cannot "
                       "detect a privileged operator who rewrites both the events and the stored anchors.",
}


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ts(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def event_record(e: AuditEvent) -> Tuple[Dict[str, Any], List[str]]:
    problems = []
    try:
        meta = json.loads(e.event_metadata) if e.event_metadata else {}
    except (TypeError, ValueError):
        meta = {"_unparsed": e.event_metadata}
        problems.append("metadata is not valid JSON")
    if e.created_at is None:
        problems.append("missing timestamp")
    if not e.event_type or not e.id:
        problems.append("missing identifier or type")
    rec = {"actor_name": e.actor_name, "actor_role": e.actor_role, "brand_id": e.brand_id, "content_id": e.content_id,
           "created_at": ts(e.created_at), "description": e.description, "event_type": e.event_type, "id": e.id, "metadata": meta}
    return rec, problems


def chain(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out, prev = [], GENESIS
    for r in records:
        h = sha256(prev + "\n" + canonical({k: r.get(k) for k in EVENT_FIELDS}))
        out.append({"event": {k: r.get(k) for k in EVENT_FIELDS}, "prev_hash": prev, "hash": h})
        prev = h
    return out


def verify_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Independent check of a manifest: recompute every event hash, the links and the final hash."""
    prev, problems = GENESIS, []
    entries = manifest.get("audit_events", {}).get("chain", [])
    for i, entry in enumerate(entries):
        ev = entry.get("event") or {}
        if entry.get("prev_hash") != prev:
            problems.append(f"event {i} ({ev.get('id')}): prev_hash does not match the previous event's hash")
        h = sha256(prev + "\n" + canonical({k: ev.get(k) for k in EVENT_FIELDS}))
        if h != entry.get("hash"):
            problems.append(f"event {i} ({ev.get('id')}): content does not match its hash")
        prev = entry.get("hash") or h
    final = manifest.get("integrity", {}).get("final_chain_hash")
    if final != (prev if entries else GENESIS):
        problems.append("final_chain_hash does not match the last event hash")
    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    if manifest.get("manifest_sha256") and sha256(canonical(body)) != manifest["manifest_sha256"]:
        problems.append("manifest_sha256 does not match the manifest contents")
    return {"valid": not problems, "events_checked": len(entries), "problems": problems}


# ---------------------------------------------------------------- snapshot

def _run_block(db: Session, run: ReviewRun, rules: Dict[str, BrandRule], docs: Dict[str, SourceDocument], limits: List[str], label: str):
    findings = db.query(Finding).filter(Finding.review_run_id == run.id).order_by(Finding.start_offset, Finding.id).all()
    checks = db.query(ClaimCheck).filter(ClaimCheck.review_run_id == run.id).order_by(ClaimCheck.start_offset, ClaimCheck.id).all()
    claims = []
    for c in checks:
        src = (json.loads(c.details_json or "{}").get("source") or {})
        doc = docs.get(c.source_document_id) if c.source_document_id else None
        if c.status == "supported" and not c.passage_text:
            limits.append(f"{label}: a supported claim has no stored passage text.")
        if c.passage_text and not doc:
            limits.append(f"{label}: claim \"{c.claim_text[:60]}\" cites a source record that no longer exists; the stored passage copy is included.")
        claims.append({"id": c.id, "claim_text": c.claim_text, "status": c.status, "rationale": c.rationale,
                       "passage_id": c.passage_id, "passage_text": c.passage_text,
                       "source": {"document_id": c.source_document_id, "name": doc.name if doc else src.get("name"),
                                  "section": src.get("section"), "page": src.get("page"),
                                  "expiry_date": doc.expiry_date if doc else src.get("expiry_date"), "record_exists": doc is not None}
                       if (c.source_document_id or src) else None})
    return {
        "id": run.id, "created_at": ts(run.created_at), "engine": run.engine_type, "ai_status": run.ai_status, "risk_score": run.risk_score,
        "findings": [{"id": f.id, "severity": f.severity, "category": f.category, "rule_id": f.rule_id,
                      "rule_name": rules[f.rule_id].name if f.rule_id in rules else None, "rule_text": rules[f.rule_id].rule_text if f.rule_id in rules else None,
                      "matched_text": f.matched_text, "explanation": f.explanation, "source_reference": f.source_reference,
                      "finding_source": f.finding_source, "is_applied": bool(f.is_applied), "is_dismissed": bool(f.is_dismissed)} for f in findings],
        "claims": claims,
    }


def build_manifest(db: Session, campaign: Campaign, exported_by: str, export_id: str,
                   previous: Optional[AuditPackExport] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    brand = db.query(Brand).filter(Brand.id == campaign.brand_id).first()
    asset_ids = [a.content_id for a in db.query(CampaignAsset).filter(CampaignAsset.campaign_id == campaign.id).all()]
    items = db.query(ContentItem).filter(ContentItem.id.in_(asset_ids)).order_by(ContentItem.created_at, ContentItem.id).all() if asset_ids else []
    rules = {r.id: r for r in db.query(BrandRule).filter(BrandRule.brand_id == campaign.brand_id).all()}
    docs = {d.id: d for d in db.query(SourceDocument).filter(SourceDocument.brand_id == campaign.brand_id).all()}
    limits: List[str] = []
    if not items:
        limits.append("The campaign has no assets, so there is no content, review or approval evidence to report.")

    assets = []
    for it in items:
        versions = db.query(ContentVersion).filter(ContentVersion.content_id == it.id).order_by(ContentVersion.version_number).all()
        vnum = {v.id: v.version_number for v in versions}
        vblocks = []
        for v in versions:
            label = f"{it.title} v{v.version_number}"
            runs = db.query(ReviewRun).filter(ReviewRun.content_version_id == v.id).order_by(ReviewRun.created_at, ReviewRun.id).all()
            if not runs:
                limits.append(f"{label} was never analysed; it has no findings or claim verdicts.")
            img = db.query(ImageAsset).filter(ImageAsset.content_version_id == v.id).first()
            vblocks.append({"id": v.id, "version_number": v.version_number, "created_by": v.created_by, "created_at": ts(v.created_at),
                            "change_summary": v.change_summary, "text": v.body, "text_sha256": sha256(v.body or ""),
                            "text_origin": "ocr" if img else "authored",
                            "image": {"sha256": img.sha256, "mime_type": img.mime_type, "width": img.width, "height": img.height} if img else None,
                            "review_runs": [_run_block(db, r, rules, docs, limits, label) for r in runs]})
            if img:
                limits.append(f"{label} is an image creative: the pack includes its OCR text and image SHA-256, not the image itself.")
        decisions = db.query(ReviewDecision).filter(ReviewDecision.content_id == it.id).order_by(ReviewDecision.created_at, ReviewDecision.id).all()
        pubs = db.query(Publication).filter(Publication.content_id == it.id).order_by(Publication.created_at, Publication.id).all()
        attempts = db.query(AuditEvent).filter(AuditEvent.content_id == it.id,
                                               AuditEvent.event_type.in_(["content_published", "publish_refused", "publish_duplicate"])) \
            .order_by(AuditEvent.created_at, AuditEvent.id).all()
        if not decisions:
            limits.append(f"{it.title}: no approval decisions are recorded.")
        status = policy_engine.evaluate(db, it)
        assets.append({
            "id": it.id, "title": it.title, "content_type": it.content_type, "media_kind": it.media_kind, "status": it.status,
            "current_version_number": it.current_version_number, "approved_version_id": it.approved_version_id,
            "approved_version_number": vnum.get(it.approved_version_id), "approval_requirements_met": status["satisfied"],
            "approval_blocking": status["blocking"], "versions": vblocks,
            "decisions": [{"id": d.id, "decision": d.decision, "reviewer_name": d.reviewer_name, "reviewer_role": d.reviewer_role,
                           "reviewer_user_id": d.reviewer_user_id, "version_id": d.content_version_id, "version_number": vnum.get(d.content_version_id),
                           "evidence_confirmed": bool(d.evidence_confirmed), "comments": d.comments, "created_at": ts(d.created_at)} for d in decisions],
            "publications": [{"id": p.id, "version_number": p.version_number, "channel": p.channel, "status": p.status,
                              "body_sha256": p.body_sha256, "published_by": p.published_by, "created_at": ts(p.created_at),
                              "destination": json.loads(p.export_json).get("destination")} for p in pubs],
            "publish_attempts": [{"event_id": e.id, "event_type": e.event_type, "description": e.description, "created_at": ts(e.created_at)} for e in attempts],
        })

    # Audit events and chain.
    rows = db.query(AuditEvent).filter(AuditEvent.content_id.in_(asset_ids)).all() if asset_ids else []
    rows.sort(key=lambda e: (ts(e.created_at) or "", e.id or ""))
    records, malformed = [], []
    for e in rows:
        rec, problems = event_record(e)
        records.append(rec)
        if problems:
            malformed.append({"event_id": e.id, "problems": problems})
    entries = chain(records)
    final = entries[-1]["hash"] if entries else GENESIS

    checks = [{"check": "chain_recomputed", "result": "pass", "detail": f"{len(entries)} event(s) hashed in order."}]
    if malformed:
        checks.append({"check": "events_well_formed", "result": "fail", "detail": f"{len(malformed)} event(s) are malformed.", "events": malformed})
    else:
        checks.append({"check": "events_well_formed", "result": "pass", "detail": "Every event has an id, type, timestamp and valid metadata JSON."})
    changed: List[str] = []
    missing: List[str] = []
    if previous:
        prior = json.loads(previous.event_hashes_json or "{}")
        now_by_id = {}
        for entry in entries:
            ev = entry["event"]
            now_by_id[ev["id"]] = sha256(canonical({k: ev.get(k) for k in EVENT_FIELDS}))
        for eid, h in prior.items():
            if eid not in now_by_id:
                missing.append(eid)
            elif now_by_id[eid] != h:
                changed.append(eid)
        ok = not changed and not missing
        checks.append({"check": "matches_previous_export", "result": "pass" if ok else "fail", "previous_export_id": previous.id,
                       "previous_export_at": ts(previous.created_at),
                       "detail": (f"All {len(prior)} event(s) from the previous export are unchanged." if ok else
                                  f"{len(changed)} event(s) changed and {len(missing)} event(s) are missing since export {previous.id}."),
                       "changed_event_ids": changed, "missing_event_ids": missing})
    else:
        checks.append({"check": "matches_previous_export", "result": "not_available",
                       "detail": "This is the first export of this campaign, so there is no earlier anchor to compare stored events against."})
        limits.append("First export of this campaign: stored events could only be hashed, not compared against an earlier anchor.")

    if changed or missing or malformed:
        overall = "fail" if (changed or missing) else "incomplete"
    else:
        overall = "pass" if previous else "pass_unanchored"
    summary = {
        "pass": "The available events are well formed and match the previous export's stored hashes.",
        "pass_unanchored": "The available events are well formed and were hashed into a chain. No earlier export exists to compare them with.",
        "incomplete": "Some events are malformed; they are included and hashed as stored, but the record is incomplete.",
        "fail": "Stored events differ from, or are missing compared with, the previous export.",
    }[overall]
    if malformed:
        limits.append(f"{len(malformed)} audit event(s) are malformed (see integrity.checks).")
    limits.append("Only events linked to the campaign's assets are included; workspace-level events (rule, source and policy changes) are not chained here.")

    manifest = {
        "schema": SCHEMA,
        "export": {"id": export_id, "exported_at": ts(now), "exported_by": exported_by},
        "campaign": {"id": campaign.id, "name": campaign.name, "brief": campaign.brief, "created_by": campaign.created_by,
                     "created_at": ts(campaign.created_at), "brand": {"id": brand.id, "name": brand.name, "is_sample": bool(brand.is_sample)}},
        "assets": assets,
        "audit_events": {"count": len(entries), "chain": entries},
        "integrity": {"algorithm": "SHA-256 hash chain", "genesis": GENESIS, "final_chain_hash": final, "verification": overall,
                      "summary": summary, "checks": checks, "scheme": SCHEME_DOC, "digitally_signed": False},
        "limitations": list(dict.fromkeys(limits)),
    }
    manifest["manifest_sha256"] = sha256(canonical(manifest))
    return manifest


# ---------------------------------------------------------------- PDF

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def safe(text: Any) -> str:
    """Escape untrusted text for ReportLab paragraphs (which parse markup) and drop control characters."""
    if text is None:
        return "—"
    return escape(_CTRL.sub("", str(text))).replace("\n", "<br/>")


def render_pdf(m: Dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=8.5, leading=11)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, leading=9.5, textColor=colors.HexColor("#4a5565"))
    mono = ParagraphStyle("m", parent=small, fontName="Courier", fontSize=7, leading=9)
    h1, h2, h3 = ss["Title"], ss["Heading2"], ss["Heading3"]
    P = lambda t, s=body: Paragraph(safe(t), s)  # noqa: E731

    def table(rows, widths):
        t = Table(rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8cdd4")),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef1f4")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
        return t

    integ, exp, camp = m["integrity"], m["export"], m["campaign"]
    s: List[Any] = [Paragraph(safe(f"Campaign audit pack: {camp['name']}"), h1)]
    if camp["brand"]["is_sample"]:
        s.append(P("Fictional demo data (Northstar Cloud). Not a real company or campaign.", small))
    s += [table([[P("Field", small), P("Value", small)],
                 [P("Workspace"), P(camp["brand"]["name"])], [P("Campaign ID"), Paragraph(safe(camp["id"]), mono)],
                 [P("Export ID"), Paragraph(safe(exp["id"]), mono)], [P("Exported at (UTC)"), P(exp["exported_at"])],
                 [P("Exported by"), P(exp["exported_by"])], [P("Assets"), P(len(m["assets"]))],
                 [P("Audit events chained"), P(m["audit_events"]["count"])],
                 [P("Chain verification"), P(f"{integ['verification']}: {integ['summary']}")],
                 [P("Final chain hash"), Paragraph(safe(integ["final_chain_hash"]), mono)],
                 [P("Manifest SHA-256"), Paragraph(safe(m["manifest_sha256"]), mono)]], [40 * mm, 130 * mm]),
          Spacer(1, 4 * mm)]
    if camp.get("brief"):
        s += [Paragraph("Approved brief", h3), P(camp["brief"])]
    s += [Paragraph("What the integrity data shows", h3),
          P("The JSON manifest contains every chained event with its hash and previous hash. Recomputing the chain with the scheme "
            "in integrity.scheme detects edits to a copy of the manifest. Comparison with the previous export detects stored events that "
            "changed between exports. This pack is not digitally signed. A hash chain does not prove authenticity, gives no "
            "non-repudiation, and cannot detect a privileged operator who rewrites both the events and the stored anchors.", small)]
    s += [Paragraph("Integrity checks", h3),
          table([[P("Check", small), P("Result", small), P("Detail", small)]] +
                [[P(c["check"]), P(c["result"]), P(c["detail"])] for c in integ["checks"]], [45 * mm, 22 * mm, 103 * mm])]
    s += [Paragraph("Limitations and missing evidence", h3)] + [P(f"• {x}") for x in m["limitations"]]

    for a in m["assets"]:
        s += [PageBreak(), Paragraph(safe(a["title"]), h2),
              P(f"Asset {a['id']} · {a['content_type']} · {a['media_kind']} · status {a['status']} · current v{a['current_version_number']}"
                f" · approved version: {('v' + str(a['approved_version_number'])) if a['approved_version_number'] else 'none'}"
                f" · approval requirements met: {'yes' if a['approval_requirements_met'] else 'no'}", small)]
        for b in a["approval_blocking"]:
            s.append(P(f"Blocking: {b}", small))
        for v in a["versions"]:
            s += [Paragraph(safe(f"Version {v['version_number']} — {v['created_by']}, {v['created_at']}"), h3),
                  P(f"Version ID {v['id']} · {v['change_summary'] or ''} · text {v['text_origin']} · text SHA-256 {v['text_sha256']}", small),
                  P(v["text"])]
            if v["image"]:
                s.append(P(f"Image {v['image']['mime_type']} {v['image']['width']}×{v['image']['height']}, SHA-256 {v['image']['sha256']}", small))
            if not v["review_runs"]:
                s.append(P("Not analysed: no findings or claim verdicts exist for this version.", small))
            for r in v["review_runs"]:
                s.append(P(f"Review run {r['id']} at {r['created_at']} · engine {r['engine']} · risk score {r['risk_score']}", small))
                if r["findings"]:
                    s.append(table([[P(h, small) for h in ("Severity", "Finding", "Rule / reference", "State")]] +
                                   [[P(f["severity"]), P(f"{f['category']}: \"{f['matched_text']}\" — {f['explanation']}"),
                                     P(f["rule_name"] or f["source_reference"] or "built-in check"),
                                     P("dismissed" if f["is_dismissed"] else "applied" if f["is_applied"] else "open")] for f in r["findings"]],
                                   [18 * mm, 92 * mm, 42 * mm, 18 * mm]))
                else:
                    s.append(P("No findings in this run.", small))
                if r["claims"]:
                    s.append(table([[P(h, small) for h in ("Verdict", "Claim", "Cited source passage")]] +
                                   [[P(c["status"]), P(c["claim_text"]),
                                     P((f"{c['source']['name']}{' · ' + c['source']['section'] if c['source'].get('section') else ''}"
                                        f"{'' if c['source']['record_exists'] else ' (record deleted)'}: \"{c['passage_text']}\"")
                                       if c["source"] and c["passage_text"] else "No passage cited.")] for c in r["claims"]],
                                   [20 * mm, 60 * mm, 90 * mm]))
        s.append(Paragraph("Approval decisions", h3))
        s.append(table([[P(h, small) for h in ("When", "Decision", "Who", "Version", "Evidence confirmed", "Note")]] +
                       [[P(d["created_at"]), P(d["decision"]), P(f"{d['reviewer_name']} ({d['reviewer_role']})"), P(f"v{d['version_number']}"),
                         P("yes" if d["evidence_confirmed"] else "no"), P(d["comments"] or "")] for d in a["decisions"]],
                       [30 * mm, 22 * mm, 38 * mm, 14 * mm, 18 * mm, 48 * mm]) if a["decisions"] else P("No decisions recorded.", small))
        s.append(Paragraph("Publishing", h3))
        if a["publish_attempts"]:
            s.append(table([[P(h, small) for h in ("When", "Outcome", "Detail")]] +
                           [[P(p["created_at"]), P(p["event_type"]), P(p["description"])] for p in a["publish_attempts"]], [32 * mm, 30 * mm, 108 * mm]))
        else:
            s.append(P("No publishing attempts recorded.", small))

    s += [PageBreak(), Paragraph("Audit event chain", h2),
          P("Event ID and hash prefixes; full values are in the JSON manifest.", small),
          table([[P(h, small) for h in ("#", "Time (UTC)", "Event", "Actor", "Event ID", "Hash")]] +
                [[P(i), P(e["event"]["created_at"]), P(e["event"]["event_type"]), P(e["event"]["actor_name"]),
                  Paragraph(safe(e["event"]["id"]), mono), Paragraph(safe(e["hash"][:16]), mono)] for i, e in enumerate(m["audit_events"]["chain"])],
                [8 * mm, 34 * mm, 34 * mm, 30 * mm, 38 * mm, 26 * mm])
          if m["audit_events"]["chain"] else P("No audit events are linked to this campaign's assets.", small)]

    buf = io.BytesIO()
    footer = f"AUDITRA audit pack {exp['id']} · manifest {m['manifest_sha256'][:16]} · not digitally signed"

    def on_page(canvas, doc):
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#6a7282"))
        canvas.drawString(15 * mm, 8 * mm, footer)
        canvas.drawRightString(195 * mm, 8 * mm, f"Page {doc.page}")

    SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
                      title=f"Audit pack: {camp['name']}", author="AUDITRA").build(s, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
