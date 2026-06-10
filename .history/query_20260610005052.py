from scripts.generation import generate


def ask(question: str) -> dict[str, str]:
    """Run a full query and return answer plus source information."""
    result = generate(question)
    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "citations": result.get("citations", {}),
        "error": result.get("error"),
    }
