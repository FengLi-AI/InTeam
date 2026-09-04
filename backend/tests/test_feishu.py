"""飞书只读客户端测试（mock 飞书 API 响应）。"""
import pytest

from app.services.feishu import (
    FeishuClient,
    FeishuDocument,
    FeishuError,
    FeishuPermissionError,
)


def _field(block_type: int) -> str:
    if 3 <= block_type <= 11:
        return f"heading{block_type - 2}"
    return {12: "bullet", 13: "ordered"}.get(block_type, "text")


def _block(block_type: int, content: str) -> dict:
    return {
        "block_id": f"b{block_type}",
        "block_type": block_type,
        _field(block_type): {"elements": [{"text_run": {"content": content}}]},
    }


def test_extract_sections_groups_by_heading():
    blocks = [
        _block(3, "入职首周"),  # heading1
        _block(2, "第一天上午参加入职说明会"),
        _block(12, "提前 10 分钟到场"),  # bullet
        _block(4, "考勤"),  # heading2
        _block(2, "每天 09:30 打卡"),
    ]
    doc = FeishuDocument(doc_token="T", title="新员工手册", url="https://x/docx/T", blocks=blocks)
    sections = FeishuClient.extract_sections(doc)

    assert len(sections) == 2
    assert sections[0].section == "入职首周"
    assert "说明会" in sections[0].text
    assert "- 提前 10 分钟到场" in sections[0].text
    assert sections[1].section == "考勤"
    assert "打卡" in sections[1].text
    assert all(s.title == "新员工手册" for s in sections)
    assert all(s.doc_token == "T" for s in sections)
    assert all(s.source_url == "https://x/docx/T" for s in sections)


def test_extract_sections_intro_falls_into_overview():
    blocks = [_block(2, "正文在无标题之前"), _block(3, "章节")]
    doc = FeishuDocument(doc_token="T", title="t", url="u", blocks=blocks)
    sections = FeishuClient.extract_sections(doc)
    assert sections[0].section == "概述"
    assert "正文在无标题之前" in sections[0].text


def test_fetch_document_returns_title_and_blocks(monkeypatch):
    client = FeishuClient(app_id="a", app_secret="s")
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(path)
        if path.endswith("/documents/T"):
            return {"document": {"title": "测试文档"}}
        return {"items": [_block(2, "内容")], "has_more": False}

    monkeypatch.setattr(client, "_get", fake_get)
    monkeypatch.setattr(client, "_get_token", lambda: "tok")

    doc = client.fetch_document("T")
    assert doc.title == "测试文档"
    assert len(doc.blocks) == 1
    assert doc.url.endswith("/T")
    # 只调用了文档元数据与 blocks 两个只读接口
    assert len(calls) == 2
    assert all("documents" in c for c in calls)


def test_client_has_no_write_methods():
    """只读红线：类方法中不出现 post/put/patch/delete 业务写接口。"""
    forbidden = {"post", "put", "patch", "delete"}
    methods = {name for name in dir(FeishuClient) if not name.startswith("_")}
    assert forbidden.isdisjoint(methods)


def test_permission_error_mapping():
    client = FeishuClient("a", "s")
    with pytest.raises(FeishuPermissionError):
        client._raise_by_code(99991672, "permission denied")
    with pytest.raises(FeishuPermissionError):
        client._raise_by_code(12345, "无权限访问该文档")
    with pytest.raises(FeishuError):
        client._raise_by_code(99999999, "unknown server error")
