"""六主题上手地图及用户进度。"""
from __future__ import annotations

from collections import Counter

from ..db import base
from ..db.models import Action, OnboardingProgress, _utcnow


TOPICS = (
    {
        "topic_key": "today_start",
        "title": "今日开始",
        "summary": "先完成入职第一天最重要的准备。",
        "suggested_questions": [
            "我入职第一周应该优先完成什么？",
            "需要先开通哪些账号和权限？",
            "第一次和导师对齐应该聊什么？",
        ],
    },
    {
        "topic_key": "company_business",
        "title": "公司与业务",
        "summary": "了解公司定位、产品、客户和工作价值观。",
        "suggested_questions": [
            "公司主要服务哪类客户？",
            "三款核心产品分别解决什么问题？",
            "公司倡导的工作价值观是什么？",
        ],
    },
    {
        "topic_key": "my_role",
        "title": "我的岗位",
        "summary": "明确岗位职责以及 30、60、90 天上手目标。",
        "suggested_questions": [
            "AI 产品经理的主要职责是什么？",
            "入职满一个月应达到什么程度？",
            "60 天目标要求完成什么闭环？",
        ],
    },
    {
        "topic_key": "current_project",
        "title": "当前项目",
        "summary": "理解北辰计划的背景、目标、模块和当前状态。",
        "suggested_questions": [
            "北辰计划现在处于什么阶段？",
            "北辰计划由哪些功能模块组成？",
            "当前项目有哪些 P0 风险？",
        ],
    },
    {
        "topic_key": "team_collaboration",
        "title": "团队与协作",
        "summary": "认识关键角色并掌握协作与升级路径。",
        "suggested_questions": [
            "遇到 RAG 评测问题应该找谁？",
            "需求是否进入当前版本由谁确认？",
            "问题卡住半天后应该如何升级？",
        ],
    },
    {
        "topic_key": "common_processes",
        "title": "常用流程",
        "summary": "掌握远程、请假、报销、出差和权限流程。",
        "suggested_questions": [
            "远程办公需要怎么申请？",
            "报销 2600 元需要提前做什么？",
            "请假、报销和权限申请分别用哪个系统？",
        ],
    },
)
TOPIC_KEYS = frozenset(topic["topic_key"] for topic in TOPICS)
PROGRESS_STATUSES = frozenset({"not_started", "exploring", "completed"})


def _validate_topic(topic_key: str) -> None:
    if topic_key not in TOPIC_KEYS:
        raise KeyError(topic_key)


def list_onboarding_map(user_id: int) -> list[dict]:
    with base.SessionLocal() as session:
        progress = {
            row.topic_key: row.status
            for row in session.query(OnboardingProgress)
            .filter(OnboardingProgress.user_id == user_id)
            .all()
        }
        action_counts = Counter(
            row.topic_key
            for row in session.query(Action)
            .filter(Action.user_id == user_id, Action.status == "open")
            .all()
            if row.topic_key
        )

    return [
        {
            **topic,
            "status": progress.get(topic["topic_key"], "not_started"),
            "open_action_count": action_counts.get(topic["topic_key"], 0),
        }
        for topic in TOPICS
    ]


def set_topic_progress(user_id: int, topic_key: str, status: str) -> dict:
    _validate_topic(topic_key)
    if status not in PROGRESS_STATUSES:
        raise ValueError(status)
    with base.SessionLocal() as session:
        row = (
            session.query(OnboardingProgress)
            .filter(
                OnboardingProgress.user_id == user_id,
                OnboardingProgress.topic_key == topic_key,
            )
            .first()
        )
        if row is None:
            row = OnboardingProgress(
                user_id=user_id,
                topic_key=topic_key,
                status=status,
            )
            session.add(row)
        else:
            row.status = status
            row.updated_ts = _utcnow()
        session.commit()
    return next(item for item in list_onboarding_map(user_id) if item["topic_key"] == topic_key)


def sync_topic_from_actions(user_id: int, topic_key: str) -> None:
    """按用户已确认行动同步主题：有未完成则了解中，全部完成则已完成。"""
    if not topic_key or topic_key not in TOPIC_KEYS:
        return
    with base.SessionLocal() as session:
        actions = (
            session.query(Action)
            .filter(Action.user_id == user_id, Action.topic_key == topic_key)
            .all()
        )
    if not actions:
        return
    set_topic_progress(
        user_id,
        topic_key,
        "completed" if all(item.status == "done" for item in actions) else "exploring",
    )
