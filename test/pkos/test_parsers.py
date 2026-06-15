import pytest
import tempfile
from pathlib import Path
from kgsrc.pkos.parsers import DocumentParser, TextParser, WebParser


def test_text_parser_plain_text():
    parser = TextParser()
    content = parser.parse_text("Hello world")
    assert content.raw_text == "Hello world"
    assert content.title is None


def test_text_parser_markdown_with_frontmatter():
    parser = TextParser()
    md = """---
title: "Test Doc"
---
# Hello
World content."""
    content = parser.parse_text(md)
    assert content.raw_text == "# Hello\nWorld content."
    assert content.title == "Test Doc"


def test_text_parser_markdown_without_frontmatter():
    parser = TextParser()
    md = "# Hello\nWorld content."
    content = parser.parse_text(md)
    assert content.raw_text == "# Hello\nWorld content."
    assert content.title == "Hello"


def test_web_parser_extracts_text():
    parser = WebParser()
    html = "<html><head><title>Page Title</title></head><body><p>Hello world</p></body></html>"
    content = parser.parse_html(html, source_url="https://example.com")
    assert "Hello world" in content.raw_text
    assert content.title == "Page Title"
    assert content.source_url == "https://example.com"


def test_web_parser_fallback():
    parser = WebParser()
    html = "<html><body><p>Hello</p></body></html>"
    content = parser.parse_html(html)
    assert "Hello" in content.raw_text


def test_parser_get_for_type():
    assert isinstance(DocumentParser.get_parser("text"), TextParser)
    assert isinstance(DocumentParser.get_parser("markdown"), TextParser)
    assert isinstance(DocumentParser.get_parser("web"), WebParser)
    assert DocumentParser.get_parser("unknown") is None
