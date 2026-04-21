/**
 * MCP (Model Context Protocol) client wrapper.
 */

export interface MCPClientConfig {
  baseUrl: string;
  headers?: Record<string, string>;
  timeoutMs?: number;
}

export class MCPClient {
  readonly baseUrl: string;
  readonly headers: Record<string, string>;
  readonly timeoutMs: number;

  constructor(config: MCPClientConfig) {
    this.baseUrl = config.baseUrl;
    this.headers = config.headers ?? {};
    this.timeoutMs = config.timeoutMs ?? 30_000;
  }

  async listTools(): Promise<Array<Record<string, unknown>>> {
    const response = await fetch(`${this.baseUrl}/list-tools`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.headers },
      body: JSON.stringify({}),
      signal: AbortSignal.timeout(this.timeoutMs),
    });

    if (!response.ok) {
      throw new Error(`MCP list-tools failed: ${response.status}`);
    }

    const data = (await response.json()) as { tools?: Array<Record<string, unknown>> };
    return data.tools ?? [];
  }

  async callTool(
    name: string,
    args: Record<string, unknown> = {},
  ): Promise<unknown> {
    const response = await fetch(`${this.baseUrl}/call-tool`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.headers },
      body: JSON.stringify({ name, arguments: args }),
      signal: AbortSignal.timeout(this.timeoutMs),
    });

    if (!response.ok) {
      throw new Error(`MCP call-tool "${name}" failed: ${response.status}`);
    }

    return response.json();
  }
}
