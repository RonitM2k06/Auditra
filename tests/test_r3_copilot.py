"""Governance Copilot: read-only, permission-scoped, cites its tool calls."""
import sys
import types
import uuid

import pytest

from tests.conftest import make_client, register_client


@pytest.fixture(scope="module")
def creator():
    return make_client("creator")


@pytest.fixture(scope="module")
def brand_id(creator):
    return next(b["id"] for b in creator.get("/api/brands").json() if b["slug"] == "northstar")


def ask(c, brand_id, q):
    r = c.post(f"/api/brands/{brand_id}/copilot", json={"question": q})
    assert r.status_code == 200, r.text
    return r.json()


def test_deterministic_campaign_risk(creator, brand_id, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = ask(creator, brand_id, "What could go wrong in the Atlas Pro launch campaign?")
    assert r["mode"] == "deterministic" and "No AI model" in r["notice"]
    assert [t["tool"] for t in r["trace"]] == ["list_campaigns", "campaign_risk"]
    assert "Atlas Pro launch" in r["answer"] and "risk level" in r["answer"]


def test_deterministic_claim_check_cites_source(creator, brand_id, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = ask(creator, brand_id, 'Verify "Atlas Pro costs $59 per member per month."')
    assert "contradicted" in r["answer"]
    out = r["trace"][0]["output"][0]
    assert out["source"] == "Northstar Product Fact Sheet 2026" and "$49" in out["passage"]


def test_deterministic_unverified_and_help(creator, brand_id, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert "unanalysed" in ask(creator, brand_id, "Which content is not analysed yet?")["answer"]
    assert "I can answer" in ask(creator, brand_id, "hello there")["answer"]


def test_copilot_is_audited_and_permissioned(creator, brand_id):
    ask(creator, brand_id, "Which sources are expiring?")
    events = creator.get(f"/api/brands/{brand_id}/audit?event_type=copilot_query").json()
    assert events and events[0]["event_metadata"]["tools"] == ["governance_overview"]
    assert make_client().post(f"/api/brands/{brand_id}/copilot", json={"question": "hi there"}).status_code == 401
    outsider = register_client(f"cop-{uuid.uuid4().hex[:6]}@example.com")
    assert outsider.post(f"/api/brands/{brand_id}/copilot", json={"question": "hi there"}).status_code == 404
    assert creator.post(f"/api/brands/{brand_id}/copilot", json={"question": "x"}).status_code == 422


class _Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _FakeMessages:
    """Scripted model: one tool call (with a foreign campaign id), then a final answer."""
    calls = []

    def create(self, **kw):
        _FakeMessages.calls.append(kw)
        assert kw["model"] == "claude-opus-5-5" and "tool_choice" not in kw and kw["fallbacks"] == "default"
        if len(_FakeMessages.calls) == 1:
            return _Block(stop_reason="tool_use", model="claude-opus-5-5", content=[
                _Block(type="tool_use", id="t1", name="campaign_risk", input={"campaign_id": "someone-elses-campaign"}),
                _Block(type="tool_use", id="t2", name="list_campaigns", input={}),
            ])
        results = kw["messages"][-1]["content"]
        assert results[0]["tool_use_id"] == "t1" and "No campaign" in results[0]["content"]
        return _Block(stop_reason="end_turn", model="claude-opus-5-5", content=[_Block(type="text", text="Atlas Pro launch is the only campaign.")])


def test_claude_mode_tool_loop(creator, brand_id, monkeypatch):
    fake = types.ModuleType("anthropic")
    fake.Anthropic = lambda **kw: _Block(beta=_Block(messages=_FakeMessages()))
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-real")
    _FakeMessages.calls = []
    r = ask(creator, brand_id, "Which campaigns exist?")
    assert r["mode"] == "claude" and r["answer"].startswith("Atlas Pro launch")
    assert [t["tool"] for t in r["trace"]] == ["campaign_risk", "list_campaigns"]
    assert r["trace"][0]["output"] == {"error": "No campaign with that id in this workspace."}  # scoped to this workspace
    tool_names = {t["name"] for t in _FakeMessages.calls[0]["tools"]}
    assert not tool_names & {"approve", "publish", "apply", "update_rule"}  # read-only toolset


def test_model_failure_falls_back(creator, brand_id, monkeypatch):
    fake = types.ModuleType("anthropic")

    def boom(**kw):
        raise RuntimeError("network down")
    fake.Anthropic = boom
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-real")
    r = ask(creator, brand_id, "Which sources are expiring?")
    assert r["mode"] == "deterministic" and "failed" in r["notice"]
