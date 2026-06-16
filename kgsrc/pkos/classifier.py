"""LLM-based content classifier for PKOS.

Extracts title, summary, topic, identities, tags from raw text.
Supports dual LLM providers: primary (MiniMax via ChatAnthropic) and
secondary fallback (e.g. DeepSeek via ChatOpenAI) when rate-limited.
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from knowledge_vector.config import config


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
    """Classify content using LLM with automatic fallback.

    Primary LLM: MiniMax via ChatAnthropic (config.anthropic_*).
    Fallback LLM: Secondary provider via ChatOpenAI (config.llm_*).
    On rate-limit (429), automatically falls back to secondary.
    MiniMax config is preserved and retried on next invocation.
    """

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
        self._fallback_llm = None

    def _get_llm(self):
        """Get primary LLM (MiniMax via ChatAnthropic)."""
        if self._llm is None:
            self._llm = ChatAnthropic(model=self.model)
        return self._llm

    def _get_fallback_llm(self):
        """Get fallback LLM (e.g. DeepSeek via ChatOpenAI)."""
        if self._fallback_llm is None:
            from langchain_openai import ChatOpenAI
            self._fallback_llm = ChatOpenAI(
                model=config.llm_model or "deepseek-v4-flash",
                api_key=config.llm_api_key,
                base_url=config.llm_base_url,
            )
        return self._fallback_llm

    def _has_fallback(self) -> bool:
        """Check if a fallback LLM is configured."""
        return bool(config.llm_api_key and config.llm_base_url)

    def _invoke_llm(self, prompt: str):
        """Invoke primary LLM."""
        llm = self._get_llm()
        return llm.invoke([HumanMessage(content=prompt)])

    def _invoke_fallback_llm(self, prompt: str):
        """Invoke fallback LLM."""
        llm = self._get_fallback_llm()
        return llm.invoke([HumanMessage(content=prompt)])

    def _parse_response(self, response) -> ClassificationResult:
        """Parse LLM response into ClassificationResult."""
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
            summary=data.get("summary", ""),
            topic=data.get("topic", "未分类"),
            identities=data.get("identities", []),
            tags=data.get("tags", []),
        )

    def _is_rate_limit_error(self, e: Exception) -> bool:
        """Check if an exception is a rate-limit / quota error (429)."""
        msg = str(e).lower()
        return "429" in msg or "rate_limit" in msg or "用量上限" in msg

    def classify_content(self, text: str, source_type: str = "text") -> ClassificationResult:
        """Classify raw text content.

        Tries primary LLM (MiniMax) first. On rate-limit, falls back
        to secondary LLM if configured. If both fail, uses fallback defaults.
        """
        max_chars = 8000
        truncated = text[:max_chars] if len(text) > max_chars else text
        prompt = self.CLASSIFY_PROMPT.format(text=truncated)

        # Try primary LLM
        try:
            response = self._invoke_llm(prompt)
            return self._parse_response(response)
        except Exception as e:
            if self._is_rate_limit_error(e) and self._has_fallback():
                print(f"[LLMClassifier] Primary rate-limited, falling back to {config.llm_model}")
            else:
                print(f"[LLMClassifier] Primary LLM failed: {e}, using fallback")
                return self._fallback_result(text)
            # Try fallback LLM
        try:
            response = self._invoke_fallback_llm(prompt)
            return self._parse_response(response)
        except Exception as e:
            print(f"[LLMClassifier] Fallback LLM also failed: {e}, using fallback")

        return self._fallback_result(text)

    def _fallback_result(self, text: str) -> ClassificationResult:
        """Generate a basic result without LLM."""
        lines = text.strip().split("\n")
        title = lines[0][:30] if lines else "未命名文档"
        title = title.lstrip("# ").strip()[:30]
        return ClassificationResult(
            title=title,
            summary=text[:100],
            topic="未分类",
        )
