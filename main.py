import asyncio
import logging
import uuid
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from src import config
from src.agent import create_enterprise_copilot, close_connections

# Load environment variables (OPENAI_API_KEY)
load_dotenv()

async def chat_loop():
    print("\n--- Enterprise Architecture Copilot ---")
    print("Type 'exit' or 'quit' to stop.\n")

    # Per-session thread_id so multiple users don't share conversation state
    # if a checkpointer is wired in later.
    thread_id = str(uuid.uuid4())
    print(f"Session id: {thread_id}\n")

    # Initialize the compiled LangGraph agent
    agent = create_enterprise_copilot()

    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                break

            # Initial state for the graph
            inputs = {"messages": [HumanMessage(content=user_input)]}

            run_config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": config.recursion_limit(),
            }
            
            print("\nCopilot: ", end="", flush=True)
            
            # Single run: stream to show tool calls, then use last state for final answer (one LangSmith trace per query)
            printed_msgs = set()
            last_messages = []
            async for chunk in agent.astream(inputs, run_config, stream_mode="values"):
                if "messages" in chunk:
                    last_messages = chunk["messages"]
                    for msg in chunk["messages"]:
                        if msg.id not in printed_msgs:
                            if msg.type == "ai" and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    print(f"\n[Tool Call] {tc['name']}({tc['args']})")
                            elif msg.type == "tool":
                                print(f"[Tool Response] {msg.content[:200]}..." if len(msg.content) > 200 else f"[Tool Response] {msg.content}")
                            elif msg.type == "ai" and not msg.tool_calls:
                                pass
                            printed_msgs.add(msg.id)
            
            final_content = last_messages[-1].content if last_messages else "(no response)"
            print(f"\nFinal Answer: {final_content}")
            print("-" * 20)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        print("\nExiting gracefully...")
    finally:
        try:
            from src.agent import close_connections
            close_connections()
        except Exception as e:
            logging.exception("Error closing database connections during shutdown: %s", e)
            raise
        print("Done.")
