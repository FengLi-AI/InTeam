"""FAQ 沉淀 / 确认 / 检索测试。"""
from app.services.faq import add_faq, confirm_faq, search_faq


def test_faq_candidate_not_searchable_until_confirmed():
    faq_id = add_faq("怎么连数据库", "找 DBA 申请只读账号", "https://x")
    assert search_faq("数据库") == []  # 候选未确认，检索不到


def test_faq_confirm_then_searchable():
    faq_id = int(add_faq("怎么连数据库", "找 DBA 申请只读账号", "https://x/doc"))
    assert confirm_faq(faq_id) is True
    items = search_faq("数据库怎么连")
    assert items
    assert items[0]["question"] == "怎么连数据库"
    assert items[0]["source_url"] == "https://x/doc"


def test_confirm_missing_faq_returns_false():
    assert confirm_faq(999999) is False


def test_search_no_match_returns_empty():
    assert search_faq("火星基地在哪") == []
