"""Evidence ingestion, lexical retrieval (BM25) and conservative claim verification.

Design rules
  * Passages are stored verbatim; every verdict cites a stored passage id or none at all.
  * Word overlap alone never makes a claim "supported": every number in the claim must be
    found in the passage with the same unit, absolute wording must be backed explicitly,
    and most of the claim's content words must be present.
  * A conflicting number for the same unit makes a claim "contradicted" only when the
    passage is clearly about the same thing (high term overlap). Otherwise it is
    "needs_review".
  * Dates are only used when the source record has them; nothing is inferred.
"""
import io
import math
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_PDF_PAGES = 60
ALLOWED_FORMATS = {"txt", "md", "pdf"}

STOPWORDS = set("""
a an and are as at be been by for from has have in into is it its of on or our that the their this to was were will with
you your we us can more than up per all any each every also just over under about via across within not no
""".split())
NEGATIONS = {"not", "no", "never", "without", "cannot", "isn't", "doesn't", "won't", "unavailable"}
ABSOLUTE_TERMS = {"guarantee", "guaranteed", "guarantees", "always", "never", "100%", "best", "#1", "only", "first",
                  "fastest", "cheapest", "risk-free", "unlimited", "perfect", "zero"}
CLAIM_CUES = re.compile(
    r"\d|%|\$|€|£|₹|\b(fastest|best|leading|first|only|guarantee\w*|proven|certified|compliant|available|supports?|"
    r"reduces?|increases?|improves?|faster|cheaper|uptime|sla|iso|soc ?2|gdpr|hipaa|award\w*|rated|trusted by|"
    r"launch\w*|includes?|free|unlimited|risk-free|#1|never|always)\b",
    re.I,
)
UNIT_ALIASES = {
    "percent": "%", "per cent": "%", "pct": "%",
    "days": "day", "day": "day", "hours": "hour", "hour": "hour", "hrs": "hour", "minutes": "minute", "min": "minute",
    "months": "month", "month": "month", "years": "year", "year": "year", "weeks": "week", "week": "week",
    "x": "x", "times": "x", "ms": "ms", "seconds": "second", "second": "second",
    "regions": "region", "region": "region", "customers": "customer", "members": "member", "countries": "country",
    "users": "user", "seats": "seat", "gb": "gb", "tb": "tb",
}
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                "ten": 10, "twelve": 12, "fourteen": 14, "fifteen": 15, "twenty": 20, "thirty": 30, "sixty": 60, "ninety": 90}
QTY_RE = re.compile(
    r"(?P<cur>[$€£₹])\s?(?P<num1>\d[\d,]*(?:\.\d+)?)"
    r"|(?P<num2>\d[\d,]*(?:\.\d+)?)\s?(?:-\s?)?(?P<unit>%|percent|per cent|x\b|times|days?|hours?|hrs|minutes?|min\b|months?|years?|weeks?|ms\b|seconds?|regions?|customers?|members?|countries|users|seats|gb\b|tb\b)?"
    r"|\b(?P<word>one|two|three|four|five|six|seven|eight|nine|ten|twelve|fourteen|fifteen|twenty|thirty|sixty|ninety)\b[\s-]+(?P<unit2>days?|hours?|months?|years?|weeks?|times|regions?|countries)",
    re.I,
)


def tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9#%][a-z0-9%\-\.]*", text.lower())
    out = []
    for t in tokens:
        t = t.strip(".-")
        if not t or t in STOPWORDS:
            continue
        if len(t) > 4 and t.endswith("s") and not t.endswith(("ss", "as", "is", "us")):
            t = t[:-1]  # light plural folding
        out.append(t)
    return out


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str  # %, $, day, x, "" (bare number) ...
    text: str


MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
DATE_RE = re.compile(
    r"\b(?P<m1>jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(?P<d1>\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(?P<y1>20\d\d))?"
    r"|\b(?P<d2>\d{1,2})(?:st|nd|rd|th)?\s+(?P<m2>jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?(?:,?\s+(?P<y2>20\d\d))?"
    r"|\b(?P<y3>20\d\d)-(?P<m3>\d{2})-(?P<d3>\d{2})\b",
    re.I,
)


def extract_dates(text: str) -> List[Tuple[int, int, Optional[str], int, int, str]]:
    """(month, day, year-or-None, start, end, matched text) for each calendar date mentioned."""
    out = []
    for m in DATE_RE.finditer(text):
        if m.group("m1"):
            month, day, year = MONTHS[m.group("m1")[:3].lower()], int(m.group("d1")), m.group("y1")
        elif m.group("m2"):
            month, day, year = MONTHS[m.group("m2")[:3].lower()], int(m.group("d2")), m.group("y2")
        else:
            month, day, year = int(m.group("m3")), int(m.group("d3")), m.group("y3")
        if 1 <= month <= 12 and 1 <= day <= 31:
            out.append((month, day, year, m.start(), m.end(), m.group(0)))
    return out


def extract_quantities(text: str) -> List[Quantity]:
    out: List[Quantity] = []
    dates = extract_dates(text)
    for month, day, _, _, _, raw in dates:
        out.append(Quantity(float(month * 100 + day), "date", raw))
    for m in QTY_RE.finditer(text):
        if any(s <= m.start() < e for _, _, _, s, e, _ in dates):
            continue
        if m.group("cur"):
            out.append(Quantity(float(m.group("num1").replace(",", "")), m.group("cur"), m.group(0).strip()))
        elif m.group("num2"):
            unit = (m.group("unit") or "").lower()
            unit = UNIT_ALIASES.get(unit, unit)
            try:
                value = float(m.group("num2").replace(",", ""))
            except ValueError:
                continue
            out.append(Quantity(value, unit, m.group(0).strip()))
        elif m.group("word"):
            unit = UNIT_ALIASES.get(m.group("unit2").lower(), m.group("unit2").lower())
            out.append(Quantity(float(NUMBER_WORDS[m.group("word").lower()]), unit, m.group(0).strip()))
    # Bare numbers that are years (2024, 2026) are dates, not quantities to compare.
    return [q for q in out if not (q.unit == "" and 1900 <= q.value <= 2100)]


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def detect_format(filename: str, data: bytes) -> str:
    if data[:5] == b"%PDF-":
        return "pdf"
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    if ext in ("md", "markdown"):
        return "md"
    if ext == "txt":
        return "txt"
    raise ValueError("Unsupported file type. Upload UTF-8 .txt, Markdown (.md) or PDF.")


def decode_text(data: bytes) -> str:
    if b"\x00" in data[:4096]:
        raise ValueError("The file looks binary, not text. Upload UTF-8 text, Markdown or PDF.")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("The file is not valid UTF-8 text.")


def split_passages(text: str, fmt: str) -> List[Dict]:
    """Splits text into paragraph-level passages, keeping the nearest Markdown heading as section."""
    passages: List[Dict] = []
    section: Optional[str] = None
    buf: List[str] = []

    def flush():
        joined = " ".join(s.strip() for s in buf).strip()
        if len(joined) >= 12:
            # Long paragraphs are split on sentence boundaries into ~700-char chunks.
            while len(joined) > 900:
                cut = joined.rfind(". ", 0, 700)
                cut = cut + 1 if cut > 200 else 700
                passages.append({"section": section, "text": joined[:cut].strip()})
                joined = joined[cut:].strip()
            passages.append({"section": section, "text": joined})
        buf.clear()

    for line in text.splitlines():
        stripped = line.strip()
        heading = re.match(r"^#{1,6}\s+(.*)$", stripped) if fmt == "md" else None
        if heading:
            flush()
            section = heading.group(1).strip()[:250]
        elif not stripped:
            flush()
        elif re.match(r"^([-*•]|\d+[.)])\s+", stripped):
            flush()
            buf.append(re.sub(r"^([-*•]|\d+[.)])\s+", "", stripped))
            flush()
        else:
            buf.append(stripped)
    flush()
    return passages


def extract_pdf(data: bytes) -> List[Dict]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise ValueError("PDF support is not installed on this server.") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError(f"PDF has {len(reader.pages)} pages; the limit is {MAX_PDF_PAGES}.")
        out = []
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            for p in split_passages(text, "txt"):
                p["page"] = i
                out.append(p)
        return out
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("The PDF could not be read. It may be corrupt or image-only (scanned PDFs need OCR first).") from exc


def parse_iso_date(value: Optional[str]) -> Optional[str]:
    if value is None or not str(value).strip():
        return None
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        raise ValueError(f"'{value}' is not a date in YYYY-MM-DD format.")


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

@dataclass
class IndexedPassage:
    id: str
    text: str
    section: Optional[str]
    page: Optional[int]
    document_id: str
    document_name: str
    source_identifier: Optional[str]
    effective_date: Optional[str]
    expiry_date: Optional[str]
    review_date: Optional[str]
    tokens: List[str] = field(default_factory=list)


class BM25Index:
    def __init__(self, passages: Sequence[IndexedPassage], k1: float = 1.4, b: float = 0.75):
        self.passages = list(passages)
        for p in self.passages:
            p.tokens = tokenize(p.text + " " + (p.section or ""))
        self.k1, self.b = k1, b
        self.avgdl = (sum(len(p.tokens) for p in self.passages) / len(self.passages)) if self.passages else 0.0
        self.df: Dict[str, int] = {}
        for p in self.passages:
            for t in set(p.tokens):
                self.df[t] = self.df.get(t, 0) + 1

    def search(self, query: str, top_k: int = 3) -> List[Tuple[IndexedPassage, float]]:
        q = tokenize(query)
        if not q or not self.passages:
            return []
        n = len(self.passages)
        scored = []
        for p in self.passages:
            tf: Dict[str, int] = {}
            for t in p.tokens:
                tf[t] = tf.get(t, 0) + 1
            score = 0.0
            for t in set(q):
                if t not in tf:
                    continue
                idf = math.log(1 + (n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                denom = tf[t] + self.k1 * (1 - self.b + self.b * len(p.tokens) / (self.avgdl or 1))
                score += idf * tf[t] * (self.k1 + 1) / denom
            if score > 0:
                scored.append((p, score))
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]


# ---------------------------------------------------------------------------
# Claim extraction and verification
# ---------------------------------------------------------------------------

@dataclass
class CandidateClaim:
    text: str
    start: int
    end: int


def extract_claims(text: str) -> List[CandidateClaim]:
    """Sentence-level candidates that state a checkable fact (numbers, superlatives, capability verbs)."""
    claims = []
    # Sentence ends at . ! ? followed by whitespace/end, so "99.9%" stays in one sentence.
    for m in re.finditer(r"(?:[^.!?\n]|[.!?](?=[^\s.!?]))+[.!?]*", text):
        sentence = m.group(0)
        stripped = sentence.strip()
        if len(stripped) < 12 or len(tokenize(stripped)) < 3:
            continue
        if re.match(r"^(disclaimer|terms|note)\b", stripped, re.I):
            continue  # disclosures are checked by rules, not as marketing claims
        if not CLAIM_CUES.search(stripped):
            continue
        lead = len(sentence) - len(sentence.lstrip())
        claims.append(CandidateClaim(stripped, m.start() + lead, m.start() + lead + len(stripped)))
    return claims


def _has_negation_near(tokens_text: str, terms: set) -> bool:
    words = re.findall(r"[a-z']+", tokens_text.lower())
    for i, w in enumerate(words):
        if w in NEGATIONS:
            window = set(words[max(0, i - 4): i + 5])
            if window & terms:
                return True
    return False


@dataclass
class Verdict:
    status: str
    rationale: str
    passage: Optional[IndexedPassage]
    score: float
    coverage: float
    details: Dict


def verify_claim(claim: str, index: BM25Index, today: Optional[date] = None) -> Verdict:
    today = today or date.today()
    hits = index.search(claim, top_k=3)
    claim_terms = set(tokenize(claim))
    claim_qty = extract_quantities(claim)
    absolute = sorted({t for t in ABSOLUTE_TERMS if re.search(rf"(?<![\w#]){re.escape(t)}(?!\w)", claim.lower())})

    if not hits:
        return Verdict("unsupported", "No approved source passage shares meaningful terms with this claim. "
                       "This means no evidence was found, not that the claim is false.", None, 0.0, 0.0,
                       {"absolute_terms": absolute, "quantities": [q.text for q in claim_qty]})

    best: Optional[Verdict] = None
    verdicts: List[Verdict] = []
    for passage, score in hits:
        p_terms = set(passage.tokens)
        coverage = len(claim_terms & p_terms) / len(claim_terms) if claim_terms else 0.0
        p_qty = extract_quantities(passage.text)
        matched, conflicts, missing = [], [], []
        for q in claim_qty:
            same_unit = [pq for pq in p_qty if pq.unit == q.unit]
            if any(abs(pq.value - q.value) < 1e-9 for pq in same_unit):
                matched.append(q.text)
            elif same_unit and q.unit:
                conflicts.append({"claim": q.text, "source": [pq.text for pq in same_unit]})
            else:
                missing.append(q.text)
        unbacked_absolute = [t for t in absolute if t not in passage.text.lower()]
        negation_mismatch = _has_negation_near(passage.text, claim_terms) != _has_negation_near(claim, claim_terms)
        details = {
            "coverage": round(coverage, 2), "matched_quantities": matched, "conflicting_quantities": conflicts,
            "missing_quantities": missing, "unbacked_absolute_terms": unbacked_absolute,
            "negation_mismatch": negation_mismatch, "quantities": [q.text for q in claim_qty],
        }

        if negation_mismatch and coverage >= 0.8 and not conflicts and not missing:
            # The passage states the same thing with the opposite polarity ("is not HIPAA certified").
            v = Verdict("contradicted", f"The source states the opposite of this claim ({int(coverage * 100)}% of the claim's terms "
                        "appear, but one side is negated).", passage, score, coverage, details)
        elif conflicts and coverage >= 0.5:
            c = conflicts[0]
            v = Verdict("contradicted", f"The source states {', '.join(c['source'])} where the claim says {c['claim']}, "
                        f"in a passage about the same topic ({int(coverage * 100)}% of the claim's terms appear).",
                        passage, score, coverage, details)
        elif (coverage >= 0.6 and not missing and not conflicts and not unbacked_absolute and not negation_mismatch
              and (claim_qty or coverage >= 0.75)):
            v = Verdict("supported", f"The passage contains {int(coverage * 100)}% of the claim's terms"
                        + (f" and the same figures ({', '.join(matched)})" if matched else "")
                        + ". A reviewer should still confirm the wording means the same thing.",
                        passage, score, coverage, details)
        elif coverage < 0.3:
            v = Verdict("unsupported", "The closest approved passage shares few terms with this claim, so it does not "
                        "establish it. No evidence found is not evidence the claim is false.", passage, score, coverage, details)
        else:
            reasons = []
            if missing:
                reasons.append(f"figure(s) {', '.join(missing)} not found in the passage")
            if conflicts:
                reasons.append("a figure differs but the passage may be about something else")
            if unbacked_absolute:
                reasons.append(f"absolute wording ({', '.join(unbacked_absolute)}) is not in the source")
            if negation_mismatch:
                reasons.append("the passage and claim differ in negation (possible contradiction)")
            if not reasons:
                reasons.append(f"only {int(coverage * 100)}% of the claim's terms appear")
            v = Verdict("needs_review", "Related evidence exists but does not clearly establish the claim: " + "; ".join(reasons) + ".",
                        passage, score, coverage, details)

        verdicts.append(v)
        rank = {"contradicted": 4, "supported": 3, "needs_review": 2, "unsupported": 1}
        if best is None or (rank[v.status], v.coverage) > (rank[best.status], best.coverage):
            best = v

    supporting = [v for v in verdicts if v.status == "supported"]
    def expired(v: Verdict) -> bool:
        return bool(v.passage and v.passage.expiry_date and date.fromisoformat(v.passage.expiry_date) < today)

    current_support = [v for v in supporting if not expired(v)]
    current_conflicts = [v for v in verdicts if not expired(v) and v.details.get("conflicting_quantities") and v.coverage >= 0.3]
    if best and best.status == "supported" and expired(best) and current_conflicts:
        # Only an expired source backs the figure; a current source states a different one.
        cur = current_conflicts[0]
        c = cur.details["conflicting_quantities"][0]
        cur.details["expired_support"] = f"{best.passage.document_name} (expired {best.passage.expiry_date})"
        best = Verdict("contradicted",
                       f"The current source {cur.passage.document_name} states {', '.join(c['source'])} where the claim says {c['claim']}. "
                       f"The claimed figure only appears in {best.passage.document_name}, which expired on {best.passage.expiry_date}.",
                       cur.passage, cur.score, cur.coverage, cur.details)
    elif best and best.status == "contradicted" and current_support and expired(best):
        # The conflicting figure comes from an expired source; a current source supports the claim.
        old_doc, old_exp = best.passage.document_name, best.passage.expiry_date
        best = current_support[0]
        best.details["superseded_conflict"] = f"{old_doc} (expired {old_exp}) gives a different figure"
        best.rationale += f" An expired source ({old_doc}, expired {old_exp}) gives a different figure and was not used."
    elif best and best.status == "contradicted" and supporting and not current_support:
        old = supporting[0].passage
        best.details["expired_support"] = f"{old.document_name} (expired {old.expiry_date})"
        best.rationale += f" The claimed figure only appears in {old.document_name}, which expired on {old.expiry_date}."
    elif best and best.status == "contradicted" and current_support:
        alt = current_support[0]
        best.status = "needs_review"
        best.details["supporting_passage_id"] = alt.passage.id
        best.details["supporting_document"] = alt.passage.document_name
        best.rationale = ("Approved sources disagree: one passage supports this claim ("
                          f"{alt.passage.document_name}) and another conflicts with it. " + best.rationale)

    # Staleness applies to the cited passage's document, using only dates the record actually has.
    if best and best.passage and best.status in ("supported", "contradicted", "needs_review"):
        exp, rev = best.passage.expiry_date, best.passage.review_date
        if exp and date.fromisoformat(exp) < today:
            best.details["stale_reason"] = f"source expired on {exp}"
            if best.status == "supported":
                best.status = "stale"
                best.rationale = f"The passage supports the claim, but its source expired on {exp}. Confirm the figure is still current."
            else:
                best.rationale += f" Note: the source expired on {exp}."
        elif rev and date.fromisoformat(rev) < today:
            best.details["stale_reason"] = f"source review date {rev} has passed"
            if best.status == "supported":
                best.status = "stale"
                best.rationale = f"The passage supports the claim, but the source's review date ({rev}) has passed."
    return best
