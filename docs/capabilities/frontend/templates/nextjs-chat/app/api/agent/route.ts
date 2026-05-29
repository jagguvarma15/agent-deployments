// Proxy /api/agent → ${NEXT_PUBLIC_AGENT_URL}/chat, streaming the response back.
// Keeps the browser on a same-origin endpoint so CORS / cookies stay simple,
// and lets the deployment set NEXT_PUBLIC_AGENT_URL per environment.

import { NextRequest } from "next/server";

export const runtime = "edge";

const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.text();
  const upstream = await fetch(`${AGENT_URL.replace(/\/$/, "")}/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
  });

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text().catch(() => "");
    return new Response(
      JSON.stringify({ error: "agent error", status: upstream.status, detail }),
      {
        status: upstream.status || 502,
        headers: { "content-type": "application/json" },
      },
    );
  }

  // Pass the upstream stream through unchanged. The Vercel AI SDK on the
  // client side reads the same protocol the backend emits.
  return new Response(upstream.body, {
    status: 200,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "text/plain",
      "cache-control": "no-store",
    },
  });
}
