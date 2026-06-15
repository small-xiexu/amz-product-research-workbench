export const SITE_OPTIONS = [
  { value: "US", label: "美国", domain: "Amazon.com" },
  { value: "CA", label: "加拿大", domain: "Amazon.ca" },
  { value: "MX", label: "墨西哥", domain: "Amazon.com.mx" },
] as const;

export type SiteCode = (typeof SITE_OPTIONS)[number]["value"];

const SITE_VALUES = new Set<string>(SITE_OPTIONS.map((site) => site.value));

export function normalizeSite(value: string | null | undefined): SiteCode {
  const normalized = String(value || "US").trim().toUpperCase();
  return SITE_VALUES.has(normalized) ? (normalized as SiteCode) : "US";
}
