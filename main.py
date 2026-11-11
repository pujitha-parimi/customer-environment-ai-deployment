"""Interactive command-line interface. The HTTP API lives in api.py."""
from llm_client import LLMConfigError, LLMError
from logging_config import configure_logging
from service import (  # noqa: F401  (re-exported for backwards compatibility)
    classify_query,
    handle_order_query,
    route_query,
)


def main():
    configure_logging()
    print("=" * 45)
    print("  MULTI-AGENT CUSTOMER SUPPORT")
    print("=" * 45)
    print("Type 'exit' or 'quit' to quit.\n")

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if query.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break
        if not query:
            print("Please enter a question.\n")
            continue

        try:
            category, answer = route_query(query)
            print(f"\nRouted to: {category.title()} Agent")
            print(f"\nSupport Agent: {answer}\n")
        except LLMConfigError:
            print("\nThe AI service is not configured. Contact your administrator.\n")
        except LLMError:
            print("\nThe AI provider is unavailable right now. Please try again later.\n")
        except Exception:
            print("\nSorry, I couldn't process your request right now. Please try again later.\n")


if __name__ == "__main__":
    main()
