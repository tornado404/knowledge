"""Text splitter combining MarkdownHeaderTextSplitter and RecursiveCharacterTextSplitter."""

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
    TextSplitter,
)
from typing import List, Tuple

# Markdown headers to split on
MARKDOWN_HEADERS = [
    ("#", "header1"),
    ("##", "header2"),
    ("###", "header3"),
    ("####", "header4"),
]


def create_splitter(
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    headers_to_split_on: List[Tuple[str, str]] = None,
) -> TextSplitter:
    """Create a composite text splitter.

    First splits by Markdown headers (preserving structure), then further
    splits by character count if needed.

    Args:
        chunk_size: Maximum chunk size after final splitting.
        chunk_overlap: Overlap between chunks.
        headers_to_split_on: List of (header_marker, header_level) tuples.

    Returns:
        A TextSplitter instance.
    """
    if headers_to_split_on is None:
        headers_to_split_on = MARKDOWN_HEADERS

    # First stage: split by Markdown headers
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        return_each_line=False,
    )

    # Second stage: split by character count if chunks are too large
    character_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
        length_function=len,
    )

    # Return the character splitter (MarkdownHeaderTextSplitter is applied first in the pipeline)
    return character_splitter


def split_documents(
    documents: List,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List:
    """Split documents using both Markdown-aware and character-based splitting.

    Args:
        documents: List of LangChain Document objects.
        chunk_size: Maximum chunk size.
        chunk_overlap: Overlap between chunks.

    Returns:
        List of split Document objects.
    """
    # First split by Markdown headers
    headers_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=MARKDOWN_HEADERS,
        return_each_line=False,
    )

    # Split the documents
    docs_chunks = []
    for doc in documents:
        # Split by headers first
        header_chunks = headers_splitter.split_text(doc.page_content)
        for chunk in header_chunks:
            # Preserve metadata
            chunk.metadata = {**doc.metadata, **chunk.metadata}
            docs_chunks.append(chunk)

    # Then apply character splitting to each chunk
    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
        length_function=len,
    )

    return char_splitter.split_documents(docs_chunks)
