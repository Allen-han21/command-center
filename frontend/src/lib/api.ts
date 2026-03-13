const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Jobs ──

export interface Job {
  id: string;
  title: string;
  prompt: string;
  work_dir: string;
  status: "queued" | "scheduled" | "running" | "completed" | "failed" | "cancelled";
  blocked_by: string[];
  priority: number;
  time_slot: "sleep" | "lunch" | "commute" | "anytime";
  scheduled_at: string | null;
  max_budget: number;
  timeout_min: number;
  model: "sonnet" | "opus" | "haiku";
  effort: "low" | "medium" | "high" | "max";
  use_worktree: boolean;
  session_id: string | null;
  pid: number | null;
  result_summary: string | null;
  output_path: string | null;
  error_message: string | null;
  retry_count: number;
  max_retries: number;
  jira_ticket: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface JobCreate {
  title: string;
  prompt: string;
  work_dir?: string;
  priority?: number;
  time_slot?: Job["time_slot"];
  max_budget?: number;
  timeout_min?: number;
  model?: Job["model"];
  effort?: Job["effort"];
  blocked_by?: string[];
  jira_ticket?: string;
  max_retries?: number;
}

export const jobs = {
  list: (status?: string) =>
    request<Job[]>(`/jobs${status ? `?status=${status}` : ""}`),
  get: (id: string) => request<Job>(`/jobs/${id}`),
  create: (data: JobCreate) =>
    request<Job>("/jobs", { method: "POST", body: JSON.stringify(data) }),
  cancel: (id: string) =>
    request<Job>(`/jobs/${id}/cancel`, { method: "POST" }),
  retry: (id: string) =>
    request<Job>(`/jobs/${id}/retry`, { method: "POST" }),
  delete: (id: string) =>
    request<void>(`/jobs/${id}`, { method: "DELETE" }),
};

// ── Dashboard ──

export interface DashboardSummary {
  running_jobs: number;
  queued_jobs: number;
  today_spent_usd: number;
  today_limit_usd: number;
  today_job_count: number;
  next_slot: string | null;
  recent_completed: { id: string; title: string; completed_at: string | null }[];
  failed_jobs: { id: string; title: string; error_message: string | null }[];
}

export const dashboard = {
  get: () => request<DashboardSummary>("/dashboard"),
};

// ── Time Slots ──

export interface TimeSlot {
  name: string;
  start_time: string | null;
  end_time: string | null;
  max_concurrent: number;
  enabled: boolean;
  days: string[];
}

export const timeSlots = {
  list: () => request<TimeSlot[]>("/time-slots"),
  update: (name: string, data: Partial<TimeSlot>) =>
    request<TimeSlot>(`/time-slots/${name}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
};

// ── Budget ──

export interface Budget {
  date: string;
  limit_usd: number;
  spent_usd: number;
  job_count: number;
  remaining_usd: number;
}

export const budget = {
  get: () => request<Budget>("/budget/today"),
  update: (limit_usd: number) =>
    request<Budget>("/budget/today", {
      method: "PUT",
      body: JSON.stringify({ limit_usd }),
    }),
};
