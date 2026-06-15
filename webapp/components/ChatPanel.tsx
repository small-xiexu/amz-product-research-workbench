"use client";

import * as React from "react";
import { MessagesSquare, SendHorizonal } from "lucide-react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import type { ChatMessage, ToolRun } from "@/lib/types";

export interface DisplayMessage {
  id?: string;
  role: "user" | "assistant";
  content: string;
  toolRuns?: ToolRun[];
  streaming?: boolean;
}

export function ChatPanel({
  messages,
  busy,
  placeholder = "输入消息，Enter 换行，⌘/Ctrl+Enter 发送",
  onSend,
}: {
  messages: DisplayMessage[];
  busy: boolean;
  placeholder?: string;
  onSend: (text: string) => void;
}) {
  const [draft, setDraft] = React.useState("");
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const endRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (messages.length === 0 && !busy) {
      scrollRef.current?.scrollTo({ top: 0 });
      return;
    }
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  const submit = () => {
    const text = draft.trim();
    if (!text || busy) return;
    onSend(text);
    setDraft("");
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div className="mx-auto mt-8 max-w-3xl rounded-xl border border-border bg-surface p-5 shadow-card">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-100 text-primary">
                <MessagesSquare className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase text-secondary">AI 协作入口</p>
                <h1 className="mt-1 text-xl font-bold text-primary">这里是运营和 AI 的主对话区</h1>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  可以直接输入一句选品想法；如果还没选模式，我会先把想法记录到左侧流程摘要，让你确认本轮怎么走。
                  需要 MCP、卖家精灵导出、ASIN 评论抓取或运营决策时，AI 会在对话里停下来说明。
                </p>
              </div>
            </div>
          </div>
        ) : null}

        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
            <div
              className={`max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed ${
                m.role === "user"
                  ? "bg-primary text-primary-fg"
                  : "border border-border bg-surface text-foreground"
              }`}
            >
              {m.content ? <div className="whitespace-pre-wrap">{m.content}</div> : null}
              {m.streaming ? (
                <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-secondary align-middle" />
              ) : null}
              {m.toolRuns && m.toolRuns.length > 0 ? (
                <div className="mt-2 space-y-1.5">
                  {m.toolRuns.map((run) => (
                    <div key={run.call_id} className="rounded-lg bg-muted px-2.5 py-1.5">
                      <div className="flex items-center gap-2">
                        <Badge tone={run.ok ? "success" : "danger"}>{run.ok ? "工具" : "失败"}</Badge>
                        <code className="font-mono text-xs text-slate-600">{run.name}</code>
                      </div>
                      {!run.ok && run.error ? (
                        <p className="mt-1 text-xs text-destructive">{run.error}</p>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        ))}

        {busy && !messages.some((m) => m.streaming) ? (
          <div className="flex justify-start">
            <div className="rounded-xl border border-border bg-surface px-3.5 py-2.5">
              <div className="flex gap-1">
                <span className="h-2 w-2 animate-bounce rounded-full bg-secondary [animation-delay:-0.3s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-secondary [animation-delay:-0.15s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-secondary" />
              </div>
            </div>
          </div>
        ) : null}
        {/* busy 由调用方在流式开始后置为 false，改用消息内的 streaming 光标 */}
        <div ref={endRef} />
      </div>

      <div className="border-t border-border p-3">
        <div className="flex items-end gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey || e.shiftKey)) {
                e.preventDefault();
                submit();
              }
            }}
            rows={2}
            placeholder={placeholder}
            className="max-h-32 flex-1 resize-none rounded-lg border border-border bg-surface px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
          <Button onClick={submit} disabled={busy || !draft.trim()} aria-label="发送消息">
            <SendHorizonal className="h-4 w-4" />
            <span className="hidden sm:inline">发送</span>
          </Button>
        </div>
      </div>
    </div>
  );
}

export function toDisplayMessages(messages: ChatMessage[]): DisplayMessage[] {
  return messages
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m, index) => ({ id: `${m.role}-${index}`, role: m.role as "user" | "assistant", content: m.content }));
}
