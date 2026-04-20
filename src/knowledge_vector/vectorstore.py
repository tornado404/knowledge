"""Milvus vector store implementation with MilvusClient."""

from typing import List, Optional, Any
from pathlib import Path
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from pymilvus import MilvusClient

from .config import config

# Default model for Chinese text embedding
DEFAULT_EMBED_MODEL = "BAAI/bge-small-zh-v1.5"


def get_embeddings(
    model: str = None,
) -> HuggingFaceEmbeddings:
    """Get local embeddings instance using HuggingFace.

    Args:
        model: Model name for embeddings.

    Returns:
        HuggingFaceEmbeddings instance.
    """
    return HuggingFaceEmbeddings(
        model_name=model or DEFAULT_EMBED_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


class MilvusVectorStore:
    """Milvus vector store wrapper using MilvusClient."""

    def __init__(
        self,
        collection_name: str = None,
        embeddings: Any = None,
        connection_args: dict = None,
    ):
        """Initialize Milvus vector store.

        Args:
            collection_name: Name of the Milvus collection.
            embeddings: Embeddings instance.
            connection_args: Connection parameters for Milvus.
        """
        self.collection_name = collection_name or config.milvus_collection
        self.embeddings = embeddings or get_embeddings()

        # Connection args for Milvus (Docker or remote)
        self.connection_args = connection_args or {
            "uri": f"http://{config.milvus_host}:{config.milvus_port}",
        }

        self._client: Optional[MilvusClient] = None

    def _get_client(self) -> MilvusClient:
        """Get or create MilvusClient."""
        if self._client is None:
            self._client = MilvusClient(**self.connection_args)
        return self._client

    def create_from_documents(
        self,
        documents: List[Document],
        drop_old: bool = False,
    ) -> "MilvusVectorStore":
        """Create vector store from documents.

        Args:
            documents: List of LangChain Document objects.
            drop_old: Whether to drop existing collection.

        Returns:
            self for chaining.
        """
        client = self._get_client()

        # Drop existing collection if requested
        if drop_old and self.collection_name in client.list_collections():
            client.drop_collection(self.collection_name)

        # Prepare data first to get vector dimension
        texts = [doc.page_content for doc in documents]
        sources = [doc.metadata.get("source", "") for doc in documents]

        # Generate a sample embedding to determine dimension
        sample_vector = self.embeddings.embed_query(texts[0] if texts else "test")
        dimension = len(sample_vector)

        # Create collection if not exists
        if self.collection_name not in client.list_collections():
            client.create_collection(
                collection_name=self.collection_name,
                dimension=dimension,
                primary_field_name="pk",
                vector_field_name="vector",
                metric_type="IP",
                auto_id=True,
            )

        # Generate all embeddings
        vectors = self.embeddings.embed_documents(texts)

        # Insert data - match schema: text, source, vector
        data = [
            {"text": text, "source": source, "vector": vector}
            for text, source, vector in zip(texts, sources, vectors)
        ]

        client.insert(collection_name=self.collection_name, data=data)

        # Note: Index will be created automatically or on first search
        # For manual index creation, use:
        # index_params = client.prepare_index_params(...)
        # client.create_index(collection_name=self.collection_name, index_params=index_params)

        return self

    def load(self) -> "MilvusVectorStore":
        """Load existing vector store.

        Returns:
            self for chaining.
        """
        self._get_client()
        return self

    def search(
        self,
        query: str,
        k: int = 4,
        filter: str = None,
    ) -> List[Document]:
        """Search for similar documents.

        Args:
            query: Search query text.
            k: Number of results to return.
            filter: Optional metadata filter expression.

        Returns:
            List of matching Documents.
        """
        client = self._get_client()

        query_vector = self.embeddings.embed_query(query)

        results = client.search(
            collection_name=self.collection_name,
            data=[query_vector],
            limit=k,
            filter=filter,
            output_fields=["text", "source"],
        )

        documents = []
        for result in results[0]:
            text = result["entity"]["text"]
            metadata = {"source": result["entity"].get("source", "")}
            doc = Document(page_content=text, metadata=metadata)
            documents.append(doc)

        return documents

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
    ) -> List[tuple[Document, float]]:
        """Search with relevance scores.

        Args:
            query: Search query text.
            k: Number of results to return.

        Returns:
            List of (Document, score) tuples.
        """
        client = self._get_client()

        query_vector = self.embeddings.embed_query(query)

        results = client.search(
            collection_name=self.collection_name,
            data=[query_vector],
            limit=k,
            output_fields=["text", "source"],
        )

        documents_with_scores = []
        for result in results[0]:
            text = result["entity"]["text"]
            metadata = {"source": result["entity"].get("source", "")}
            doc = Document(page_content=text, metadata=metadata)
            # distance is the negative of IP score for normalized vectors
            score = result["distance"]
            documents_with_scores.append((doc, score))

        return documents_with_scores

    @property
    def client(self) -> MilvusClient:
        """Get the underlying MilvusClient."""
        return self._get_client()
