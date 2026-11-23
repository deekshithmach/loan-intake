// Typed client for the FastAPI backend (apps/api/main.py).
// 127.0.0.1, not localhost: on Windows the browser tries IPv6 ::1 first and uvicorn (IPv4) costs ~2s per connection.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type DocType = "paystub" | "w2" | "statement" | "unknown";
export type Status = "processing" | "in_review" | "approved" | "rejected" | "failed";
export type Severity = "low" | "medium" | "high";

export interface Usage {
  calls: number;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  cost_usd: number;
}

export interface Extraction {
  file: string;
  doc_type: DocType;
  scanned: boolean;
  classified_by: string;
  ok: boolean;
  data: Record<string, unknown> | null;
  error: string | null;
  attempts: number;
  usage: Usage;
}

export interface Evidence {
  doc: string;
  field: string;
  value: unknown;
  note: string;
}

export interface Flag {
  code: string;
  severity: Severity;
  message: string;
  evidence: Evidence[];
  decision?: "accept" | "dismiss";
}

export interface AppSummary {
  id: string;
  status: Status;
  applicant_name: string | null;
  model: string | null;
  flag_count: number;
  created_at: string;
  updated_at: string;
  profile: Record<string, unknown> | null;
}

export interface ModelInfo {
  id: string;
  label: string;
  provider: string;
  free: boolean;
  available: boolean;
  default: boolean;
}

/** One row per model on the Model stats tab. Fields the backend has not computed yet are null. */
export interface ModelStats {
  model: string;
  runs: number;
  avg_latency_s: number;
  avg_cost_usd: number;
  avg_tokens: number;
  p50_latency_s: number | null;
  p95_latency_s: number | null;
  extraction_success_rate: number | null;
  reviewed: number | null;
  edits_per_review: number | null;
  flag_dismissal_rate: number | null;
  approval_rate: number | null;
}

export interface AppDetail extends AppSummary {
  awaiting_review: boolean;
  extractions: Record<string, Extraction>;
  flags: Flag[];
}

export interface AuditEvent {
  id: number;
  ts: string;
  actor: string;
  action: string;
  detail: Record<string, unknown>;
}

export interface ReviewBody {
  decision: "approve" | "reject";
  reviewer: string;
  edits: Record<string, Record<string, string | number>>;
  flag_decisions: Record<string, "accept" | "dismiss">;
  notes: string;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(API_URL + path, { cache: "no-store", ...init });
  } catch {
    throw new Error(`Can't reach the API at ${API_URL}. Is it running?`);
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {}
    throw new Error(msg || `Request failed (${res.status})`);
  }
  return res.json();
}

export const api = {
  list: (status?: string) => req<AppSummary[]>(status ? `/applications?status=${status}` : "/applications"),
  get: (id: string) => req<AppDetail>(`/applications/${id}`),
  audit: (id: string) => req<AuditEvent[]>(`/applications/${id}/audit`),
  models: () => req<ModelInfo[]>("/models"),
  stats: () => req<{ models: ModelStats[] }>("/stats"),
  upload: (files: File[], model?: string) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    if (model) form.append("model", model);
    return req<{ id: string; status: Status }>("/applications", { method: "POST", body: form });
  },
  review: (id: string, body: ReviewBody) =>
    req<AppDetail>(`/applications/${id}/review`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }),
  fileUrl: (id: string, file: string) => `${API_URL}/applications/${id}/files/${baseName(file)}`,
};

export function baseName(path: string): string {
  return path.split(/[\\/]/).pop() ?? path;
}
