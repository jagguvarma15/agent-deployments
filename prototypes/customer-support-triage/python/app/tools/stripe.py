"""Mock Stripe MCP tool for billing lookups.

In production, this would connect to a real Stripe MCP server.
The mock returns realistic responses for demo and eval purposes.
"""

import json

# Mock billing data
_MOCK_CUSTOMERS = {
    "default": {
        "customer_id": "cus_demo123",
        "email": "customer@example.com",
        "plan": "Pro",
        "monthly_amount": "$49.00",
        "status": "active",
        "last_payment": "2026-04-01",
        "next_billing": "2026-05-01",
        "payment_method": "Visa ending in 4242",
    }
}

_MOCK_RESPONSES = {
    "charge": "Found recent charge of $49.00 on 2026-04-01 for Pro plan subscription. Status: succeeded. No duplicate charges detected.",
    "refund": "Refund policy: Full refunds available within 30 days of charge. To process a refund, the customer should confirm the charge date and amount.",
    "subscription": "Current subscription: Pro plan at $49.00/month. Next billing date: 2026-05-01. Plan can be changed or cancelled from account settings.",
    "invoice": "Most recent invoice #INV-2026-0401 for $49.00 issued on 2026-04-01. Status: paid. PDF available at billing portal.",
    "payment_method": "Current payment method: Visa ending in 4242, expiring 12/2027. To update, customer can visit the billing portal.",
}


async def stripe_lookup(query: str) -> str:
    """Look up billing information. Returns a structured response string."""
    query_lower = query.lower()

    # Match against known query types
    for keyword, response in _MOCK_RESPONSES.items():
        if keyword in query_lower:
            customer = _MOCK_CUSTOMERS["default"]
            return f"Customer: {customer['email']} ({customer['customer_id']})\n{response}"

    # Default: return customer overview
    customer = _MOCK_CUSTOMERS["default"]
    return f"Customer billing summary:\n{json.dumps(customer, indent=2)}"
