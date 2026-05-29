"use client";

import { Chat } from "@/components/Chat";

export default function Page() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">Agent</h1>
        <p className="text-sm text-zinc-500">
          Streaming chat backed by the project&apos;s agent service.
        </p>
      </header>
      <Chat />
    </main>
  );
}
