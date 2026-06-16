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

function InlineMarkdown({ text }: { text: string }) {
  const nodes = React.useMemo(() => {
    const parts: React.ReactNode[] = [];
    const boldPattern = /\*\*([^\n*]+?)\*\*/g;
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = boldPattern.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index));
      }
      parts.push(
        <strong key={`strong-${match.index}`} className="font-semibold">
          {match[1]}
        </strong>,
      );
      lastIndex = boldPattern.lastIndex;
    }

    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex));
    }

    return parts;
  }, [text]);

  return <>{nodes}</>;
}

type MarkdownList = {
  type: "ol" | "ul";
  items: Array<{
    main: string;
    details: Array<{ text: string; bullet: boolean }>;
  }>;
};

function MessageContent({ content, role }: { content: string; role: DisplayMessage["role"] }) {
  const blocks = React.useMemo(() => {
    const rendered: React.ReactNode[] = [];
    const lines = content.split("\n");
    let paragraph: string[] = [];
    let list: MarkdownList | null = null;

    const clean = (value: string) => value.trim().replace(/\s{2,}$/g, "");

    const flushParagraph = () => {
      const text = paragraph.map(clean).filter(Boolean).join("\n");
      if (text) {
        rendered.push(
          <p key={`p-${rendered.length}`} className="whitespace-pre-wrap">
            <InlineMarkdown text={text} />
          </p>,
        );
      }
      paragraph = [];
    };

    const flushList = () => {
      if (!list || list.items.length === 0) return;
      const ListTag = list.type;
      rendered.push(
        <ListTag
          key={`list-${rendered.length}`}
          className={`ml-4 space-y-2 ${list.type === "ol" ? "list-decimal" : "list-disc"}`}
        >
          {list.items.map((item, itemIndex) => (
            <li key={itemIndex}>
              <InlineMarkdown text={clean(item.main)} />
              {item.details.length > 0 ? (
                <div className="mt-1 space-y-1 text-slate-600">
                  {item.details.map((detail, detailIndex) => (
                    <div key={detailIndex} className={detail.bullet ? "flex gap-2" : "whitespace-pre-wrap"}>
                      {detail.bullet ? <span className="select-none text-slate-400">-</span> : null}
                      <span>
                        <InlineMarkdown text={clean(detail.text)} />
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}
            </li>
          ))}
        </ListTag>,
      );
      list = null;
    };

    for (const rawLine of lines) {
      const line = rawLine.trimEnd();
      const trimmed = line.trim();
      if (!trimmed) {
        flushParagraph();
        continue;
      }

      const heading = trimmed.match(/^(#{1,4})\s+(.+)$/);
      if (heading) {
        flushParagraph();
        flushList();
        const levelClass = heading[1].length <= 2 ? "text-base" : "text-sm";
        rendered.push(
          <h3 key={`h-${rendered.length}`} className={`${levelClass} font-semibold text-foreground`}>
            <InlineMarkdown text={clean(heading[2])} />
          </h3>,
        );
        continue;
      }

      const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
      if (ordered) {
        flushParagraph();
        if (!list || list.type !== "ol") {
          flushList();
          list = { type: "ol", items: [] };
        }
        list.items.push({ main: ordered[1], details: [] });
        continue;
      }

      const unordered = line.match(/^\s*[-*]\s+(.+)$/);
      if (unordered) {
        flushParagraph();
        const isNested = Boolean(list && /^\s+/.test(rawLine) && list.items.length > 0);
        if (isNested && list) {
          list.items[list.items.length - 1].details.push({ text: unordered[1], bullet: true });
        } else {
          if (!list || list.type !== "ul") {
            flushList();
            list = { type: "ul", items: [] };
          }
          list.items.push({ main: unordered[1], details: [] });
        }
        continue;
      }

      if (list && /^\s+/.test(rawLine) && list.items.length > 0) {
        list.items[list.items.length - 1].details.push({ text: trimmed, bullet: false });
        continue;
      }

      flushList();
      paragraph.push(line);
    }

    flushParagraph();
    flushList();

    return rendered;
  }, [content]);
  const isUser = role === "user";

  if (isUser) {
    return (
      <div className="whitespace-pre-wrap">
        <InlineMarkdown text={content} />
      </div>
    );
  }

  return <div className="space-y-3">{blocks}</div>;
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
              {m.content ? <MessageContent content={m.content} role={m.role} /> : null}
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
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && !e.shiftKey) {
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
