/**
 * Knowledge base search tool. Falls back to mock data when Qdrant is unavailable.
 */

interface KBArticle {
  id: string;
  title: string;
  content: string;
  category: string;
}

const MOCK_KB: KBArticle[] = [
  {
    id: "kb-001",
    title: "How to reset your password",
    content:
      "Go to Settings > Security > Reset Password. Enter your current password, then your new password twice. Click Save.",
    category: "account",
  },
  {
    id: "kb-002",
    title: "API rate limits and error codes",
    content:
      "Rate limits: 100 req/min for free, 1000/min for Pro. 429 = rate limited. Common: 400 (bad request), 401 (unauthorized), 500 (server error).",
    category: "technical",
  },
  {
    id: "kb-003",
    title: "Updating your billing information",
    content:
      "Navigate to Account > Billing > Payment Methods. Click Update next to your current method. Enter new card details.",
    category: "billing",
  },
  {
    id: "kb-004",
    title: "Troubleshooting large payload errors",
    content:
      "Maximum payload size is 10MB. For larger payloads, use streaming or split requests. Check Content-Type header and JSON validity.",
    category: "technical",
  },
  {
    id: "kb-005",
    title: "Two-factor authentication setup",
    content:
      "Go to Settings > Security > 2FA. Choose authenticator app or SMS. Scan QR code. Enter 6-digit code to verify. Save backup codes.",
    category: "account",
  },
  {
    id: "kb-006",
    title: "Integration webhook configuration",
    content:
      "Set up at Settings > Integrations > Webhooks. Add endpoint URL, select events, save. Payloads are signed with your webhook secret.",
    category: "technical",
  },
];

export function mockSearch(query: string, topK = 3): string {
  const words = query.toLowerCase().split(/\s+/);
  const scored: Array<[number, KBArticle]> = [];

  for (const article of MOCK_KB) {
    const text = `${article.title} ${article.content}`.toLowerCase();
    const score = words.filter((w) => text.includes(w)).length;
    if (score > 0) scored.push([score, article]);
  }

  scored.sort((a, b) => b[0] - a[0]);
  const top = scored.slice(0, topK);

  if (top.length === 0)
    return "No relevant articles found in the knowledge base.";

  return top.map(([, a]) => `**${a.title}**\n${a.content}`).join("\n\n---\n\n");
}

export async function kbSearch(query: string, topK = 3): Promise<string> {
  // In production, this would query Qdrant. Falls back to mock search.
  return mockSearch(query, topK);
}
