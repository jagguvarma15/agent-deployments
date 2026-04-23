"""Knowledge base search tool using Qdrant.

Falls back to mock data when Qdrant is unavailable, making the prototype
runnable without the full infra stack for development and testing.
"""

import structlog

logger = structlog.get_logger()

# Mock KB articles for when Qdrant is unavailable
_MOCK_KB = [
    {
        "id": "kb-001",
        "title": "How to reset your password",
        "content": (
            "Go to Settings > Security > Reset Password. Enter your current"
            " password, then your new password twice. Click Save. You'll"
            " receive a confirmation email."
        ),
        "category": "account",
    },
    {
        "id": "kb-002",
        "title": "API rate limits and error codes",
        "content": (
            "Rate limits: 100 requests/minute for free tier, 1000/minute"
            " for Pro. When exceeded, you'll get a 429 status code."
            " Implement exponential backoff. Common errors: 400 (bad"
            " request), 401 (unauthorized), 500 (server error —"
            " contact support)."
        ),
        "category": "technical",
    },
    {
        "id": "kb-003",
        "title": "Updating your billing information",
        "content": (
            "Navigate to Account > Billing > Payment Methods. Click"
            " 'Update' next to your current method. Enter new card"
            " details. Changes take effect on your next billing cycle."
        ),
        "category": "billing",
    },
    {
        "id": "kb-004",
        "title": "Troubleshooting large payload errors",
        "content": (
            "Maximum payload size is 10MB for the standard API. For"
            " larger payloads, use the streaming endpoint or split your"
            " request. If you're getting 500 errors, check that your"
            " Content-Type header is set correctly and the JSON is valid."
        ),
        "category": "technical",
    },
    {
        "id": "kb-005",
        "title": "Two-factor authentication setup",
        "content": (
            "Go to Settings > Security > 2FA. Choose your method:"
            " authenticator app (recommended) or SMS. Scan the QR code"
            " with your authenticator app. Enter the 6-digit code to"
            " verify. Save your backup codes in a secure location."
        ),
        "category": "account",
    },
    {
        "id": "kb-006",
        "title": "Integration webhook configuration",
        "content": (
            "Set up webhooks at Settings > Integrations > Webhooks. Add"
            " your endpoint URL, select events to subscribe to, and save."
            " We'll send a test ping. Webhook payloads are signed with"
            " your webhook secret for verification."
        ),
        "category": "technical",
    },
]


async def kb_search(query: str, top_k: int = 3) -> str:
    """Search the knowledge base. Falls back to keyword matching if Qdrant is unavailable."""
    try:
        return await _qdrant_search(query, top_k)
    except Exception:
        logger.info("qdrant_unavailable_using_mock", query=query)
        return _mock_search(query, top_k)


async def _qdrant_search(query: str, top_k: int) -> str:
    """Search using Qdrant vector DB."""
    from qdrant_client import AsyncQdrantClient

    from app.settings import settings

    client = AsyncQdrantClient(url=settings.qdrant_url)

    # Check if collection exists
    collections = await client.get_collections()
    collection_names = [c.name for c in collections.collections]
    if settings.qdrant_collection not in collection_names:
        raise RuntimeError("Collection not found")

    # Use Qdrant's built-in query (requires fastembed or pre-indexed data)
    results = await client.query(
        collection_name=settings.qdrant_collection,
        query_text=query,
        limit=top_k,
    )

    if not results:
        return "No relevant articles found in the knowledge base."

    articles = []
    for point in results:
        payload = point.metadata
        articles.append(f"**{payload.get('title', 'Untitled')}**\n{payload.get('content', '')}")

    return "\n\n---\n\n".join(articles)


def _mock_search(query: str, top_k: int) -> str:
    """Simple keyword-based fallback search."""
    query_lower = query.lower()
    scored = []
    for article in _MOCK_KB:
        score = sum(
            1
            for word in query_lower.split()
            if word in article["title"].lower() or word in article["content"].lower()
        )
        if score > 0:
            scored.append((score, article))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    if not top:
        return "No relevant articles found in the knowledge base."

    articles = [f"**{a['title']}**\n{a['content']}" for _, a in top]
    return "\n\n---\n\n".join(articles)
