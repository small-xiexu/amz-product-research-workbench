"use client";

import * as React from "react";
import { Card, CardHeader, CardBody } from "./ui/card";
import { Badge } from "./ui/badge";
import { api } from "@/lib/api";

export function FileUploadCard({
  sessionId,
  uploadedFiles,
  disabled = false,
  onUploaded,
}: {
  sessionId: string;
  uploadedFiles: string[];
  disabled?: boolean;
  onUploaded: (summary: { upload_folder: string; saved: string[]; total: number }) => void | Promise<void>;
}) {
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const summary = await api.upload(sessionId, files);
      await onUploaded(summary);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <Card>
      <CardHeader title="卖家精灵 / 评论导出" subtitle="上传后告诉 AI，由它盘点数据" />
      <CardBody>
        <label
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (busy || disabled) return;
            handleFiles(e.dataTransfer.files);
          }}
          className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-border bg-muted/40 px-4 py-6 text-center transition-colors ${
            busy || disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:border-secondary"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".xlsx,.xls,.csv,.tsv,.html,.htm"
            disabled={busy || disabled}
            className="sr-only"
            onChange={(e) => handleFiles(e.target.files)}
          />
          <span className="text-sm font-medium text-foreground">
            {busy ? "上传并触发 AI 盘点中..." : disabled ? "AI 正在处理，稍后再上传" : "点击或拖拽上传"}
          </span>
          <span className="mt-1 text-xs text-slate-500">支持 .xlsx / .xls / .csv / .tsv / .html，可多选</span>
        </label>

        {error ? <p className="mt-2 text-xs text-destructive" role="alert">{error}</p> : null}

        {uploadedFiles.length > 0 ? (
          <div className="mt-3">
            <div className="mb-1.5 flex items-center gap-2">
              <Badge tone="success">已上传 {uploadedFiles.length}</Badge>
            </div>
            <ul className="space-y-1">
              {uploadedFiles.map((f) => (
                <li key={f} className="truncate font-mono text-xs text-slate-600">
                  {f}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}
