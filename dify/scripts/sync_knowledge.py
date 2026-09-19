#!/usr/bin/env python3
"""Safely create and populate the InTeam Dify knowledge bases.

The command is dry-run by default. Pass --apply to create knowledge bases and
upload documents. Existing documents with the same filename are left intact.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DIFY_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = DIFY_DIR / ".env"


@dataclass(frozen=True)
class KnowledgeBaseSpec:
    key: str
    name: str
    description: str
    source_dir: Path
    doc_form: str
    process_rule: dict[str, Any]


SPECS = {
    "role_collaboration": KnowledgeBaseSpec(
        key="role_collaboration",
        name="InTeam-岗位与协作库",
        description="InTeam 新员工的岗位目标、团队角色、联系人和产品研发协作流程。",
        source_dir=DIFY_DIR / "knowledge-source" / "role-collaboration",
        doc_form="text_model",
        process_rule={
            "mode": "custom",
            "rules": {
                "pre_processing_rules": [
                    {"id": "remove_extra_spaces", "enabled": True},
                    {"id": "remove_urls_emails", "enabled": False},
                ],
                "segmentation": {
                    "separator": "\n---\n",
                    "max_tokens": 2000,
                    "chunk_overlap": 0,
                },
            },
        },
    ),
    "project": KnowledgeBaseSpec(
        key="project",
        name="InTeam-项目知识库",
        description="InTeam 北辰计划的背景、模块、术语、里程碑、风险和发布规则。",
        source_dir=DIFY_DIR / "knowledge-source" / "project",
        doc_form="hierarchical_model",
        process_rule={
            "mode": "hierarchical",
            "rules": {
                "pre_processing_rules": [
                    {"id": "remove_extra_spaces", "enabled": True},
                    {"id": "remove_urls_emails", "enabled": False},
                ],
                "parent_mode": "full-doc",
                "segmentation": {
                    "separator": "\n\n",
                    "max_tokens": 2000,
                    "chunk_overlap": 0,
                },
                "subchunk_segmentation": {
                    "separator": "\n",
                    "max_tokens": 220,
                    "chunk_overlap": 30,
                },
            },
        },
    ),
}


class DifyApiError(RuntimeError):
    pass


def load_env(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"配置文件不存在：{path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


class DifyKnowledgeClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        body: bytes | None = None,
        content_type: str | None = None,
        timeout: float = 60,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "InTeam-Dify-Knowledge-Sync/1.0",
        }
        if json_body is not None:
            body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=body, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise DifyApiError(f"Dify API HTTP {exc.code}: {error_body[:1000]}") from exc
        except urllib.error.URLError as exc:
            raise DifyApiError(f"无法连接 Dify API：{exc.reason}") from exc
        if not payload:
            return {}
        return json.loads(payload.decode("utf-8"))

    def list_datasets(self) -> list[dict[str, Any]]:
        result = self.request("GET", "/datasets?page=1&limit=100")
        return list(result.get("data") or [])

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        return self.request("GET", f"/datasets/{dataset_id}")

    def create_dataset(
        self,
        spec: KnowledgeBaseSpec,
        *,
        embedding_model: str,
        embedding_model_provider: str,
        retrieval_model: dict[str, Any],
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            "/datasets",
            json_body={
                "name": spec.name,
                "description": spec.description,
                "indexing_technique": "high_quality",
                "permission": "only_me",
                "provider": "vendor",
                "embedding_model": embedding_model,
                "embedding_model_provider": embedding_model_provider,
                "retrieval_model": retrieval_model,
            },
        )

    def update_dataset_retrieval(
        self, dataset_id: str, retrieval_model: dict[str, Any]
    ) -> dict[str, Any]:
        return self.request(
            "PATCH",
            f"/datasets/{dataset_id}",
            json_body={"retrieval_model": retrieval_model},
        )

    def list_documents(self, dataset_id: str) -> list[dict[str, Any]]:
        result = self.request(
            "GET", f"/datasets/{dataset_id}/documents?page=1&limit=100"
        )
        return list(result.get("data") or [])

    def upload_document(
        self, dataset_id: str, path: Path, spec: KnowledgeBaseSpec
    ) -> dict[str, Any]:
        boundary = f"----InTeamDify{uuid.uuid4().hex}"
        config = {
            "indexing_technique": "high_quality",
            "doc_form": spec.doc_form,
            "doc_language": "Chinese",
            "process_rule": spec.process_rule,
        }
        parts: list[bytes] = []
        parts.append(
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="data"\r\n'
                "Content-Type: application/json; charset=utf-8\r\n\r\n"
                f"{json.dumps(config, ensure_ascii=False)}\r\n"
            ).encode("utf-8")
        )
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
                "Content-Type: text/markdown; charset=utf-8\r\n\r\n"
            ).encode("utf-8")
            + path.read_bytes()
            + b"\r\n"
        )
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        return self.request(
            "POST",
            f"/datasets/{dataset_id}/document/create-by-file",
            body=b"".join(parts),
            content_type=f"multipart/form-data; boundary={boundary}",
            timeout=120,
        )


def find_source_dataset(client: DifyKnowledgeClient) -> dict[str, Any]:
    configured_id = os.getenv("DIFY_DATASET_COMPANY_COMMON_ID", "").strip()
    if configured_id:
        return client.get_dataset(configured_id)
    datasets = client.list_datasets()
    candidates = [item for item in datasets if item.get("name") == "InTeam"]
    if len(candidates) != 1:
        raise SystemExit(
            "无法唯一识别公司通识库。请在 dify/.env 填写 "
            "DIFY_DATASET_COMPANY_COMMON_ID。"
        )
    return client.get_dataset(str(candidates[0]["id"]))


def wait_until_available(
    client: DifyKnowledgeClient,
    dataset_id: str,
    filename: str,
    *,
    timeout_seconds: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        matches = [
            document
            for document in client.list_documents(dataset_id)
            if document.get("name") == filename
        ]
        if matches:
            document = matches[0]
            status = document.get("display_status")
            print(f"  索引状态：{filename} -> {status}")
            if status == "available":
                if int(document.get("word_count") or 0) <= 0:
                    raise DifyApiError(f"{filename} 已完成但没有可用文本")
                return document
            if status in {"error", "disabled"}:
                raise DifyApiError(
                    f"{filename} 索引失败：{document.get('error') or status}"
                )
        time.sleep(5)
    raise DifyApiError(f"等待 {filename} 索引完成超时")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file", type=Path, default=DEFAULT_ENV_PATH, help="Dify 环境变量文件"
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=sorted(SPECS),
        help="只同步指定知识库；可重复。默认同步两个知识库。",
    )
    parser.add_argument("--apply", action="store_true", help="实际创建和上传")
    parser.add_argument(
        "--wait-seconds", type=int, default=600, help="单个文档最大索引等待时间"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env(args.env_file)
    base_url = os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1").strip()
    api_key = os.getenv("DIFY_DATASET_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("DIFY_DATASET_API_KEY 未配置")

    client = DifyKnowledgeClient(base_url, api_key)
    source = find_source_dataset(client)
    embedding_model = str(source.get("embedding_model") or "")
    embedding_model_provider = str(source.get("embedding_model_provider") or "")
    if not embedding_model or not embedding_model_provider:
        raise SystemExit("公司通识库没有可复用的 Embedding 模型配置")
    source_retrieval_model = source.get("retrieval_model_dict")
    if not isinstance(source_retrieval_model, dict):
        raise SystemExit("公司通识库没有可复用的检索配置")
    retrieval_model = dict(source_retrieval_model)
    # The 9-document demo corpus needs a wider candidate pool before reranking.
    # Top K 5 missed exact 30-day and Alpha milestone chunks in live tests.
    retrieval_model["top_k"] = 10

    targets = args.target or list(SPECS)
    existing_by_name = {
        str(item.get("name")): item for item in client.list_datasets()
    }
    print(f"模式：{'执行' if args.apply else '预演'}")
    print(f"复用 Embedding：{embedding_model}")
    results: dict[str, str] = {}

    for target in targets:
        spec = SPECS[target]
        files = sorted(
            path
            for path in spec.source_dir.glob("*.md")
            if not path.name.startswith("._")
        )
        if len(files) != 3:
            raise SystemExit(f"{spec.source_dir} 应有 3 份 Markdown，实际为 {len(files)}")
        print(f"\n[{spec.name}] {spec.doc_form}")
        dataset = existing_by_name.get(spec.name)
        if dataset is None:
            print("  将创建知识库")
            if not args.apply:
                for path in files:
                    print(f"  将上传：{path.name}")
                continue
            dataset = client.create_dataset(
                spec,
                embedding_model=embedding_model,
                embedding_model_provider=embedding_model_provider,
                retrieval_model=retrieval_model,
            )
            print(f"  已创建：{dataset['id']}")
        else:
            print(f"  复用已有知识库：{dataset['id']}")

        dataset_id = str(dataset["id"])
        results[target] = dataset_id
        dataset_detail = client.get_dataset(dataset_id)
        if dataset_detail.get("retrieval_model_dict") != retrieval_model:
            print("  将同步公司通识库的 Hybrid Search / Rerank 配置")
            if args.apply:
                client.update_dataset_retrieval(dataset_id, retrieval_model)
                print("  检索配置已同步")
        existing_documents = {
            str(item.get("name")): item
            for item in client.list_documents(dataset_id)
        }
        for path in files:
            existing = existing_documents.get(path.name)
            if existing is not None:
                print(f"  跳过已有文档：{path.name} ({existing.get('display_status')})")
                continue
            print(f"  上传：{path.name}")
            client.upload_document(dataset_id, path, spec)
            wait_until_available(
                client,
                dataset_id,
                path.name,
                timeout_seconds=args.wait_seconds,
            )

    if args.apply:
        print("\n知识库 ID：")
        for key, dataset_id in results.items():
            print(f"  {key}={dataset_id}")
    else:
        print("\n这是预演，没有修改 Dify。确认后添加 --apply。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DifyApiError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
