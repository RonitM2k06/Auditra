"""Build AUDITRA_Round3_Submission.pdf from the repository's verified facts.

Usage: python generate_round3_pdf.py
Evaluation numbers are read from evaluation/results.json (run evaluation/run_eval.py first).
Test counts below must match the last real `pytest` run; update TEST_RESULT if it changes.
"""
import json
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, SimpleDocTemplate, Spacer

from generate_submission_pdf import (
    AMBER, AMBER_BG, CONTENT_W, LINE, MARGIN, MUTED, NAVY, PAGE_H, PAGE_W, TEAL, bullets, callout, p, section, shot, table,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "AUDITRA_Round3_Submission.pdf")

REPO_URL = "https://github.com/RonitM2k06/Auditra"
# Leave empty until the Round 3 build is deployed and the URL has been opened and checked.
LIVE_URL = os.getenv("AUDITRA_R3_LIVE_URL", "")
TEST_RESULT = "63 passed, 0 failed (pytest, 29 Oct 2026)"

EVAL = json.load(open(os.path.join(ROOT, "evaluation", "results.json"), encoding="utf-8"))


def cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    x, y = MARGIN, PAGE_H - 70 * mm
    canvas.setFillColor(TEAL)
    canvas.roundRect(x, y, 16 * mm, 16 * mm, 3.5 * mm, stroke=0, fill=1)
    canvas.setStrokeColor(colors.white)
    canvas.setLineWidth(2.4)
    canvas.setLineCap(1)
    path = canvas.beginPath()
    path.moveTo(x + 4.6 * mm, y + 8.2 * mm)
    path.lineTo(x + 7.2 * mm, y + 5.6 * mm)
    path.lineTo(x + 11.8 * mm, y + 10.6 * mm)
    canvas.drawPath(path, stroke=1, fill=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 40)
    canvas.drawString(MARGIN, y - 22 * mm, "AUDITRA")
    canvas.setFont("Helvetica", 15)
    canvas.setFillColor(colors.HexColor("#CBD5E1"))
    canvas.drawString(MARGIN, y - 33 * mm, "Evidence-first brand governance")
    canvas.setFont("Helvetica", 11)
    canvas.drawString(MARGIN, y - 41 * mm, "Every claim traced to evidence. Every approval bound to a version.")
    canvas.setFillColor(TEAL)
    canvas.rect(MARGIN, y - 52 * mm, 30 * mm, 1.2 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(MARGIN, 60 * mm, "TechCircuit Round 3 — Final submission")
    canvas.setFont("Helvetica", 11)
    canvas.setFillColor(colors.HexColor("#CBD5E1"))
    canvas.drawString(MARGIN, 52 * mm, "Team Quoding")
    canvas.drawString(MARGIN, 45 * mm, "Arya Kashyap (Team Leader)  ·  Ronit Mongia  ·  Moli Verma")
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.drawString(MARGIN, 30 * mm, "Screenshots are from the running application with the fictional Northstar Cloud demo workspace.")
    canvas.restoreState()


def later(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN, PAGE_H - 12 * mm, PAGE_W - MARGIN, PAGE_H - 12 * mm)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(TEAL)
    canvas.drawString(MARGIN, PAGE_H - 10 * mm, "AUDITRA")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 10 * mm, "Team Quoding · Round 3 submission")
    canvas.drawRightString(PAGE_W - MARGIN, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build():
    c = EVAL["creatives"]["summary"]
    cl = EVAL["claims"]["summary"]
    W2 = [44 * mm, CONTENT_W - 44 * mm]
    story = [PageBreak()]

    story += section("1 · Executive summary", "From rule checker to governance system")
    story += [
        p("Marketing teams publish faster than legal and brand teams can review. AUDITRA checks copy <b>and image creatives</b> "
          "against a brand's rules and its <b>approved source documents</b> before anything ships. Each finding points to the passage, "
          "image region, rule or source behind it. Approval is enforced on the server by configurable policies and bound to an exact "
          "version, and only that version can be published."),
        p("Round 3 delivered the three committed improvements as working, tested vertical slices, plus three signature features:"),
        *bullets([
            "<b>Multimodal governance:</b> content-validated PNG/JPEG upload, on-server OCR with text boxes, the same rules on OCR text, "
            "WCAG contrast, palette Delta-E and logo similarity, all drawn on the creative.",
            "<b>Evidence-grounded claims:</b> TXT/Markdown/PDF sources split into stored passages, BM25 retrieval, and five conservative "
            "verdicts — supported, contradicted, stale, needs review, no evidence found.",
            "<b>Enterprise governance:</b> real accounts and sessions, per-workspace roles checked on every endpoint, approval policies, "
            "self-approval blocking, version-bound approvals and a guarded, idempotent publishing sandbox.",
            "<b>Brand DNA, Campaign consistency graph, Decision replay</b> — built on the same stored records, with no invented scores.",
        ]),
        callout(f"<b>Verification:</b> {TEST_RESULT}; frontend production build succeeds. Evaluation on fictional, team-authored data: "
                f"creatives {c['true_positive_labels']}/{c['true_positive_labels'] + c['missed_labels']} expected labels found with "
                f"{c['false_positive_labels']} false positives; claims {cl['correct']}/{cl['claims']} correctly classified with "
                f"<b>{cl['falsely_marked_supported']}</b> claims wrongly marked supported. These are not real-world accuracy figures."),
        PageBreak(),
    ]

    story += section("2 · Problem and value", "Why governance needs evidence, not just rules")
    story += [
        p("A rule checker can say a word is banned. It cannot say whether \"$59 per month\" matches the current price sheet, whether "
          "the banner's disclaimer is legible, or whether the version being published is the one legal approved. Those are the "
          "failures that cause real incidents: outdated prices, unsupported claims, and last-minute edits slipping past sign-off."),
        table([
            ["Risk", "How AUDITRA addresses it"],
            ["Unsupported or outdated claims", "Each claim is retrieved against approved sources; stale and contradicted claims trigger policies."],
            ["Text inside images escapes review", "OCR feeds image text through the same rules and claim checks, with regions on the image."],
            ["Inconsistent campaign facts", "Prices, dates and disclosures are compared across every asset and the brief."],
            ["Approval bypass", "Server-side roles and policies; approvals bound to a version; edits invalidate approval."],
            ["Publishing the wrong version", "Publish re-checks status, version and policies; refusals and duplicates are logged."],
        ], [60 * mm, CONTENT_W - 60 * mm]),
        PageBreak(),
    ]

    story += section("3 · Implemented features", "What works today")
    story += [table([
        ["Feature", "Status"],
        ["Round 2: workspaces, rulebook, claims registry, rule engine, optional AI step, corrections, versions, workflow, audit, dashboard", "Implemented (kept)"],
        ["Authentication: email/password (PBKDF2), demo personas, HttpOnly session cookies, logout revocation", "Implemented"],
        ["Authorisation: creator / reviewer / admin per workspace, enforced on every endpoint", "Implemented"],
        ["Approval policies, version-bound approvals, self-approval block, evidence confirmation", "Implemented"],
        ["Publishing: local sandbox connector with export record, idempotent per version", "Implemented (sandbox, not a live channel)"],
        ["Creative analysis: OCR, rules on OCR text, contrast, palette, logo similarity", "Implemented"],
        ["Evidence library and claim verification (TXT, MD, text PDF)", "Implemented"],
        ["Brand DNA, contradictions, rule-change simulation", "Implemented"],
        ["Campaign consistency graph", "Implemented"],
        ["Decision replay with rule snapshots and counterfactual", "Implemented (snapshots from Round 3 onward)"],
        ["SSO, live CMS/social connectors, scanned-PDF OCR, video", "Planned — not implemented"],
    ], [CONTENT_W - 52 * mm, 52 * mm]), PageBreak()]

    story += section("4 · Screens", "The running application")
    story += [
        shot("r3-02-creative-review.jpg", "Creative review: OCR text boxes (dashed), findings drawn as severity-coloured regions, and the rule behind a finding."),
        shot("r3-03-claim-evidence.jpg", "Claim evidence: \"$59 per member per month\" is contradicted by the current fact sheet; the cited passage, section and dates are shown."),
        PageBreak(),
        shot("r3-04-campaign-graph.jpg", "Campaign consistency: assets on the left, extracted facts on the right; the landing page disagrees on price and date, with passages side by side."),
        shot("r3-06-approval-policy.jpg", "Approval requirements: a critical finding triggers the two-approver policy; one approval is recorded, publishing would be refused."),
        PageBreak(),
        shot("r3-05-brand-dna.jpg", "Brand DNA: dimensions derived from configured rules, with the seeded rule conflict surfaced."),
        shot("r3-01-sign-in.jpg", "Sign-in: one-click demo personas for judges, plus real registration."),
        PageBreak(),
    ]

    story += section("5 · Architecture", "One FastAPI service, one analysis pipeline")
    story += [
        p("A React + TypeScript SPA talks to a FastAPI service over JSON. Every analysis runs through <font face='Courier'>review_pipeline.py</font>:"),
        *bullets([
            "Rule engine on the current version (exact offsets).",
            "For creatives: findings mapped back to OCR text boxes; contrast, palette and logo measured from pixels.",
            "Candidate claims retrieved against approved passages and classified; contradicted and stale claims become findings.",
            "Findings, claim checks and a snapshot of the rules, policies and sources in force are stored against the version.",
            "Policy evaluation determines what approval that version needs; publishing re-checks everything before writing the sandbox record.",
        ]),
        table([
            ["Module", "Responsibility"],
            ["auth.py", "Sessions, password hashing, explicit permission matrix, workspace scoping"],
            ["vision.py", "Upload validation, RapidOCR (ONNX), WCAG contrast, CIE Delta-E palette, template-matching logo similarity"],
            ["evidence.py", "Source ingestion (txt/md/pdf), passage splitting, BM25, claim extraction and verdicts"],
            ["policies.py", "Per-version policy evaluation: triggers, required role, distinct approvers, evidence confirmation"],
            ["intelligence.py", "Brand DNA, contradictions, in-memory simulation, campaign consistency, replay diffs"],
            ["migrations.py", "Additive, idempotent column migrations, tested on a copy of the Round 2 database"],
        ], W2),
        PageBreak(),
    ]

    story += section("6 · Commitment one", "Multimodal brand governance")
    story += [
        *bullets([
            "<b>Intake:</b> PNG/JPEG identified by magic bytes and full decode (never filename/MIME); 4 MB, 64–6000 px, 30 MP limits; corrupt, empty, oversized and renamed files rejected with clear errors; identical re-uploads refused; nothing written to disk.",
            "<b>OCR:</b> RapidOCR runs on the server; each line keeps its box and confidence. Lines under 80% confidence become a finding asking a human to check the transcription.",
            "<b>Rules:</b> the existing rule engine runs on the OCR transcript; matches are mapped back to image regions. Image text cannot be \"corrected\" in place — the reviewer is told to upload a revision, which becomes a new version.",
            "<b>Visual checks:</b> contrast from a two-colour split inside each text box (WCAG AA 4.5:1 / 3:1), flagged uncertain over varied backgrounds; palette share and CIE76 Delta-E to the brand palette; logo normalised cross-correlation against an admin-uploaded reference, explicitly not proof of authenticity.",
        ]),
        p("Evaluation", "h2"),
        table([["Creative", "Expected", "Found", "False pos.", "Missed"]] + [
            [r["creative"], ", ".join(r["expected"]) or "none", ", ".join(r["actual"]) or "none",
             ", ".join(r["false_positives"]) or "none", ", ".join(r["missed"]) or "none"] for r in EVAL["creatives"]["rows"]
        ], [40 * mm, 42 * mm, 42 * mm, 25 * mm, CONTENT_W - 149 * mm]),
        p("Four fictional creatives produced by <font face='Courier'>samples/generate_samples.py</font>. They were made during development, so the result shows designed behaviour, not generalisation.", "muted"),
        PageBreak(),
    ]

    story += section("7 · Commitment two", "Evidence-grounded claim verification")
    story += [
        *bullets([
            "<b>Sources:</b> UTF-8 text, Markdown (sections kept) and text-based PDF (page numbers kept). Name, identifier, effective, expiry and review dates and approval status are stored only when supplied. Pending and retired sources are not used.",
            "<b>Retrieval:</b> BM25 over stored passages. Every cited passage is a stored record; its text is copied onto the claim check so history survives source deletion.",
            "<b>Verdicts:</b> <i>supported</i> only when most claim terms and every figure (same unit) appear and no absolute wording is unbacked; <i>contradicted</i> when a current source gives a different figure/date for the same thing; <i>stale</i> when support comes only from an expired or overdue source; <i>needs review</i> for partial or negated evidence; <i>no evidence found</i> otherwise — explicitly not \"false\".",
            "<b>Governance link:</b> contradicted and stale claims can trigger approval policies requiring an approver to confirm the evidence was reviewed.",
        ]),
        p("Evaluation", "h2"),
        callout(f"{cl['claims']} claims against 3 sample sources: <b>{cl['correct']}/{cl['claims']}</b> classified as expected; "
                f"<b>{cl['falsely_marked_supported']}</b> wrongly marked supported; expected document cited for "
                f"{cl['retrieval_cited_expected_document']} claims that need a citation. Both errors were unsupported claims labelled "
                "\"needs review\" — the conservative direction."),
        table([["Claim", "Expected", "Actual"]] + [[r["claim"], r["expected"], r["actual"]] for r in EVAL["claims"]["rows"]],
              [CONTENT_W - 60 * mm, 30 * mm, 30 * mm]),
        PageBreak(),
    ]

    story += section("8 · Commitment three", "Enterprise governance and publishing")
    story += [
        table([
            ["Control", "Implementation"],
            ["Authentication", "PBKDF2-SHA256 (310k iterations, per-user salt); 256-bit session tokens stored as SHA-256; HttpOnly, SameSite=Lax, Secure on HTTPS; 12 h expiry; revoked on logout. No default admin credentials."],
            ["Authorisation", "Explicit permission matrix (creator / reviewer / admin) checked on every endpoint; non-members get 404; denials inside a workspace are audited."],
            ["CSRF / CORS", "State-changing calls require a custom header; CORS closed unless configured."],
            ["Approval policies", "Triggers: open finding >= severity, claim verdict, finding category. Requirements: role, distinct approvers, evidence confirmation. Admin-configurable."],
            ["Version binding", "Approvals must name the reviewed version; stale versions rejected; edits and revisions reset approval; authors cannot approve their own content; duplicate approvals refused."],
            ["Publishing", "Sandbox connector: refuses drafts, rejected, unapproved and stale versions; re-checks policies; one record per version (database unique constraint); repeats return the existing record; every attempt audited. Nothing is sent to a third party."],
            ["Audit", "Logins, logouts, rule/source/policy/member changes, analyses, corrections, decisions, publish attempts and permission denials. An application log in an ordinary table — not tamper-proof."],
        ], W2),
        PageBreak(),
    ]

    story += section("9–11 · Signature features", "Brand DNA, consistency graph, decision replay")
    story += [
        p("Brand DNA digital twin", "h2"),
        p("Eight dimensions (tone, terminology, prohibited language, disclosures, claim restrictions, claims & evidence, visual identity, "
          "risk & approval) are built only from stored records, each listing the rules or sources behind it and marked configured, thin or "
          "missing. No overall score is shown. Contradiction detection separates <b>definite</b> conflicts (a required disclosure containing "
          "prohibited wording, a replacement that is itself prohibited or discouraged, two replacements for one term) from <b>possible</b> ones "
          "(same pattern with different outcomes, overlapping patterns with different severities, approved claims with different figures). "
          "The simulator applies proposed changes to copies of the rules and reports gained/lost findings, policy impact and new conflicts per item; tests confirm the active data is unchanged."),
        p("Cross-channel consistency graph", "h2"),
        p("Campaigns group assets and an optional approved brief. Prices, percentages, quantities and dates are extracted with their sentence; "
          "values are only compared when their surrounding wording overlaps, and are labelled confirmed mismatch, uncertain or consistent. "
          "Missing required disclosures and high-severity rule conflicts are listed with links to fix each asset. Nothing is rewritten automatically. "
          "A test confirms unrelated numbers (\"40 engineers\" vs \"50 GB\") are not reported as contradictions."),
        p("Decision replay", "h2"),
        p("Compares any two versions: word-level diff; findings resolved, new, persisted or changed; the rulebook snapshot stored with each "
          "analysis (recorded from Round 3 onward — older runs are reported as having no snapshot rather than reconstructed); decisions; publications; "
          "and the audit timeline. Reviewers can run a counterfactual (disable a rule) on a historical version without changing anything."),
        PageBreak(),
    ]

    story += section("10 · Testing", "Methodology and results")
    story += [
        callout(f"<b>{TEST_RESULT}.</b> Frontend: <font face='Courier'>tsc -b &amp;&amp; vite build</font> succeeds. "
                "Tests use an isolated temporary SQLite database and never touch demo or production data."),
        *bullets([
            "Security: anonymous access, CSRF header, password hashing, session revocation after logout, creator->admin actions, reviewer edits, cross-workspace reads and writes, audited denials, last-admin protection.",
            "Workflow: unanalysed and stale-version approvals, missing version, notes required, self-approval, duplicate approval, two-approver policy, evidence-confirmation policy, approval reset on edit, invalid transitions.",
            "Publishing: drafts, creators, unknown channel, stale version, rejected content, duplicate publish, export download, refusal after edit.",
            "Inputs: malformed JSON, missing fields, whitespace-only and oversized text, invalid IDs, empty/corrupt/wrong-type/tiny/oversized/renamed images, bad source types and dates, PDF ingestion.",
            "Features: OCR->rule->region mapping, contrast maths, Delta-E, logo match, eight claim-verdict cases, Brand DNA provenance, contradictions, simulation immutability, campaign mismatches with passages, replay diff and counterfactual, empty workspaces.",
            "Migration: Round 2 database copy upgraded in place; existing rows kept; demo personas and Round 3 data added; seeded approved item publishable.",
            "Browser: sign-in, creative analysis, claims, campaign graph, Brand DNA and approval panel checked in Chrome at 1440 px. Phone-width layout of the new pages was <b>not</b> verified in this round.",
        ]),
        PageBreak(),
    ]

    story += section("12–15 · Limits and roadmap", "What is not done, honestly")
    story += [
        p("Known limitations", "h2"),
        *bullets([
            "BM25 misses paraphrases with no shared words; contradictory wording without differing figures is routed to review, not labelled contradicted.",
            "OCR can misread stylised text; contrast estimates weaken over gradients and photos; logo similarity is not authenticity or placement.",
            "Evaluation sets are small, fictional and team-authored; no independent labelling or user research.",
            "Publishing is a sandbox; no SSO; login throttling is per serverless instance; the demo workspace is shared by all visitors.",
            "Deployment of the Round 3 build depends on the OCR runtime loading on the host's Linux image; if it cannot, creative upload returns a clear error and text features continue to work.",
        ]),
        p("Changes since Round 2", "h2"),
        *bullets([
            "Persona switcher replaced with real authentication and server-side authorisation; CORS wildcard removed.",
            "New: creatives, evidence library, claim checks, policies, publishing, Brand DNA, campaigns, replay, governance page.",
            "Additive migrations; Round 2 demo data upgraded in place. Test suite grew from 11 to 63.",
        ]),
        p("Roadmap", "h2"),
        *bullets([
            "OIDC/SAML SSO; real CMS and social connectors behind the same publish guard.",
            "Hybrid lexical + embedding retrieval with the same conservative verdict layer; negation-aware contradiction detection.",
            "Layout checks (logo placement, safe zones), video frames, and an independently labelled evaluation set.",
        ]),
        Spacer(1, 6),
        p("16 · Links", "h2"),
        callout(f"<b>Source repository:</b> <link href='{REPO_URL}' color='#0F9488'>{REPO_URL}</link><br/>"
                + (f"<b>Live application (Round 3):</b> <link href='{LIVE_URL}' color='#0F9488'>{LIVE_URL}</link>" if LIVE_URL
                   else "<b>Live application:</b> the Round 3 build has not been deployed yet; no Round 3 URL is claimed here."),
                **({} if LIVE_URL else {"bg": AMBER_BG, "border": AMBER})),
    ]

    doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=20 * mm, bottomMargin=18 * mm,
                            title="AUDITRA — Round 3 Submission", author="Team Quoding")
    doc.build(story, onFirstPage=cover, onLaterPages=later)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
