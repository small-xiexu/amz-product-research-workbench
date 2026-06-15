"use client";

import * as React from "react";
import { Card, CardHeader, CardBody } from "./ui/card";
import { Badge } from "./ui/badge";
import type { ArtifactMap } from "@/lib/types";

export function ArtifactPreview({ artifacts }: { artifacts: ArtifactMap }) {
  const pool = artifacts.candidate_pool;
  const manifest = artifacts.manifest;
  if (!pool && !manifest) return null;

  return (
    <Card>
      <CardHeader title="数据产出" subtitle="盘点与候选池摘要" />
      <CardBody className="space-y-3 text-sm">
        {manifest ? (
          <div>
            <div className="mb-1 text-xs font-medium text-slate-500">数据盘点</div>
            <div className="flex flex-wrap gap-1.5">
              {(manifest.available_sources || []).map((s) => (
                <Badge key={s} tone="primary">
                  {s}
                </Badge>
              ))}
              {(manifest.missing_sources || []).map((s) => (
                <Badge key={s} tone="warning">
                  缺 {s}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}

        {pool ? (
          <div className="grid grid-cols-2 gap-2">
            <Stat label="候选数" value={(pool.candidates || []).length} />
            <Stat label="方向卡" value={(pool.direction_cards || []).length} />
            <Stat label="建议VOC ASIN" value={(pool.next_review_voc_asins || []).length} />
            <Stat label="Pool ID" value={pool.metadata?.pool_id ? "已生成" : "—"} />
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg bg-muted px-3 py-2">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-0.5 font-mono text-sm font-semibold text-foreground">{value}</div>
    </div>
  );
}
