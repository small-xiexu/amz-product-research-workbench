"use client";

import * as React from "react";
import { Card, CardHeader, CardBody } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import type { CandidateDirection, CandidatePoolArtifact } from "@/lib/types";

function statusTone(status?: string): "success" | "warning" | "danger" | "neutral" {
  if (!status) return "neutral";
  if (status.includes("主线") || status.includes("继续")) return "success";
  if (status.includes("旁支") || status.includes("观察") || status.includes("参考")) return "warning";
  if (status.includes("排除") || status.includes("放弃")) return "danger";
  return "neutral";
}

export function DirectionCards({
  candidatePool,
  disabled = false,
  onChoose,
}: {
  candidatePool: CandidatePoolArtifact | undefined;
  disabled?: boolean;
  onChoose: (text: string) => void;
}) {
  const cards: CandidateDirection[] = candidatePool?.direction_cards || candidatePool?.candidates || [];

  if (!candidatePool) return null;

  return (
    <Card>
      <CardHeader title="候选方向选择台" subtitle="点选你要深挖的主线，决定会发给 AI" />
      <CardBody className="space-y-2.5">
        {cards.length === 0 ? (
          <p className="text-sm text-slate-400">候选池暂无方向卡。</p>
        ) : (
          cards.map((card, i) => {
            const name = card.name || card.label || card.candidate_name || `方向 ${i + 1}`;
            const status = card.status || card.role;
            return (
              <div key={card.direction_id || card.candidate_id || i} className="rounded-lg border border-border p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-semibold text-foreground">{name}</span>
                      {status ? <Badge tone={statusTone(status)}>{status}</Badge> : null}
                    </div>
                    {card.ai_suggestion ? (
                      <p className="mt-1 text-xs text-slate-500">{card.ai_suggestion}</p>
                    ) : null}
                    <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-slate-500">
                      {card.product_count != null ? <span>商品 {card.product_count}</span> : null}
                      {card.monthly_units != null ? <span>月销 {card.monthly_units}</span> : null}
                      {card.representative_asin ? (
                        <span className="font-mono">{card.representative_asin}</span>
                      ) : null}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={disabled}
                    onClick={() => onChoose(`我选择深挖这个方向：${name}。请基于它继续推进。`)}
                  >
                    {disabled ? "处理中" : "深挖"}
                  </Button>
                </div>
              </div>
            );
          })
        )}
      </CardBody>
    </Card>
  );
}

const DECISIONS: { label: string; tone: "primary" | "accent" | "danger"; text: string }[] = [
  { label: "Go · 推进", tone: "primary", text: "我倾向 Go，请给出推进所需的下一步动作和待补项。" },
  { label: "Wait · 观察", tone: "accent", text: "我倾向 Wait，请说明还需要补哪些证据才能下结论。" },
  { label: "No-Go · 放弃", tone: "danger", text: "我倾向 No-Go，请总结放弃理由并归档。" },
];

export function DecisionBar({ disabled = false, onDecide }: { disabled?: boolean; onDecide: (text: string) => void }) {
  return (
    <Card>
      <CardHeader title="决策" subtitle="利润/合规未回填时只能 Wait" />
      <CardBody>
        <div className="grid grid-cols-3 gap-2">
          {DECISIONS.map((d) => (
            <Button key={d.label} size="sm" variant={d.tone} disabled={disabled} onClick={() => onDecide(d.text)}>
              {d.label}
            </Button>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}
