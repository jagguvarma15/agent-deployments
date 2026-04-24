"""Q&A agent using Pydantic AI with retrieval tool."""

from pydantic_ai import Agent

from app.settings import settings
from app.tools.retriever import search_similar

QA_SYSTEM_PROMPT = """You are a document Q&A assistant. Your job is to answer questions
based on the documents in the knowledge base.

When answering:
1. Use the search_knowledge_base tool to find relevant document chunks.
2. Base your answer ONLY on the retrieved content.
3. Include citations referencing the source documents.
4. If no relevant information is found, say so clearly.

Always provide accurate, concise answers with proper citations."""

_qa_agent: Agent | None = None


def _get_agent() -> Agent:
    global _qa_agent
    if _qa_agent is None:
        _qa_agent = Agent(
            f"anthropic:{settings.qa_model}",
            system_prompt=QA_SYSTEM_PROMPT,
        )

        @_qa_agent.tool_plain
        def search_knowledge_base(query: str, top_k: int = 5) -> str:
            """Search the knowledge base for relevant document chunks.

            Args:
                query: The search query.
                top_k: Number of results to return.

            Returns:
                Formatted search results.
            """
            return search_similar(query, top_k=top_k)

    return _qa_agent


async def answer_question(question: str, top_k: int = 5) -> tuple[str, list[dict]]:
    """Answer a question using the Q&A agent.

    Args:
        question: The user's question.
        top_k: Number of chunks to retrieve.

    Returns:
        Tuple of (answer_text, citations_list).
    """
    agent = _get_agent()
    result = await agent.run(f"Answer this question (retrieve up to {top_k} chunks): {question}")

    # Extract citations from tool calls
    citations: list[dict] = []
    for msg in result.all_messages():
        if hasattr(msg, "parts"):
            for part in msg.parts:
                if hasattr(part, "tool_name") and part.tool_name == "search_knowledge_base":
                    citations.append({
                        "tool": part.tool_name,
                        "args": part.args if hasattr(part, "args") else {},
                    })

    return result.data, citations
