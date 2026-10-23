# AUDITRA — AI-Powered Brand Governance & Content Review

> **Round 2 — The Build** | Team: **Quoding**  
> *Pre-publication brand-governance control layer evaluating content against approved brand rules, terminology, facts, claims, and compliance disclosures.*

---

## 1. Product Overview & Vision

AUDITRA is not a generic writing chatbot or grammar checker. It is an **evidence-first, human-controlled brand review and governance control layer**.

Every meaningful finding answers six critical governance questions:
1. **What exact content triggered the finding?** (Exact character offsets and highlighted text spans)
2. **What rule or approved source is relevant?** (Traceable citation to configured policies, e.g. *Northstar Legal Governance Standard §4.1*)
3. **Why is the content problematic?** (Grounded explanation derived from brand policies)
4. **How severe or urgent is the issue?** (Critical, High, Medium, Low)
5. **What targeted correction addresses it?** (One-click in-place replacement creating an immutable version revision)
6. **Who reviewed and what decision was made?** (Human approval state machine with chronological audit logging)

---

## 2. Architecture & Technology Stack

```
┌────────────────────────────────────────────────────────────────────────┐
│                        AUDITRA Single-Port Architecture               │
├────────────────────────────────────────────────────────────────────────┤
│  Frontend (React 19 + TypeScript + Vite + Tailwind CSS + Lucide Icons) │
│  - Tri-pane Review Studio with live risk meter & targeted replacements │
│  - Command Centre Dashboard with real-time KPI metrics                 │
│  - Brand Rulebook & Verified Claims Registry (Full CRUD + Ingestion)   │
│  - Approval Queue with reviewer decision controls                      │
│  - Chronological Append-Only Audit Trail                               │
│  - Governance Insights & Friction Analytics                            │
├──────────────────────────────────┬─────────────────────────────────────┤
│  API Gateway & Server (FastAPI)  │  Deterministic Compliance Engine    │
│  - RESTful API with validation   │  - Exact & case-insensitive regex   │
│  - Server-enforced state machine │  - Prohibited phrases & terms       │
│  - Pydantic v2 schemas           │  - Preferred terminology mapping    │
│  - SPA static files mount        │  - Mandatory disclosure check       │
├──────────────────────────────────┼─────────────────────────────────────┤
│  AI Assistant Layer (Optional)   │  Persistence Layer                  │
│  - Gemini / OpenAI / Anthropic   │  - SQLite with WAL journal mode     │
│  - Grounded rule injection       │  - SQLAlchemy 2.0 ORM               │
│  - Honest deterministic fallback │  - Relational schema with cascades  │
└──────────────────────────────────┴─────────────────────────────────────┘
```

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS 3.4, Lucide React.
- **Backend**: Python 3.12, FastAPI, Pydantic v2, Uvicorn, Python-Multipart.
- **Persistence**: SQLite with Write-Ahead Logging (WAL) and foreign key enforcement via SQLAlchemy ORM (durable file `auditra.db`).
- **Compliance Engine**: Zero-LLM deterministic regex and token offset matcher.
- **AI Integration**: Grounded server-side schema with transparent fallback disclosure (`engine: "deterministic" | "hybrid_ai"`).
- **PDF Generation**: ReportLab document pipeline generating `AUDITRA_Round2_Submission.pdf`.

---

## 3. Implemented Features Inventory

| Feature | Status | Implementation Details |
|---|---|---|
| **First-Run & Sample Workspace** | ✅ Implemented & Tested | Auto-bootstraps "Northstar Cloud" demo workspace with 7 rules, 3 claims, and demo content. One-click reset button available in UI and API. |
| **Brand Rulebook & Claims Registry** | ✅ Implemented & Tested | Complete CRUD for brand rules across 7 categories (Prohibited, Preferred, Required Disclosures, Restricted Claims, Tone, Style). Upload parser for `.txt` and `.md` guideline documents. Verified claims registry. |
| **Content Review Studio** | ✅ Implemented & Tested | Tri-pane editor with live word/char counters, risk score gauge (0-100), severity breakdown, finding filters, and targeted recommendation chips. |
| **Deterministic Rule Engine** | ✅ Implemented & Tested | Token-boundary matching for prohibited phrases, preferred terminology substitutions, missing mandatory disclosure detection, and unverified performance claim flagging. |
| **Targeted Corrections & Versioning** | ✅ Implemented & Tested | One-click suggestion application. In-place replacement creates version checkpoint (v1 -> v2) and marks finding resolved. Custom edit capability. |
| **Review & Approval State Machine** | ✅ Implemented & Tested | Strict server-side transition enforcement: `Draft` → `In Review` → `Changes Requested` / `Approved` / `Rejected`. Prevents invalid transitions (e.g. Draft directly to Approved). |
| **Audit Trail & Event Log** | ✅ Implemented & Tested | Append-only event history capturing draft creation, scans, applied corrections, comments, and decisions with actor roles and timestamps. |
| **Command Centre Dashboard** | ✅ Implemented & Tested | Aggregated statistics computed from persisted data: Total reviews, Awaiting approval, High-severity issues, Approved reviews, status breakdowns, and recent activity. |
| **Governance Insights** | ✅ Implemented & Tested | Frequency of violation categories, top friction rules, average turnaround metrics, and hypothesis-driven rule clarity recommendations. |
| **Demo Persona Switcher** | ✅ Implemented & Tested | Interactive role toggle between *Alex Rivers (Creator)*, *Sarah Chen (Compliance Lead)*, and *Administrator*. |

---

## 4. Quickstart & Local Setup

### Prerequisites
- Python 3.10+ (Tested on Python 3.12.7)
- Node.js 18+ & npm 9+ (Tested on Node v24.16.0, npm 11.13.0)

### 1. Clone & Setup Backend
```bash
# Navigate to project root
python -m venv venv

# Windows PowerShell:
.\venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt
```

### 2. Build Frontend Assets
```bash
cd frontend
npm install
npm run build
cd ..
```

### 3. Run the Integrated Application
```bash
# Start backend server (serves both API and compiled SPA on a single port)
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser at **`http://localhost:8000`** to access the complete application!

*(Optional development mode: run `npm run dev` inside `frontend/` to run Vite dev server with proxy).*

---

## 5. Environment Variables

Create a `.env` file in the project root if you wish to configure optional LLM keys or custom database storage:

```env
# Optional external AI providers (if omitted, deterministic engine runs with zero disruption)
GEMINI_API_KEY=""
OPENAI_API_KEY=""
ANTHROPIC_API_KEY=""

# Database connection (defaults to SQLite with WAL persistence in ./auditra.db)
DATABASE_URL="sqlite:///./auditra.db"

# Server configuration
PROJECT_NAME="AUDITRA"
VERSION="2.0.0"
```

---

## 6. Verification & Automated Testing

A comprehensive test suite of 10 automated test suites validates the entire product:

```bash
# Run all tests using pytest
$env:PYTHONPATH="." ; .\venv\Scripts\pytest -v tests/
```

### Test Coverage Highlights:
- **`test_health_endpoint`**: Verifies API liveness and engine configuration disclosure.
- **`test_deterministic_rule_engine_violations`**: Tests prohibited phrase detection, preferred terminology flags, missing disclosure detection, and unverified claim detection.
- **`test_deterministic_rule_engine_clean_content`**: Negative case verification — clean copy generates exactly 0 false positives.
- **`test_brands_and_sample_workspace`**: Tests workspace bootstrapping and persistence.
- **`test_content_lifecycle_and_corrections`**: Full journey: Draft creation -> Scan -> 1-click apply correction -> Version bump -> Reviewer decision -> Audit logging.
- **`test_dashboard_and_insights_endpoints`**: Confirms all statistics and charts compute from real persisted data.
- **`test_guideline_upload_parsing`**: Verifies text and markdown guideline document ingestion.
- **`test_claims_crud`**: Tests approved claims registry.
- **`test_state_machine_strict_enforcement`**: Proves invalid state transitions (e.g. Draft -> Approved directly) are blocked with HTTP 400.
- **`test_complete_judge_end_to_end_journey`**: Step-by-step automated execution of the 12-step master judge workflow.

---

## 7. Judge Demo Walkthrough (3-Minute Tour)

Judges can complete a full governance workflow in under three minutes using the fictional **Northstar Cloud** workspace:

1. **Open Overview**: Visit `http://localhost:8000`. Notice the Command Centre dashboard with real KPIs, active severity distribution, and recent activity.
2. **Open Content Reviews**: Click **Content Reviews** in the sidebar. Select *"Q4 Enterprise Cloud Promotion (Demo Scenario)"*.
3. **Inspect the Findings in Studio**:
   - Risk score is 55/100 (High Risk).
   - Flag 1: Prohibited term `"guarantees results"` citing *Northstar Legal Governance Standard §4.1*.
   - Flag 2: Terminology violation `"users"` citing *Northstar Editorial Style Guide §1.2*.
   - Flag 3: Restricted claim `"double your performance in seven days"` citing *Northstar Product Claims Manual §3.0*.
4. **Apply Targeted Correction**:
   - In the findings panel for `"users"`, click **Apply**.
   - Watch the editor automatically update `"users"` to `"members"`.
   - The version automatically advances to Version 2, creating an audit checkpoint.
5. **Submit for Human Review**:
   - Click **Submit for Review**. Status transitions from `Draft` to `In Review`.
6. **Reviewer Decision**:
   - Switch the active persona in the bottom-left sidebar to **Sarah Chen (Compliance Lead)**.
   - Reviewer controls appear: click **Approve** (or open the **Approval Queue** tab).
   - Enter compliance notes and certify release. Status becomes `Approved`.
7. **Trace in Audit Trail**:
   - Navigate to the **Audit Trail** tab.
   - Inspect the chronological log documenting `draft_created`, `analysis_run`, `correction_applied`, `submitted_for_review`, and `content_approved`.

---

## 8. Round 1 vs Round 2 Evolution

- **From Concept to Functional Core**: Round 1 proposed an AI review layer; Round 2 delivered a production-ready full-stack platform with deterministic regex matching, relational database persistence, and an interactive tri-pane review studio.
- **Evidence-First Grounding**: Instead of relying solely on probabilistic LLMs that hallucinate guidelines, Round 2 introduced strict rule citations grounded in real database records with transparent fallback disclosure.
- **State Machine Integrity**: Replaced informal status badges with an enforced server-side finite state machine guaranteeing human oversight before content publication.

---

## 9. Proposed Round 3 Strategic Roadmap

1. **Multimodal Brand Governance**:
   Extend governance from text to marketing graphics, banners, and video assets. Inspect images for brand-palette compliance, logo exclusion zones, contrast accessibility, and embedded image OCR text verification.
2. **Evidence-Grounded Brand Knowledge & Claim Verification**:
   Incorporate high-precision semantic retrieval (RAG) over authoritative internal documents (10-K filings, SOC2 audits, lab whitepapers) with automated provenance tracking and freshness expiration dates.
3. **Enterprise Governance & Publishing Integrations**:
   Introduce multi-tenant organizational hierarchies, SSO/SAML 2.0, dual-custody approval gates for high-risk legal claims, and direct CMS publishing connectors for HubSpot, WordPress, and social scheduling platforms.

---

## 10. License & Team

Built with pride for **Techcircuit Round 2** by team **Quoding**.  
Submission document: `AUDITRA_Round2_Submission.pdf` (included in repository root).
