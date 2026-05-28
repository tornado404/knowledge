"""Main entry point for Knowledge RAG Chat."""

import sys
from pathlib import Path

# Add kgsrc to Python path
sys.path.insert(0, str(Path(__file__).parent / "kgsrc"))

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
    parser.add_argument(
        "--multi-agent",
        action="store_true",
        help="Enable multi-agent collaboration mode"
    )

    args = parser.parse_args()

    if args.mode == "api":
        print(f"Starting API server at http://{args.host}:{args.port}")
        from knowledge_vector.chat import run_server
        run_server(host=args.host, port=args.port)

    elif args.mode == "chat":
        if args.multi_agent:
            # Multi-agent mode
            import asyncio
            from knowledge_vector.multi_agent import get_orchestrator
            from knowledge_vector.memory import ConversationMemory

            async def run_multi_agent_chat():
                orchestrator = get_orchestrator()
                await orchestrator.initialize()

                memory = ConversationMemory(max_turns=10)
                session_id = "local-session"

                print("Knowledge RAG Chat - Multi-Agent Mode (type 'quit' to exit, 'clear' to clear history)")
                print("-" * 50)

                while True:
                    question = input("\nYou: ").strip()
                    if question.lower() in ["quit", "exit", "q"]:
                        break
                    if question.lower() == "clear":
                        memory.clear()
                        print("History cleared.")
                        continue
                    if not question:
                        continue

                    # Process with orchestrator
                    state = await orchestrator.process_question(session_id, question)

                    # Wait for completion (简单轮询)
                    import asyncio
                    for _ in range(30):  # 最多等 30 秒
                        await asyncio.sleep(1)
                        result = await orchestrator.get_task_result(state.task_id)
                        if result and result["status"] in ["done", "failed", "paused"]:
                            break

                    result = await orchestrator.get_task_result(state.task_id)
                    answer = result["answer"] if result else "处理超时"

                    memory.add_user(question)
                    memory.add_assistant(answer)

                    print(f"\nAssistant: {answer}")

                await orchestrator.shutdown()

            asyncio.run(run_multi_agent_chat())
        else:
            # Single agent mode
            from knowledge_vector.agent import invoke_agent
            from knowledge_vector.memory import ConversationMemory
            import readline  # Optional: for better CLI experience

            memory = ConversationMemory(max_turns=10)
            print("Knowledge RAG Chat - Agentic RAG with routing (type 'quit' to exit, 'clear' to clear history)")
            print("-" * 50)

            while True:
                question = input("\nYou: ").strip()
                if question.lower() in ["quit", "exit", "q"]:
                    break
                if question.lower() == "clear":
                    memory.clear()
                    print("History cleared.")
                    continue
                if not question:
                    continue

                # Get history for RAG (format: [{"role": "user"/"assistant", "content": "..."}])
                history = memory.get_history()

                # Invoke agent with routing
                answer = invoke_agent(question, history=history)

                # Add to history
                memory.add_user(question)
                memory.add_assistant(answer)

                print(f"\nAssistant: {answer}")
                print(f"[Turn {memory.turn_count}]")

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
