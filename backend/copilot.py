"""Governance Copilot: a small, read-only agent that answers questions about one workspace.

* Every tool is read-only and runs with the signed-in user's workspace permissions.
  The agent cannot edit content, change rules, approve or publish.
* Every answer returns the tool calls it made and the records they returned ("citations"),
  so a reviewer can check each statement against stored evidence.
* With ANTHROPIC_API_KEY set, Claude (claude-opus-5-5) plans the tool calls. Without a key, a
  deterministic router answers common questions from the same tools and says so.
"""
import json
import os
import re
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend import intelligence
from backend import policies as policy_engine
from backend.models import ApprovedClaim, Brand, BrandRule, ContentItem, ContentVersion, Finding
from backend.models_r3 import ApprovalPolicy, Campaign, ClaimCheck, SourceDocument
from backend.review_pipeline import build_index, verify_text
from backend.risk import campaign_risk

MODEL = "claude-opus-5-5"
MAX_STEPS = 6

SYSTEM_PROMPT = """You are the AUDITRA Governance Copilot for the brand workspace "{brand}".
You help brand, legal and marketing reviewers understand governance risk.

Rules:
- Use the tools to look things up. Only state facts that appear in tool results; if the tools do not show something, say it is not recorded.
- Cite the records you rely on by name (content title, claim, source document, rule).
- Distinguish detected issues from heuristic estimates, and "not analysed" from "passed".
- You are read-only: you cannot edit, approve, reject or publish. When action is needed, say which screen to use (Studio Fix tab, Approval tab, Campaign risk radar, Evidence library, Brand DNA).
- Be concise: a short answer first, then the supporting points."""


class Toolbox:
    """Read-only tools scoped to one workspace."""

    def __init__(self, db: Session, brand_id: str):
        self.db, self.brand_id = db, brand_id

    # --- tool implementations -------------------------------------------------
    def list_campaigns(self) -> Any:
        return [{"campaign_id": c.id, "name": c.name, "brief": c.brief}
                for c in self.db.query(Campaign).filter(Campaign.brand_id == self.brand_id).all()]

    def campaign_risk(self, campaign_id: str) -> Any:
        c = self.db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.brand_id == self.brand_id).first()
        if not c:
            return {"error": "No campaign with that id in this workspace."}
        r = campaign_risk(self.db, c)
        return {"name": r["name"], "level": r["level"], "complete": r["complete"], "explanation": r["explanation"],
                "counts": r["counts"], "unverified": [u["title"] for u in r["unverified"]],
                "risks": [{"severity": x["severity"], "basis": x["basis"], "title": x["title"],
                           "evidence": (x["evidence"].get("text") or x["evidence"].get("explanation") or "")[:240],
                           "action": x["action"]} for x in r["risks"][:15]]}

    def list_content(self, status: Optional[str] = None) -> Any:
        q = self.db.query(ContentItem).filter(ContentItem.brand_id == self.brand_id)
        if status:
            q = q.filter(ContentItem.status == status)
        out = []
        for it in q.order_by(ContentItem.updated_at.desc()).limit(40).all():
            v = self.db.query(ContentVersion).filter(ContentVersion.content_id == it.id,
                                                     ContentVersion.version_number == it.current_version_number).first()
            out.append({"content_id": it.id, "title": it.title, "status": it.status, "media_kind": it.media_kind,
                        "version": it.current_version_number,
                        "analysed": bool(v and policy_engine.latest_run_for_version(self.db, v.id))})
        return out

    def content_detail(self, content_id: str) -> Any:
        it = self.db.query(ContentItem).filter(ContentItem.id == content_id, ContentItem.brand_id == self.brand_id).first()
        if not it:
            return {"error": "No content with that id in this workspace."}
        v = self.db.query(ContentVersion).filter(ContentVersion.content_id == it.id,
                                                 ContentVersion.version_number == it.current_version_number).first()
        run = policy_engine.latest_run_for_version(self.db, v.id) if v else None
        status = policy_engine.evaluate(self.db, it)
        findings, claims = [], []
        if run:
            findings = [{"severity": f.severity, "category": f.category, "text": f.matched_text, "source": f.source_reference}
                        for f in self.db.query(Finding).filter(Finding.review_run_id == run.id, Finding.is_applied == False,  # noqa: E712
                                                               Finding.is_dismissed == False).all()]  # noqa: E712
            claims = [{"claim": c.claim_text, "status": c.status, "rationale": c.rationale[:200]}
                      for c in self.db.query(ClaimCheck).filter(ClaimCheck.review_run_id == run.id).all()]
        return {"title": it.title, "status": it.status, "version": it.current_version_number, "analysed": run is not None,
                "text": (v.body if v else "")[:1500], "open_findings": findings, "claims": claims,
                "approval_satisfied": status["satisfied"], "approval_blocking": status["blocking"]}

    def search_evidence(self, query: str) -> Any:
        hits = build_index(self.db, self.brand_id).search(query, top_k=4)
        return [{"document": p.document_name, "section": p.section, "expiry_date": p.expiry_date, "passage": p.text,
                 "score": round(s, 2)} for p, s in hits]

    def verify_claims(self, text: str) -> Any:
        return [{"claim": c["claim_text"], "status": c["status"], "rationale": c["rationale"],
                 "source": (c["source"] or {}).get("name"), "passage": c["passage_text"]}
                for c in verify_text(text[:5000], build_index(self.db, self.brand_id))]

    def governance_overview(self) -> Any:
        rules = self.db.query(BrandRule).filter(BrandRule.brand_id == self.brand_id).all()
        claims = self.db.query(ApprovedClaim).filter(ApprovedClaim.brand_id == self.brand_id).all()
        docs = self.db.query(SourceDocument).filter(SourceDocument.brand_id == self.brand_id).all()
        policies = self.db.query(ApprovalPolicy).filter(ApprovalPolicy.brand_id == self.brand_id).all()
        return {"active_rules": sum(1 for r in rules if r.is_active),
                "rule_conflicts": [{"certainty": c["certainty"], "title": c["title"], "explanation": c["explanation"]}
                                   for c in intelligence.detect_contradictions(rules, claims)],
                "sources": [{"name": d.name, "status": d.approval_status, "expiry_date": d.expiry_date,
                             "review_date": d.review_date} for d in docs],
                "policies": [{"name": p.name, "active": p.is_active} for p in policies]}

    # --- registry -----------------------------------------------------------
    def registry(self) -> Dict[str, Dict[str, Any]]:
        def schema(props: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
            return {"type": "object", "properties": props, "required": required, "additionalProperties": False}

        return {
            "list_campaigns": {"fn": lambda a: self.list_campaigns(), "description": "List campaigns in the workspace with their ids and briefs.",
                               "schema": schema({}, [])},
            "campaign_risk": {"fn": lambda a: self.campaign_risk(a["campaign_id"]),
                              "description": "Risk radar for one campaign: level, de-duplicated risks with evidence and actions, and unanalysed assets.",
                              "schema": schema({"campaign_id": {"type": "string"}}, ["campaign_id"])},
            "list_content": {"fn": lambda a: self.list_content(a.get("status")),
                             "description": "List content items with status (draft, in_review, changes_requested, approved, rejected) and whether the current version was analysed.",
                             "schema": schema({"status": {"type": "string", "enum": ["draft", "in_review", "changes_requested", "approved", "rejected"]}}, [])},
            "content_detail": {"fn": lambda a: self.content_detail(a["content_id"]),
                               "description": "Current text, open findings, claim checks and approval blockers for one content item.",
                               "schema": schema({"content_id": {"type": "string"}}, ["content_id"])},
            "search_evidence": {"fn": lambda a: self.search_evidence(a["query"]),
                                "description": "Search approved source documents; returns verbatim passages with document, section and expiry date.",
                                "schema": schema({"query": {"type": "string"}}, ["query"])},
            "verify_claims": {"fn": lambda a: self.verify_claims(a["text"]),
                              "description": "Check marketing text's claims against approved sources (supported, contradicted, stale, needs review, no evidence). Read-only.",
                              "schema": schema({"text": {"type": "string"}}, ["text"])},
            "governance_overview": {"fn": lambda a: self.governance_overview(),
                                    "description": "Rule count, rule conflicts, evidence sources with dates, and approval policies.",
                                    "schema": schema({}, [])},
        }


def _record(trace: List[Dict[str, Any]], name: str, args: Dict[str, Any], result: Any) -> Any:
    trace.append({"tool": name, "input": args, "output": result})
    return result


def ask_with_claude(tools: Toolbox, brand_name: str, question: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    import anthropic

    client = anthropic.Anthropic(timeout=60.0, max_retries=1)
    reg = tools.registry()
    tool_defs = [{"name": n, "description": t["description"], "input_schema": t["schema"], "strict": True} for n, t in reg.items()]
    messages: List[Dict[str, Any]] = [{"role": m["role"], "content": m["content"]} for m in history[-6:]]
    messages.append({"role": "user", "content": question})
    trace: List[Dict[str, Any]] = []
    for _ in range(MAX_STEPS):
        response = client.beta.messages.create(
            model=MODEL, max_tokens=4000, system=SYSTEM_PROMPT.format(brand=brand_name), tools=tool_defs,
            messages=messages, output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        )
        if response.stop_reason == "refusal":
            return {"answer": "The model declined to answer this question.", "trace": trace, "mode": "claude"}
        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content if b.type == "text").strip()
            return {"answer": text or "No answer was produced.", "trace": trace, "mode": "claude", "model": response.model}
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            tool = reg.get(block.name)
            try:
                out = _record(trace, block.name, block.input, tool["fn"](block.input)) if tool else {"error": "unknown tool"}
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(out, default=str)[:12000]})
            except Exception as exc:  # a failed lookup is reported to the model, never hidden
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": f"Tool failed: {exc}", "is_error": True})
        messages.append({"role": "user", "content": results})
    return {"answer": "I stopped after several lookups without a final answer. Try a narrower question.", "trace": trace, "mode": "claude"}


def _find_by_name(items: List[Dict[str, Any]], question: str, key: str) -> Optional[Dict[str, Any]]:
    q = question.lower()
    best, score = None, 0
    for it in items:
        words = [w for w in re.findall(r"[a-z0-9]+", it[key].lower()) if len(w) > 2]
        s = sum(1 for w in words if w in q)
        if s > score:
            best, score = it, s
    return best


def ask_deterministic(tools: Toolbox, question: str) -> Dict[str, Any]:
    """Keyword router over the same tools, for deployments without a model key."""
    q = question.lower()
    trace: List[Dict[str, Any]] = []
    quoted = re.findall(r"[\"“]([^\"”]{8,})[\"”]", question)

    if quoted or re.search(r"\b(verify|true|accurate|supported|claim)\b", q) and quoted:
        res = _record(trace, "verify_claims", {"text": quoted[0]}, tools.verify_claims(quoted[0]))
        if not res:
            return {"answer": "I found no checkable claim in that text (claims need figures, superlatives or capability statements).", "trace": trace}
        lines = [f"- “{r['claim']}”: **{r['status'].replace('_', ' ')}**. {r['rationale']}" for r in res]
        return {"answer": "Checked against the approved sources:\n" + "\n".join(lines), "trace": trace}

    if re.search(r"\b(risk|go wrong|campaign|launch|conflict)\b", q):
        camps = _record(trace, "list_campaigns", {}, tools.list_campaigns())
        if not camps:
            return {"answer": "There are no campaigns in this workspace yet.", "trace": trace}
        camp = _find_by_name(camps, question, "name") or camps[0]
        r = _record(trace, "campaign_risk", {"campaign_id": camp["campaign_id"]}, tools.campaign_risk(camp["campaign_id"]))
        top = "\n".join(f"- [{x['severity']}, {x['basis']}] {x['title']} — {x['action']}" for x in r["risks"][:6]) or "- none detected"
        extra = f"\n\nNot yet analysed: {', '.join(r['unverified'])}." if r["unverified"] else ""
        return {"answer": f"**{r['name']}** risk level: **{r['level'].replace('_', ' ')}**. {r['explanation']}\n\nTop risks:\n{top}{extra}", "trace": trace}

    if re.search(r"\b(publish|ready|approv|block|queue|waiting)\b", q):
        items = _record(trace, "list_content", {}, tools.list_content())
        item = _find_by_name(items, question, "title")
        if item:
            d = _record(trace, "content_detail", {"content_id": item["content_id"]}, tools.content_detail(item["content_id"]))
            if not d["analysed"]:
                return {"answer": f"**{d['title']}** v{d['version']} has not been analysed, so it can't be approved or published yet.", "trace": trace}
            state = "meets its approval requirements" if d["approval_satisfied"] else "is blocked: " + "; ".join(d["approval_blocking"])
            return {"answer": f"**{d['title']}** v{d['version']} is *{d['status'].replace('_', ' ')}* and {state}. "
                              f"It has {len(d['open_findings'])} open finding(s).", "trace": trace}
        waiting = [i for i in items if i["status"] == "in_review"]
        approved = [i for i in items if i["status"] == "approved"]
        return {"answer": f"{len(waiting)} item(s) in review ({', '.join(i['title'] for i in waiting) or 'none'}); "
                          f"{len(approved)} approved ({', '.join(i['title'] for i in approved) or 'none'}). Name an item to see what blocks it.", "trace": trace}

    if re.search(r"\b(unverified|not checked|not analy[sz]ed|coverage|unchecked|missing)", q):
        items = _record(trace, "list_content", {}, tools.list_content())
        un = [i["title"] for i in items if not i["analysed"]]
        return {"answer": (f"{len(un)} item(s) have an unanalysed current version: " + ", ".join(un) + "." if un
                           else "Every content item's current version has been analysed."), "trace": trace}

    if re.search(r"\b(source|evidence|document|expir|stale|polic|rule|conflict)", q):
        o = _record(trace, "governance_overview", {}, tools.governance_overview())
        exp = [s["name"] for s in o["sources"] if s["expiry_date"]]
        conflicts = "; ".join(c["title"] for c in o["rule_conflicts"]) or "none"
        return {"answer": f"{o['active_rules']} active rules; rule conflicts: {conflicts}. "
                          f"{len(o['sources'])} evidence sources ({', '.join(s['name'] + (' — expires ' + s['expiry_date'] if s['expiry_date'] else '') for s in o['sources'])}). "
                          f"Active policies: {', '.join(p['name'] for p in o['policies'] if p['active']) or 'none'}.", "trace": trace}

    return {"answer": "I can answer questions such as: *What could go wrong in the Atlas Pro launch?*, *Is the landing page ready to publish?*, "
                      "*Which content hasn't been checked?*, *Which sources are expiring?*, or check a quoted claim: *Verify \"Atlas Pro costs $59 per month\"*.",
            "trace": trace}


def ask(db: Session, brand: Brand, question: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    tools = Toolbox(db, brand.id)
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            return ask_with_claude(tools, brand.name, question, history)
        except Exception as exc:
            result = ask_deterministic(tools, question)
            result["mode"] = "deterministic"
            result["notice"] = f"The AI model call failed ({type(exc).__name__}); answered with the built-in rule-based assistant instead."
            return result
    result = ask_deterministic(tools, question)
    result["mode"] = "deterministic"
    result["notice"] = "No AI model is configured on this server, so the built-in rule-based assistant answered from the same read-only tools."
    return result
