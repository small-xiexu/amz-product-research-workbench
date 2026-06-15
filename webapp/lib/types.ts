export type Mode = "mode_pending" | "broad_discovery" | "targeted_deep_dive";

export interface ToolRun {
  call_id: string;
  name: string;
  arguments: Record<string, unknown>;
  result: unknown;
  ok: boolean;
  error: string | null;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  tool_runs: ToolRun[];
  steps: number;
  stopped_reason: string;
  artifacts_keys: string[];
}

export interface SessionState {
  session_id: string;
  mode: Mode;
  intent: string;
  site: string;
  messages: ChatMessage[];
  workflow_state: Record<string, unknown> | null;
  artifacts: ArtifactMap;
}

export interface ChatMessage {
  role: "user" | "assistant" | "tool";
  content: string;
  tool_calls?: { id: string; name: string; arguments: Record<string, unknown> }[];
  tool_call_id?: string;
  name?: string;
}

export interface ArtifactManifest {
  available_sources?: string[];
  missing_sources?: string[];
}

export interface CandidatePoolArtifact {
  metadata?: { pool_id?: string };
  direction_cards?: CandidateDirection[];
  candidates?: CandidateDirection[];
  next_review_voc_asins?: string[];
}

export type ArtifactMap = {
  manifest?: ArtifactManifest;
  candidate_pool?: CandidatePoolArtifact;
  uploaded_files?: string[];
  upload_folder?: string;
  [key: string]: unknown;
};

export interface AppConfig {
  provider: string;
  model: string;
  anthropic_base_url?: string;
  openai_base_url?: string;
  sorftime_mcp_url?: string;
  anthropic_key_set: boolean;
  openai_key_set: boolean;
  sorftime_key_set?: boolean;
  available_providers: string[];
  available_models?: Record<string, string[]>;
  keys?: Record<string, { set: boolean; source?: string | null; hint?: string | null }>;
}

export interface CandidateDirection {
  direction_id?: string;
  candidate_id?: string;
  name?: string;
  label?: string;
  candidate_name?: string;
  role?: string;
  status?: string;
  product_count?: number;
  monthly_units?: number;
  representative_asin?: string;
  ai_suggestion?: string;
}

export type StreamEvent =
  | { type: "text"; delta: string }
  | { type: "tool_start"; name: string; call_id: string; arguments: Record<string, unknown> }
  | { type: "tool_result"; name: string; call_id: string; ok: boolean; result: unknown; error: string | null }
  | { type: "done"; stopped_reason: string; steps: number; final_text: string }
  | { type: "session"; artifacts_keys: string[] }
  | { type: "error"; message: string };
