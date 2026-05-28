"""Chat API - FastAPI server for RAG chatbot with multi-turn conversation."""

import os
import sys
import uuid
import json
from pathlib import Path
from typing import List, Optional, Dict, Any, AsyncGenerator, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Add kgsrc to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal

from knowledge_vector.chain import create_rag_chain
from knowledge_vector.memory import ConversationMemory
from knowledge_vector.agent import invoke_agent, stream_invoke_agent


# ==================== 现有模型 ====================

class ChatMessage(BaseModel):
    """Chat message model."""
    role: str = Field(default="user", description="Message role: user or assistant")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str = Field(..., description="User message")
    k: int = Field(default=4, description="Number of documents to retrieve")
    session_id: Optional[str] = Field(default=None, description="Session ID for conversation history")
    include_history: bool = Field(default=True, description="Whether to include conversation history")


class ChatResponse(BaseModel):
    """Chat response model."""
    answer: str = Field(..., description="Generated answer")
    sources: List[dict] = Field(default_factory=list, description="Retrieved document sources")
    session_id: str = Field(..., description="Session ID")
    turn_count: int = Field(default=0, description="Number of conversation turns")


class HistoryResponse(BaseModel):
    """Conversation history response."""
    session_id: str
    turn_count: int
    messages: List[ChatMessage]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model: str
    collection: str


# ==================== OpenAI Chat-Compatible 模型 ====================

class Message(BaseModel):
    """OpenAI 格式的单条消息"""
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI Chat Completions 兼容请求"""
    model: str = "MiniMax-M2.7"
    messages: List[Message]
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2000, ge=1)
    stream: bool = False
    session_id: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    """OpenAI Chat Completions 兼容响应（非流式）"""
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:8]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    model: str
    choices: List[dict]
    usage: dict = Field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})


# In-memory session store with ConversationMemory
class SessionStore:
    """Session store with ConversationMemory and optional persistence.

    支持上下文压缩:
    - max_turns: 最大保存的对话轮数（默认10）
    - compression_threshold: 开始压缩的阈值（默认5）
    - use_summarization: 是否使用摘要压缩（默认True）
    - max_summary_history: 最大摘要历史条数（默认10）
    - auto_compress_policy: 自动压缩策略（默认 ON_EVERY_ADD）
    - persistence: 持久化管理器（可选）
    """

    def __init__(
        self,
        max_turns: int = 10,
        compression_threshold: int = 5,
        use_summarization: bool = True,
        token_budget: int = 3000,
        max_summary_history: int = 10,
        auto_compress_policy: str = "on_every_add",
        use_llm_summarizer: bool = False,
        persistence=None,
    ):
        from .memory import AutoCompressPolicy

        self.sessions: Dict[str, ConversationMemory] = {}
        self.max_turns = max_turns
        self.compression_threshold = compression_threshold
        self.use_summarization = use_summarization
        self.token_budget = token_budget
        self.max_summary_history = max_summary_history
        self.auto_compress_policy = AutoCompressPolicy.from_string(auto_compress_policy)
        self.use_llm_summarizer = use_llm_summarizer
        self.persistence = persistence

    def get_memory(self, session_id: str) -> ConversationMemory:
        """Get or create a ConversationMemory for a session."""
        if session_id not in self.sessions:
            # 尝试从持久化存储加载
            if self.persistence:
                memory = self.persistence.load_session(session_id)
                if memory:
                    self.sessions[session_id] = memory
                    return memory

            # 创建新的 memory
            self.sessions[session_id] = ConversationMemory(
                max_turns=self.max_turns,
                compression_threshold=self.compression_threshold,
                use_summarization=self.use_summarization,
                token_budget=self.token_budget,
                max_summary_history=self.max_summary_history,
                use_llm_summarizer=self.use_llm_summarizer,
            )
        return self.sessions[session_id]

    def get_messages(self, session_id: str) -> List[ChatMessage]:
        """Get all messages for a session."""
        memory = self.get_memory(session_id)
        return memory.get_messages()

    def get_history(self, session_id: str) -> List[dict]:
        """Get conversation history as list of dicts."""
        memory = self.get_memory(session_id)
        return memory.get_history()

    def get_summary_context(self, session_id: str) -> str:
        """Get summary context for agent system prompt."""
        memory = self.get_memory(session_id)
        return memory.get_summary_context()

    def get_history_with_summary(self, session_id: str) -> Tuple[List[dict], str]:
        """Get history and summary separately."""
        memory = self.get_memory(session_id)
        return memory.get_history_with_summary()

    def add_message(self, session_id: str, role: str, content: str):
        """Add a message to the session history and auto-compress if needed."""
        memory = self.get_memory(session_id)
        memory.add_message(role=role, content=content)

        # 自动压缩检查（使用策略）
        if self.use_summarization and self.auto_compress_policy.should_compress(memory.turn_count):
            if memory._should_compress():
                memory.compress()

        # 自动保存（如果启用持久化）
        if self.persistence and self.persistence.auto_save:
            self.persistence.save_session(session_id, memory)

    def compress_session(self, session_id: str) -> bool:
        """手动触发会话压缩

        Returns:
            是否实际执行了压缩
        """
        memory = self.get_memory(session_id)
        result = memory.compress()

        # 压缩后保存
        if result and self.persistence:
            self.persistence.save_session(session_id, memory)

        return result

    def clear_session(self, session_id: str):
        """Clear session history."""
        if session_id in self.sessions:
            del self.sessions[session_id]

        # 同时删除持久化文件
        if self.persistence:
            self.persistence.delete_session(session_id)

    def has_session(self, session_id: str) -> bool:
        """Check if session exists."""
        if session_id in self.sessions:
            return True
        # 检查持久化存储
        if self.persistence:
            return self.persistence._get_session_path(session_id).exists()
        return False

    def list_sessions(self) -> List[str]:
        """List all session IDs."""
        session_ids = set(self.sessions.keys())
        # 合并持久化存储中的 session
        if self.persistence:
            session_ids.update(self.persistence.list_sessions())
        return list(session_ids)

    def get_compression_stats(self, session_id: str) -> dict:
        """Get compression stats for a session."""
        memory = self.get_memory(session_id)
        return memory.get_compression_stats()


# Global instance - use config to determine LLM summarizer and persistence
from knowledge_vector.config import config as _config

# 初始化持久化管理器（默认启用，存储到 ./sessions 目录）
_persistence = None
if _config.session_persistence:
    from .session_persistence import SessionPersistence
    _persistence = SessionPersistence(
        storage_dir=_config.session_storage_dir,
        auto_save=True,
        max_age_days=_config.session_max_age_days,
    )
    # 启动时清理过期 session
    _persistence.cleanup_expired()

session_store = SessionStore(
    use_llm_summarizer=_config.use_llm_summarizer,
    persistence=_persistence,
)

app = FastAPI(
    title="Knowledge RAG Chat API",
    description="RAG chatbot API with multi-turn conversation support",
    version="0.2.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat endpoint - ask a question and get RAG-powered answer with history.

    支持自动上下文压缩，当对话轮数达到阈值时自动压缩旧对话。
    """
    try:
        # Get or create session
        session_id = request.session_id or f"session_{datetime.now().timestamp()}"

        # Add user message to history (auto-compress if threshold reached)
        session_store.add_message(session_id, "user", request.message)

        # Get conversation memory
        memory = session_store.get_memory(session_id)

        # Get conversation history for RAG
        history_text = memory.get_history_for_rag() if request.include_history else ""

        # Create RAG chain
        rag_chain = create_rag_chain(use_history=request.include_history)

        # Get answer (with or without history)
        if request.include_history and history_text:
            answer = rag_chain.invoke(
                request.message,
                k=request.k,
                history=history_text
            )
        else:
            answer = rag_chain.invoke(
                request.message,
                k=request.k,
            )

        # Retrieve sources
        docs = rag_chain.retrieve(request.message, k=request.k)
        sources = [
            {"source": doc.metadata.get("source", "unknown"), "content": doc.page_content[:200]}
            for doc in docs
        ]

        # Add assistant message to history (auto-compress if threshold reached)
        session_store.add_message(session_id, "assistant", answer)

        # Get updated turn count (after compression)
        memory = session_store.get_memory(session_id)

        return ChatResponse(
            answer=answer,
            sources=sources,
            session_id=session_id,
            turn_count=memory.turn_count,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    from knowledge_vector.config import config

    return HealthResponse(
        status="healthy",
        model=config.anthropic_model or "MiniMax-M2.7",
        collection=config.milvus_collection,
    )


@app.get("/sessions/{session_id}/history", response_model=HistoryResponse)
async def get_history(session_id: str):
    """Get conversation history for a session."""
    if not session_store.has_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    memory = session_store.get_memory(session_id)
    messages = memory.get_messages()

    return HistoryResponse(
        session_id=session_id,
        turn_count=memory.turn_count,
        messages=[ChatMessage(role=m.role, content=m.content) for m in messages],
    )


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a conversation session."""
    session_store.clear_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@app.get("/sessions")
async def list_sessions():
    """List all active session IDs."""
    return {
        "sessions": list(session_store.sessions.keys()),
        "count": len(session_store.sessions),
    }


@app.get("/sessions/{session_id}/stats")
async def get_session_stats(session_id: str):
    """Get compression stats for a session."""
    if not session_store.has_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    return session_store.get_compression_stats(session_id)


@app.post("/sessions/{session_id}/compress")
async def compress_session(session_id: str):
    """Manually trigger compression for a session."""
    if not session_store.has_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    compressed = session_store.compress_session(session_id)
    return {
        "session_id": session_id,
        "compressed": compressed,
        "stats": session_store.get_compression_stats(session_id),
    }


# ==================== OpenAI Chat-Compatible 端点 ====================

def extract_history_from_messages(messages: List[Message]) -> tuple[str, List[dict]]:
    """从 OpenAI messages 格式提取最新用户问题和历史

    Returns:
        (user_question, history_list)
    """
    history = []
    user_question = ""

    for msg in messages:
        if msg.role == "system":
            continue  # system prompt 在 generate_node 内部处理
        elif msg.role == "user":
            if not user_question:
                user_question = msg.content
            else:
                # 之前的用户消息作为历史
                history.append({"role": "user", "content": msg.content})
        elif msg.role == "assistant":
            history.append({"role": "assistant", "content": msg.content})

    return user_question, history


async def stream_answer(question: str, history: List[dict], model: str, summary_context: str = "") -> AsyncGenerator[str, None]:
    """SSE 流式生成回答"""
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    created = int(datetime.now().timestamp())

    async for answer_chunk in stream_invoke_agent(question, history, summary_context=summary_context):
        chunk = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"content": answer_chunk},
                "finish_reason": None
            }]
        }
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    # 发送 [DONE]
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI Chat-Compatible 端点

    支持:
    - 非流式响应 (stream: false)
    - 流式 SSE 响应 (stream: true)
    - 多轮对话历史传递
    - 自动压缩上下文注入
    - 自动 session 压缩（当提供 session_id 时）
    """
    try:
        # 提取历史和最新用户问题
        user_question, history = extract_history_from_messages(request.messages)

        if not user_question:
            raise HTTPException(status_code=400, detail="No user message found")

        # 从 session 获取压缩后的历史摘要，并记录用户消息
        summary_context = ""
        sid = request.session_id
        if sid:
            session_store.add_message(sid, "user", user_question)
            memory = session_store.get_memory(sid)
            summary_context = memory.get_summary_context()

        if request.stream:
            # 流式响应 - 需要收集完整回答以记录到 session
            async def stream_and_record():
                full_answer = ""
                async for chunk in stream_answer(user_question, history, request.model, summary_context=summary_context):
                    # 解析 chunk 获取内容
                    if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
                        try:
                            data = json.loads(chunk[6:].strip())
                            if "choices" in data and data["choices"]:
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                full_answer += content
                        except:
                            pass
                    yield chunk

                # 记录完整回答到 session
                if sid and full_answer:
                    session_store.add_message(sid, "assistant", full_answer)

            return StreamingResponse(
                stream_and_record(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
            )
        else:
            # 非流式响应
            answer = invoke_agent(user_question, history, summary_context=summary_context)

            # 记录回答到 session
            if sid:
                session_store.add_message(sid, "assistant", answer)

            return ChatCompletionResponse(
                id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
                object="chat.completion",
                created=int(datetime.now().timestamp()),
                model=request.model,
                choices=[{
                    "index": 0,
                    "message": {"role": "assistant", "content": answer},
                    "finish_reason": "stop"
                }],
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the FastAPI server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


# ==================== Multi-Agent 端点 ====================

def _register_multi_agent_routes():
    """注册 Multi-Agent 路由"""
    from knowledge_vector.multi_agent.api_endpoints import router as multi_agent_router
    app.include_router(multi_agent_router)


# 注册 multi-agent 路由
_register_multi_agent_routes()


if __name__ == "__main__":
    run_server()
