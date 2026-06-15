import { DataSourcesPanel } from "@/components/DataSourcesPanel";
import type { AppConfig } from "@/lib/types";

async function loadConfig(): Promise<AppConfig | null> {
  try {
    const backend = process.env.BACKEND_URL || "http://localhost:8000";
    const response = await fetch(`${backend}/api/config`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as AppConfig;
  } catch {
    return null;
  }
}

export default async function DataSourcesSettingsPage() {
  const config = await loadConfig();
  return <DataSourcesPanel initialConfig={config} />;
}
