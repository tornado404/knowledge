"""LLM-based content classifier for PKOS.

Extracts title, summary, topic, identities, tags from raw text.
Reuses ChatAnthropic pattern from chain.py.
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from ..knowledge_vector.config import config


def extract_json_block(text: str) -> dict:
    """Extract JSON from markdown code block or raw string."""
    pattern = r"```json\s*\n(.*?)\n```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        text = match.group(1)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}


@dataclass
class ClassificationResult:
    """Result of LLM classification."""

    title: str = "未命名文档"
    summary: str = ""
    topic: str = "未分类"
    identities: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


class LLMClassifier:
    """Classify content using LLM."""

    CLASSIFY_PROMPT = """你是一个个人知识管理助手。请分析以下文本内容，提取关键信息。

要求：
1. title: 为内容起一个简洁的标题（不超过30字）
2. summary: 生成100字以内的内容摘要
3. topic: 推断一个主题分类（如"人工智能","编程","生活","未分类"等）
4. identities: 推断可能相关的身份标签（如["程序员","父亲","骑行爱好者"]）
5. tags: 提取3-5个关键词标签

请严格按以下JSON格式输出（不要输出其他内容）：
```json
{{
  "title": "...",
  "summary": "...",
  "topic": "...",
  "identities": ["..."],
  "tags": ["..."]
}}
```

文本内容：
{text}
"""

    def __init__(self, model: str = None):
        self.model = model or config.anthropic_model or "MiniMax-M2.7"
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            self._llm = ChatAnthropic(model=self.model)
        return self._llm

    def _invoke_llm(self, prompt: str):
        """Invoke LLM with a prompt. Extracted for testability."""
        llm = self._get_llm()
        return llm.invoke([HumanMessage(content=prompt)])

    def classify_content(self, text: str, source_type: str = "text") -> ClassificationResult:
        """Classify raw text content.

        Args:
            text: Raw text content.
            source_type: Source type hint.

        Returns:
            ClassificationResult with fallback defaults on failure.
        """
        # Truncate if too long
        max_chars = 8000
        truncated = text[:max_chars] if len(text) > max_chars else text

        prompt = self.CLASSIFY_PROMPT.format(text=truncated)

        try:
            response = self._invoke_llm(prompt)
            raw = response.content
            if isinstance(raw, list):
                raw = raw[0] if raw else ""
                if isinstance(raw, dict):
                    raw = raw.get("text", "")
            if isinstance(raw, dict):
                raw = raw.get("text", "")
            raw = str(raw).strip()

            data = extract_json_block(raw)

            return ClassificationResult(
                title=data.get("title", "未命名文档"),
                summary=data.get("summary", text[:100]),
                topic=data.get("topic", "未分类"),
                identities=data.get("identities", []),
                tags=data.get("tags", []),
            )
        except Exception as e:
            print(f"[LLMClassifier] classify failed: {e}, using fallback")
            # Fallback: use first line as title, first 100 chars as summary
            lines = text.strip().split("\n")
            title = lines[0][:30] if lines else "未命名文档"
            return ClassificationResult(
                title=title,
                summary=text[:100],
                topic="未分类",
            )
