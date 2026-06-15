import pytest
from unittest.mock import patch, MagicMock
from kgsrc.pkos.classifier import LLMClassifier, extract_json_block


def test_extract_json_block():
    text = 'Some text\n```json\n{"title": "Hello"}\n```\nmore text'
    result = extract_json_block(text)
    assert result == {"title": "Hello"}


def test_extract_json_block_no_block():
    text = '{"title": "Hello"}'
    result = extract_json_block(text)
    assert result == {"title": "Hello"}


def test_extract_json_block_invalid():
    text = "not json"
    result = extract_json_block(text)
    assert result == {}


def test_classifier_classify_content_mock():
    classifier = LLMClassifier()
    mock_response = MagicMock()
    mock_response.content = '{"title": "Test", "summary": "Summary", "topic": "AI", "identities": ["程序员"], "tags": ["python"]}'

    with patch.object(classifier, "_invoke_llm", return_value=mock_response):
        result = classifier.classify_content("Hello world", source_type="text")
        assert result.title == "Test"
        assert result.summary == "Summary"
        assert result.topic == "AI"
        assert result.identities == ["程序员"]
        assert result.tags == ["python"]


def test_classifier_classify_content_fallback():
    classifier = LLMClassifier()
    with patch.object(classifier, "_invoke_llm", side_effect=Exception("LLM error")):
        result = classifier.classify_content("Hello world", source_type="text")
        assert result.title == "Hello world"
        assert result.topic == "未分类"
        assert result.summary == "Hello world"[:100]
