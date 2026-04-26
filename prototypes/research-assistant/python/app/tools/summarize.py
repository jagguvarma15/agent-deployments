"""Text summarization tool."""


async def summarize(text: str, max_length: int = 200) -> str:
    """Summarize text by truncating to max_length characters."""
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(" ", 1)[0] + "..."
