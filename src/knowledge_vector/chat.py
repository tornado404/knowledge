"""Chat API - FastAPI server for RAG chatbot."""

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


class ChatResponse(BaseModel):
    """Chat response model."""
    answer: str = Field(..., description="Generated answer")
    sources: List[dict] = Field(default_factory=list, description="Retrieved document sources")
    session_id: str = Field(..., description="Session ID")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model: str
    collection: str


# In-memory session store (use Redis/DB for production)
class SessionStore:
    """Simple in-memory session store."""

    def __init__(self):
        self.sessions: Dict[str, List[ChatMessage]] = {}

    def get_messages(self, session_id: str) -> List[ChatMessage]:
        return self.sessions.get(session_id, [])

    def add_message(self, session_id: str, role: str, content: str):
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].append(ChatMessage(role=role, content=content))

    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]


# Global instances
session_store = SessionStore()
app = FastAPI(
    title="Knowledge RAG Chat API",
    description="RAG chatbot API using Milvus vector store and MiniMax LLM",
    version="0.1.0",
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
    """Chat endpoint - ask a question and get RAG-powered answer."""
    try:
        # Get or create session
        session_id = request.session_id or f"session_{datetime.now().timestamp()}"

        # Add user message to history
        session_store.add_message(session_id, "user", request.message)

        # Create RAG chain
        rag_chain = create_rag_chain()

        # Get answer
        answer = rag_chain.invoke(request.message, k=request.k)

        # Retrieve sources
        docs = rag_chain.retrieve(request.message, k=request.k)
        sources = [
            {"source": doc.metadata.get("source", "unknown"), "content": doc.page_content[:200]}
            for doc in docs
        ]

        # Add assistant message to history
        session_store.add_message(session_id, "assistant", answer)

        return ChatResponse(
            answer=answer,
            sources=sources,
            session_id=session_id,
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


@app.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    """Get conversation history for a session."""
    messages = session_store.get_messages(session_id)
    return {"session_id": session_id, "messages": messages}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a conversation session."""
    session_store.clear_session(session_id)
    return {"status": "deleted", "session_id": session_id}


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the FastAPI server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
