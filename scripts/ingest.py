#!/usr/bin/env python3
"""Ingest Markdown documents into Milvus vector store."""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_vector import MarkdownLoader, split_documents, MilvusVectorStore
from knowledge_vector.config import config


def main():
    parser = argparse.ArgumentParser(description="Ingest Markdown documents into Milvus")
    parser.add_argument(
        "--docs-dir",
        type=str,
        default="docs",
        help="Directory containing Markdown files (default: docs)",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=None,
        help="Milvus collection name (default: from config)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Maximum chunk size (default: 1000)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Chunk overlap (default: 200)",
    )
    parser.add_argument(
        "--drop-old",
        action="store_true",
        help="Drop existing collection before ingesting",
    )
    args = parser.parse_args()

    print(f"Loading Markdown files from: {args.docs_dir}")
    print(f"Collection: {args.collection or config.milvus_collection}")
    print(f"Chunk size: {args.chunk_size}, Overlap: {args.chunk_overlap}")

    # Step 1: Load Markdown documents
    loader = MarkdownLoader(args.docs_dir)
    try:
        documents = loader.load()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Loaded {len(documents)} documents")

    # Step 2: Split documents
    print("Splitting documents...")
    chunks = split_documents(
        documents,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    print(f"Created {len(chunks)} chunks")

    # Step 3: Create vector store and ingest
    print("Creating Milvus vector store...")
    vectorstore = MilvusVectorStore(collection_name=args.collection)
    vectorstore.create_from_documents(chunks, drop_old=args.drop_old)

    print(f"Successfully ingested {len(chunks)} chunks into collection '{vectorstore.collection_name}'")


if __name__ == "__main__":
    main()
