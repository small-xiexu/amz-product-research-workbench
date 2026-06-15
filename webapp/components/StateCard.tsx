"use client";

import * as React from "react";
import { Card, CardHeader, CardBody } from "./ui/card";
import { Badge } from "./ui/badge";
import { SITE_OPTIONS, normalizeSite } from "@/lib/sites";
import type { SessionState } from "@/lib/types";

const MODE_LABEL: Record<string, string> = {
  mode_pending: "待选择模式",
  broad_discovery: "无方向探索",
  targeted_deep_dive: "指定方向深挖",
};

// 基于产出物推断流程进度（轻量，不强绑后端阶段机）
const STEPS = [
  { key: "upload_folder", label: "上传导出" },
  { key: "manifest", label: "数据盘点" },
  { key: "candidate_pool", label: "候选池" },
  { key: "research_package", label: "深挖包" },
  { key: "report", label: "报告" },
];

export function StateCard({
  session,
  siteDraft,
  siteBusy = false,
  onSiteDraftChange,
  onSiteSave,
}: {
  session: SessionState;
  siteDraft: string;
  siteBusy?: boolean;
  onSiteDraftChange: (site: string) => void;
  onSiteSave: (site?: string) => void;
}) {
  const artifacts = session.artifacts || {};
  const normalizedDraft = normalizeSite(siteDraft);
  const siteChanged = normalizedDraft !== session.site;
  return (
    <Card>
      <CardHeader
        title="当前会话"
        subtitle={session.intent || (session.mode === "mode_pending" ? "先和 AI 对齐本轮选品方式" : "未填写意图")}
        action={<Badge tone={session.mode === "mode_pending" ? "warning" : "primary"}>{MODE_LABEL[session.mode] || session.mode}</Badge>}
      />
      <CardBody>
        <div className="mb-3 space-y-3">
          <div className="text-xs text-slate-500">
            会话 <span className="font-mono text-foreground">{session.session_id}</span>
          </div>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-600">站点</span>
            <select
              value={normalizedDraft}
              disabled={siteBusy}
              onChange={(event) => {
                const nextSite = event.target.value;
                onSiteDraftChange(nextSite);
                onSiteSave(nextSite);
              }}
              className="h-10 w-full cursor-pointer rounded-lg border border-border bg-surface px-3 text-sm font-medium text-foreground transition-colors duration-150 focus:border-primary focus:outline-none focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
              aria-label="站点"
            >
              {SITE_OPTIONS.map((site) => (
                <option key={site.value} value={site.value}>
                  {site.label}（{site.value}）
                </option>
              ))}
            </select>
            <span className="mt-1 block text-[11px] text-slate-400">
              {siteBusy ? "站点保存中..." : siteChanged ? "已选择，正在同步会话站点。" : "当前只支持北美三站。"}
            </span>
          </label>
        </div>

        <ol className="flex items-center">
          {STEPS.map((step, i) => {
            const done = Boolean(artifacts[step.key]);
            return (
              <React.Fragment key={step.key}>
                <li className="flex flex-col items-center">
                  <span
                    className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
                      done ? "bg-primary text-primary-fg" : "bg-muted text-slate-400"
                    }`}
                  >
                    {i + 1}
                  </span>
                  <span className={`mt-1 text-[11px] ${done ? "text-foreground" : "text-slate-400"}`}>
                    {step.label}
                  </span>
                </li>
                {i < STEPS.length - 1 ? (
                  <span
                    className={`mx-1 mb-4 h-0.5 flex-1 ${
                      artifacts[STEPS[i + 1].key] ? "bg-primary" : "bg-border"
                    }`}
                  />
                ) : null}
              </React.Fragment>
            );
          })}
        </ol>
      </CardBody>
    </Card>
  );
}
