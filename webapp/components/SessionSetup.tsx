"use client";

import * as React from "react";
import { Compass, Crosshair } from "lucide-react";
import { Button } from "./ui/button";
import { Card, CardBody, CardHeader } from "./ui/card";
import { normalizeSite } from "@/lib/sites";
import type { Mode } from "@/lib/types";

const MODE_OPTIONS: {
  id: Exclude<Mode, "mode_pending">;
  title: string;
  desc: string;
  icon: React.ComponentType<{ className?: string }>;
}[] = [
  {
    id: "targeted_deep_dive",
    title: "指定方向深挖",
    desc: "已经有一个产品方向，AI 先帮你确认边界、拆关键词，再决定要不要调 MCP 或导出卖家精灵数据。",
    icon: Crosshair,
  },
  {
    id: "broad_discovery",
    title: "无方向探索",
    desc: "只有大概品类或模糊想法，AI 先帮你收敛 3-5 个候选方向，再让运营选择主线继续深挖。",
    icon: Compass,
  },
];

export function SessionSetup({
  busy,
  compact = false,
  initialIntent = "",
  site,
  onStart,
}: {
  busy: boolean;
  compact?: boolean;
  initialIntent?: string;
  site: string;
  onStart: (payload: { mode: Exclude<Mode, "mode_pending">; intent: string; site: string }) => void;
}) {
  const [mode, setMode] = React.useState<Exclude<Mode, "mode_pending">>("targeted_deep_dive");
  const intent = initialIntent.trim();

  const submit = () => {
    onStart({ mode, intent, site: normalizeSite(site) });
  };

  return (
    <Card className={compact ? "w-full" : "mx-auto w-full max-w-3xl"}>
      <CardHeader
        title="先和 AI 对齐本轮怎么走"
        subtitle="先确认站点和模式；右侧输入的想法会先作为本轮草稿，确认后再进入正式对话。"
      />
      <CardBody className="space-y-4">
        <div className="rounded-lg border border-border bg-muted/35 px-3 py-2.5">
          <span className="block text-xs font-medium text-slate-500">本轮选品草稿</span>
          <p className={`mt-1 text-sm leading-5 ${intent ? "text-foreground" : "text-slate-400"}`}>
            {intent || "还没有输入。可以在右侧主输入框先写一句选品想法。"}
          </p>
        </div>

        <div className={`grid gap-3 ${compact ? "" : "md:grid-cols-2"}`}>
          {MODE_OPTIONS.map((option) => {
            const Icon = option.icon;
            const selected = option.id === mode;
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => setMode(option.id)}
                className={`${compact ? "min-h-[112px] p-3" : "min-h-[124px] p-4"} cursor-pointer rounded-lg border text-left transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary focus-visible:ring-offset-2 ${
                  selected ? "border-primary bg-blue-50" : "border-border bg-surface hover:border-secondary hover:bg-muted/40"
                }`}
                aria-pressed={selected}
              >
                <span className="flex items-center gap-2">
                  <span
                    className={`inline-flex h-9 w-9 items-center justify-center rounded-lg ${
                      selected ? "bg-primary text-primary-fg" : "bg-muted text-primary"
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="text-sm font-semibold text-foreground">{option.title}</span>
                </span>
                <span className="mt-3 block text-xs leading-5 text-slate-600">{option.desc}</span>
              </button>
            );
          })}
        </div>

        <Button className="h-11 w-full" disabled={busy} onClick={submit}>
          {busy ? "启动中..." : "让 AI 开始带"}
        </Button>
      </CardBody>
    </Card>
  );
}
