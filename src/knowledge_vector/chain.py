"""RAG Chain - Retrieval Augmented Generation with MiniMax/LLM."""

import os
from typing import List, Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from .vectorstore import MilvusVectorStore
from .config import config


# Default system prompt for RAG (单轮)
DEFAULT_SYSTEM_PROMPT = """你是一个知识库助手。请根据以下参考信息回答用户的问题。
如果参考信息中没有相关内容，请如实告知，不要编造答案。

参考信息：
{context}
"""

# 多轮对话 system prompt
DEFAULT_HISTORY_SYSTEM_PROMPT = """你是一个知识库助手。请根据以下参考信息和对话历史回答用户的问题。
如果参考信息中没有相关内容，请如实告知，不要编造答案。
注意理解对话历史中的指代词（如"它"、"上面说的"等）。

对话历史：
{history}

参考信息：
{context}
"""


def create_rag_chain(
    collection_name: str = None,
    model_name: str = None,
    system_prompt: str = None,
    use_history: bool = True,
) -> "RAGChain":
    """Create a RAG chain.

    Args:
        collection_name: Milvus collection name.
        model_name: LLM model name (e.g., "MiniMax-M2.7").
        system_prompt: System prompt template.
        use_history: 是否使用多轮对话模式.

    Returns:
        RAGChain instance.
    """
    return RAGChain(
        collection_name=collection_name,
        model_name=model_name,
        system_prompt=system_prompt,
        use_history=use_history,
    )


class RAGChain:
    """RAG Chain for retrieval augmented generation."""

    def __init__(
        self,
        collection_name: str = None,
        model_name: str = None,
        system_prompt: str = None,
        use_history: bool = True,
    ):
        """Initialize RAG Chain.

        Args:
            collection_name: Milvus collection name.
            model_name: LLM model name.
            system_prompt: System prompt template with {context} placeholder.
            use_history: 是否使用多轮对话模式.
        """
        self.vectorstore = MilvusVectorStore(collection_name=collection_name)
        self.vectorstore.load()

        self.model_name = model_name or config.anthropic_model or "MiniMax-M2.7"
        self.use_history = use_history

        # 选择 prompt 模板
        if use_history and system_prompt is None:
            self.system_prompt = DEFAULT_HISTORY_SYSTEM_PROMPT
        else:
            self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

        # Initialize LLM
        self.llm = ChatAnthropic(model=self.model_name)

        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{question}"),
        ])

        # Create chain: prompt -> llm -> output
        self.chain = self.prompt | self.llm | StrOutputParser()

    def invoke(
        self,
        question: str,
        k: int = 4,
        filter: str = None,
        history: str = None,
    ) -> str:
        """Invoke the RAG chain to answer a question.

        Args:
            question: User question.
            k: Number of documents to retrieve.
            filter: Optional metadata filter.
            history: 对话历史字符串（用于多轮对话）.

        Returns:
            Generated answer as string.
        """
        # Retrieve relevant documents
        docs = self.vectorstore.search(question, k=k, filter=filter)

        # Build context from documents
        context = self._build_context(docs)

        # 构建 prompt 变量
        prompt_vars = {
            "context": context,
            "question": question,
        }

        # 如果启用历史模式，始终传递 history 变量（即使为空）
        if self.use_history:
            prompt_vars["history"] = history if history else ""

        # Generate answer
        answer = self.chain.invoke(prompt_vars)

        return answer

    def _build_context(self, docs: List[Document]) -> str:
        """Build context string from documents.

        Args:
            docs: List of retrieved documents.

        Returns:
            Context string.
        """
        context_parts = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "unknown")
            content = doc.page_content
            context_parts.append(f"[文档{i}] ({source})\n{content}")

        return "\n\n".join(context_parts)

    def retrieve(self, query: str, k: int = 4) -> List[Document]:
        """Retrieve documents without generating answer.

        Args:
            query: Search query.
            k: Number of documents.

        Returns:
            List of retrieved documents.
        """
        return self.vectorstore.search(query, k=k)
