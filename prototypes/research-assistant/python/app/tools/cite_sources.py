"""Citation formatting tool."""


def cite_sources(facts: list[str]) -> str:
    """Format facts with numbered citations."""
    if not facts:
        return "No facts to cite."
    cited = []
    for i, fact in enumerate(facts, 1):
        cited.append(f"[{i}] {fact}")
    return "\n".join(cited)
