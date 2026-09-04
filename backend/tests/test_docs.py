"""资料库文档列表与导读测试。"""
from app.services.docs import doc_intro, list_docs


def test_list_docs_empty_without_ark():
    """conftest 清空了方舟配置，向量库不可用 → 返回空列表。"""
    assert list_docs() == []


def test_doc_intro_fallback():
    intro = doc_intro("nonexistent_token")
    assert intro  # 无内容时返回兜底文案，不抛异常
