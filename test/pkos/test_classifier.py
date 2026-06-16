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


def test_classifier_rate_limit_triggers_secondary():
    """Rate-limit (429) should trigger secondary LLM when configured."""
    classifier = LLMClassifier()
    mock_response = MagicMock()
    mock_response.content = '{"title": "Fallback", "summary": "ok", "topic": "AI", "identities": [], "tags": []}'

    with (
        patch.object(classifier, "_invoke_llm", side_effect=Exception("Error code: 429 - rate_limit_error")),
        patch.object(classifier, "_has_fallback", return_value=True),
        patch.object(classifier, "_invoke_fallback_llm", return_value=mock_response),
    ):
        result = classifier.classify_content("Hello world")
        assert result.title == "Fallback"
        assert result.topic == "AI"


def test_classifier_rate_limit_without_secondary_falls_through():
    """Without secondary configured, rate-limit falls through to default fallback."""
    classifier = LLMClassifier()
    with (
        patch.object(classifier, "_invoke_llm", side_effect=Exception("Error code: 429 - rate_limit_error")),
        patch.object(classifier, "_has_fallback", return_value=False),
    ):
        result = classifier.classify_content("Hello world")
        assert result.title == "Hello world"
        assert result.topic == "未分类"


def test_classifier_secondary_also_fails():
    """When both primary and secondary fail, use fallback defaults."""
    classifier = LLMClassifier()
    with (
        patch.object(classifier, "_invoke_llm", side_effect=Exception("Error code: 429 - rate_limit_error")),
        patch.object(classifier, "_has_fallback", return_value=True),
        patch.object(classifier, "_invoke_fallback_llm", side_effect=Exception("Secondary error")),
    ):
        result = classifier.classify_content("Hello world")
        assert result.title == "Hello world"
        assert result.topic == "未分类"


def test_classifier_is_rate_limit_error():
    classifier = LLMClassifier()
    assert classifier._is_rate_limit_error(Exception("Error code: 429"))
    assert classifier._is_rate_limit_error(Exception("rate_limit_error"))
    assert classifier._is_rate_limit_error(Exception("已达到 Token Plan 用量上限"))
    assert not classifier._is_rate_limit_error(Exception("Some other error"))
