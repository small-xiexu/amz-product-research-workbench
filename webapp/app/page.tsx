"use client";

import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { AppConfig, SessionState } from "@/lib/types";
import { ChatPanel, DisplayMessage, toDisplayMessages } from "@/components/ChatPanel";
import { StateCard } from "@/components/StateCard";
import { FileUploadCard } from "@/components/FileUploadCard";
import { DirectionCards, DecisionBar } from "@/components/DirectionCards";
import { ArtifactPreview } from "@/components/ArtifactPreview";
import { Button } from "@/components/ui/button";
import { normalizeSite } from "@/lib/sites";

type MobilePanel = "chat" | "workbench";

const LAST_SESSION_KEY = "amz-workbench:last-session-id";

function messageId(prefix: string) {
  const id = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `${prefix}-${id}`;
}

function syncSessionPointer(sessionId: string | null) {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (sessionId) {
    window.localStorage.setItem(LAST_SESSION_KEY, sessionId);
    url.searchParams.set("session", sessionId);
  } else {
    window.localStorage.removeItem(LAST_SESSION_KEY);
    url.searchParams.delete("session");
  }
  window.history.replaceState(null, "", url);
}

function readableModelLabel(config: AppConfig | null) {
  if (!config) return "AI 未配置";
  const activeKeySet = config.provider === "anthropic" ? config.anthropic_key_set : config.openai_key_set;
  if (!activeKeySet) return "AI 待配置";
  const model = config.model.toLowerCase();
  if (config.provider === "anthropic") {
    if (model.includes("opus-4")) return "AI：Claude Opus 4";
    if (model.includes("sonnet-4")) return "AI：Claude Sonnet 4";
    if (model.includes("3-5") && model.includes("sonnet")) return "AI：Claude Sonnet 3.5";
    if (model.includes("opus")) return "AI：Claude Opus";
    if (model.includes("sonnet")) return "AI：Claude Sonnet";
    return "AI：Claude";
  }
  if (model.includes("gpt-4o-mini")) return "AI：GPT-4o mini";
  if (model.includes("gpt-4o")) return "AI：GPT-4o";
  if (model.includes("gpt-4.1")) return "AI：GPT-4.1";
  return "AI 已配置";
}

export default function Home() {
  const [session, setSession] = React.useState<SessionState | null>(null);
  const [messages, setMessages] = React.useState<DisplayMessage[]>([]);
  const [busy, setBusy] = React.useState(false);
  const [creating, setCreating] = React.useState(false);
  const [config, setConfig] = React.useState<AppConfig | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [mobilePanel, setMobilePanel] = React.useState<MobilePanel>("chat");
  const [siteDraft, setSiteDraft] = React.useState("US");
  const [siteSaving, setSiteSaving] = React.useState(false);
  const sendingRef = React.useRef(false);
  const sidebarRef = React.useRef<HTMLElement>(null);

  React.useLayoutEffect(() => {
    if (typeof window === "undefined") return;
    const previousScrollRestoration = window.history.scrollRestoration;
    window.history.scrollRestoration = "manual";
    document.documentElement.classList.add("workbench-scroll-lock");
    window.scrollTo(0, 0);
    return () => {
      window.history.scrollRestoration = previousScrollRestoration;
      document.documentElement.classList.remove("workbench-scroll-lock");
    };
  }, []);

  React.useEffect(() => {
    window.scrollTo(0, 0);
    sidebarRef.current?.scrollTo({ top: 0 });
  }, [session?.session_id]);

  React.useEffect(() => {
    let cancelled = false;
    api.getConfig().then(setConfig).catch(() => setConfig(null));
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const restoredId = params.get("session") || window.localStorage.getItem(LAST_SESSION_KEY);
    if (!restoredId) {
      setCreating(true);
      api
        .createSession()
        .then((created) => {
          if (cancelled) return;
          setSession(created);
          setSiteDraft(created.site);
          setMessages(toDisplayMessages(created.messages || []));
          syncSessionPointer(created.session_id);
        })
        .catch((e) => {
          if (!cancelled) setError((e as Error).message);
        })
        .finally(() => {
          if (!cancelled) setCreating(false);
        });
      return () => {
        cancelled = true;
      };
    }
    api
      .getSession(restoredId)
      .then((restored) => {
        if (cancelled) return;
        setSession(restored);
        setSiteDraft(restored.site);
        setMessages(toDisplayMessages(restored.messages || []));
        syncSessionPointer(restored.session_id);
      })
      .catch(() => {
        if (cancelled) return;
        syncSessionPointer(null);
        setCreating(true);
        api
          .createSession()
          .then((created) => {
            if (cancelled) return;
            setSession(created);
            setSiteDraft(created.site);
            setMessages(toDisplayMessages(created.messages || []));
            syncSessionPointer(created.session_id);
          })
          .catch((e) => {
            if (!cancelled) setError((e as Error).message);
          })
          .finally(() => {
            if (!cancelled) setCreating(false);
          });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshSession = React.useCallback(async (id: string) => {
    try {
      const s = await api.getSession(id);
      setSession(s);
      setSiteDraft(s.site);
    } catch {
      /* ignore */
    }
  }, []);

  const createSession = async (site = "US") => {
    setCreating(true);
    setError(null);
    const selectedSite = normalizeSite(site);
    try {
      const s = await api.createSession("mode_pending", "", selectedSite);
      setSession(s);
      setSiteDraft(s.site);
      setMessages([]);
      setMobilePanel("chat");
      syncSessionPointer(s.session_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCreating(false);
    }
  };

  const saveSite = async (siteOverride?: string) => {
    if (!session || siteSaving) return;
    const nextSite = normalizeSite(siteOverride ?? siteDraft);
    if (nextSite === session.site) {
      setSiteDraft(nextSite);
      return;
    }
    setSiteSaving(true);
    setError(null);
    try {
      const updated = await api.updateSession(session.session_id, { site: nextSite });
      setSession(updated);
      setSiteDraft(updated.site);
      syncSessionPointer(updated.session_id);
    } catch (e) {
      setError((e as Error).message);
      setSiteDraft(session.site);
    } finally {
      setSiteSaving(false);
    }
  };

  const sendFromComposer = async (text: string) => {
    if (!session) return;
    await send(text);
  };

  const send = async (text: string, sessionIdOverride?: string) => {
    const sid = sessionIdOverride || session?.session_id;
    if (!sid || sendingRef.current) return;
    sendingRef.current = true;
    const assistantId = messageId("assistant");
    setMessages((prev) => [
      ...prev,
      { id: messageId("user"), role: "user", content: text },
      { id: assistantId, role: "assistant", content: "", streaming: true, toolRuns: [] },
    ]);
    setBusy(true);
    setMobilePanel("chat");
    setError(null);

    const patchAssistant = (fn: (m: DisplayMessage) => DisplayMessage) =>
      setMessages((prev) => {
        return prev.map((message) => (message.id === assistantId ? fn(message) : message));
      });

    try {
      await api.chatStream(sid, text, (event) => {
        switch (event.type) {
          case "text":
            patchAssistant((m) => ({ ...m, content: m.content + event.delta }));
            break;
          case "tool_start":
            patchAssistant((m) => ({
              ...m,
              toolRuns: [
                ...(m.toolRuns || []),
                { call_id: event.call_id, name: event.name, arguments: event.arguments, result: null, ok: true, error: null },
              ],
            }));
            break;
          case "tool_result":
            patchAssistant((m) => ({
              ...m,
              toolRuns: (m.toolRuns || []).map((r) =>
                r.call_id === event.call_id ? { ...r, ok: event.ok, result: event.result, error: event.error } : r,
              ),
            }));
            break;
          case "done":
            patchAssistant((m) => ({ ...m, content: m.content || event.final_text, streaming: false }));
            break;
          case "error":
            patchAssistant((m) => ({ ...m, content: `提示：${event.message}`, streaming: false }));
            setError(event.message);
            break;
          default:
            break;
        }
      });
      await refreshSession(sid);
    } catch (e) {
      setError((e as Error).message);
      patchAssistant((m) => ({ ...m, content: `提示：${(e as Error).message}`, streaming: false }));
    } finally {
      sendingRef.current = false;
      setBusy(false);
    }
  };

  const handleUploaded = async (summary: { saved: string[]; total: number }) => {
    if (!session) return;
    await refreshSession(session.session_id);
    const uploaded = summary.saved.length > 0 ? `新增 ${summary.saved.length} 个文件，当前共 ${summary.total} 个文件` : `当前共 ${summary.total} 个文件`;
    await send(
      `我已经上传了卖家精灵/评论导出文件（${uploaded}）。请先调用 inspect_manual_exports 盘点数据，告诉我缺什么、下一步该做什么。`,
      session.session_id,
    );
  };

  const startNewSession = () => {
    if ((messages.length > 0 || Object.keys(artifacts).length > 0) && !window.confirm("确定要重新开始一轮选品吗？当前会话会从页面上移除。")) {
      return;
    }
    setSession(null);
    setMessages([]);
    setSiteDraft("US");
    setError(null);
    setMobilePanel("chat");
    syncSessionPointer(null);
    void createSession();
  };

  if (!session) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="rounded-xl border border-border bg-surface px-5 py-4 text-sm text-slate-600 shadow-card">
          {creating ? "正在打开工作台..." : "工作台未打开"}
        </div>
        {error ? <p className="pb-6 text-center text-sm text-destructive">{error}</p> : null}
      </main>
    );
  }

  const artifacts = session.artifacts || {};

  return (
    <main className="flex h-dvh min-h-0 flex-col overflow-hidden bg-background">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-primary">AMZ 选品工作台</span>
          <span className="text-xs text-slate-400">运营 × AI 交互式选品</span>
        </div>
        <div className="order-3 grid w-full grid-cols-2 rounded-lg bg-muted p-1 lg:hidden">
          {[
            ["chat", "对话"],
            ["workbench", "流程"],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setMobilePanel(key as MobilePanel)}
              className={`h-9 rounded-md text-sm font-medium transition-colors ${
                mobilePanel === key ? "bg-surface text-primary shadow-card" : "text-slate-500"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden rounded-full bg-muted px-3 py-1 text-xs font-medium text-slate-600 sm:inline">
            {readableModelLabel(config)}
          </span>
          <Link
            href="/settings/ai"
            className="inline-flex h-9 cursor-pointer items-center justify-center gap-2 rounded-lg bg-transparent px-3 text-sm font-medium text-foreground transition-colors duration-150 hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary focus-visible:ring-offset-2"
          >
            AI 配置
          </Link>
          <Link
            href="/settings/data-sources"
            className="inline-flex h-9 cursor-pointer items-center justify-center gap-2 rounded-lg bg-transparent px-3 text-sm font-medium text-foreground transition-colors duration-150 hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary focus-visible:ring-offset-2"
          >
            数据源配置
          </Link>
          <Button size="sm" variant="ghost" onClick={startNewSession} disabled={creating}>
            {creating ? "创建中" : "重新开始"}
          </Button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[380px_minmax(0,1fr)]">
        <aside
          ref={sidebarRef}
          className={`min-h-0 space-y-3 overflow-y-auto border-r border-border bg-background p-3 ${
            mobilePanel === "workbench" ? "block" : "hidden"
          } lg:block`}
        >
          <StateCard
            session={session}
            siteDraft={siteDraft}
            siteBusy={siteSaving}
            onSiteDraftChange={setSiteDraft}
            onSiteSave={saveSite}
          />
          <FileUploadCard
            sessionId={session.session_id}
            uploadedFiles={artifacts.uploaded_files || []}
            disabled={busy}
            onUploaded={handleUploaded}
          />
          <DirectionCards candidatePool={artifacts.candidate_pool} disabled={busy} onChoose={(t) => send(t)} />
          <ArtifactPreview artifacts={artifacts} />
          {artifacts.candidate_pool ? <DecisionBar disabled={busy} onDecide={(t) => send(t)} /> : null}
        </aside>

        <section
          className={`min-h-0 overflow-hidden flex-col bg-surface ${
            mobilePanel === "chat" ? "flex" : "hidden"
          } lg:flex`}
        >
          <ChatPanel
            messages={messages}
            busy={busy || creating}
            placeholder="直接输入选品想法，Enter 换行，⌘/Ctrl+Enter 发送；AI 会自动识别本轮模式"
            onSend={sendFromComposer}
          />
        </section>
      </div>

    </main>
  );
}
