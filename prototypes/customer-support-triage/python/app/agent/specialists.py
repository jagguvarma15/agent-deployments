"""Specialist agents for each intent category."""

from pydantic_ai import Agent

from app.models.schemas import Intent
from app.settings import settings
from app.tools.kb import kb_search
from app.tools.stripe import stripe_lookup

SPECIALIST_PROMPTS = {
    Intent.BILLING: """You are a billing support specialist. Help customers with payment issues,
subscription changes, invoices, and charges. You have access to the Stripe tool to look up
billing information. Be helpful, concise, and professional.""",
    Intent.TECHNICAL: """You are a technical support specialist. Help customers with bugs, errors,
API issues, and integration problems. You have access to a knowledge base search tool.
Provide clear, actionable guidance.""",
    Intent.ACCOUNT: """You are an account support specialist. Help customers with password resets,
profile updates, and account settings. You have access to a knowledge base search tool.
Guide them step by step.""",
    Intent.GENERAL: """You are a general support specialist. Help customers with general questions,
feedback, and feature requests. Be friendly and helpful.""",
}


def _make_billing_agent() -> Agent:
    agent = Agent(
        f"anthropic:{settings.specialist_model}",
        system_prompt=SPECIALIST_PROMPTS[Intent.BILLING],
    )

    @agent.tool_plain
    async def lookup_billing(query: str) -> str:
        """Look up billing information for a customer using Stripe."""
        return await stripe_lookup(query)

    return agent


def _make_technical_agent() -> Agent:
    agent = Agent(
        f"anthropic:{settings.specialist_model}",
        system_prompt=SPECIALIST_PROMPTS[Intent.TECHNICAL],
    )

    @agent.tool_plain
    async def search_knowledge_base(query: str) -> str:
        """Search the technical knowledge base for relevant articles."""
        return await kb_search(query)

    return agent


def _make_account_agent() -> Agent:
    agent = Agent(
        f"anthropic:{settings.specialist_model}",
        system_prompt=SPECIALIST_PROMPTS[Intent.ACCOUNT],
    )

    @agent.tool_plain
    async def search_knowledge_base(query: str) -> str:
        """Search the account knowledge base for relevant articles."""
        return await kb_search(query)

    return agent


def _make_general_agent() -> Agent:
    return Agent(
        f"anthropic:{settings.specialist_model}",
        system_prompt=SPECIALIST_PROMPTS[Intent.GENERAL],
    )


_agents: dict[Intent, Agent] = {}


def get_specialist(intent: Intent) -> Agent:
    """Get the specialist agent for a given intent (lazy-initialized)."""
    if intent not in _agents:
        factories = {
            Intent.BILLING: _make_billing_agent,
            Intent.TECHNICAL: _make_technical_agent,
            Intent.ACCOUNT: _make_account_agent,
            Intent.GENERAL: _make_general_agent,
        }
        _agents[intent] = factories[intent]()
    return _agents[intent]


async def run_specialist(intent: Intent, message: str) -> tuple[str, list[dict]]:
    """Run the specialist agent and return (response_text, tool_calls)."""
    agent = get_specialist(intent)
    result = await agent.run(message)
    tool_calls = [
        {"tool_name": call.tool_name, "args": call.args}
        for call in result.all_messages()
        if hasattr(call, "tool_name")
    ]
    return result.data, tool_calls
