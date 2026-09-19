"""Behavioral checks; live-model evaluation is recorded separately."""
import asyncio
import json
import uuid
import pytest
from app.core.config import settings
from app.db import base
from app.db.models import AgentRun, AgentSuggestion, Action
from app.services.agent import model
from app.services.agent.knowledge import KnowledgeTools
from app.services.agent.runtime import ACTIVE, run_agent
from app.services.agent import runtime
from app.services.agent.storage import get_run


def tool(name, args, call_id="call_1"):
    return {"role":"assistant", "content":None, "tool_calls":[{"id":call_id, "type":"function", "function":{"name":name,"arguments":json.dumps(args)}}]}


def final(**kwargs):
    result={"status":"completed","title":"讲解准备","answer":"依据资料，先讲主线，再介绍能源转化。","source_ids":["hall-overview"],"missing_information":[],"suggested_actions":[{"title":"完成一次计时试讲","reason":"确认讲解时长"}],**kwargs}
    return {"role":"assistant","content":json.dumps(result,ensure_ascii=False)}


def run(monkeypatch, responses, stop=None, choices=None):
    received=[]
    async def fake(messages, **kwargs):
        if choices is not None: choices.append(kwargs.get("require_tools", False))
        received.append(json.loads(json.dumps(messages)))
        response=responses.pop(0)
        if isinstance(response,Exception): raise response
        return response
    monkeypatch.setattr(model,"complete",fake)
    uid,rid=101,uuid.uuid4().hex
    with base.SessionLocal() as db:
        db.add(AgentRun(id=rid,user_id=uid,scenario="exhibition",question="准备讲解"));db.commit()
    async def consume():
        signal=stop or asyncio.Event();ACTIVE[(uid,rid)]=signal
        frames=[]
        async for frame in run_agent(rid,{"id":uid},"准备10分钟讲解","exhibition",None,signal):
            if frame.startswith("data:"): frames.append(json.loads(frame[5:]))
        return frames
    return asyncio.run(consume()),received,get_run(uid,rid)


def test_model_uses_real_result_to_choose_next_tool(monkeypatch):
    frames,calls,stored=run(monkeypatch,[tool("search_knowledge",{"query":"展厅主线"}),tool("read_document",{"document_id":"hall-overview"},"call_2"),final()])
    assert stored["status"]=="completed" and stored["result"]["tool_calls"]==2
    assert "认识能源" in calls[1][-1]["content"] and calls[1][-1]["role"]=="tool"
    assert calls[2][-1]["tool_call_id"]=="call_2"
    assert [e["event"]["tool"] for e in frames if e["type"]=="trace" and e["event"]["kind"]=="tool_start"]==["search_knowledge","read_document"]
    with base.SessionLocal() as db:
        assert db.query(Action).count()==0
        assert db.query(AgentSuggestion).one().decision=="pending"


def test_clarification_needs_no_tools_or_actions(monkeypatch):
    _,_,stored=run(monkeypatch,[final(status="needs_input",source_ids=[],answer="面向哪类观众，预计讲多久？")])
    assert stored["status"]=="needs_input" and stored["result"]["tool_calls"]==0
    assert stored["result"]["action_suggestions"]==[]


def test_old_actions_are_supplied_only_after_task_lookup(monkeypatch):
    monkeypatch.setattr(runtime, "user_context", lambda user: {
        "current_date": "2026-09-19", "position": "讲解员",
        "actions": [{"title": "不应成为新任务的旧目标", "status": "open"}],
        "pending": [], "recently_dismissed": [],
    })
    _, calls, stored = run(monkeypatch, [tool("read_document", {"document_id": "hall-overview"}), final()])
    assert "不应成为新任务的旧目标" not in calls[0][0]["content"]
    assert "不应成为新任务的旧目标" in calls[1][0]["content"]
    assert stored["status"] == "completed"


def test_unknown_tool_is_denied(monkeypatch):
    _,calls,stored=run(monkeypatch,[tool("bash",{"command":"whoami"}),final(status="limited",source_ids=[],suggested_actions=[])])
    assert json.loads(calls[1][-1]["content"])["status"]=="denied"
    assert any(e["kind"]=="tool_rejected" for e in stored["events"])


@pytest.mark.parametrize("args",[{"document_id":"../../.env"},{"document_id":"hall-overview","user_id":999}])
def test_path_and_identity_injection_rejected(monkeypatch,args):
    _,calls,_=run(monkeypatch,[tool("read_document",args),final(status="limited",source_ids=[],suggested_actions=[])])
    assert json.loads(calls[1][-1]["content"])["status"]=="invalid_arguments"


def test_acl_applies_to_both_search_and_read(monkeypatch):
    monkeypatch.setattr(settings,"allow_all_authenticated_docs",False)
    monkeypatch.setattr(settings,"doc_acl",{"1":["hall-overview"]})
    tools=KnowledgeTools("exhibition",{"id":1})
    assert set(tools.documents)=={"hall-overview"}
    assert tools.execute("read_document",{"document_id":"operation-rules"})["status"]=="not_found"
    assert KnowledgeTools("exhibition",{"id":2}).execute("search_knowledge",{"query":"能源"})["results"]==[]


def test_each_tool_in_same_turn_counts_against_budget(monkeypatch):
    monkeypatch.setattr(settings,"agent_max_tools",1)
    response=tool("search_knowledge",{"query":"能源"})
    response["tool_calls"]+=tool("read_document",{"document_id":"hall-overview"},"second")["tool_calls"]
    _,_,stored=run(monkeypatch,[response])
    assert stored["status"]=="limit" and stored["result"]["tool_calls"]==1
    with base.SessionLocal() as db: assert db.query(AgentSuggestion).count()==0


def test_unobserved_source_requires_repair(monkeypatch):
    _,calls,stored=run(monkeypatch,[final(source_ids=["not-real"]),tool("search_knowledge",{"query":"不存在的统计"}),final(status="limited",source_ids=[],suggested_actions=[],answer="现有资料不足以确认。")])
    assert len(calls)==3 and stored["status"]=="limited"
    assert stored["result"]["sources"]==[]


def test_answer_without_lookup_requires_tool_then_returns_to_auto(monkeypatch):
    choices = []
    responses = [final(), tool("read_document", {"document_id": "hall-overview"}), final()]
    _, _, stored = run(monkeypatch, responses, choices=choices)
    assert stored["status"] == "completed"
    assert choices == [False, True, False]
    assert stored["result"]["tool_calls"] == 1


def test_pre_cancel_never_calls_model(monkeypatch):
    signal=asyncio.Event();signal.set()
    _,calls,stored=run(monkeypatch,[],signal)
    assert not calls and stored["status"]=="cancelled"


def test_failure_never_becomes_success(monkeypatch):
    _,_,stored=run(monkeypatch,[RuntimeError("test")])
    assert stored["status"]=="failed" and "answer" not in stored["result"]
    with base.SessionLocal() as db: assert db.query(AgentSuggestion).count()==0


@pytest.mark.parametrize("mode",["cancel","timeout"])
def test_inflight_model_is_cancelled(monkeypatch,mode):
    cancelled=[]
    async def slow(messages):
        try: await asyncio.sleep(30)
        finally: cancelled.append(True)
    monkeypatch.setattr(model,"complete",slow)
    if mode=="timeout": monkeypatch.setattr(settings,"agent_timeout",.03)
    rid=uuid.uuid4().hex
    with base.SessionLocal() as db:
        db.add(AgentRun(id=rid,user_id=1,scenario="exhibition",question="test"));db.commit()
    async def consume():
        signal=asyncio.Event()
        async def later():
            await asyncio.sleep(.05)
            if mode=="cancel": signal.set()
        stopper=asyncio.create_task(later())
        async for _ in run_agent(rid,{"id":1},"准备","exhibition",None,signal): pass
        await stopper
    asyncio.run(consume())
    assert cancelled
    assert get_run(1,rid)["status"]==("cancelled" if mode=="cancel" else "limit")


def test_repeated_candidates_do_not_duplicate(monkeypatch):
    run(monkeypatch,[tool("read_document",{"document_id":"hall-overview"}),final()])
    _,_,stored=run(monkeypatch,[tool("read_document",{"document_id":"hall-overview"}),final()])
    assert stored["result"]["action_suggestions"]==[]
    with base.SessionLocal() as db: assert db.query(AgentSuggestion).count()==1


def test_api_history_and_parent_are_user_isolated(api_client,auth_client,monkeypatch):
    assert api_client.get("/api/v1/agent/runs").status_code==401
    rid=uuid.uuid4().hex
    with base.SessionLocal() as db:
        db.add(AgentRun(id=rid,user_id=999,scenario="exhibition",question="private"));db.commit()
    assert auth_client.get(f"/api/v1/agent/runs/{rid}").status_code==404
    assert auth_client.post(f"/api/v1/agent/runs/{rid}/stop").status_code==404
    assert auth_client.get("/api/v1/agent/runs").json()["items"]==[]
    monkeypatch.setattr(settings,"deepseek_api_key","test")
    assert auth_client.post("/api/v1/agent/runs",json={"question":"继续","parent_run_id":rid}).status_code==404


def test_feature_flag_and_credentials(auth_client,monkeypatch):
    monkeypatch.setattr(settings,"agent_enabled",False)
    assert auth_client.post("/api/v1/agent/runs",json={"question":"准备"}).status_code==503
    monkeypatch.setattr(settings,"agent_enabled",True)
    assert auth_client.get("/api/v1/agent/config").json()["ready"] is False
    assert auth_client.post("/api/v1/agent/runs",json={"question":"准备"}).status_code==503


def test_api_end_to_end_candidate_confirmation(auth_client, monkeypatch):
    monkeypatch.setattr(settings,"deepseek_api_key","test")
    responses=[tool("read_document",{"document_id":"hall-overview"}),final()]
    async def fake(messages): return responses.pop(0)
    monkeypatch.setattr(model,"complete",fake)
    response=auth_client.post("/api/v1/agent/runs",json={"question":"帮我准备10分钟中学生讲解","scenario":"exhibition"})
    assert response.status_code==200
    events=[json.loads(frame[5:]) for frame in response.text.split("\n\n") if frame.startswith("data:")]
    done=events[-1]; assert done["status"]=="completed"
    sid=done["result"]["action_suggestions"][0]["id"]
    assert auth_client.get("/api/v1/actions").json()["actions"]==[]
    first=auth_client.post("/api/v1/actions",json={"suggestion_id":sid})
    second=auth_client.post("/api/v1/actions",json={"suggestion_id":sid})
    assert first.status_code==second.status_code==200
    assert first.json()["item"]["id"]==second.json()["item"]["id"]
    assert len(auth_client.get("/api/v1/actions").json()["actions"])==1
    assert auth_client.get(f"/api/v1/agent/runs/{done['run_id']}").json()["result"]["answer"]


def test_restart_marks_stale_runs_interrupted():
    from app.services.agent.storage import recover_interrupted
    rid=uuid.uuid4().hex
    with base.SessionLocal() as db:
        db.add(AgentRun(id=rid,user_id=1,scenario="company",question="old"));db.commit()
    recover_interrupted()
    assert get_run(1,rid)["status"]=="interrupted"

@pytest.mark.parametrize("kind,expected", [("task_input", "completed"), ("source_gap", "limited"), ("live_check", "limited")])
def test_information_gap_kind_controls_status_without_losing_detail(monkeypatch, kind, expected):
    _, _, stored = run(monkeypatch, [tool("read_document", {"document_id": "hall-overview"}), final(status="limited", information_gaps=[{"kind":kind,"text":"需要补充的具体内容"}])])
    assert stored["status"] == expected
    assert stored["result"]["missing_information"] == ["需要补充的具体内容"]
    assert stored["result"]["information_gaps"][0]["kind"] == kind


def test_task_gap_does_not_bypass_clarification_or_evidence(monkeypatch):
    _, _, stored = run(monkeypatch, [final(status="needs_input", source_ids=[], information_gaps=[{"kind":"task_input","text":"准备什么任务？"}])])
    assert stored["status"] == "needs_input" and stored["result"]["tool_calls"] == 0
    _, calls, stored = run(monkeypatch, [final(status="limited", information_gaps=[{"kind":"task_input","text":"讲解时长"}]), tool("read_document", {"document_id":"hall-overview"}), final()])
    assert len(calls) == 3 and stored["result"]["tool_calls"] == 1


def test_third_turn_keeps_original_user_requirements(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "test")
    received=[]
    async def fake(messages, **kwargs):
        received.append(messages)
        return final(status="needs_input",source_ids=[],suggested_actions=[],answer="还需要什么？")
    monkeypatch.setattr(model,"complete",fake)
    parent=None
    questions=["给中学生准备能源展厅讲解", "改成5分钟", "只保留风能"]
    for question in questions:
        response=auth_client.post("/api/v1/agent/runs",json={"question":question,"scenario":"exhibition","parent_run_id":parent})
        frames=[json.loads(f[5:]) for f in response.text.split("\n\n") if f.startswith("data:")]
        parent=frames[-1]["run_id"]
    assert [m["content"] for m in received[-1] if m["role"]=="user"] == questions
    assert '"weekday":' in received[-1][0]["content"]


def test_ready_material_can_include_a_pre_use_live_check(monkeypatch):
    _, _, stored = run(monkeypatch, [tool("read_document", {"document_id":"hall-overview"}), final(information_gaps=[{"kind":"live_check","text":"讲解前由现场人员确认设备可用"}])])
    assert stored["status"] == "completed"
    assert stored["result"]["information_gaps"][0]["kind"] == "live_check"


def test_backend_only_package_contains_both_scenarios(monkeypatch, tmp_path):
    from app.services.agent import knowledge
    import shutil
    from pathlib import Path
    backend = tmp_path / 'backend'
    corpus = backend / 'data/agent-knowledge'
    shutil.copytree(knowledge.BACKEND_DIR / 'data/agent-knowledge/exhibition', corpus / 'exhibition', ignore=shutil.ignore_patterns('._*'))
    for category in ('company-common', 'role-collaboration', 'project'):
        shutil.copytree(knowledge.PROJECT_ROOT / 'dify/knowledge-source' / category, corpus / 'company' / category, ignore=shutil.ignore_patterns('._*'))
    monkeypatch.setattr(knowledge, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(knowledge, 'BACKEND_DIR', backend)
    assert len(KnowledgeTools('company', {'id':1}).documents) == 9
    assert len(KnowledgeTools('exhibition', {'id':1}).documents) == 9
    assert KnowledgeTools('company', {'id':1}).execute('search_knowledge', {'query':'需求评审'})['results']
