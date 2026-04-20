"""Chat API - FastAPI server for RAG chatbot with multi-turn conversation."""

import os
import sys
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from knowledge_vector.chain import create_rag_chain
from knowledge_vector.memory import ConversationMemory


# Pydantic models
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


# In-memory session store with ConversationMemory
class SessionStore:
    """In-memory session store with ConversationMemory."""

    def __init__(self):
        self.sessions: Dict[str, ConversationMemory] = {}

    def get_memory(self, session_id: str) -> ConversationMemory:
        """Get or create a ConversationMemory for a session."""
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationMemory(max_turns=10)
        return self.sessions[session_id]

    def get_messages(self, session_id: str) -> List[ChatMessage]:
        """Get all messages for a session."""
        memory = self.get_memory(session_id)
        return memory.get_messages()

    def add_message(self, session_id: str, role: str, content: str):
        """Add a message to the session history."""
        memory = self.get_memory(session_id)
        memory.add_message(role=role, content=content)

    def clear_session(self, session_id: str):
        """Clear session history."""
        if session_id in self.sessions:
            del self.sessions[session_id]

    def has_session(self, session_id: str) -> bool:
        """Check if session exists."""
        return session_id in self.sessions


# Global instance
session_store = SessionStore()

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
    """Chat endpoint - ask a question and get RAG-powered answer with history."""
    try:
        # Get or create session
        session_id = request.session_id or f"session_{datetime.now().timestamp()}"

        # Get conversation memory
        memory = session_store.get_memory(session_id)

        # Add user message to history
        memory.add_user(request.message)

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

        # Add assistant message to history
        memory.add_assistant(answer)

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


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the FastAPI server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
