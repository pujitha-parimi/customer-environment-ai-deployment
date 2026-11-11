
def validate_customer_query(query: str) -> dict:
    """Validate a customer support query."""

    cleaned_query = query.strip()

    if not cleaned_query:
        return {
            "valid": False,
            "message": "Please enter a question."
        }

    if "\x00" in cleaned_query:
        return {
            "valid": False,
            "message": "Your question contains invalid characters."
        }

    if len(cleaned_query) > 2000:
        return {
            "valid": False,
            "message": "Please keep your question under 2000 characters."
        }

    return {
        "valid": True,
        "message": "Query is valid.",
        "query": cleaned_query
    }
