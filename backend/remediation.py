"""Smart remediation: evidence-grounded fix suggestions, in-memory preview, and a single guarded apply.

Suggestion kinds
  wording         the rule supplies approved replacement wording (prohibited/preferred terms, tone, style)
  add_disclosure  append the rule's required disclosure text verbatim
  factual         a current source states a different figure; the replacement swaps in the source figure and
                  must be explicitly confirmed by a person, citing the passage
  evidence_needed no reliable source exists (stale, unsupported, needs review); no replacement is offered.
                  On text assets the claim can be removed (replacement exactly ""), never rewritten.
  creative        the issue is in an image; the artwork must be revised and re-uploaded

Nothing is saved until apply; apply creates one new version, resets approval and requires re-analysis.
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from backend import evidence
from backend.intelligence import text_diff
from backend.review_pipeline import compute_findings, verify_text

WORDING_CATEGORIES = {"prohibited_term", "preferred_term", "tone_voice", "formatting_style", "restricted_claim"}


def factual_tokens(text: str) -> set:
    """Figures and dates in a text. Changing these is a factual change."""
    return {q.text.lower().replace(" ", "") for q in evidence.extract_quantities(text or "")}


def factual_change_labels(before: str, after: str) -> List[str]:
    """Readable figures/dates that differ between two texts (as written, e.g. 'November 12, 2026')."""
    changed = factual_tokens(before) ^ factual_tokens(after)
    labels = {q.text for q in evidence.extract_quantities(before or "") + evidence.extract_quantities(after or "")
              if q.text.lower().replace(" ", "") in changed}
    return sorted(labels)


def suggestions(item, version, findings, claim_checks) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    image = item.media_kind == "image"
    for f in findings:
        if f.is_applied or f.is_dismissed or f.category.startswith("claim_"):
            continue
        base = {"id": f"f:{f.id}", "finding_id": f.id, "severity": f.severity, "category": f.category,
                "original": f.matched_text, "start": f.start_offset, "end": f.end_offset,
                "explanation": f.explanation, "source_reference": f.source_reference}
        if image:
            out.append({**base, "kind": "creative", "replacement": f.suggested_correction,
                        "note": "Text inside an image can't be edited here. Revise the artwork and upload it as a new version."})
        elif f.category == "required_phrase" and f.suggested_correction:
            out.append({**base, "kind": "add_disclosure", "original": "", "replacement": f.suggested_correction.strip(),
                        "note": "Appends the disclosure text exactly as configured in the rule."})
        elif f.category in WORDING_CATEGORIES and f.suggested_correction:
            factual = bool(factual_tokens(f.matched_text) ^ factual_tokens(f.suggested_correction))
            out.append({**base, "kind": "factual" if factual else "wording", "replacement": f.suggested_correction,
                        "requires_confirmation": factual,
                        "note": "Approved replacement wording from the brand rule." + (" It changes a figure, so confirm it is accurate." if factual else "")})
        elif f.end_offset > f.start_offset:
            out.append({**base, "kind": "manual", "replacement": None,
                        "note": "The rule gives no replacement. Rewrite the passage yourself; the preview re-checks it."})
    for c in claim_checks:
        if c.status == "supported":
            continue
        details = json.loads(c.details_json or "{}")
        src = details.get("source") or {}
        base = {"id": f"c:{c.id}", "claim_check_id": c.id, "severity": "high" if c.status == "contradicted" else "medium",
                "category": f"claim_{c.status}", "original": c.claim_text, "start": c.start_offset, "end": c.end_offset,
                "explanation": c.rationale, "evidence": {"passage": c.passage_text, "source": src.get("name"),
                                                         "section": src.get("section"), "expiry_date": src.get("expiry_date")}}
        conflicts = details.get("conflicting_quantities") or []
        if c.status == "contradicted" and conflicts and c.passage_text and not image:
            claim_fig, source_figs = conflicts[0]["claim"], conflicts[0]["source"]
            if len(source_figs) == 1 and claim_fig in c.claim_text:
                out.append({**base, "kind": "factual", "replacement": c.claim_text.replace(claim_fig, source_figs[0], 1),
                            "requires_confirmation": True,
                            "note": f"Uses the figure stated in {src.get('name')} ({source_figs[0]}). This changes a factual claim: "
                                    "confirm the source is correct before applying."})
                continue
        out.append({**base, "kind": "evidence_needed", "replacement": None, "removable": not image,
                    "note": {"stale": "The only supporting source is expired or overdue for review. Add a current source, or remove the claim.",
                             "unsupported": "No approved source supports this claim. Add evidence to the library, or remove or soften the claim.",
                             "needs_review": "Evidence is partial or ambiguous. A reviewer must decide; AUDITRA will not invent a replacement.",
                             "contradicted": ("The sources disagree or give several figures; choose the correct value manually, or remove the claim."
                                              if conflicts else "A source states the opposite of this claim. Remove it, or rewrite it by hand against the cited passage.")}[c.status]})
    return out


def apply_fixes(body: str, fixes: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """Applies span replacements right-to-left (so offsets stay valid), then appends disclosures."""
    spans = [f for f in fixes if f["kind"] != "add_disclosure"]
    appends = [f for f in fixes if f["kind"] == "add_disclosure"]
    spans.sort(key=lambda f: f["start"], reverse=True)
    last_start = len(body) + 1
    for f in spans:
        if f["end"] > last_start:
            raise ValueError("Two selected fixes overlap. Apply one, preview, then the other.")
        if body[f["start"]:f["end"]] != f["original"]:
            raise ValueError(f"\"{f['original'][:40]}\" no longer matches the current text. Re-run the analysis.")
        start, end = f["start"], f["end"]
        if f["replacement"] == "":  # a removal also takes one adjacent space, so no double spaces remain
            if body[end:end + 1] == " ":
                end += 1
            elif body[start - 1:start] == " ":
                start -= 1
        body = body[:start] + f["replacement"] + body[end:]
        last_start = start
    for f in appends:
        if f["replacement"].lower() not in body.lower():
            body = body.rstrip() + "\n\n" + f["replacement"]
    return body, spans + appends


def preview(body: str, new_body: str, rules, claims, index, brand_name: str) -> Dict[str, Any]:
    before = compute_findings(body, rules, claims, brand_name)
    after = compute_findings(new_body, rules, claims, brand_name)
    cb = {c["claim_text"]: c["status"] for c in verify_text(body, index)}
    ca = verify_text(new_body, index)
    key = lambda f: (f.get("rule_id") or f["category"], f["matched_text"].lower())  # noqa: E731
    bk, ak = {key(f) for f in before}, {key(f) for f in after}
    return {
        "before_body": body, "after_body": new_body, "diff": text_diff(body, new_body),
        "findings_before": len(before), "findings_after": len(after),
        "resolved": [f for f in before if key(f) not in ak], "introduced": [f for f in after if key(f) not in bk],
        "claims_after": [{"claim_text": c["claim_text"], "status": c["status"], "was": cb.get(c["claim_text"]),
                          "source": (c["source"] or {}).get("name")} for c in ca],
        "factual_changes": factual_change_labels(body, new_body),
    }
