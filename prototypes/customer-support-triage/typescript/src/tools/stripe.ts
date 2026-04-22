/**
 * Mock Stripe tool for billing lookups.
 */

const MOCK_CUSTOMER = {
  customer_id: "cus_demo123",
  email: "customer@example.com",
  plan: "Pro",
  monthly_amount: "$49.00",
  status: "active",
  last_payment: "2026-04-01",
  next_billing: "2026-05-01",
  payment_method: "Visa ending in 4242",
};

const MOCK_RESPONSES: Record<string, string> = {
  charge:
    "Found recent charge of $49.00 on 2026-04-01 for Pro plan subscription. Status: succeeded. No duplicate charges detected.",
  refund:
    "Refund policy: Full refunds available within 30 days of charge. To process a refund, the customer should confirm the charge date and amount.",
  subscription:
    "Current subscription: Pro plan at $49.00/month. Next billing date: 2026-05-01. Plan can be changed or cancelled from account settings.",
  invoice:
    "Most recent invoice #INV-2026-0401 for $49.00 issued on 2026-04-01. Status: paid. PDF available at billing portal.",
  payment_method:
    "Current payment method: Visa ending in 4242, expiring 12/2027. To update, customer can visit the billing portal.",
};

export async function stripeLookup(query: string): Promise<string> {
  const q = query.toLowerCase();

  for (const [keyword, response] of Object.entries(MOCK_RESPONSES)) {
    if (q.includes(keyword)) {
      return `Customer: ${MOCK_CUSTOMER.email} (${MOCK_CUSTOMER.customer_id})\n${response}`;
    }
  }

  return `Customer billing summary:\n${JSON.stringify(MOCK_CUSTOMER, null, 2)}`;
}
