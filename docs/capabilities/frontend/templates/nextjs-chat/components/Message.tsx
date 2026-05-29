import type { Message as AiMessage } from "ai";

type Role = AiMessage["role"];

const ROLE_LABEL: Record<Role, string> = {
  user: "You",
  assistant: "Agent",
  system: "System",
  function: "Tool",
  tool: "Tool",
  data: "Data",
};

export function Message({ role, content }: { role: Role; content: string }) {
  const isUser = role === "user";
  return (
    <li className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
      <span className="mb-1 text-xs uppercase tracking-wide text-zinc-400">
        {ROLE_LABEL[role] ?? role}
      </span>
      <div
        className={`max-w-[80%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
          isUser
            ? "bg-agent-user text-white"
            : "bg-zinc-100 text-zinc-900"
        }`}
      >
        {content}
      </div>
    </li>
  );
}
