"use client";

import * as React from "react";
import { ArrowLeft, Eye, EyeOff, Loader2, PlugZap, Save } from "lucide-react";
import Link from "next/link";
import { api, type ConfigUpdatePayload } from "@/lib/api";
import type { AppConfig } from "@/lib/types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardBody, CardHeader } from "./ui/card";

const DEFAULT_MODELS: Record<string, string> = {
  anthropic: "claude-sonnet-4-20250514",
  openai: "gpt-4o",
};

type Notice = { tone: "success" | "danger"; text: string };

export function AiConfigPanel({ initialConfig }: { initialConfig: AppConfig | null }) {
  const [config, setConfig] = React.useState<AppConfig | null>(initialConfig);
  const [provider, setProvider] = React.useState(initialConfig?.provider || "anthropic");
  const [model, setModel] = React.useState(initialConfig?.model || DEFAULT_MODELS.anthropic);
  const [baseUrls, setBaseUrls] = React.useState<Record<string, string>>({
    anthropic: initialConfig?.anthropic_base_url || "",
    openai: initialConfig?.openai_base_url || "",
  });
  const [apiKey, setApiKey] = React.useState("");
  const [showKey, setShowKey] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [testing, setTesting] = React.useState(false);
  const [notice, setNotice] = React.useState<Notice | null>(null);

  const providerKey = provider === "anthropic" ? config?.keys?.anthropic : config?.keys?.openai;
  const hasKey = Boolean(apiKey.trim() || providerKey?.set);
  const currentKeyHint = providerKey?.set ? providerKey.hint : "未配置";
  const baseUrl = baseUrls[provider] || "";
  const hasBaseUrl = Boolean(baseUrl.trim());
  const baseUrlPlaceholder =
    provider === "anthropic" ? "https://your-claude-gateway.example" : "http://localhost:8888";
  const baseUrlHelper =
    provider === "openai"
      ? "填写你的兼容网关地址；没写 /v1 也可以，系统会自动补上。"
      : "填写你的兼容网关地址；Claude 会按这里的 URL 调用。";
  const statusText = hasKey && hasBaseUrl ? "已可测试" : hasBaseUrl ? "待配置 Key" : "待配置 URL";

  const buildPayload = (): ConfigUpdatePayload => ({
    provider,
    model: model.trim(),
    anthropic_base_url: (baseUrls.anthropic || "").trim(),
    openai_base_url: (baseUrls.openai || "").trim(),
    anthropic_api_key: provider === "anthropic" ? apiKey.trim() || undefined : undefined,
    openai_api_key: provider === "openai" ? apiKey.trim() || undefined : undefined,
    sorftime_mcp_url: config?.sorftime_mcp_url || "https://mcp.sorftime.com",
  });

  const updateBaseUrl = (value: string) => {
    setBaseUrls((current) => ({ ...current, [provider]: value }));
  };

  const onProviderChange = (nextProvider: string) => {
    setProvider(nextProvider);
    setModel(DEFAULT_MODELS[nextProvider] || "");
    setApiKey("");
    setNotice(null);
  };

  const save = async () => {
    setSaving(true);
    setNotice(null);
    try {
      const next = await api.setConfig(buildPayload());
      setConfig(next);
      setBaseUrls({
        anthropic: next.anthropic_base_url || "",
        openai: next.openai_base_url || "",
      });
      setApiKey("");
      setNotice({ tone: "success", text: "配置已保存。" });
    } catch (error) {
      setNotice({ tone: "danger", text: (error as Error).message });
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    setTesting(true);
    setNotice(null);
    try {
      const result = await api.testConfig(buildPayload());
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
            <h1 className="text-lg font-semibold text-foreground">AI 配置</h1>
            <p className="text-xs text-slate-500">配置模型接口，测试能不能正常调用。</p>
          </div>
          <Link
            href="/settings/data-sources"
            className="inline-flex h-9 items-center rounded-lg border border-border px-3 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary sm:ml-auto"
          >
            数据源配置
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-3xl px-4 py-4">
        <Card>
          <CardHeader
            title="模型连接配置"
            subtitle="只需要接口类型、URL、API Key 和模型名称"
            action={<Badge tone={hasKey && hasBaseUrl ? "success" : "warning"}>{statusText}</Badge>}
          />
          <CardBody className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="接口类型" htmlFor="provider">
                <select
                  id="provider"
                  value={provider}
                  onChange={(event) => onProviderChange(event.target.value)}
                  className="h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-blue-100"
                >
                  <option value="anthropic">Claude / Anthropic 兼容接口</option>
                  <option value="openai">OpenAI / GPT 兼容接口</option>
                </select>
              </Field>

              <Field label="模型名称" htmlFor="model">
                <input
                  id="model"
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  placeholder={provider === "anthropic" ? "claude-sonnet-4-20250514" : "gpt-4o"}
                  className="h-11 w-full rounded-lg border border-border bg-surface px-3 font-mono text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-blue-100"
                />
              </Field>
            </div>

            <Field label="接口地址 URL" htmlFor="base-url" helper={baseUrlHelper}>
              <input
                id="base-url"
                value={baseUrl}
                onChange={(event) => updateBaseUrl(event.target.value)}
                placeholder={baseUrlPlaceholder}
                className="h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-blue-100"
              />
            </Field>

            <Field label="API Key" htmlFor="api-key" helper={`当前：${currentKeyHint}。填入新 Key 后保存会覆盖旧 Key；留空则继续使用已保存 Key。`}>
              <div className="flex gap-2">
                <input
                  id="api-key"
                  value={apiKey}
                  type={showKey ? "text" : "password"}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder="输入 API Key"
                  autoComplete="off"
                  className="h-11 min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 font-mono text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-blue-100"
                />
                <Button variant="ghost" onClick={() => setShowKey((value) => !value)} aria-label={showKey ? "隐藏 API Key" : "显示 API Key"}>
                  {showKey ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                </Button>
              </div>
            </Field>

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
              <Button variant="ghost" onClick={test} disabled={testing || saving || !model.trim() || !hasBaseUrl || !hasKey}>
                {testing ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <PlugZap className="h-4 w-4" aria-hidden="true" />}
                测试连接
              </Button>
              <Button onClick={save} disabled={saving || testing || !model.trim() || !hasBaseUrl}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Save className="h-4 w-4" aria-hidden="true" />}
                保存配置
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
