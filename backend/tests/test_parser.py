"""模型输出解析器单元测试（纯函数单测重点）。"""
import pytest

from app.services.parser import ParseError, parse_json


def test_parse_plain_json():
    r = parse_json('{"answer": "答案", "sources": [{"title": "t", "section": "s"}], "confidence": "high"}')
    assert r.answer == "答案"
    assert [source.model_dump(exclude_none=True) for source in r.sources] == [
        {"title": "t", "section": "s"}
    ]
    assert r.confidence == "high"


def test_parse_json_with_markdown_fence():
    r = parse_json('```json\n{"answer": "x", "confidence": "low"}\n```')
    assert r.answer == "x"
    assert r.confidence == "low"


def test_parse_json_with_noise_around():
    r = parse_json('好的，答案如下：\n{"answer": "y", "confidence": "none"}')
    assert r.answer == "y"


def test_parse_missing_optional_fields_defaults():
    r = parse_json('{"answer": "z"}')
    assert r.sources == []
    assert r.confidence == "none"


def test_parse_invalid_raises():
    with pytest.raises(ParseError):
        parse_json("这不是 JSON")
