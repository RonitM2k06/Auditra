"""Reproducible evaluation of AUDITRA's creative analysis and claim verification.

Run from the repo root:   python evaluation/run_eval.py
Writes evaluation/RESULTS.md and evaluation/results.json.

The datasets are small, fictional and written by the team. Results show whether the
pipeline behaves as designed on these cases; they are NOT estimates of real-world accuracy.
"""
import json
import os
import sys
from datetime import date
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image  # noqa: E402

from backend import evidence, vision  # noqa: E402
from backend.review_pipeline import compute_findings  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = date(2026, 10, 29)  # fixed so results are reproducible

# ---------------------------------------------------------------------------
# Rulebook used for the creative set (mirrors the seeded Northstar rules)
# ---------------------------------------------------------------------------
RULES = [
    SimpleNamespace(id="r-guarantee", name="No guarantees", category="prohibited_term", match_pattern="guarantees results", rule_text="", suggested_replacement=None, severity="critical", is_active=True, description="", source_reference=None),
    SimpleNamespace(id="r-riskfree", name="No risk-free", category="prohibited_term", match_pattern="100% risk-free", rule_text="", suggested_replacement=None, severity="critical", is_active=True, description="", source_reference=None),
    SimpleNamespace(id="r-users", name="Members not users", category="preferred_term", match_pattern="users", rule_text="", suggested_replacement="members", severity="medium", is_active=True, description="", source_reference=None),
    SimpleNamespace(id="r-disclaimer", name="Disclaimer", category="required_phrase", match_pattern="Results may vary based on client workload", rule_text="", suggested_replacement=None, severity="high", is_active=True, description="", source_reference=None),
]
PALETTE = ["#0F9D91", "#101B2D", "#FFFFFF", "#E9EEF2", "#5B6B7F"]

# Expected labels per sample creative (finding categories that should / should not appear).
CREATIVES = {
    "01-compliant-atlas.png": {"expect": set(), "logo": "match"},
    "02-violations-guarantee.png": {"expect": {"prohibited_term", "required_phrase", "visual_contrast", "visual_palette", "visual_logo"}, "logo": "not_found"},
    "03-terminology-uptime.png": {"expect": {"preferred_term", "required_phrase"}, "logo": "match"},
    "04-low-contrast.png": {"expect": {"visual_contrast"}, "logo": "match"},  # logo is present in this creative
}
TRACKED = {"prohibited_term", "preferred_term", "required_phrase", "visual_contrast", "visual_palette", "visual_logo"}

# ---------------------------------------------------------------------------
# Claim set: verified against the three sample source documents
# ---------------------------------------------------------------------------
CLAIMS = [
    ("Northstar maintains a 99.995% uptime SLA backed by multi-region automated failover.", "supported"),
    ("Northstar Cloud is available in 14 regions.", "supported"),
    ("Northstar accelerates enterprise workload throughput by up to 34% within 90 days.", "supported"),
    ("Atlas Pro costs $49 per member per month.", "supported"),
    ("Atlas Pro launches on November 12, 2026.", "supported"),
    ("Every new Atlas Pro workspace includes a 14-day free trial.", "supported"),
    ("Northstar is SOC 2 Type II certified.", "supported"),
    ("Northstar maintains a 99.9% uptime SLA.", "contradicted"),
    ("Northstar Cloud is available in 20 regions.", "contradicted"),
    ("Atlas Pro costs $59 per member per month.", "contradicted"),
    ("Atlas Pro launches on November 14, 2026.", "contradicted"),
    ("Every new Atlas Pro workspace includes a 30-day free trial.", "contradicted"),
    ("Northstar accelerates workload throughput by up to 50% within 90 days.", "contradicted"),
    ("Northstar is ISO 27001 certified for its managed control plane.", "stale"),
    ("Customer data is encrypted at rest with AES-256.", "stale"),
    ("Northstar is the fastest cloud platform in the world.", "unsupported"),
    ("Northstar cuts infrastructure costs by 40% for every customer.", "unsupported"),
    ("Northstar is trusted by 10,000 banks worldwide.", "unsupported"),
    ("Northstar won the 2026 Cloud Innovation Award.", "unsupported"),
    ("Northstar is HIPAA certified for regulated workloads.", "needs_review"),
    ("Northstar guarantees 99.995% uptime for every workload.", "needs_review"),
]

SOURCES = [
    ("northstar-fact-sheet-2026.md", "Northstar Product Fact Sheet 2026", "2026-01-15", "2027-01-15", None),
    ("northstar-pricing-2025.md", "Northstar Pricing Sheet 2025", "2025-01-01", "2025-12-31", None),
    ("northstar-security-overview.txt", "Security & Compliance Overview", None, None, "2026-03-01"),
]
# Which document a correct retrieval should cite for each label (None = any / no citation needed).
EXPECTED_DOC = {
    "Northstar is ISO 27001 certified for its managed control plane.": "Security & Compliance Overview",
    "Customer data is encrypted at rest with AES-256.": "Security & Compliance Overview",
    "Northstar is HIPAA certified for regulated workloads.": "Security & Compliance Overview",
}


def build_index():
    passages = []
    for fname, name, eff, exp, rev in SOURCES:
        with open(os.path.join(ROOT, "samples", "sources", fname), "rb") as fh:
            data = fh.read()
        fmt = evidence.detect_format(fname, data)
        for i, p in enumerate(evidence.split_passages(evidence.decode_text(data), fmt)):
            passages.append(evidence.IndexedPassage(id=f"{fname}#{i}", text=p["text"], section=p.get("section"), page=None,
                                                    document_id=fname, document_name=name, source_identifier=None,
                                                    effective_date=eff, expiry_date=exp, review_date=rev))
    return evidence.BM25Index(passages)


def eval_creatives():
    rows, tp, fp, fn = [], 0, 0, 0
    with open(os.path.join(ROOT, "samples", "brand", "northstar-logo.png"), "rb") as fh:
        logo = Image.open(fh).convert("RGB")
    for name, label in CREATIVES.items():
        with open(os.path.join(ROOT, "samples", "creatives", name), "rb") as fh:
            img, _ = vision.validate_image(fh.read())
        ocr = vision.run_ocr(img)
        findings = compute_findings(ocr["text"], RULES, [], "Northstar Cloud")
        visual = vision.analyse_visuals(img, ocr, PALETTE, logo)
        findings += vision.visual_findings(visual, ocr)
        got = {f["category"] for f in findings} & TRACKED
        exp = label["expect"]
        tp += len(got & exp)
        fp += len(got - exp)
        fn += len(exp - got)
        rows.append({"creative": name, "ocr_lines": len(ocr["lines"]), "mean_ocr_confidence": round(sum(l["confidence"] for l in ocr["lines"]) / max(1, len(ocr["lines"])), 3),
                     "expected": sorted(exp), "actual": sorted(got), "false_positives": sorted(got - exp), "missed": sorted(exp - got),
                     "logo_expected": label["logo"], "logo_actual": visual["logo"]["status"], "logo_score": visual["logo"].get("score")})
    return rows, {"true_positive_labels": tp, "false_positive_labels": fp, "missed_labels": fn,
                  "precision": round(tp / (tp + fp), 3) if tp + fp else None, "recall": round(tp / (tp + fn), 3) if tp + fn else None}


def eval_claims():
    index = build_index()
    rows, correct, cited_ok, cited_total = [], 0, 0, 0
    confusion = {}
    for text, expected in CLAIMS:
        v = evidence.verify_claim(text, index, today=TODAY)
        ok = v.status == expected
        correct += ok
        confusion.setdefault(expected, {}).setdefault(v.status, 0)
        confusion[expected][v.status] += 1
        doc = v.passage.document_name if v.passage else None
        if expected in ("supported", "contradicted", "stale"):
            cited_total += 1
            want = EXPECTED_DOC.get(text, "Northstar Product Fact Sheet 2026")
            cited_ok += doc == want
        rows.append({"claim": text, "expected": expected, "actual": v.status, "correct": ok, "cited_document": doc,
                     "coverage": round(v.coverage, 2), "rationale": v.rationale})
    falsely_supported = sum(1 for r in rows if r["actual"] == "supported" and r["expected"] != "supported")
    return rows, {"claims": len(rows), "correct": correct, "accuracy": round(correct / len(rows), 3),
                  "falsely_marked_supported": falsely_supported,
                  "retrieval_cited_expected_document": f"{cited_ok}/{cited_total}", "confusion": confusion}


def main():
    creative_rows, creative_summary = eval_creatives()
    claim_rows, claim_summary = eval_claims()
    out = {"date": TODAY.isoformat(), "creatives": {"summary": creative_summary, "rows": creative_rows},
           "claims": {"summary": claim_summary, "rows": claim_rows}}
    with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)

    lines = ["# AUDITRA evaluation results", "",
             "Generated by `python evaluation/run_eval.py` with a fixed evaluation date of "
             f"{TODAY.isoformat()}. Datasets are small, fictional and team-authored: these numbers show the pipeline "
             "behaves as designed on known cases, not real-world accuracy.", "",
             "## Creative analysis (4 labelled sample creatives)", "",
             f"Label-level precision **{creative_summary['precision']}**, recall **{creative_summary['recall']}** "
             f"({creative_summary['true_positive_labels']} correct labels, {creative_summary['false_positive_labels']} false positives, "
             f"{creative_summary['missed_labels']} missed).", "",
             "| Creative | OCR lines (mean conf.) | Expected | Actual | False positives | Missed | Logo (score) |", "|---|---|---|---|---|---|---|"]
    for r in creative_rows:
        lines.append(f"| {r['creative']} | {r['ocr_lines']} ({r['mean_ocr_confidence']}) | {', '.join(r['expected']) or 'none'} | {', '.join(r['actual']) or 'none'} | "
                     f"{', '.join(r['false_positives']) or 'none'} | {', '.join(r['missed']) or 'none'} | {r['logo_actual']} ({r['logo_score']}) |")
    lines += ["", f"## Claim verification ({claim_summary['claims']} claims against 3 sample sources)", "",
              f"Correct classification: **{claim_summary['correct']}/{claim_summary['claims']}** ({claim_summary['accuracy']}). "
              f"Claims wrongly marked *supported*: **{claim_summary['falsely_marked_supported']}**. "
              f"Retrieval cited the expected document for {claim_summary['retrieval_cited_expected_document']} claims that need a citation.", "",
              "| Claim | Expected | Actual | Cited source |", "|---|---|---|---|"]
    for r in claim_rows:
        lines.append(f"| {r['claim']} | {r['expected']} | {'✅ ' if r['correct'] else '❌ '}{r['actual']} | {r['cited_document'] or '—'} |")
    lines += ["", "## Known limitations", "",
              "- Lexical retrieval (BM25) misses paraphrases that share no words with the source.",
              "- Contradictions are only detected through differing figures/dates with the same unit; contradictory wording is routed to *needs review*.",
              "- Contrast is estimated from the two dominant colours in each OCR box; gradients and photos reduce reliability.",
              "- Logo similarity is template matching; recoloured or distorted logos can score low."]
    with open(os.path.join(HERE, "RESULTS.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(json.dumps({"creatives": creative_summary, "claims": {k: v for k, v in claim_summary.items() if k != 'confusion'}}, indent=2))


if __name__ == "__main__":
    main()
