// Proxy /api/agent -> ${NEXT_PUBLIC_AGENT_URL}/chat, adapting the wire shapes.
// The browser side speaks the Vercel AI SDK's useChat protocol
// ({messages: [{role, content}]} in, plain text out via streamProtocol: "text");
// the backend speaks the canonical /chat contract
// ({message, history: [{role: "user"|"agent", text}]} -> {reply}, non-streaming
// JSON — see docs/reference/chat-contract.md). This route translates between
// them and keeps the browser on a same-origin endpoint so CORS stays simple.

import { NextRequest } from "next/server";

export const runtime = "edge";

const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";

interface UiMessage {
  role: string;
  content: string;
}

export async function POST(req: NextRequest) {
  const { messages = [] } = (await req.json().catch(() => ({}))) as {
    messages?: UiMessage[];
  };
  const chat = messages.filter((m) => m.role === "user" || m.role === "assistant");
  const lastUserIndex = chat.map((m) => m.role).lastIndexOf("user");
  const message = lastUserIndex >= 0 ? chat[lastUserIndex].content : "";
  const prior = lastUserIndex >= 0 ? chat.slice(0, lastUserIndex) : chat;
  const body = {
    message,
    // Courtesy client cap; the backend trim is the authoritative bound.
    history: prior.slice(-40).map((m) => ({
      role: m.role === "assistant" ? ("agent" as const) : ("user" as const),
      text: m.content,
    })),
  };

  const upstream = await fetch(`${AGENT_URL.replace(/\/$/, "")}/chat`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body: JSON.stringify(body),
  });

  if (!upstream.ok) {
    const detail = await upstream.text().catch(() => "");
    return new Response(
      JSON.stringify({ error: "agent error", status: upstream.status, detail }),
      {
        status: upstream.status || 502,
        headers: { "content-type": "application/json" },
      },
    );
  }

  // The contract's reply is non-streaming JSON; return it as plain text,
  // which useChat({ streamProtocol: "text" }) accepts as a complete message.
  const data = (await upstream.json().catch(() => null)) as { reply?: string } | null;
  return new Response(typeof data?.reply === "string" ? data.reply : "", {
    status: 200,
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}
