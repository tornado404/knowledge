"""Main entry point for Knowledge RAG Chat."""

import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import argparse


def main():
    parser = argparse.ArgumentParser(description="Knowledge RAG Chat")
    parser.add_argument(
        "--mode",
        choices=["api", "chat", "retrieve"],
        default="api",
        help="Run mode: api (FastAPI server), chat (interactive chat), retrieve (search only)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="API server host")
    parser.add_argument("--port", type=int, default=8000, help="API server port")
    parser.add_argument("--query", type=str, help="Query for retrieve mode")
    parser.add_argument("--k", type=int, default=4, help="Number of documents to retrieve")

    args = parser.parse_args()

    if args.mode == "api":
        print(f"Starting API server at http://{args.host}:{args.port}")
        from knowledge_vector.chat import run_server
        run_server(host=args.host, port=args.port)

    elif args.mode == "chat":
        from knowledge_vector.chain import create_rag_chain
        import readline  # Optional: for better CLI experience

        rag_chain = create_rag_chain()
        print("Knowledge RAG Chat (type 'quit' to exit)")
        print("-" * 40)

        while True:
            question = input("\nYou: ").strip()
            if question.lower() in ["quit", "exit", "q"]:
                break
            if not question:
                continue

            answer = rag_chain.invoke(question, k=args.k)
            print(f"\nAssistant: {answer}")

    elif args.mode == "retrieve":
        from knowledge_vector.chain import create_rag_chain

        if not args.query:
            print("Error: --query required for retrieve mode")
            return

        rag_chain = create_rag_chain()
        docs = rag_chain.retrieve(args.query, k=args.k)

        print(f"Found {len(docs)} documents:\n")
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "unknown")
            content = doc.page_content[:300].replace("\n", " ")
            print(f"{i}. [{source}]")
            print(f"   {content}...")
            print()


if __name__ == "__main__":
    main()
