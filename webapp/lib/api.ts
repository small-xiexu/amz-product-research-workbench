import type { AppConfig, ChatResponse, Mode, SessionState, StreamEvent } from "./types";

export interface ConfigUpdatePayload {
  provider: string;
  model: string;
  anthropic_api_key?: string;
  openai_api_key?: string;
  anthropic_base_url?: string;
  openai_base_url?: string;
  sorftime_mcp_url?: string;
  sorftime_api_key?: string;
  clear_anthropic_key?: boolean;
  clear_openai_key?: boolean;
  clear_sorftime_key?: boolean;
}

async function errorMessage(res: Response, fallback: string): Promise<string> {
  const detail = await res.json().catch(() => null);
  if (typeof detail?.detail === "string") return detail.detail;
  if (typeof detail?.message === "string") return detail.message;
  return fallback;
}

// 通过 Next.js rewrites 代理到 FastAPI（见 next.config.mjs）
async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    throw new Error(await errorMessage(res, `请求失败：${res.status}`));
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => jsonFetch<{ status: string; provider: string; model: string }>("/api/health"),

  getConfig: () => jsonFetch<AppConfig>("/api/config"),

  setConfig: (payload: ConfigUpdatePayload) =>
    jsonFetch<AppConfig>("/api/config", { method: "POST", body: JSON.stringify(payload) }),

  testConfig: (payload: ConfigUpdatePayload) =>
    jsonFetch<{ ok: boolean; provider: string; model: string; message: string }>("/api/config/test", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  testDataSource: (payload: ConfigUpdatePayload) =>
    jsonFetch<{ ok: boolean; source: string; message: string; tool_count?: number; tools?: string[] }>(
      "/api/config/data-sources/test",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),

  createSession: (mode: Mode = "mode_pending", intent = "", site = "US") =>
    jsonFetch<SessionState>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ mode, intent, site }),
    }),

  getSession: (id: string) => jsonFetch<SessionState>(`/api/sessions/${id}`),

  updateSession: (id: string, payload: Partial<{ mode: Mode; intent: string; site: string }>) =>
    jsonFetch<SessionState>(`/api/sessions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  chat: (sessionId: string, message: string) =>
    jsonFetch<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, message }),
    }),

  chatStream: async (
    sessionId: string,
    message: string,
    onEvent: (event: StreamEvent) => void,
  ): Promise<void> => {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message }),
    });
    if (!res.ok || !res.body) {
      throw new Error(await errorMessage(res, `请求失败：${res.status}`));
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        const json = line.slice(5).trim();
        if (!json) continue;
        try {
          onEvent(JSON.parse(json) as StreamEvent);
        } catch {
          /* 忽略不完整片段 */
        }
      }
    }
  },

  upload: async (sessionId: string, files: FileList) => {
    const form = new FormData();
    form.append("session_id", sessionId);
    Array.from(files).forEach((f) => form.append("files", f));
    const res = await fetch("/api/upload", { method: "POST", body: form });
    if (!res.ok) throw new Error(await errorMessage(res, "上传失败，请检查文件格式或后端状态"));
    return res.json() as Promise<{ upload_folder: string; saved: string[]; total: number }>;
  },
};
