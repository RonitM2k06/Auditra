"""Build AUDITRA_Round2_Submission.pdf from verified project facts and real screenshots.

Usage: python generate_submission_pdf.py
Screenshots are read from docs/screenshots/ (captured from the running app at 1440x900).
"""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(ROOT, "docs", "screenshots")
OUT = os.path.join(ROOT, "AUDITRA_Round2_Submission.pdf")

# >>> INSERT VERIFIED URLS HERE before regenerating. Leave empty until each link has been opened and works. <<<
LIVE_URL = ""   # e.g. the deployed app root that serves the Overview page
REPO_URL = "https://github.com/RonitM2k06/Auditra"   # verified 24 Oct 2026

NAVY = colors.HexColor("#111C2E")
TEAL = colors.HexColor("#0F9488")
PALE_TEAL = colors.HexColor("#E8F7F4")
INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#667085")
LINE = colors.HexColor("#E4E7EC")
SUBTLE = colors.HexColor("#F6F8FB")
AMBER_BG = colors.HexColor("#FFFAEB")
AMBER = colors.HexColor("#B45309")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

S = {
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=20, leading=25, textColor=INK, spaceAfter=4),
    "kicker": ParagraphStyle("kicker", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=TEAL, spaceAfter=3),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=INK, spaceBefore=10, spaceAfter=4),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=15, textColor=INK, spaceAfter=6),
    "muted": ParagraphStyle("muted", fontName="Helvetica", fontSize=9, leading=13, textColor=MUTED, spaceAfter=4),
    "caption": ParagraphStyle("caption", fontName="Helvetica-Oblique", fontSize=8.5, leading=12, textColor=MUTED, spaceBefore=3, spaceAfter=10),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=9, leading=12.5, textColor=INK, alignment=TA_LEFT),
    "cellb": ParagraphStyle("cellb", fontName="Helvetica-Bold", fontSize=9, leading=12.5, textColor=INK),
    "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=10, leading=14.5, textColor=INK, leftIndent=12, bulletIndent=2, spaceAfter=3),
}


def p(text, style="body"):
    return Paragraph(text, S[style])


def bullets(items):
    return [Paragraph(t, S["bullet"], bulletText="•") for t in items]


def section(kicker, title):
    return [p(kicker.upper(), "kicker"), p(title, "h1"), Spacer(1, 4)]


def shot(name, caption, width=CONTENT_W):
    path = os.path.join(SHOTS, name)
    img = Image(path)
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth, img.drawHeight = width, width * ratio
    framed = Table([[img]], colWidths=[width + 2])
    framed.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return KeepTogether([framed, p(caption, "caption")])


def table(rows, widths, header=True):
    data = [[p(c, "cellb" if (header and i == 0) else "cell") if isinstance(c, str) else c for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
             ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), SUBTLE))
    t.setStyle(TableStyle(style))
    return t


def callout(text, bg=PALE_TEAL, border=TEAL):
    t = Table([[p(text, "cell")]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LINEBEFORE", (0, 0), (0, -1), 3, border),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return t


def links_callout():
    """Project links box: shows LIVE_URL / REPO_URL once set, otherwise states plainly that they do not exist yet."""
    if LIVE_URL and REPO_URL:
        return callout(f"<b>Live application:</b> <link href='{LIVE_URL}' color='#0F9488'>{LIVE_URL}</link><br/>"
                       f"<b>Source repository:</b> <link href='{REPO_URL}' color='#0F9488'>{REPO_URL}</link><br/>"
                       "The live instance contains only the fictional Northstar demo data and has no login.")
    live = (f"<link href='{LIVE_URL}' color='#0F9488'>{LIVE_URL}</link>" if LIVE_URL
            else "not yet deployed; no public URL has been verified.")
    repo = (f"<link href='{REPO_URL}' color='#0F9488'>{REPO_URL}</link>" if REPO_URL
            else "not yet published; no remote is configured for the local repository.")
    return callout(f"<b>Live application:</b> {live}<br/><b>Source repository:</b> {repo}<br/>"
                   "These links will be added once the team publishes the repository and deploys the app.",
                   bg=AMBER_BG, border=AMBER)


def cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    # brand mark
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
    canvas.drawString(MARGIN, y - 33 * mm, "Brand governance and content review")
    canvas.setFont("Helvetica", 11)
    canvas.drawString(MARGIN, y - 41 * mm, "Evidence-linked findings, targeted corrections, accountable human approval.")
    canvas.setFillColor(TEAL)
    canvas.rect(MARGIN, y - 52 * mm, 30 * mm, 1.2 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(MARGIN, 60 * mm, "Techcircuit Round 2 — The Build")
    canvas.setFont("Helvetica", 11)
    canvas.setFillColor(colors.HexColor("#CBD5E1"))
    canvas.drawString(MARGIN, 52 * mm, "Team Quoding")
    canvas.drawString(MARGIN, 45 * mm, "Arya Kashyap (Team Leader)  ·  Ronit Mongia  ·  Moli Verma")
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.drawString(MARGIN, 30 * mm, "All screenshots are captured from the running application using the fictional Northstar Cloud demo workspace.")
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
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 10 * mm, "Team Quoding · Round 2 submission")
    canvas.drawRightString(PAGE_W - MARGIN, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build():
    story = [PageBreak()]  # page 1 is the drawn cover

    # Executive summary
    story += section("Executive summary", "Check content against the brand before it ships")
    story += [
        p("Marketing and brand teams publish a constant stream of copy, and the review step is usually a manual read "
          "against a PDF of guidelines. Mistakes such as absolute guarantees, unapproved claims, missing disclosures "
          "and off-brand terminology are expensive to catch after publication."),
        p("<b>AUDITRA</b> is a working web application that checks copy against a brand's configured rulebook, shows "
          "each finding on the exact passage with the rule or source behind it, offers a targeted correction, and moves "
          "the piece through a human approval workflow with version history and an audit trail."),
        callout("<b>What is built in Round 2:</b> a full-stack app (React + FastAPI + SQLite) with a brand rulebook, a "
                "deterministic rule engine, an optional and grounded AI step with safe fallback, a review studio with "
                "inline highlights and one-click corrections, a server-enforced approval workflow, an approval queue, "
                "an audit trail, an overview dashboard and governance insights, all backed by persisted data."),
        Spacer(1, 8),
        p("Problem and target users", "h2"),
        *bullets([
            "<b>Content creators</b> who need to know, before submitting, what breaks brand policy and how to fix it.",
            "<b>Brand and compliance reviewers</b> who need to see what was flagged, on which version, and record an accountable decision.",
            "<b>Brand owners</b> who need to maintain the rulebook and see which rules are triggered most often.",
        ]),
        p("Differentiators", "h2"),
        *bullets([
            "<b>Evidence first:</b> every rule finding carries exact character offsets and the configured source reference (for example, <i>Northstar Legal Governance Standard §4.1</i>). When no source exists, the UI says so instead of inventing one.",
            "<b>Deterministic core, optional AI:</b> rule checks work with no AI provider at all; AI findings are labelled as AI-assisted, unknown rule IDs are discarded, and provider failures fall back to rule findings.",
            "<b>Humans decide:</b> automated checks never approve content. The server rejects invalid transitions, and requesting changes or rejecting requires a written note.",
        ]),
        PageBreak(),
    ]

    # Features
    story += section("Implemented features", "What works today")
    story.append(table([
        ["Area", "Implemented behaviour"],
        ["Workspaces", "Multiple brand workspaces; seeded Northstar Cloud demo with 7 rules, 3 approved claims and 3 sample pieces; scoped demo reset."],
        ["Brand rulebook", "Create, edit, toggle and delete rules in six categories with severity, match pattern, replacement and source reference; approved-claims registry; .txt/.md guideline import that turns matching lines into rules (created active, so they should be reviewed)."],
        ["Rule engine", "Prohibited wording, preferred terminology, missing required disclosures, restricted and unverified claims, style checks; exact offsets per finding."],
        ["AI step (optional)", "Gemini, OpenAI or Anthropic when a key is configured; grounded against active rules; on failure the review completes with rule findings and records the failure."],
        ["Review studio", "Editor and marked-up view, severity highlights, findings panel with counts and source filter, expandable findings, apply / edit-then-apply / dismiss, stale-review warnings, version history, discussion."],
        ["Corrections and versions", "Applying a suggestion replaces only the matched passage and creates a new immutable version; re-review checks the new version."],
        ["Approval workflow", "Draft → In review → Approved / Changes requested / Rejected, enforced by the server; warning before approving with open critical or high findings."],
        ["Approval queue", "Status counts, queue items with highest severity and open findings, reviewer pane with copy, findings, discussion and decisions."],
        ["Audit trail", "Chronological timeline of server-recorded events with actor, time, related content and labelled details."],
        ["Overview and insights", "KPIs, items needing attention, workflow status, open findings by severity, findings by category, most-triggered rules, decision turnaround."],
        ["Demo roles", "Switch between creator, reviewer and admin personas. This is a demo convenience, not authentication."],
    ], [38 * mm, CONTENT_W - 38 * mm]))
    story.append(PageBreak())

    # Workflow
    story += section("Core workflow", "From draft to accountable decision")
    story.append(shot("01-overview.png", "Figure 1. Overview: KPIs, items needing attention, workflow status and open findings by severity, all computed from stored data."))
    story.append(shot("02-review-studio.png", "Figure 2. Review studio: marked-up copy with severity-coded highlights and the findings panel for the current version."))
    story.append(shot("03-finding-expanded.png", "Figure 3. An expanded finding: why it matters, the brand rule it comes from, and a suggested correction with Apply, Edit first and Dismiss."))
    story += [
        p("Steps a judge can follow", "h2"),
        *bullets([
            "Start a new review, load the labelled demo copy and run the review.",
            "Expand a finding to see the passage, the rule and the suggested correction; click it to jump to the passage.",
            "Apply the correction (a new version is saved), then re-run the review on the new version.",
            "Submit for approval, switch to the reviewer persona, and approve or request changes with a note.",
            "Open the audit trail to trace every step; refresh to confirm persistence.",
        ]),
    ]
    story.append(shot("04-rulebook.png", "Figure 4. Brand rulebook: rules with category, severity, match pattern, suggested replacement and source reference."))
    story.append(shot("05-approvals.png", "Figure 5. Approval queue: status counts, the waiting item with its highest severity, and a reviewer pane explaining why it needs review and what to do next."))
    story.append(shot("06-audit.png", "Figure 6. Audit trail: human-readable event timeline with actor, related content, version and labelled details."))
    story.append(shot("07-insights.png", "Figure 7. Governance insights: findings by category and most-triggered rules, with an explanation of how each figure is calculated."))
    story.append(PageBreak())

    # Architecture
    story += section("Technical architecture", "One process, one database, clear boundaries")
    story.append(table([
        ["Layer", "Implementation"],
        ["Frontend", "React 19, TypeScript, Vite, Tailwind CSS, lucide-react icons. Hash-based routes so every screen survives a refresh. Shared component kit for buttons, badges, tables, dialogs and toasts."],
        ["API", "FastAPI with Pydantic v2 schemas. Routes for brands, rules and claims, content, reviews, workflow, audit, dashboard and insights. Also serves the built frontend, so the app runs on one port."],
        ["Rule engine", "Deterministic matcher producing findings with category, severity, offsets, explanation, source reference and suggested correction."],
        ["AI service", "Optional provider call with the brand's active rules and claims in the prompt; output validated against stored rule IDs and the actual text."],
        ["Persistence", "SQLAlchemy 2 over SQLite in WAL mode with foreign keys: brands, rules, claims, content items, immutable versions, review runs, findings, comments, decisions, audit events."],
    ], [30 * mm, CONTENT_W - 30 * mm]))
    story += [
        p("Data flow for a review", "h2"),
        p("The studio saves the text as a content version. <font name='Courier'>POST /api/content/{id}/review</font> runs the "
          "rule engine (plus the AI step if configured) against the brand's active rules and claims and stores the findings "
          "against that version. Applying a finding creates the next version. Submit and decision endpoints move the item "
          "through the state machine, and every step writes an audit event."),
        p("AI analysis and evidence grounding", "h2"),
        *bullets([
            "With no provider key, the health endpoint reports <i>deterministic_fallback</i>, the UI shows <b>Rules only</b>, and reviews use the rule engine alone.",
            "When a provider is configured, AI findings whose rule ID does not exist are stripped of it, offsets are re-located in the real text, and findings are marked as AI-assisted with a human-verification flag.",
            "If the provider call fails, the review still completes with rule findings and the run records <i>ai_status: failed</i>. This path was tested with an invalid key.",
        ]),
        p("Human approval, history and auditability", "h2"),
        *bullets([
            "Content versions are immutable; each correction or edit creates a new version, and findings are tied to the version they were raised on. The studio warns when findings belong to an older version.",
            "Decisions record the reviewer, decision, note and version. The server refuses invalid transitions (for example, approving a draft).",
            "The audit trail is an append-only application log in the database. It is not presented as tamper-proof.",
        ]),
        PageBreak(),
    ]

    # Testing
    story += section("Testing and validation", "What was actually verified")
    story.append(table([
        ["Check", "Result (24 Oct 2026)"],
        ["Backend test suite (pytest, isolated temporary database)", "11 passed"],
        ["Frontend production build (tsc -b and vite build)", "Succeeds"],
        ["Ad-hoc HTTP smoke script (not part of the repository) on a running server with a throwaway database", "21 of 21 checks passed: rule create, edit and validation; content creation; rule findings with offsets and source; deterministic fallback; correction to v2; re-review; state-machine enforcement; dashboard and queue consistency; comments; approval; version history; audit lifecycle; 404 handling"],
        ["Persistence across a server restart", "Brand, approved status and audit trail all present after restart"],
        ["AI provider failure", "Review completes with rule findings and ai_status: failed"],
        ["Browser check (Chrome via Playwright)", "All screens at 1440×900, 1024×768, 768×1024 and 375×812: no console errors, no failed API calls, no horizontal overflow; full creator-to-reviewer journey completed in the UI"],
        ["Successful live AI call", "<b>Not tested</b>: no provider key was available"],
    ], [70 * mm, CONTENT_W - 70 * mm]))
    story += [
        Spacer(1, 6),
        p("Defects found and fixed during validation included: new reviews failing to save (a schema required a field the "
          "frontend did not send), test runs writing into the demo database, an overview panel contradicting the approval "
          "count, raw validation JSON in error messages, and the frontend dev server lacking an API proxy.", "muted"),
    ]

    # Changes from Round 1 (compared with the team's Round 1 proposal PDF)
    story += [
        p("Round 1 proposal compared with the Round 2 build", "h2"),
        p("Compared item by item with our Round 1 submission (<i>Round 1: The Plan</i>). Status reflects the code as submitted."),
        table([
            ["Round 1 plan", "Round 2 status"],
            ["Brand rulebook: guidelines, tone, facts, claims, terminology", "<b>Built.</b> Rules in six categories plus an approved-claims registry. Logo and visual assets are not supported."],
            ["Text submission, rule checks, explainable findings, suggestions", "<b>Built.</b> Deterministic checks with exact offsets, explanations, source references and targeted corrections."],
            ["AI-assisted analysis with validated, labelled output", "<b>Built, not demonstrated live.</b> Grounding and the fallback are implemented; no successful live provider call was tested."],
            ["Review workflow: comments, request changes, approve, reject", "<b>Built</b>, enforced by the server."],
            ["Revision history and audit trail", "<b>Built.</b> Immutable versions and a server-written event log."],
            ["Governance insights", "<b>Built.</b> Category, rule and turnaround summaries from stored data."],
            ["Role-based permissions (privacy and security section)", "<b>Not built.</b> There is a demo role switcher only; there is no login or access control."],
            ["Document upload and text extraction", "<b>Partial.</b> .txt and .md guideline import only; no PDF, DOCX or content-document upload."],
            ["OCR and visual checks (could-have)", "<b>Not built.</b> Moved to Round 3."],
            ["Database: PostgreSQL (SQLite for prototype)", "<b>SQLite</b>, configurable through DATABASE_URL; not tested on PostgreSQL."],
            ["Multiple brand workspaces (could-have)", "<b>Built.</b>"],
            ["Testing with sample brands; user feedback", "<b>Partial.</b> Automated tests and a browser walkthrough on a fictional brand; no user interviews and no false-positive measurement yet."],
            ["Deployed prototype and judge-accessible repository", "<b>Pending.</b> Not deployed and not yet pushed at the time of writing."],
        ], [62 * mm, CONTENT_W - 62 * mm]),
        Spacer(1, 14),
    ]

    # Limitations
    story += section("Current limitations", "What is not done yet")
    story += bullets([
        "<b>No authentication or authorisation.</b> The role switcher is for demonstration only.",
        "<b>Deployment:</b> " + ("a temporary demo instance is available for judging; it has no login, so it holds fictional demo data only."
                                if LIVE_URL else "no public deployment has been verified at the time of writing."),
        "The rule engine is pattern-based and does not understand paraphrase; the AI step can help but needs human verification.",
        "Text content only: no images, video or rich-text formatting.",
        "Guideline import accepts UTF-8 text and Markdown only (no PDF or DOCX extraction), and imported rules are active immediately, so an imported document takes effect before anyone reviews it.",
        "No structured evaluation set yet: we have not measured detection rate, false positives or reviewer agreement, and no user interviews have been run.",
        "SQLite suits a single node; concurrent multi-user production use needs a server database.",
        "The audit log is an application table, not a tamper-proof ledger.",
    ])

    # Round 3
    story += [Spacer(1, 6)] + section("Round 3", "Three improvements and how we will measure them")
    r3 = [
        ("1. Multimodal brand governance for visual creatives",
         "Extend the same rulebook to banners and social images: palette and logo usage, minimum contrast, and OCR of on-image text checked by the existing rule engine.",
         "Precision and recall on a labelled set of compliant and non-compliant creatives; share of on-image text violations caught that text-only review misses; reviewer time per creative."),
        ("2. Evidence-grounded brand knowledge and claim verification",
         "Retrieve from approved source documents (product facts, certifications, policy) so each claim is matched to a dated, attributable passage, with expiry for stale evidence.",
         "Share of flagged claims linked to a correct source passage; false 'verified' rate (target near zero); reviewer agreement with the suggested evidence."),
        ("3. Enterprise governance and publishing integrations",
         "Real identity (SSO) and roles, multi-step approval policies for high-risk content, and connectors so only approved versions are published to CMS and scheduling tools.",
         "Zero unapproved versions published in integration tests; median time from submission to decision; policy coverage (share of content routed by a defined policy)."),
    ]
    for title, value, measure in r3:
        story.append(KeepTogether([p(title, "h2"), p(f"<b>Value.</b> {value}"), p(f"<b>Evaluation.</b> {measure}")]))
    story.append(Spacer(1, 14))

    # Stack and links
    story += section("Implementation details", "Technology stack and links")
    story.append(table([
        ["Component", "Technology"],
        ["Frontend", "React 19, TypeScript 6, Vite 8, Tailwind CSS 3.4, lucide-react"],
        ["Backend", "Python 3.12, FastAPI, Pydantic v2, Uvicorn, SQLAlchemy 2"],
        ["Database", "SQLite with WAL and foreign keys (configurable via DATABASE_URL)"],
        ["AI providers (optional)", "Gemini, OpenAI or Anthropic via server-side environment variables"],
        ["Testing", "pytest with FastAPI TestClient (in tests/); browser checks were run manually with Playwright and are not part of the repository"],
        ["Run locally", "pip install -r requirements.txt; npm install and npm run build in frontend/; uvicorn backend.main:app --port 8000"],
    ], [42 * mm, CONTENT_W - 42 * mm]))
    story += [
        Spacer(1, 10),
        p("Project links", "h2"),
        links_callout(),
    ]

    doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=20 * mm, bottomMargin=18 * mm,
                            title="AUDITRA — Round 2 Submission", author="Team Quoding")
    doc.build(story, onFirstPage=cover, onLaterPages=later)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
