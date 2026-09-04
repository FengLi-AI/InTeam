"""飞书客户端：只读拉取文档 blocks 并提取文本，另支持发通知消息。

只读红线：本模块对飞书文档只调用 GET 类只读接口，永不回写文档；
`_get_token` 的 `POST /auth/v3/...` 是换取应用身份令牌的鉴权动作。
第 3 阶段新增 `send_message`（im:message）仅用于转人工发通知给 mentor，
不触碰任何文档写权限。
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

import httpx

LOG = logging.getLogger("inteam.feishu")

# 飞书 docx block_type 常量（用于识别标题层级与文本）
BLOCK_TEXT = 2
BLOCK_HEADING1 = 3  # heading1..heading9 = 3..11
BLOCK_HEADING9 = 11
_BLOCK_BULLET = 12
_BLOCK_ORDERED = 13
_BLOCK_CODE = 14
_BLOCK_QUOTE = 15
_BLOCK_TODO = 17

_HEADING_TYPES = set(range(BLOCK_HEADING1, BLOCK_HEADING9 + 1))

# block_type → 文本所在字段名（飞书 docx 不同 block 用不同字段承载 elements）
_TEXT_FIELDS = {
    2: "text",  # 文本段落
    12: "bullet",  # 无序列表
    13: "ordered",  # 有序列表
    14: "code",  # 代码块
    15: "quote",  # 引用
    17: "todo",  # 待办
}


class FeishuError(Exception):
    """飞书 API 返回非 0 错误码。"""

    def __init__(self, code: int, msg: str) -> None:
        self.code = code
        self.msg = msg
        super().__init__(f"feishu error {code}: {msg}")


class FeishuPermissionError(FeishuError):
    """应用身份无权限读取该文档（越权即不可见）。"""


@dataclass
class FeishuDocument:
    """一次拉取到的飞书文档：token + 标题 + 链接 + 原始 blocks。"""

    doc_token: str
    title: str
    url: str
    blocks: list[dict]


@dataclass
class Section:
    """从飞书文档提取的一段：文档标题 + 章节 + 正文 + 出处。"""

    title: str
    section: str
    text: str
    doc_token: str
    source_url: str


class FeishuClient:
    """应用身份只读访问飞书文档。"""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        base_url: str = "https://open.feishu.cn",
        doc_url_prefix: str = "https://feishu.cn/docx/",
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self.doc_url_prefix = doc_url_prefix.rstrip("/") + "/"
        self._token: str | None = None
        self._token_expire_at: float = 0.0

    # ---- 只读 HTTP 封装 ----
    def _get_token(self) -> str:
        """换取并缓存 tenant_access_token（应用身份鉴权）。"""
        if self._token and time.time() < self._token_expire_at - 60:
            return self._token
        resp = httpx.post(
            f"{self.base_url}/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            self._raise_by_code(data.get("code", -1), data.get("msg", "unknown"))
        self._token = data["tenant_access_token"]
        self._token_expire_at = time.time() + int(data.get("expire", 7200))
        return self._token

    def _get(self, path: str, params: dict | None = None) -> dict:
        """GET 请求，校验 code==0，返回 data 字段。"""
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self._get_token()}"}
        resp = httpx.get(url, headers=headers, params=params, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            self._raise_by_code(data.get("code", -1), data.get("msg", "unknown"))
        return data.get("data", {})

    def send_message(self, receive_id: str, text: str, receive_id_type: str = "open_id") -> str:
        """发飞书消息（im:message，只发通知、不碰文档），返回 message_id。

        第 3 阶段引入：转人工通知 mentor。需应用已申请 im:message 权限。
        """
        resp = httpx.post(
            f"{self.base_url}/open-apis/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers={"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json"},
            json={
                "receive_id": receive_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}, ensure_ascii=False),
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            self._raise_by_code(data.get("code", -1), data.get("msg", "unknown"))
        return (data.get("data") or {}).get("message_id", "")

    @staticmethod
    def _raise_by_code(code: int, msg: str) -> None:
        """把权限类错误映射为 FeishuPermissionError，其余为 FeishuError。"""
        lower = msg.lower()
        if code in (99991663, 99991668, 99991672) or "permission" in lower or "权限" in msg or "无权" in msg:
            raise FeishuPermissionError(code, msg)
        raise FeishuError(code, msg)

    # ---- 拉取文档 ----
    def fetch_document(self, doc_token: str) -> FeishuDocument:
        """拉取文档标题与全部 blocks。"""
        meta = self._get(f"/open-apis/docx/v1/documents/{doc_token}")
        title = (meta.get("document") or {}).get("title") or doc_token
        blocks = self._fetch_blocks(doc_token)
        return FeishuDocument(
            doc_token=doc_token,
            title=title,
            url=f"{self.doc_url_prefix}{doc_token}",
            blocks=blocks,
        )

    def _fetch_blocks(self, doc_token: str) -> list[dict]:
        """分页拉取文档全部 blocks（扁平列表）。"""
        blocks: list[dict] = []
        page_token: str | None = None
        while True:
            params: dict = {"page_size": 500, "document_revision_id": -1}
            if page_token:
                params["page_token"] = page_token
            data = self._get(f"/open-apis/docx/v1/documents/{doc_token}/blocks", params)
            blocks.extend(data.get("items", []))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
            if not page_token:
                break
        return blocks

    # ---- 文本提取 ----
    @staticmethod
    def extract_sections(doc: FeishuDocument) -> list[Section]:
        """按标题把 blocks 切分为若干 Section（正文归到最近的标题下）。"""
        sections: list[Section] = []
        current_section = "概述"
        buf: list[str] = []

        def flush() -> None:
            if buf:
                sections.append(
                    Section(
                        title=doc.title,
                        section=current_section,
                        text="\n".join(buf).strip(),
                        doc_token=doc.doc_token,
                        source_url=doc.url,
                    )
                )
                buf.clear()

        for block in doc.blocks:
            bt = block.get("block_type")
            text = FeishuClient._block_text(block)
            if bt in _HEADING_TYPES:
                flush()
                current_section = text or f"标题{bt - BLOCK_HEADING1 + 1}"
            elif text:
                buf.append(text)
        flush()
        return sections

    @staticmethod
    def _block_text(block: dict) -> str:
        """提取 block 的纯文本；bullet/ordered 加前缀；无文本返回空串。

        注意：飞书 docx 中标题块（heading1~heading9）的文本在 `headingN` 字段里，
        普通段落、列表、引用等分别在 `text`/`bullet`/`quote` 等字段里。
        """
        bt = block.get("block_type")
        if BLOCK_HEADING1 <= bt <= BLOCK_HEADING9:
            field = f"heading{bt - BLOCK_HEADING1 + 1}"
        else:
            field = _TEXT_FIELDS.get(bt)
        if not field:
            return ""
        text_obj = block.get(field)
        if not isinstance(text_obj, dict):
            return ""
        parts: list[str] = []
        for el in text_obj.get("elements", []) or []:
            tr = el.get("text_run")
            if tr and tr.get("content"):
                parts.append(tr["content"])
        raw = "".join(parts).strip()
        if not raw:
            return ""
        if bt == _BLOCK_BULLET:
            return f"- {raw}"
        if bt == _BLOCK_ORDERED:
            return f"1. {raw}"
        return raw
