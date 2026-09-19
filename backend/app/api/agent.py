"""Authenticated task preparation endpoints, isolated from the Dify chat path."""
import asyncio
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from ..core.config import settings
from ..core.security import CurrentUser
from ..db import base
from ..db.models import AgentRun
from ..services.agent.schemas import RunRequest
from ..services.agent.runtime import ACTIVE, run_agent
from ..services.agent.storage import get_run, list_runs
from ..services.rate_limit import chat_gate, limiter

router = APIRouter(prefix="/agent")


@router.get("/config")
def agent_config(user: CurrentUser):
    ready = bool(settings.agent_enabled and (settings.agent_api_key or settings.deepseek_api_key))
    return {"enabled": settings.agent_enabled, "ready": ready,
        "message": "" if ready else "任务准备尚未配置模型，请联系维护人员。"}


@router.get("/runs")
def runs(user: CurrentUser):
    return {"items": list_runs(int(user["id"]))}


@router.get("/runs/{run_id}")
def detail(run_id: str, user: CurrentUser):
    item = get_run(int(user["id"]), run_id)
    if item is None:
        raise HTTPException(404, "任务不存在")
    return item


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str, user: CurrentUser):
    item = get_run(int(user["id"]), run_id)
    if item is None:
        raise HTTPException(404, "任务不存在")
    signal = ACTIVE.get((int(user["id"]), run_id))
    if signal and item["status"] == "running":
        signal.set()
    else:
        signal = None
    return {"status": "stopping" if signal else item["status"]}


@router.post("/runs")
async def prepare(req: RunRequest, user: CurrentUser):
    if not settings.agent_enabled:
        raise HTTPException(503, "任务准备已关闭")
    if not (settings.agent_api_key or settings.deepseek_api_key):
        raise HTTPException(503, "任务准备尚未配置模型")
    uid = int(user["id"])
    parent = get_run(uid, req.parent_run_id) if req.parent_run_id else None
    if req.parent_run_id and (not parent or parent["scenario"] != req.scenario):
        raise HTTPException(404, "之前的准备任务不存在或不属于当前场景")
    if parent and parent["status"] == "running":
        raise HTTPException(409, "上一个任务尚未结束")
    key = f"user:{uid}"
    limiter.check(key + ":agent-hour", settings.chat_hourly_limit, 3600)
    chat_gate.acquire(key, settings.chat_concurrency_per_user, settings.chat_concurrency_global)
    run_id = uuid.uuid4().hex
    stop = asyncio.Event()
    try:
        with base.SessionLocal() as db:
            db.add(AgentRun(id=run_id, user_id=uid, scenario=req.scenario, question=req.question,
                parent_run_id=req.parent_run_id, model=settings.agent_model))
            db.commit()
        ACTIVE[(uid, run_id)] = stop
    except Exception:
        chat_gate.release(key)
        raise

    async def stream():
        try:
            async for event in run_agent(run_id, user, req.question, req.scenario, parent, stop):
                yield event
        finally:
            chat_gate.release(key)
            ACTIVE.pop((uid, run_id), None)
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Content-Encoding": "identity"})
