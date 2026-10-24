# Round 2 submission checklist — AUDITRA (Team Quoding)

Status as of 24 Oct 2026. **Verified** = checked against the running app or files; **Prepared, unverified** = written but needs a team confirmation; **Blocked** = needs an action only the team can take.

| Item | Status | Evidence / next step |
|---|---|---|
| Working project link | **Verified** | https://auditra-iqmf.onrender.com/ (health check healthy, all main screens load, a live review returned 7 findings; free plan, resets to demo data on restart). |
| Source-code repository link | **Verified** | https://github.com/RonitM2k06/Auditra (public; `main` matches the local commit; PDF on GitHub is byte-identical). |
| Updated project PDF | **Verified** | `AUDITRA_Round2_Submission.pdf`: 11 A4 pages, 7 screenshots, page numbers; rendered and checked page by page. Rebuild with `python generate_submission_pdf.py` after adding the links. |
| Completed features | **Verified** | README *What is implemented*; PDF pages 2–3. Backed by 11 passing tests, an ad-hoc 21/21 HTTP smoke test and a manual browser run. |
| Technology and implementation details | **Verified** | README *Architecture* and *Run it locally*; PDF pages 8 and 11. |
| Changes from the Round 1 proposal | **Verified** | PDF pages 9–10 compare item by item with `AUDITRA_Round_1_Solution_Proposal` (Downloads). Not built: role-based access, PDF/DOCX extraction, OCR/visual checks, PostgreSQL, user feedback testing, deployment. |
| Three Round 3 improvements | **Verified** | PDF page 10–11 and README, each with its value and evaluation criteria. |
| Team members | **Prepared, unverified** | The cover lists Arya Kashyap (Team Leader), Ronit Mongia and Moli Verma, matching the Round 1 cover. **The Round 1 participant table says "Team size: 2" and omits Moli Verma.** Confirm against the official registration. |
| Secrets | **Verified** | No API keys in tracked files; `.env`, `*.db`, `venv/`, `dist/` and `node_modules/` are ignored. |
| Live AI analysis | **Prepared, unverified** | The fallback and failure paths are verified; a successful provider call is untested. |

## Where the URLs go (only after opening each link and confirming it works)

1. `generate_submission_pdf.py`: set `LIVE_URL` and `REPO_URL` (the marked block near the top), then run `python generate_submission_pdf.py`.
2. `README.md`: replace the two placeholder lines (*Live demo* / *Repository*) at the top.
3. This file: change *Working project link* and *Source-code repository link* to **Verified**.

## Publishing (run these yourself)

```bash
git status                       # review: 20 modified files, docs/ and tests/conftest.py new
git add -A
git commit -m "Round 2: UI redesign, review studio, audit trail, docs and submission PDF"
gh auth login                    # once, if not already authenticated
gh repo create <owner>/auditra --public --source=. --push   # or --private and add the judges
```

## Deployment notes

- Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`, run from the repo root (the default DB path is relative).
- Build: `pip install -r requirements.txt && cd frontend && npm ci && npm run build`. The build host needs Node 18+ as well as Python.
- Health check: `GET /api/health`.
- Storage: SQLite needs a persistent disk, with `DATABASE_URL=sqlite:////<disk>/auditra.db`. Without one, data resets on every redeploy.
- **Security:** there is no login. Anyone with the URL can edit rules, approve content and call `/api/brands/sample/reset`. Deploy only with demo data, share the URL only with the judges, leave the AI keys unset (or use a spend-capped key), and take it down after judging.
