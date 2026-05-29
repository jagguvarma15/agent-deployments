// Lightweight fetch helpers used by the chat UI. The Vercel AI SDK handles
// the streaming protocol itself via the useChat hook in components/Chat.tsx;
// this module is here for additional REST calls the project may add later
// (e.g. fetching tool definitions, restaurant lookups, eval feedback).

export interface ApiError {
  status: number;
  message: string;
  detail?: unknown;
}

export async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new ApiErrorImpl(response.status, response.statusText, detail);
  }
  return (await response.json()) as T;
}

class ApiErrorImpl extends Error implements ApiError {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
