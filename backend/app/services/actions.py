"""候选建议的用户确认和正式入职行动。"""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.exc import IntegrityError

from ..db import base
from ..db.models import Action, AgentSuggestion, _utcnow
from .onboarding import TOPIC_KEYS, sync_topic_from_actions


class ActionConflictError(Exception):
    """候选建议已经被拒绝或状态不允许接受。"""


def _suggestion_to_dict(item: AgentSuggestion) -> dict:
    return {
        "id": item.id,
        "client_key": item.client_key,
        "title": item.title,
        "reason": item.reason,
        "action_type": item.action_type,
        "due_hint": item.due_hint,
        "topic_key": item.topic_key,
        "related_contact_key": item.related_contact_key or None,
        "decision": item.decision,
    }


def _action_to_dict(item: Action) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "reason": item.reason,
        "status": item.status,
        "due_date": item.due_date,
        "topic_key": item.topic_key,
        "source_type": item.source_type,
        "source_suggestion_id": item.source_suggestion_id,
    }


def save_agent_suggestions(
    *,
    user_id: int,
    conversation_id: int,
    chat_message_id: int,
    suggestions: list[dict[str, Any]],
) -> list[dict]:
    """保存 Dify 的安全候选建议；同一用户的 client_key 幂等。"""
    saved: list[AgentSuggestion] = []
    with base.SessionLocal() as session:
        for raw in suggestions:
            client_key = str(raw["client_key"]).strip()
            item = (
                session.query(AgentSuggestion)
                .filter(
                    AgentSuggestion.user_id == user_id,
                    AgentSuggestion.client_key == client_key,
                )
                .first()
            )
            if item is None:
                topic_key = str(raw.get("topic_key") or "")
                item = AgentSuggestion(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    chat_message_id=chat_message_id,
                    client_key=client_key,
                    title=str(raw["title"]).strip(),
                    reason=str(raw["reason"]).strip(),
                    action_type=str(raw["action_type"]),
                    due_hint=str(raw["due_hint"]),
                    topic_key=topic_key if topic_key in TOPIC_KEYS else "",
                    related_contact_key=str(raw.get("related_contact_key") or ""),
                )
                session.add(item)
                session.flush()
            saved.append(item)
        session.commit()
        return [_suggestion_to_dict(item) for item in saved]


def list_action_plan(user_id: int) -> dict:
    with base.SessionLocal() as session:
        suggestions = (
            session.query(AgentSuggestion)
            .filter(
                AgentSuggestion.user_id == user_id,
                AgentSuggestion.decision == "pending",
            )
            .order_by(AgentSuggestion.created_ts.desc(), AgentSuggestion.id.desc())
            .all()
        )
        actions = (
            session.query(Action)
            .filter(Action.user_id == user_id)
            .order_by(Action.created_ts.desc(), Action.id.desc())
            .all()
        )

    open_actions = [item for item in actions if item.status == "open"]
    today = date.today().isoformat()
    focus = sorted(
        open_actions,
        key=lambda item: (
            0 if item.due_date and item.due_date <= today else 1,
            item.due_date or "9999-12-31",
            item.id,
        ),
    )[:3]
    done = sum(1 for item in actions if item.status == "done")
    return {
        "today_focus": [_action_to_dict(item) for item in focus],
        "suggestions": [_suggestion_to_dict(item) for item in suggestions],
        "actions": [_action_to_dict(item) for item in actions],
        "blockers": [],
        "progress": {"done": done, "total": len(actions)},
    }


def create_action(
    user_id: int,
    *,
    suggestion_id: int | None = None,
    title: str | None = None,
    reason: str = "",
    due_date: str = "",
    topic_key: str = "",
) -> dict | None:
    if suggestion_id is None:
        if not title:
            raise ValueError("manual action requires title")
        if topic_key and topic_key not in TOPIC_KEYS:
            raise KeyError(topic_key)
        with base.SessionLocal() as session:
            item = Action(
                user_id=user_id,
                title=title.strip(),
                reason=reason.strip(),
                due_date=due_date,
                topic_key=topic_key,
                source_type="manual",
            )
            session.add(item)
            session.commit()
            result = _action_to_dict(item)
        sync_topic_from_actions(user_id, topic_key)
        return result

    with base.SessionLocal() as session:
        suggestion = (
            session.query(AgentSuggestion)
            .filter(
                AgentSuggestion.id == suggestion_id,
                AgentSuggestion.user_id == user_id,
            )
            .first()
        )
        if suggestion is None:
            return None
        existing = (
            session.query(Action)
            .filter(
                Action.user_id == user_id,
                Action.source_suggestion_id == suggestion.id,
            )
            .first()
        )
        if existing is not None:
            return _action_to_dict(existing)
        if suggestion.decision == "dismissed":
            raise ActionConflictError("suggestion was dismissed")
        item = Action(
            user_id=user_id,
            title=suggestion.title,
            reason=suggestion.reason,
            due_date=due_date,
            topic_key=suggestion.topic_key,
            source_type="agent",
            source_suggestion_id=suggestion.id,
        )
        suggestion.decision = "accepted"
        suggestion.decided_ts = _utcnow()
        session.add(item)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = (
                session.query(Action)
                .filter(
                    Action.user_id == user_id,
                    Action.source_suggestion_id == suggestion_id,
                )
                .first()
            )
            if existing is None:
                raise
            return _action_to_dict(existing)
        result = _action_to_dict(item)
        linked_topic = item.topic_key
    sync_topic_from_actions(user_id, linked_topic)
    return result


def dismiss_suggestion(user_id: int, suggestion_id: int) -> dict | None:
    with base.SessionLocal() as session:
        suggestion = (
            session.query(AgentSuggestion)
            .filter(
                AgentSuggestion.id == suggestion_id,
                AgentSuggestion.user_id == user_id,
            )
            .first()
        )
        if suggestion is None:
            return None
        if suggestion.decision == "accepted":
            raise ActionConflictError("suggestion was already accepted")
        if suggestion.decision == "pending":
            suggestion.decision = "dismissed"
            suggestion.decided_ts = _utcnow()
            session.commit()
        return _suggestion_to_dict(suggestion)


def update_action(user_id: int, action_id: int, **fields: str) -> dict | None:
    with base.SessionLocal() as session:
        item = (
            session.query(Action)
            .filter(Action.id == action_id, Action.user_id == user_id)
            .first()
        )
        if item is None:
            return None
        for key in ("title", "due_date", "status"):
            if key in fields and fields[key] is not None:
                setattr(item, key, fields[key])
        if item.status == "done" and item.completed_ts is None:
            item.completed_ts = _utcnow()
        elif item.status == "open":
            item.completed_ts = None
        session.commit()
        result = _action_to_dict(item)
        topic_key = item.topic_key
    sync_topic_from_actions(user_id, topic_key)
    return result


def delete_action(user_id: int, action_id: int) -> bool:
    with base.SessionLocal() as session:
        item = (
            session.query(Action)
            .filter(Action.id == action_id, Action.user_id == user_id)
            .first()
        )
        if item is None:
            return False
        topic_key = item.topic_key
        session.delete(item)
        session.commit()
    sync_topic_from_actions(user_id, topic_key)
    return True
