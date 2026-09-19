"""Deterministic Chinese lexical retrieval over an explicit, permission-filtered corpus."""
from __future__ import annotations
import math
import re
from collections import Counter
from pathlib import Path
from .schemas import SearchArgs, ReadArgs
from ...core.config import BACKEND_DIR, PROJECT_ROOT
from ...core.security import allowed_doc_tokens

TOOLS = [
    {"type": "function", "function": {"name": "search_knowledge", "description": "搜索当前场景中已授权的企业或展厅资料。返回真实片段和资料ID；结果不足时可改写关键词补查。", "parameters": SearchArgs.model_json_schema()}},
    {"type": "function", "function": {"name": "read_document", "description": "按资料ID读取完整资料。用于核实搜索片段未展开的规则、展项与操作限制。只接受已授权资料ID，不接受路径。", "parameters": ReadArgs.model_json_schema()}},
]


def tokens(text: str) -> list[str]:
    result = re.findall(r"[a-z0-9]+", text.lower())
    for part in re.findall(r"[\u4e00-\u9fff]+", text):
        result.extend(part[i:i + 2] for i in range(len(part) - 1))
        if len(part) == 1:
            result.append(part)
    return result


class KnowledgeTools:
    def __init__(self, scenario: str, user: dict):
        self.documents = {}
        self.seen: dict[str, dict] = {}
        permitted = allowed_doc_tokens(user)
        if scenario == "exhibition":
            paths = [(p.stem, p) for p in sorted((BACKEND_DIR / "data/agent-knowledge/exhibition").glob("*.md"))]
        else:
            paths = []
            for category in ("company-common", "role-collaboration", "project"):
                source_root = PROJECT_ROOT / "dify/knowledge-source"
                if not source_root.is_dir():
                    source_root = BACKEND_DIR / "data/agent-knowledge/company"
                for index, p in enumerate(sorted(p for p in (source_root / category).glob("*.md") if not p.name.startswith("._")), 1):
                    if not p.name.startswith("._"):
                        paths.append((f"company-{category}-{index}", p))
        for doc_id, path in paths:
            if path.name.startswith("._") or (permitted is not None and doc_id not in permitted):
                continue
            body = path.read_text(encoding="utf-8")[:18000]
            title = body.splitlines()[0].lstrip("# ").strip()
            self.documents[doc_id] = {"document_id": doc_id, "title": title, "content": body}

    def execute(self, name: str, arguments: dict) -> dict:
        if name == "read_document":
            args = ReadArgs.model_validate(arguments)
            doc = self.documents.get(args.document_id)
            if doc is None:
                return {"status": "not_found", "message": "资料不存在或当前用户无权读取。"}
            self.seen[args.document_id] = {"document_id": args.document_id, "title": doc["title"], "excerpt": doc["content"][:500]}
            return {"status": "ok", **doc}
        if name != "search_knowledge":
            return {"status": "denied", "message": "工具不在允许列表中。"}
        args = SearchArgs.model_validate(arguments)
        query = set(tokens(args.query))
        docs = list(self.documents.values())
        counts = [Counter(tokens(d["title"] * 2 + d["content"])) for d in docs]
        df = Counter(t for c in counts for t in c)
        ranked = []
        for doc, count in zip(docs, counts):
            score = sum((1 + math.log(count[t])) * math.log(1 + len(docs) / (1 + df[t])) for t in query if count[t])
            if score <= 0:
                continue
            paragraphs = doc["content"].split("\n\n")
            selected = sorted(paragraphs, key=lambda p: len(query & set(tokens(p))), reverse=True)[:2]
            excerpt = "\n\n".join(selected)[:1400]
            ranked.append((score, {"document_id": doc["document_id"], "title": doc["title"], "excerpt": excerpt}))
        hits = [item for _, item in sorted(ranked, key=lambda pair: pair[0], reverse=True)[:4]]
        for hit in hits:
            self.seen[hit["document_id"]] = hit
        return {"status": "ok" if hits else "not_found", "results": hits, "message": "未命中不代表事实不存在；可尝试更具体的关键词。"}
