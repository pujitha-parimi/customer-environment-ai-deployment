
from agents.support_agent import _UNTRUSTED
from llm_client import ask_gemini


def handle_technical_query(query: str) -> str:
    """Handle technical issues and troubleshooting."""
    prompt = f"""
    You are a technical customer support specialist.

    Help customers troubleshoot technical problems.
    Give clear, beginner-friendly, step-by-step instructions.
    Ask for the error message or relevant details when needed.
    Never claim you accessed or repaired a system.

    {_UNTRUSTED}

    <customer_query>
    {query}
    </customer_query>
    """

    return ask_gemini(prompt)
