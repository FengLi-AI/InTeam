import json
from ...db import base
from ...db.models import AgentRun, _utcnow


def as_dict(row: AgentRun) -> dict:
    return {"id": row.id, "scenario": row.scenario, "question": row.question,
        "parent_run_id": row.parent_run_id, "status": row.status,
        "events": json.loads(row.events_json), "result": json.loads(row.result_json),
        "model": row.model, "created_at": row.created_ts.isoformat() + "Z"}


def get_run(user_id: int, run_id: str) -> dict | None:
    with base.SessionLocal() as db:
        row = db.query(AgentRun).filter_by(id=run_id, user_id=user_id).first()
        return as_dict(row) if row else None


def list_runs(user_id: int) -> list[dict]:
    with base.SessionLocal() as db:
        rows = db.query(AgentRun).filter_by(user_id=user_id).order_by(AgentRun.created_ts.desc()).limit(12).all()
        return [as_dict(row) for row in rows]


def save_run(run_id: str, *, status: str | None = None, events: list | None = None, result: dict | None = None):
    with base.SessionLocal() as db:
        row = db.get(AgentRun, run_id)
        if row is None:
            return
        if status is not None:
            row.status = status
            if status != "running":
                row.finished_ts = _utcnow()
        if events is not None:
            row.events_json = json.dumps(events, ensure_ascii=False)
        if result is not None:
            row.result_json = json.dumps(result, ensure_ascii=False)
        db.commit()


def recover_interrupted():
    """Only called on startup of the supported single-worker service."""
    from sqlalchemy import inspect
    if not inspect(base.engine).has_table("agent_runs"):
        return
    with base.SessionLocal() as db:
        rows = db.query(AgentRun).filter_by(status="running").all()
        for row in rows:
            row.status = "interrupted"
            row.finished_ts = _utcnow()
            row.result_json = json.dumps({"message": "服务重启，本次任务未完成。请重新准备。"}, ensure_ascii=False)
        if rows:
            db.commit()
