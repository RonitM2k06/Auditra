"""Brand DNA, rulebook contradiction detection, rule-change simulation, campaign consistency and replay diffs.

All functions here are pure (no database writes). Simulations work on copies of rules.
"""
import difflib
import re
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend import evidence
from backend.rule_engine import ComplianceRuleEngine

RULE_FIELDS = ("id", "name", "category", "description", "rule_text", "match_pattern",
               "suggested_replacement", "severity", "is_active", "source_reference")
CATEGORIES = {"prohibited_term", "preferred_term", "required_phrase", "restricted_claim", "tone_voice", "formatting_style"}
SEVERITIES = {"critical", "high", "medium", "low"}


def copy_rule(r) -> SimpleNamespace:
    return SimpleNamespace(**{k: getattr(r, k, None) for k in RULE_FIELDS})


def _pattern(r) -> str:
    return ((r.match_pattern or r.rule_text or "")).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    return bool(phrase) and re.search(rf"\b{re.escape(phrase)}\b", text or "", re.I) is not None


# ---------------------------------------------------------------------------
# Contradictions
# ---------------------------------------------------------------------------

def detect_contradictions(rules: Sequence[Any], approved_claims: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    active = [r for r in rules if r.is_active]
    forbidding = [r for r in active if r.category in ("prohibited_term", "restricted_claim")]
    out: List[Dict[str, Any]] = []

    def add(kind, certainty, rule_ids, title, explanation):
        out.append({"kind": kind, "certainty": certainty, "rule_ids": rule_ids, "title": title, "explanation": explanation})

    for req in [r for r in active if r.category == "required_phrase"]:
        for bad in forbidding:
            if _contains_phrase(_pattern(req), _pattern(bad)):
                add("required_contains_prohibited", "definite", [req.id, bad.id],
                    "A required disclosure contains prohibited wording",
                    f"'{req.name}' requires \"{_pattern(req)}\", which contains \"{_pattern(bad)}\" forbidden by '{bad.name}'. "
                    "Compliant content would always trigger the prohibition.")

    for r in active:
        repl = (r.suggested_replacement or "").strip()
        if not repl:
            continue
        for bad in forbidding:
            if bad.id != r.id and _contains_phrase(repl, _pattern(bad)):
                add("replacement_is_prohibited", "definite", [r.id, bad.id],
                    "A suggested replacement is itself prohibited",
                    f"'{r.name}' suggests \"{repl}\", but that text contains \"{_pattern(bad)}\" forbidden by '{bad.name}'.")
        for pref in [p for p in active if p.category == "preferred_term" and p.id != r.id]:
            if _contains_phrase(repl, _pattern(pref)):
                add("replacement_discouraged", "definite" if r.category == "preferred_term" else "possible", [r.id, pref.id],
                    "A suggested replacement uses discouraged terminology",
                    f"'{r.name}' suggests \"{repl}\", but '{pref.name}' asks to replace \"{_pattern(pref)}\" with \"{pref.suggested_replacement}\".")

    prefs = [r for r in active if r.category == "preferred_term"]
    for i, a in enumerate(prefs):
        for b in prefs[i + 1:]:
            if _pattern(a).lower() == _pattern(b).lower() and (a.suggested_replacement or "").lower() != (b.suggested_replacement or "").lower():
                add("conflicting_replacements", "definite", [a.id, b.id], "Two rules replace the same term differently",
                    f"\"{_pattern(a)}\" should become \"{a.suggested_replacement}\" ('{a.name}') and \"{b.suggested_replacement}\" ('{b.name}').")

    for req in [r for r in active if r.category == "required_phrase"]:
        for pref in prefs:
            if _contains_phrase(_pattern(req), _pattern(pref)):
                add("required_contains_discouraged", "definite", [req.id, pref.id],
                    "A required disclosure uses discouraged terminology",
                    f"'{req.name}' requires \"{_pattern(req)}\", but '{pref.name}' discourages \"{_pattern(pref)}\".")

    for i, a in enumerate(active):
        for b in active[i + 1:]:
            pa, pb = _pattern(a).lower(), _pattern(b).lower()
            if not pa or not pb or a.category == "required_phrase" or b.category == "required_phrase":
                continue
            if pa == pb and a.category != b.category:
                add("same_pattern_different_outcome", "possible", [a.id, b.id], "Two rules match the same text with different outcomes",
                    f"Both '{a.name}' ({a.category.replace('_', ' ')}, {a.severity}) and '{b.name}' ({b.category.replace('_', ' ')}, {b.severity}) match \"{pa}\".")
            elif pa != pb and (_contains_phrase(pa, pb) or _contains_phrase(pb, pa)) and a.severity != b.severity:
                add("overlapping_patterns", "possible", [a.id, b.id], "Overlapping rules with different severities",
                    f"\"{pa}\" and \"{pb}\" overlap, so one passage can be flagged {a.severity} by '{a.name}' and {b.severity} by '{b.name}'.")

    claims = [c for c in approved_claims if getattr(c, "is_active", True)]
    for i, a in enumerate(claims):
        qa = evidence.extract_quantities(a.claim_statement)
        for b in claims[i + 1:]:
            if (a.topic or "").lower() != (b.topic or "").lower():
                continue
            qb = evidence.extract_quantities(b.claim_statement)
            for x in qa:
                for y in qb:
                    if x.unit and x.unit == y.unit and x.value != y.value:
                        ta, tb = set(evidence.tokenize(a.claim_statement)), set(evidence.tokenize(b.claim_statement))
                        overlap = len(ta & tb) / max(1, min(len(ta), len(tb)))
                        if overlap >= 0.4:
                            add("approved_claims_disagree", "possible", [a.id, b.id], "Approved claims on the same topic give different figures",
                                f"\"{a.claim_statement}\" vs \"{b.claim_statement}\" (topic: {a.topic}). They may describe different scopes; confirm which is current.")
                        break
    seen, unique = set(), []
    for c in out:
        key = (c["kind"], tuple(sorted(c["rule_ids"])))
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


# ---------------------------------------------------------------------------
# Brand DNA
# ---------------------------------------------------------------------------

def brand_dna(rules, claims, sources, policies, palette: List[str], has_logo: bool, finding_counts: Dict[str, int], today: str) -> Dict[str, Any]:
    active = [r for r in rules if r.is_active]

    def by(cat):
        return [r for r in active if r.category == cat]

    def rule_items(rs):
        return [{"rule_id": r.id, "label": r.name, "detail": _pattern(r) + (f" → {r.suggested_replacement}" if r.suggested_replacement and r.category == "preferred_term" else ""),
                 "severity": r.severity, "source": r.source_reference} for r in rs]

    def dim(key, label, items, explanation, evidence_kind, observed_cats=()):
        n = len(items)
        return {"key": key, "label": label, "status": "missing" if n == 0 else "thin" if n == 1 else "configured",
                "count": n, "items": items, "explanation": explanation, "evidence_kind": evidence_kind,
                "observed_findings": sum(finding_counts.get(c, 0) for c in observed_cats)}

    approved_sources = [s for s in sources if s.approval_status == "approved"]
    expired = [s for s in approved_sources if s.expiry_date and s.expiry_date < today]
    dims = [
        dim("tone", "Tone & voice", rule_items(by("tone_voice") + by("formatting_style")),
            "Phrases the brand avoids for tone, plus editorial style rules.", "rules", ("tone_voice", "formatting_style")),
        dim("terminology", "Terminology", rule_items(by("preferred_term")),
            "Discouraged terms and the brand's preferred wording.", "rules", ("preferred_term",)),
        dim("prohibited", "Prohibited language", rule_items(by("prohibited_term")),
            "Wording that must never appear.", "rules", ("prohibited_term",)),
        dim("disclosures", "Required disclosures", rule_items(by("required_phrase")),
            "Text every applicable asset must include.", "rules", ("required_phrase",)),
        dim("claims", "Claim restrictions", rule_items(by("restricted_claim")),
            "Claims that need special approval. AUDITRA also applies built-in checks for unverified outcome claims.", "rules",
            ("restricted_claim", "unverified_claim", "claim_contradicted", "claim_stale")),
        dim("evidence", "Approved claims & evidence",
            [{"label": c.claim_statement, "detail": f"{c.topic} · {c.evidence_source}", "source": c.verification_date} for c in claims if c.is_active]
            + [{"label": s.name, "detail": f"Source document · {s.file_format.upper()}"
                + (f" · expires {s.expiry_date}" if s.expiry_date else " · no expiry date supplied"),
                "source_id": s.id, "expired": bool(s.expiry_date and s.expiry_date < today)} for s in approved_sources],
            f"Claims registry entries and approved source documents used for verification. {len(expired)} approved source(s) have expired.",
            "registry+sources"),
        dim("visual", "Visual identity",
            [{"label": c, "detail": "Palette colour", "color": c} for c in palette] + ([{"label": "Reference logo", "detail": "Used for similarity checks"}] if has_logo else []),
            "Approved colours and reference logo used by creative checks." + ("" if has_logo else " No reference logo is configured."),
            "visual", ("visual_palette", "visual_logo", "visual_contrast")),
        dim("governance", "Risk & approval",
            [{"label": p.name, "detail": f"{p.condition_type.replace('_', ' ')} = {p.condition_value}"
              + (f" · needs {p.required_role}" if p.required_role else "") + f" · {p.min_approvals} approver(s)"
              + (" · evidence confirmation" if p.require_evidence_confirmation else "")} for p in policies if p.is_active],
            "Approval policies applied to high-risk content.", "policies"),
    ]
    contradictions = detect_contradictions(rules, claims)
    return {
        "dimensions": dims,
        "contradictions": contradictions,
        "summary": {
            "dimensions_configured": sum(1 for d in dims if d["status"] == "configured"),
            "dimensions_thin": sum(1 for d in dims if d["status"] == "thin"),
            "dimensions_missing": sum(1 for d in dims if d["status"] == "missing"),
            "active_rules": len(active), "inactive_rules": len(rules) - len(active),
            "definite_conflicts": sum(1 for c in contradictions if c["certainty"] == "definite"),
            "possible_conflicts": sum(1 for c in contradictions if c["certainty"] == "possible"),
            "expired_sources": len(expired),
        },
        "scoring_note": "No overall brand score is shown. Each dimension reports how many configured rules or records back it; "
                        "'thin' means a single record, 'missing' means none.",
    }


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def apply_changes(rules: Sequence[Any], changes: List[Dict[str, Any]]) -> List[SimpleNamespace]:
    proposed = [copy_rule(r) for r in rules]
    for i, ch in enumerate(changes):
        op = ch.get("op")
        if op == "add":
            data = ch.get("rule") or {}
            if data.get("category") not in CATEGORIES:
                raise ValueError("New rules need a valid category.")
            if data.get("severity", "medium") not in SEVERITIES:
                raise ValueError("Severity must be critical, high, medium or low.")
            if not (data.get("match_pattern") or data.get("rule_text")):
                raise ValueError("New rules need a match pattern.")
            proposed.append(SimpleNamespace(**{**{k: None for k in RULE_FIELDS}, "name": data.get("name") or "Proposed rule",
                                               "description": data.get("description") or "", "rule_text": data.get("rule_text") or data.get("match_pattern"),
                                               "severity": data.get("severity", "medium"), **{k: v for k, v in data.items() if k in RULE_FIELDS},
                                               "id": f"proposed-{i + 1}", "is_active": True}))
            continue
        target = next((r for r in proposed if r.id == ch.get("rule_id")), None)
        if not target:
            raise ValueError(f"Rule {ch.get('rule_id')} is not in this workspace.")
        if op == "disable":
            target.is_active = False
        elif op == "enable":
            target.is_active = True
        elif op == "delete":
            proposed.remove(target)
        elif op == "update":
            for k, v in (ch.get("rule") or {}).items():
                if k in RULE_FIELDS and k != "id":
                    if k == "severity" and v not in SEVERITIES:
                        raise ValueError("Severity must be critical, high, medium or low.")
                    setattr(target, k, v)
        else:
            raise ValueError("Change op must be add, update, disable, enable or delete.")
    return proposed


def finding_key(f: Dict[str, Any]) -> Tuple:
    return (f.get("rule_id") or f["category"], f["matched_text"].lower(), f["start_offset"])


def diff_findings(before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    b = {finding_key(f): f for f in before}
    a = {finding_key(f): f for f in after}
    gained = [a[k] for k in a if k not in b]
    lost = [b[k] for k in b if k not in a]
    changed = [{"before": b[k], "after": a[k]} for k in a if k in b and a[k]["severity"] != b[k]["severity"]]
    return {"gained": gained, "lost": lost, "severity_changed": changed, "unchanged": len([k for k in a if k in b]) - len(changed)}


def run_rules(text: str, rules, claims) -> List[Dict[str, Any]]:
    return [f.to_dict() for f in ComplianceRuleEngine(list(rules), list(claims)).analyze(text)]


# ---------------------------------------------------------------------------
# Campaign consistency
# ---------------------------------------------------------------------------

_UNUSED_DATE_RE = re.compile(
    r"\b(?P<m1>jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(?P<d1>\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(?P<y1>20\d\d))?"
    r"|\b(?P<d2>\d{1,2})(?:st|nd|rd|th)?\s+(?P<m2>jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?(?:,?\s+(?P<y2>20\d\d))?"
    r"|\b(?P<y3>20\d\d)-(?P<m3>\d{2})-(?P<d3>\d{2})\b",
    re.I,
)
FACT_STOP = evidence.STOPWORDS | {"only", "now", "just", "get", "new", "today", "start", "starting", "from", "plan"}


def _context(text: str, start: int, end: int, width: int = 6) -> set:
    before = re.findall(r"[A-Za-z][A-Za-z\-]+", text[max(0, start - 70):start])[-width:]
    after = re.findall(r"[A-Za-z][A-Za-z\-]+", text[end:end + 70])[:width]
    return {t for t in evidence.tokenize(" ".join(before + after)) if t not in FACT_STOP and not t.isdigit()}


def _sentence(text: str, start: int, end: int) -> Tuple[str, int, int]:
    s = max(text.rfind(".", 0, start), text.rfind("\n", 0, start), text.rfind("!", 0, start), text.rfind("?", 0, start)) + 1
    e_candidates = [i for i in (text.find(".", end), text.find("\n", end), text.find("!", end), text.find("?", end)) if i != -1]
    e = min(e_candidates) + 1 if e_candidates else len(text)
    raw = text[s:e]
    lead = len(raw) - len(raw.lstrip())
    return raw.strip(), s + lead, s + lead + len(raw.strip())


def extract_facts(text: str) -> List[Dict[str, Any]]:
    facts = []
    date_spans = []
    for month, day, year, ds, de, raw in evidence.extract_dates(text):
        date_spans.append((ds, de))
        sent, ss, se = _sentence(text, ds, de)
        facts.append({"type": "date", "value": f"{month:02d}-{day:02d}" + (f"-{year}" if year else ""), "display": raw,
                      "compare": (month, day), "unit": "date", "context": _context(text, ds, de),
                      "start": ds, "end": de, "passage": sent, "passage_start": ss, "passage_end": se})
    for m in evidence.QTY_RE.finditer(text):
        if any(s <= m.start() < e for s, e in date_spans):
            continue
        qs = evidence.extract_quantities(m.group(0))
        if not qs:
            continue
        q = qs[0]
        if q.unit in ("", "date"):
            continue  # bare numbers are too ambiguous to compare
        ftype = "price" if q.unit in "$€£₹" else "percentage" if q.unit == "%" else "quantity"
        sent, ss, se = _sentence(text, m.start(), m.end())
        facts.append({"type": ftype, "value": f"{q.value:g}", "display": m.group(0).strip(), "compare": q.value, "unit": q.unit,
                      "context": _context(text, m.start(), m.end()), "start": m.start(), "end": m.end(),
                      "passage": sent, "passage_start": ss, "passage_end": se})
    return facts


def _similarity(a: set, b: set) -> float:
    # Overlap coefficient: short contexts ("$49 per member per month") still match longer ones.
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def campaign_consistency(assets: List[Dict[str, Any]], rules: Sequence[Any], claims: Sequence[Any]) -> Dict[str, Any]:
    """assets: [{id, title, channel, text, is_brief}]"""
    clusters: List[Dict[str, Any]] = []
    for asset in assets:
        for f in extract_facts(asset["text"]):
            f = {**f, "asset_id": asset["id"]}
            best, best_sim = None, 0.0
            for c in clusters:
                if c["type"] != f["type"] or c["unit"] != f["unit"]:
                    continue
                sim = max(_similarity(f["context"], m["context"]) for m in c["members"])
                if sim > best_sim:
                    best, best_sim = c, sim
            if best and best_sim >= 0.3:
                best["members"].append(f)
                best["min_similarity"] = min(best["min_similarity"], best_sim)
            else:
                clusters.append({"type": f["type"], "unit": f["unit"], "members": [f], "min_similarity": 1.0})

    groups = []
    for i, c in enumerate(clusters):
        asset_ids = {m["asset_id"] for m in c["members"]}
        if len(asset_ids) < 2:
            continue
        values = {str(m["compare"]) for m in c["members"]}
        shared = set.intersection(*[m["context"] for m in c["members"]]) if c["members"] else set()
        label_terms = sorted(shared)[:3]
        if len(values) == 1:
            status = "consistent"
        elif c["min_similarity"] >= 0.5:
            status = "confirmed_mismatch"
        else:
            status = "uncertain"
        groups.append({
            "id": f"fact-{i + 1}", "type": c["type"], "label": c["type"].capitalize() + (f" · {' '.join(label_terms)}" if label_terms else ""),
            "status": status, "context_similarity": round(c["min_similarity"], 2),
            "members": [{"asset_id": m["asset_id"], "display": m["display"], "value": m["value"], "passage": m["passage"],
                         "start": m["start"], "end": m["end"], "passage_start": m["passage_start"], "passage_end": m["passage_end"]}
                        for m in c["members"]],
            "explanation": (
                "All assets state the same value." if status == "consistent" else
                f"Assets give different values ({', '.join(sorted({m['display'] for m in c['members']}))}) in passages about the same thing "
                f"(shared context: {', '.join(sorted(shared)) or 'n/a'})." if status == "confirmed_mismatch" else
                "Values differ, but the surrounding wording only partly overlaps, so these may describe different things. Needs human review."
            ),
        })

    issues = []
    for g in groups:
        if g["status"] != "consistent":
            issues.append({"kind": g["status"], "title": g["label"], "explanation": g["explanation"], "fact_id": g["id"],
                           "asset_ids": sorted({m["asset_id"] for m in g["members"]})})

    rule_hits = {}
    for a in assets:
        findings = run_rules(a["text"], rules, claims)
        rule_hits[a["id"]] = findings
    for req in [r for r in rules if r.is_active and r.category == "required_phrase"]:
        pattern = _pattern(req).lower()
        has = [a["id"] for a in assets if not a.get("is_brief") and pattern in a["text"].lower()]
        missing = [a["id"] for a in assets if not a.get("is_brief") and pattern not in a["text"].lower()]
        if missing:
            issues.append({"kind": "missing_information", "title": f"Required disclosure missing: {req.name}",
                           "explanation": f"\"{_pattern(req)}\" appears in {len(has)} asset(s) but is missing from {len(missing)}.",
                           "rule_id": req.id, "asset_ids": missing, "present_in": has})
    for a in assets:
        if a.get("is_brief"):
            continue
        for f in rule_hits[a["id"]]:
            if f["category"] in ("prohibited_term", "restricted_claim", "unverified_claim") and f["severity"] in ("critical", "high"):
                issues.append({"kind": "rule_conflict", "title": f"{a['title']}: {f['category'].replace('_', ' ')}",
                               "explanation": f["explanation"], "rule_id": f.get("rule_id"), "asset_ids": [a["id"]],
                               "passage": f["matched_text"], "start": f["start_offset"], "end": f["end_offset"],
                               "source_reference": f.get("source_reference")})
    return {"facts": groups, "issues": issues,
            "counts": {k: sum(1 for i in issues if i["kind"] == k) for k in ("confirmed_mismatch", "uncertain", "missing_information", "rule_conflict")}
            | {"consistent_facts": sum(1 for g in groups if g["status"] == "consistent")}}


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

def text_diff(a: str, b: str) -> List[Dict[str, str]]:
    ta = re.findall(r"\s+|[^\s]+", a or "")
    tb = re.findall(r"\s+|[^\s]+", b or "")
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=ta, b=tb, autojunk=False).get_opcodes():
        if op == "equal":
            out.append({"op": "equal", "text": "".join(ta[i1:i2])})
        else:
            if i2 > i1:
                out.append({"op": "delete", "text": "".join(ta[i1:i2])})
            if j2 > j1:
                out.append({"op": "insert", "text": "".join(tb[j1:j2])})
    return out


def compare_runs(before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> Dict[str, List]:
    """Matches findings across versions by rule/category and matched text (offsets move between versions)."""
    def key(f):
        return (f.get("rule_id") or f["category"], (f["matched_text"] or "").strip().lower())
    b: Dict[Tuple, List] = {}
    for f in before:
        b.setdefault(key(f), []).append(f)
    persisted, changed, new = [], [], []
    for f in after:
        k = key(f)
        if b.get(k):
            prev = b[k].pop(0)
            (changed if prev["severity"] != f["severity"] or prev.get("source_reference") != f.get("source_reference") else persisted).append(
                {"before": prev, "after": f} if prev["severity"] != f["severity"] or prev.get("source_reference") != f.get("source_reference") else f)
        else:
            new.append(f)
    resolved = [f for lst in b.values() for f in lst]
    return {"persisted": persisted, "changed": changed, "new": new, "resolved": resolved}


def diff_rule_snapshots(a: Optional[List[Dict]], b: Optional[List[Dict]]) -> Optional[Dict[str, List]]:
    if a is None or b is None:
        return None
    ma, mb = {r["id"]: r for r in a}, {r["id"]: r for r in b}
    return {
        "added": [mb[k] for k in mb if k not in ma],
        "removed": [ma[k] for k in ma if k not in mb],
        "changed": [{"before": ma[k], "after": mb[k], "fields": [f for f in RULE_FIELDS if ma[k].get(f) != mb[k].get(f)]}
                    for k in mb if k in ma and ma[k] != mb[k]],
    }
