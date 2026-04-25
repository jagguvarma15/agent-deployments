"""Fact extraction tool."""

_MOCK_FACTS = [
    "Machine learning enables systems to learn from data without explicit programming.",
    "Deep learning uses multi-layer neural networks for pattern recognition.",
    "NLP combines computational linguistics with statistical methods.",
    "Transformer architectures revolutionized language understanding in 2017.",
]


def extract_facts(text: str) -> list[str]:
    """Extract key facts from text. Returns mock facts for development."""
    return _MOCK_FACTS[:3]
