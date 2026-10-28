# AUDITRA — Evidence-first Brand Governance

> **TechCircuit Round 3** · Team **Quoding** — Arya Kashyap (Team Leader), Ronit Mongia, Moli Verma

AUDITRA checks marketing copy **and image creatives** against a brand's rules and **approved source documents** before anything ships. Every finding points to the passage, image region, rule or source behind it. Approval is enforced on the server by configurable policies, bound to an exact content version, and only that approved version can be published.

Automated checks inform the decision; a named, authenticated human makes it.

**Repository:** https://github.com/RonitM2k06/Auditra
**Live demo:** see [Deployment status](#deployment-status) — the Round 3 build is deployed only after the checklist there is complete.

---

## What a judge can do in five minutes

1. Open the app and choose a **demo persona** (Alex the creator, Sarah the compliance lead, Morgan the admin). These are real accounts with server-enforced permissions, limited to the fictional *Northstar Cloud* workspace.
2. **Content reviews → "Migration promo social creative (sample)" → Run analysis.** The image's text is read by OCR; prohibited wording, missing disclosure, low-contrast text, an off-palette colour and a missing logo are drawn as regions on the creative.
3. **Campaigns → Atlas Pro launch.** The graph shows the landing page stating **$59** and **November 14** while the brief, email and social post say **$49** and **November 12**, plus a missing disclaimer — each with the exact passages side by side.
4. Open the **landing page → Run analysis → Claims tab.** "$59 per member per month" is *contradicted* by the current fact sheet (the figure only appears in an expired 2025 pricing sheet), and the cited passage, document, section and dates are shown.
5. **Submit for approval**, sign out, sign in as **Sarah**, approve. The **Approval tab** shows which policies the version triggered and what is still missing (e.g. evidence confirmation, a second approver). Try **Publish** before approval: it is refused and the refusal is in the audit trail.
6. **Brand DNA** shows the rulebook as structured dimensions, a deliberately seeded rule conflict, and a **simulator** that previews a rule change across all content without changing anything.
7. Any item → **Replay**: text diff between versions, resolved/new/persisting findings, rulebook snapshots, and the audit timeline.

---

## Feature status

| Area | Status | Notes |
|---|---|---|
| Brand workspaces, rulebook, approved-claims registry, guideline import | ✅ Round 2, kept | |
| Deterministic rule engine with offsets; optional AI step with grounding and fallback | ✅ Round 2, kept | AI step runs only for text and only with a provider key |
| Targeted corrections, immutable versions, discussion, audit trail, dashboard, insights | ✅ Round 2, kept | |
| **Authentication** (email + password, demo personas) | ✅ Round 3 | PBKDF2-SHA256 (310k), HttpOnly SameSite=Lax session cookie, server-side revocation |
| **Authorisation** (creator / reviewer / admin per workspace) | ✅ Round 3 | Explicit permission matrix in `backend/auth.py`, checked on every endpoint |
| **Approval policies** | ✅ Round 3 | Severity, claim-status and category triggers; required role, distinct approvers, evidence confirmation |
| **Version-bound approvals** | ✅ Round 3 | Approvals name the reviewed version; edits invalidate approval; self-approval blocked |
| **Publishing connector** | ✅ Round 3 (sandbox) | Local sandbox export record, idempotent per version. **Not** a live third-party integration |
| **Image creative analysis** | ✅ Round 3 | Content-validated PNG/JPEG intake, on-server OCR with boxes, rules on OCR text, WCAG contrast, palette ΔE, logo similarity |
| **Evidence retrieval & claim verification** | ✅ Round 3 | TXT/MD/PDF sources, BM25 passages, five conservative verdicts, staleness from supplied dates only |
| **Brand DNA digital twin** | ✅ Round 3 | Dimensions from real records, definite/possible contradictions, safe in-memory simulation |
| **Cross-channel consistency graph** | ✅ Round 3 | Price/date/quantity/disclosure comparison across campaign assets and brief |
| **Decision replay** | ✅ Round 3 | Version diff, finding comparison, rule snapshots (recorded from Round 3 onwards), timeline, counterfactual |
| SSO, live CMS/social connectors, OCR for scanned PDFs, video | ❌ Not implemented | See roadmap |

---

## Architecture

```
Browser ── React 19 + TypeScript SPA (Vite, Tailwind)  ── hash routes, HttpOnly session cookie
   │  JSON / multipart over /api  (state-changing calls carry X-Auditra-Client)
   ▼
FastAPI
   ├── auth.py            sessions, PBKDF2 hashing, permission matrix, workspace scoping
   ├── review_pipeline.py one analysis run: rules → (AI) → OCR regions → visual checks → claim checks → rule snapshot
   ├── rule_engine.py     deterministic matcher with offsets
   ├── vision.py          image validation, RapidOCR (ONNX), contrast, palette ΔE, logo template matching
   ├── evidence.py        source ingestion (txt/md/pdf), BM25 retrieval, claim extraction + verdicts
   ├── policies.py        approval-policy evaluation per version
   ├── intelligence.py    Brand DNA, contradictions, simulation, campaign consistency, replay diffs
   ├── migrations.py      additive, idempotent column migrations
   └── SQLAlchemy 2 ─► SQLite (local) or Postgres (Neon on Vercel)
```

**Data flow of an analysis:** current version → rule engine (offsets) → for creatives, findings mapped back to OCR boxes and visual checks measured from pixels → candidate claims retrieved against approved sources and classified → findings, claim checks and a snapshot of the rules/policies/sources used are stored against that version → policy evaluation decides what approval this version needs → decisions are recorded against the version → publish re-checks status, version and policies before writing the sandbox record.

### Main API

| Endpoint | Purpose |
|---|---|
| `POST /api/auth/login`, `/register`, `/demo`, `/logout`, `GET /api/auth/me` | Sessions |
| `GET/POST/PUT/DELETE /api/brands/{id}/members` | Workspace roles (admin) |
| `POST /api/brands/{id}/content`, `PUT /api/content/{id}` | Text content and versions |
| `POST /api/brands/{id}/creatives`, `POST /api/content/{id}/creative` | Upload a creative / revision |
| `POST /api/content/{id}/review` | Run the analysis on the current version |
| `POST /api/content/{id}/submit`, `/decision`, `GET /approval-status` | Workflow and policy status |
| `POST /api/content/{id}/publish`, `GET /api/publications/{id}/export` | Sandbox publishing |
| `GET/POST/PUT/DELETE /api/brands/{id}/sources`, `POST /evidence/search`, `/evidence/verify` | Evidence library |
| `GET/POST/PUT/DELETE /api/brands/{id}/policies` | Approval policies |
| `GET /api/brands/{id}/dna`, `POST /api/brands/{id}/simulate` | Brand DNA and simulation |
| `GET/POST /api/brands/{id}/campaigns`, `GET /api/campaigns/{id}/consistency` | Campaigns |
| `GET /api/content/{id}/replay`, `POST /api/content/{id}/versions/{n}/counterfactual` | Decision replay |
| `GET /api/health` | Health, version, database kind, deployed commit |

### Supported formats and limits

| Input | Accepted | Limits |
|---|---|---|
| Creatives | PNG, JPEG — validated by magic bytes and full decode, never by filename/MIME | 4 MB, 64–6000 px per side, 30 MP |
| Reference logo | PNG, JPEG | 1 MB |
| Sources | UTF-8 `.txt`, Markdown, text-based PDF (pypdf) | 2 MB, 60 PDF pages; encrypted or scanned PDFs are rejected/empty |
| Text content | Plain text | 50,000 characters |

Uploaded creatives are stored in the database with their version (so reviewers see exactly what was approved). They are never sent to external services. Nothing is written to the server filesystem.

---

## Run it locally

Prerequisites: Python 3.10+ (tested on 3.12.7) and Node.js 20+ (tested on 24).

```bash
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt  # includes rapidocr-onnxruntime (OCR models ship with the package)

cd frontend && npm ci && npm run build && cd ..

uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open http://localhost:8000 and pick a demo persona. On first start the database is created, migrations run, and the fictional Northstar workspace is seeded (rules, policies, three sources, a campaign, three sample creatives). The first creative analysis loads the OCR model (~1–2 s).

For frontend hot reload, keep the backend running and run `npm run dev` in `frontend/` (Vite proxies `/api`).

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./auditra.db` | SQLAlchemy URL. `postgres://` URLs are converted to psycopg automatically. |
| `AUDITRA_DEMO_LOGIN` | `true` | Set `false` to disable one-click demo personas. |
| `CORS_ORIGINS` | empty | Comma-separated origins. Empty = same-origin only (the SPA is served by the same app). |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | empty | Optional AI step for text reviews. Server-side only. |

There are **no default administrator credentials**. Demo personas have no password and can only sign in through the demo endpoint; they are members of the fictional demo workspace only. Anyone can register an account; they become admin of the workspaces they create and cannot see others.

### Database and migrations

New tables are created with `create_all`. Columns added to existing Round 2 tables are applied by `backend/migrations.py` as nullable/defaulted `ALTER TABLE ADD COLUMN` statements, recorded in `schema_migrations` and safe to re-run. An existing Round 2 Northstar workspace is upgraded in place (demo personas, policies, sources, campaign and creatives are added; existing rows are kept). This was tested against a copy of the Round 2 SQLite database.

---

## Tests and evaluation

```bash
venv\Scripts\python -m pytest -q        # 63 tests, isolated temporary SQLite database
cd frontend && npm run build            # tsc -b + vite build
python evaluation/run_eval.py           # writes evaluation/RESULTS.md and results.json
```

**Results on 29 Oct 2026:** 63 passed, 0 failed; frontend build succeeds.

The suites cover anonymous access, CSRF header enforcement, password hashing, session revocation, creator/reviewer privilege boundaries, cross-workspace isolation, permission-failure auditing, malformed JSON, empty/whitespace/oversized input, invalid IDs, stale-version approvals, self-approval, duplicate approvals, two-approver and evidence-confirmation policies, approval invalidation on edit, publishing drafts / rejected / stale versions, duplicate publishes, image validation (empty, wrong type, corrupt, tiny, renamed text file, oversized), OCR → rule → region mapping, contrast maths, palette ΔE, logo match, claim verdicts, PDF ingestion, source metadata (dates never invented), Brand DNA provenance, contradiction detection, simulation leaving data unchanged, campaign mismatches with passages, unrelated numbers not flagged, replay diffs and counterfactuals, and empty workspaces.

**Evaluation (fixed date 2026-10-29, fictional team-authored data — not a real-world accuracy estimate):**

- Creatives: 4 labelled samples, 8 expected finding labels → 8 found, 0 false positives, 0 missed. These samples were created during development, so this shows designed behaviour, not generalisation.
- Claims: 21 claims vs 3 sources → **19/21 correctly classified, 0 claims wrongly marked "supported"**, expected document cited 15/15. The two errors are unsupported claims classified *needs review* (the conservative direction).

Full tables: [`evaluation/RESULTS.md`](evaluation/RESULTS.md).

---

## Security notes

- Every protected endpoint checks the session and the caller's role **in the target workspace**; non-members get 404 so workspace IDs cannot be probed. Permission denials inside a workspace are written to its audit trail.
- Sessions: 256-bit random tokens, only SHA-256 hashes stored, 12-hour expiry, revoked on logout. Cookies are HttpOnly, SameSite=Lax, and Secure on HTTPS. No tokens in `localStorage`.
- State-changing API calls require the `X-Auditra-Client` header (blocked cross-site without CORS); CORS is closed by default.
- Login has a best-effort per-process throttle (8 failures / 5 min). On serverless hosts instances do not share it.
- Uploads are validated by content; decompression bombs are refused; filenames are never used as paths.
- The audit trail is an append-only **application log in an ordinary table**, not a tamper-proof ledger.
- The publish connector is a **local sandbox**: it records an export (content, SHA-256, approvals) and sends nothing anywhere.

## Known limitations

- Lexical retrieval (BM25) misses paraphrases with no shared words; contradictions are detected only via differing figures/dates with the same unit. Contradictory wording (e.g. "is HIPAA certified" vs "is not") is routed to *needs review*, not auto-labelled.
- OCR can misread stylised text; rules apply to the transcription. Contrast estimates are less reliable over gradients/photos. Logo similarity is not proof of authenticity or correct placement.
- Rule snapshots exist only for analyses run after the Round 3 upgrade; earlier history is not reconstructed.
- The shared demo workspace is used by every visitor; a reset affects everyone.
- No SSO; no live publishing destinations; images only (no video); scanned PDFs need OCR first.

---

## Deployment

Vercel (`vercel.json` + `api/index.py`) with a Neon Postgres database supplied via `DATABASE_URL`. The Python function bundles the OCR runtime (Vercel functions allow up to 5 GB), `maxDuration` is 60 s, and request bodies are capped by Vercel at 4.5 MB, which is why creatives are limited to 4 MB. `index.html` is served with `Cache-Control: no-cache` so a deploy never runs against a stale bundle.

1. Import the repo in Vercel (Framework Preset **Other**), connect a Postgres database so `DATABASE_URL` is set.
2. Deploy. On the first request migrations run and the demo workspace is seeded or upgraded in place.
3. Check `GET /api/health` — `commit` should match the deployed Git commit.

The `Dockerfile` works for container hosts (use a persistent volume if you use SQLite).

### Deployment status

The Round 3 build has **not yet been deployed**; the Round 2 build is live at https://auditra-bice.vercel.app/. Before deploying: confirm the OCR runtime imports on Vercel's Linux image (if `opencv` needs system libraries there, creative upload returns a clear 503 and nothing is saved — text features are unaffected), then verify `/api/health` reports the deployed commit and run the five-minute journey above.

---

## Roadmap

1. SAML/OIDC single sign-on and SCIM provisioning.
2. Real publishing connectors (CMS, social schedulers) behind the same approval guard.
3. Hybrid retrieval (BM25 + embeddings) with the same conservative verdict layer, and negation-aware contradiction detection.
4. Layout checks (logo placement, safe zones) and video frame sampling.
5. A larger, independently labelled evaluation set.

## Repository layout

```
backend/            FastAPI app, auth, pipeline, vision, evidence, policies, intelligence, routes/
frontend/           React + TypeScript SPA
tests/              pytest suites (isolated database)
samples/            fictional creatives, logo, source documents (+ generator script)
evaluation/         run_eval.py, RESULTS.md, results.json
docs/screenshots/   screenshots of the running app
```
