"use client";

import { useChat } from "ai/react";
import { Message } from "@/components/Message";

export function Chat() {
  const { messages, input, handleInputChange, handleSubmit, isLoading, error } =
    useChat({ api: "/api/agent" });

  return (
    <div className="flex flex-1 flex-col gap-4">
      <ol className="flex flex-1 flex-col gap-3 overflow-y-auto rounded-lg border border-zinc-200 bg-white p-4">
        {messages.length === 0 ? (
          <li className="text-sm text-zinc-400">
            Send a message to start the conversation.
          </li>
        ) : (
          messages.map((m) => <Message key={m.id} role={m.role} content={m.content} />)
        )}
      </ol>

      {error ? (
        <p className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error.message}
        </p>
      ) : null}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          className="flex-1 rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-500"
          value={input}
          placeholder="Ask the agent…"
          onChange={handleInputChange}
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="rounded-lg bg-agent-user px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {isLoading ? "…" : "Send"}
        </button>
      </form>
    </div>
  );
}
