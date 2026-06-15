import * as React from "react";

type Tone = "neutral" | "primary" | "success" | "warning" | "danger" | "accent";

const tones: Record<Tone, string> = {
  neutral: "bg-muted text-slate-600",
  primary: "bg-blue-100 text-primary",
  success: "bg-green-100 text-success",
  warning: "bg-amber-100 text-warning",
  danger: "bg-red-100 text-destructive",
  accent: "bg-orange-100 text-accent",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}
