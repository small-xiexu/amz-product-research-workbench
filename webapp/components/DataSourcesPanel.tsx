"use client";

import * as React from "react";
import { ArrowLeft, DatabaseZap, Eye, EyeOff, Loader2, PlugZap, Save } from "lucide-react";
import Link from "next/link";
import { api, type ConfigUpdatePayload } from "@/lib/api";
import type { AppConfig } from "@/lib/types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardBody, CardHeader } from "./ui/card";

const DEFAULT_MODEL = "claude-sonnet-4-20250514";

type Notice = { tone: "success" | "danger"; text: string };

export function DataSourcesPanel({ initialConfig }: { initialConfig: AppConfig | null }) {
  const [config, setConfig] = React.useState<AppConfig | null>(initialConfig);
  const [sorftimeUrl, setSorftimeUrl] = React.useState(initialConfig?.sorftime_mcp_url || "https://mcp.sorftime.com");
  const [sorftimeKey, setSorftimeKey] = React.useState("");
  const [showKey, setShowKey] = React.useState(false);
  const [clearKey, setClearKey] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [testing, setTesting] = React.useState(false);
  const [notice, setNotice] = React.useState<Notice | null>(null);

  const sorftimeStatus = config?.keys?.sorftime;
  const urlHasKey = /[?&]key=/.test(sorftimeUrl);
  const hasStoredKey = Boolean(sorftimeStatus?.set && (sorftimeStatus.source === "env" || !clearKey));
  const hasSorftimeKey = Boolean(sorftimeKey.trim() || hasStoredKey || urlHasKey);
  const currentKeyHint = sorftimeStatus?.set ? sorftimeStatus.hint : "未配置";

  const buildPayload = (): ConfigUpdatePayload => ({
    provider: config?.provider || "anthropic",
    model: config?.model || DEFAULT_MODEL,
    anthropic_base_url: config?.anthropic_base_url || "",
    openai_base_url: config?.openai_base_url || "",
    sorftime_mcp_url: sorftimeUrl.trim() || "https://mcp.sorftime.com",
    sorftime_api_key: sorftimeKey.trim() || undefined,
    clear_sorftime_key: clearKey,
  });

  const save = async () => {
    setSaving(true);
    setNotice(null);
    try {
      const next = await api.setConfig(buildPayload());
      setConfig(next);
      setSorftimeUrl(next.sorftime_mcp_url || "https://mcp.sorftime.com");
      setSorftimeKey("");
      setClearKey(false);
      setNotice({ tone: "success", text: "数据源配置已保存。" });
    } catch (error) {
      setNotice({ tone: "danger", text: (error as Error).message });
    } finally {
      setSaving(false);
    }
  };

  const testConnection = async () => {
    setTesting(true);
    setNotice(null);
    try {
      const result = await api.testDataSource(buildPayload());
      setNotice({ tone: "success", text: result.message });
    } catch (error) {
      setNotice({ tone: "danger", text: (error as Error).message });
    } finally {
      setTesting(false);
    }
  };

  return (
    <main className="min-h-dvh bg-background">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-3 px-4 py-3">
          <Link
            href="/"
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-border text-slate-600 transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            aria-label="返回工作台"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          </Link>
          <div className="min-w-[180px] flex-1">
            <h1 className="text-lg font-semibold text-foreground">数据源配置</h1>
            <p className="text-xs text-slate-500">配置第三方数据中心，后续工具调用会复用这里的连接信息。</p>
          </div>
          <Link
            href="/settings/ai"
            className="inline-flex h-9 items-center rounded-lg border border-border px-3 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary sm:ml-auto"
          >
            AI 配置
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-3xl px-4 py-4">
        <Card>
          <CardHeader
            title="Sorftime MCP"
            subtitle="用于类目趋势、关键词趋势、竞品流量词等实时数据"
            action={<Badge tone={hasSorftimeKey ? "success" : "warning"}>{hasSorftimeKey ? "已配置 Key" : "待配置 Key"}</Badge>}
          />
          <CardBody className="space-y-4">
            <div className="rounded-lg border border-border bg-muted/60 px-3 py-3">
              <div className="flex items-start gap-3">
                <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-100 text-primary">
                  <DatabaseZap className="h-4 w-4" aria-hidden="true" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">当前只接 Sorftime，后续新增数据中心也放在这里。</p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">
                    这里保存的是数据源连接信息；模型 URL、模型名和大模型 Key 仍在 AI 配置页维护。
                  </p>
                </div>
              </div>
            </div>

            <Field label="MCP URL" htmlFor="sorftime-url" helper="默认使用 Sorftime 官方 MCP 地址；如果以后有代理网关，再改成完整地址。">
              <input
                id="sorftime-url"
                value={sorftimeUrl}
                onChange={(event) => setSorftimeUrl(event.target.value)}
                placeholder="https://mcp.sorftime.com"
                className="h-11 w-full rounded-lg border border-border bg-surface px-3 font-mono text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-blue-100"
              />
            </Field>

            <Field label="MCP Key" htmlFor="sorftime-key" helper={`当前：${currentKeyHint}。填入新 Key 后保存会覆盖旧 Key；留空则继续使用已保存 Key。`}>
              <div className="flex gap-2">
                <input
                  id="sorftime-key"
                  value={sorftimeKey}
                  type={showKey ? "text" : "password"}
                  onChange={(event) => {
                    setSorftimeKey(event.target.value);
                    if (event.target.value.trim()) setClearKey(false);
                  }}
                  placeholder="MCP Account-SK"
                  autoComplete="off"
                  className="h-11 min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 font-mono text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-blue-100"
                />
                <Button variant="ghost" onClick={() => setShowKey((value) => !value)} aria-label={showKey ? "隐藏 MCP Key" : "显示 MCP Key"}>
                  {showKey ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                </Button>
              </div>
            </Field>

            {sorftimeStatus?.set ? (
              <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-border px-3 py-2 text-sm text-slate-600 transition-colors hover:bg-muted">
                <input
                  type="checkbox"
                  checked={clearKey}
                  onChange={(event) => {
                    setClearKey(event.target.checked);
                    if (event.target.checked) setSorftimeKey("");
                  }}
                  className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary"
                />
                <span>
                  清除已保存的 Sorftime MCP Key
                  <span className="block text-xs leading-5 text-slate-500">只清除后端本地保存的 Key；如果 `.env` 里配置了 Key，仍会作为兜底生效。</span>
                </span>
              </label>
            ) : null}

            {notice ? (
              <div
                role={notice.tone === "danger" ? "alert" : "status"}
                className={`rounded-lg border px-3 py-2 text-sm ${
                  notice.tone === "success"
                    ? "border-green-200 bg-green-50 text-success"
                    : "border-red-200 bg-red-50 text-destructive"
                }`}
              >
                {notice.text}
              </div>
            ) : null}

            <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
              <Button
                variant="ghost"
                onClick={testConnection}
                disabled={testing || saving || !sorftimeUrl.trim() || !hasSorftimeKey}
              >
                {testing ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <PlugZap className="h-4 w-4" aria-hidden="true" />}
                测试连接
              </Button>
              <Button onClick={save} disabled={saving || testing || !sorftimeUrl.trim()}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Save className="h-4 w-4" aria-hidden="true" />}
                保存数据源
              </Button>
            </div>
          </CardBody>
        </Card>
      </div>
    </main>
  );
}

function Field({
  label,
  htmlFor,
  helper,
  children,
}: {
  label: string;
  htmlFor: string;
  helper?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1 block text-xs font-medium text-slate-600">
        {label}
      </label>
      {children}
      {helper ? <p className="mt-1 text-xs leading-5 text-slate-500">{helper}</p> : null}
    </div>
  );
}
