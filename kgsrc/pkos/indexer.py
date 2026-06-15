"""Vault indexer — incremental Milvus indexing from Vault Markdown files."""

import json
from pathlib import Path
from typing import List

from langchain_core.documents import Document

from ..knowledge_vector.vectorstore import MilvusVectorStore
from ..knowledge_vector.loader import MarkdownLoader
from ..knowledge_vector.splitter import split_documents


class VaultIndexer:
    """Index Vault Markdown documents into Milvus incrementally."""

    def __init__(
        self,
        vault_dir: str = "./kgsrc/pkos/vault",
        indexed_file: str = "./pkos_indexed.json",
    ):
        self.vault_dir = Path(vault_dir)
        self.indexed_file = Path(indexed_file)
        self._indexed: set = set()
        self._load_indexed()

    def _load_indexed(self):
        if self.indexed_file.exists():
            try:
                with open(self.indexed_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._indexed = set(data.get("indexed", []))
            except Exception:
                self._indexed = set()

    def _save_indexed(self):
        try:
            self.indexed_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.indexed_file, "w", encoding="utf-8") as f:
                json.dump({"indexed": sorted(self._indexed)}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[VaultIndexer] save indexed failed: {e}")

    def _get_vectorstore(self) -> MilvusVectorStore:
        return MilvusVectorStore()

    def index_document(self, file_path: str) -> bool:
        """Index a single Vault document into Milvus.

        Args:
            file_path: Path to the Markdown file.

        Returns:
            True if indexed (or already indexed).
        """
        abs_path = str(Path(file_path).resolve())
        if abs_path in self._indexed:
            return True

        try:
            path = Path(file_path)
            if not path.exists():
                print(f"[VaultIndexer] file not found: {file_path}")
                return False

            # Load document
            loader = MarkdownLoader(directory=str(path.parent))
            docs = loader.load_single(str(path))
            if not docs:
                return False

            # Split documents
            chunks = split_documents(docs, chunk_size=1000, chunk_overlap=200)
            if not chunks:
                return False

            # Index into Milvus
            vectorstore = self._get_vectorstore()
            vectorstore.load()
            vectorstore.create_from_documents(chunks, drop_old=False)

            self._indexed.add(abs_path)
            self._save_indexed()
            return True
        except Exception as e:
            print(f"[VaultIndexer] index failed: {e}")
            return False

    def index_all_unindexed(self) -> int:
        """Index all unindexed Vault documents.

        Returns:
            Number of newly indexed documents.
        """
        count = 0
        for md_file in self.vault_dir.rglob("*.md"):
            abs_path = str(md_file.resolve())
            if abs_path not in self._indexed:
                if self.index_document(abs_path):
                    count += 1
        return count

    def get_indexed_documents(self) -> List[str]:
        """List all indexed document paths."""
        return sorted(self._indexed)

    def mark_indexed(self, file_path: str):
        """Manually mark a document as indexed."""
        self._indexed.add(str(Path(file_path).resolve()))
        self._save_indexed()
