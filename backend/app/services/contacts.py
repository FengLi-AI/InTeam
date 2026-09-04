"""关键同事：种子数据 + 列表/简介/沟通草稿/备注标签。"""
from __future__ import annotations

import logging

from ..core.config import settings
from ..db import base
from ..db.models import Contact, UserLabel

LOG = logging.getLogger("inteam.contacts")

# 虚拟关键同事（与飞书文档《星澜科技｜关键同事速查表》一致）
CONTACTS_SEED = [
    ("陈屿", "前端组", "高级前端工程师", "你的专属 mentor", "技术问题、入职任何疑问", "🧑‍💻"),
    ("周默", "前端组", "前端负责人", "直属 leader", "工作安排、目标确认", "👨‍💼"),
    ("林晓", "财务部", "财务专员", "费用报销、发票审核", "报销、发票、费用申请", "💰"),
    ("王立", "技术部", "运维工程师", "权限、设备、网络", "权限申请、生产环境", "🔧"),
    ("苏晴", "人事部", "HRBP", "入职手续、考勤", "入职手续、社保、请假考勤", "📋"),
    ("陈晨", "产品部", "产品经理", "需求与产品文档", "需求澄清、产品文档", "📱"),
    ("李想", "技术部", "后端工程师", "后端服务、接口", "接口联调、后端服务", "⚙️"),
    ("赵艺", "设计部", "UI 设计师", "设计稿、视觉规范", "设计稿、视觉规范", "🎨"),
    ("孙凯", "质量部", "测试工程师", "提测、缺陷", "提测、测试用例、缺陷", "🧪"),
    ("何晶", "行政部", "行政专员", "工位、门禁、办公用品", "工位、门禁、办公用品", "🏢"),
]


def seed_contacts() -> None:
    """首次启动时写入虚拟同事（幂等）。"""
    with base.SessionLocal() as s:
        if s.query(Contact).count() > 0:
            return
        for i, (name, dept, pos, duty, when, emoji) in enumerate(CONTACTS_SEED):
            s.add(
                Contact(
                    name=name,
                    department=dept,
                    position=pos,
                    duty=duty,
                    when_to_ask=when,
                    avatar_emoji=emoji,
                    sort_order=i,
                )
            )
        s.commit()


def _contact_to_dict(c: Contact, labels: list[str]) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "department": c.department,
        "position": c.position,
        "duty": c.duty,
        "when_to_ask": c.when_to_ask,
        "avatar_emoji": c.avatar_emoji,
        "labels": labels,
    }


# 关键词 → 同事名（用于问答里「找谁」的结构化联动）
_KEYWORD_MAP = [
    (["报销", "发票", "费用", "财务"], "林晓"),
    (["权限", "生产", "运维", "网络", "设备", "账号"], "王立"),
    (["请假", "考勤", "社保", "公积金", "福利", "人事", "hr"], "苏晴"),
    (["需求", "产品", "prd", "排期"], "陈晨"),
    (["接口", "后端", "联调", "服务"], "李想"),
    (["设计", "视觉", "ui", "设计稿"], "赵艺"),
    (["测试", "提测", "缺陷", "qa", "bug"], "孙凯"),
    (["工位", "门禁", "办公用品", "行政", "团建"], "何晶"),
    (["代码", "前端", "规范", "技术", "mentor", "导师", "开发"], "陈屿"),
    (["目标", "绩效", "工作安排", "leader", "负责人"], "周默"),
]


def match_contacts(question: str) -> list[dict]:
    """按关键词匹配与问题相关的同事，返回结构化列表（供前端联动展示）。"""
    q = question.lower()
    matched_names: list[str] = []
    for keywords, name in _KEYWORD_MAP:
        if any(k in q for k in keywords):
            matched_names.append(name)
    if not matched_names:
        return []
    with base.SessionLocal() as s:
        rows = s.query(Contact).filter(Contact.name.in_(matched_names)).all()
    return [_contact_to_dict(c, []) for c in rows]


def list_contacts(user_id: int | None = None) -> list[dict]:
    """同事列表（附当前用户的备注标签）。"""
    with base.SessionLocal() as s:
        contacts = s.query(Contact).order_by(Contact.sort_order).all()
        labels: dict[int, list[str]] = {}
        if user_id is not None:
            for lbl in s.query(UserLabel).filter(UserLabel.user_id == user_id).all():
                labels.setdefault(lbl.contact_id, []).append(lbl.label)
    return [_contact_to_dict(c, labels.get(c.id, [])) for c in contacts]


def get_contact(contact_id: int) -> Contact | None:
    with base.SessionLocal() as s:
        return s.get(Contact, contact_id)


def contact_intro(c: Contact, user_name: str = "新同事") -> str:
    """AI 生成「TA 负责什么、你什么时候该找 TA」的简介；无 Key 用模板兜底。"""
    if settings.has_key:
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                timeout=settings.timeout_seconds,
            )
            prompt = (
                f"你是一名入职助手。用一段不超过 80 字的自然中文，向新员工介绍同事：\n"
                f"姓名：{c.name}，部门：{c.department}，岗位：{c.position}，\n"
                f"职责：{c.duty}，什么时候找 TA：{c.when_to_ask}。\n"
                f"要求：口语化、直接说「TA 负责什么、你什么时候该找 TA」，不编造额外信息。"
            )
            resp = client.chat.completions.create(
                model=settings.deepseek_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                return text
        except Exception as exc:  # noqa: BLE001
            LOG.warning("contact intro generation failed: %s", exc)
    return f"{c.name}是{c.department}的{c.position}，负责{c.duty}。遇到{c.when_to_ask}时，找 TA 就对啦。"


def draft_message(c: Contact, user_name: str = "新同事") -> str:
    """AI 生成一段可直接发给 TA 的沟通草稿；无 Key 用模板兜底。"""
    if settings.has_key:
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                timeout=settings.timeout_seconds,
            )
            prompt = (
                f"你是新员工 {user_name}，要给同事 {c.name}（{c.department} {c.position}，负责{c.duty}）发消息。\n"
                f"事由：{c.when_to_ask}。\n"
                f"请写一段 50 字以内的礼貌开场消息，直接可发送，不要多余解释。"
            )
            resp = client.chat.completions.create(
                model=settings.deepseek_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                return text
        except Exception as exc:  # noqa: BLE001
            LOG.warning("draft message generation failed: %s", exc)
    return f"{c.name}你好，我是新入职的{user_name}，想咨询一下「{c.when_to_ask}」相关的事情，方便的时候请教你，谢谢！"


def add_label(user_id: int, contact_id: int, label: str) -> dict:
    """给同事打备注标签。"""
    label = label.strip()
    with base.SessionLocal() as s:
        if not label:
            return {"status": "ok", "added": False}
        exists = (
            s.query(UserLabel)
            .filter(UserLabel.user_id == user_id, UserLabel.contact_id == contact_id, UserLabel.label == label)
            .first()
        )
        if exists is not None:
            return {"status": "ok", "added": False}
        s.add(UserLabel(user_id=user_id, contact_id=contact_id, label=label))
        s.commit()
    return {"status": "ok", "added": True}
