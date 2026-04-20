"""Markdown document loader using UnstructuredMarkdownLoader."""

from pathlib import Path
from typing import List
from langchain_core.documents import Document
from langchain_community.document_loaders import UnstructuredMarkdownLoader


class MarkdownLoader:
    """Load Markdown files from a directory."""

    def __init__(self, directory: str | Path = "docs"):
        """Initialize loader with directory path.

        Args:
            directory: Path to directory containing .md files.
        """
        self.directory = Path(directory)
        if not self.directory.exists():
            self.directory.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[Document]:
        """Load all Markdown files from the directory.

        Returns:
            List of LangChain Document objects.
        """
        md_files = list(self.directory.glob("**/*.md"))
        if not md_files:
            raise FileNotFoundError(f"No .md files found in {self.directory}")

        documents = []
        for md_file in md_files:
            loader = UnstructuredMarkdownLoader(str(md_file))
            docs = loader.load()
            for doc in docs:
                doc.metadata["source"] = str(md_file.relative_to(self.directory))
            documents.extend(docs)

        return documents

    def load_single(self, file_path: str | Path) -> List[Document]:
        """Load a single Markdown file.

        Args:
            file_path: Path to the Markdown file.

        Returns:
            List containing one Document object.
        """
        loader = UnstructuredMarkdownLoader(str(file_path))
        docs = loader.load()
        for doc in docs:
            doc.metadata["source"] = str(Path(file_path).relative_to(self.directory))
        return docs
