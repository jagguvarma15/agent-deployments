"""Mock web search tool."""

_MOCK_RESULTS = [
    {
        "title": "Introduction to Machine Learning",
        "url": "https://example.com/ml-intro",
        "snippet": "Machine learning is a subset of AI that enables systems to learn from data.",
    },
    {
        "title": "Deep Learning Fundamentals",
        "url": "https://example.com/deep-learning",
        "snippet": "Deep learning uses neural networks with multiple layers to model complex patterns.",
    },
    {
        "title": "Natural Language Processing Overview",
        "url": "https://example.com/nlp",
        "snippet": "NLP combines linguistics and ML to enable computers to understand human language.",
    },
]


async def web_search(query: str) -> str:
    """Search the web. Returns mock results for development."""
    results = []
    for r in _MOCK_RESULTS:
        results.append(f"**{r['title']}**\n{r['url']}\n{r['snippet']}")
    return "\n\n".join(results)
