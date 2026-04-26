"""ReAct-loop research agent."""

from pydantic_ai import Agent

from app.settings import settings
from app.tools.web_search import web_search

_agent: Agent | None = None


def _get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent(
            f"anthropic:{settings.research_model}",
            system_prompt=(
                "You are a research assistant. Given a question, search for information, "
                "analyze results, and provide a comprehensive answer with sources."
            ),
        )

        @_agent.tool_plain
        async def search_web(query: str) -> str:
            """Search the web for relevant information."""
            return await web_search(query)

    return _agent


async def run_research(question: str, max_steps: int = 5) -> tuple[str, list[dict]]:
    """Run research on a question and return (answer, steps)."""
    agent = _get_agent()
    result = await agent.run(question)
    steps = [{"step": 1, "action": "search", "content": f"Researched: {question}"}]
    return result.data, steps
