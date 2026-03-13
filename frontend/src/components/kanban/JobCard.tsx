import { useMutation, useQueryClient } from "@tanstack/react-query";
import { jobs as jobsApi, type Job } from "../../lib/api";

const SLOT_COLORS: Record<string, string> = {
  sleep: "#818cf8",
  lunch: "#fbbf24",
  commute: "#fb923c",
  anytime: "#94a3b8",
};

const MODEL_LABELS: Record<string, string> = {
  sonnet: "S",
  opus: "O",
  haiku: "H",
};

export function JobCard({ job }: { job: Job }) {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
  };

  const cancelMut = useMutation({ mutationFn: () => jobsApi.cancel(job.id), onSuccess: invalidate });
  const retryMut = useMutation({ mutationFn: () => jobsApi.retry(job.id), onSuccess: invalidate });

  const elapsed = job.started_at
    ? Math.round((Date.now() - new Date(job.started_at).getTime()) / 60000)
    : null;

  return (
    <div className="rounded-lg bg-[var(--color-bg)] p-3 border border-[var(--color-border)] hover:border-[var(--color-surface-hover)] transition-colors group">
      {/* Title + priority */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="text-sm font-medium leading-snug line-clamp-2">{job.title}</span>
        <span className="shrink-0 text-[10px] text-[var(--color-text-muted)] bg-[var(--color-surface)] px-1.5 py-0.5 rounded">
          P{job.priority}
        </span>
      </div>

      {/* Badges */}
      <div className="flex flex-wrap gap-1.5 mb-2">
        <Badge color={SLOT_COLORS[job.time_slot]}>{job.time_slot}</Badge>
        <Badge color="#64748b">{MODEL_LABELS[job.model] ?? job.model}</Badge>
        <Badge color="#64748b">${job.max_budget.toFixed(1)}</Badge>
        {job.jira_ticket && <Badge color="#a78bfa">{job.jira_ticket}</Badge>}
      </div>

      {/* Running indicator */}
      {job.status === "running" && elapsed !== null && (
        <div className="flex items-center gap-1.5 mb-2">
          <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          <span className="text-xs text-green-400">{elapsed}m elapsed</span>
        </div>
      )}

      {/* Error message */}
      {job.error_message && (
        <p className="text-xs text-red-400 mb-2 line-clamp-2">{job.error_message}</p>
      )}

      {/* Actions */}
      <div className="flex gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
        {(job.status === "queued" || job.status === "scheduled") && (
          <ActionBtn onClick={() => cancelMut.mutate()} disabled={cancelMut.isPending}>
            Cancel
          </ActionBtn>
        )}
        {(job.status === "failed" || job.status === "cancelled") &&
          job.retry_count < job.max_retries && (
            <ActionBtn onClick={() => retryMut.mutate()} disabled={retryMut.isPending}>
              Retry ({job.retry_count}/{job.max_retries})
            </ActionBtn>
          )}
      </div>

      {/* Footer: id + time */}
      <div className="flex items-center justify-between mt-2 text-[10px] text-[var(--color-text-muted)]">
        <span className="font-mono">{job.id.slice(0, 8)}</span>
        <span>{formatTime(job.completed_at ?? job.started_at ?? job.created_at)}</span>
      </div>
    </div>
  );
}

function Badge({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span
      className="text-[10px] px-1.5 py-0.5 rounded font-medium"
      style={{ backgroundColor: `${color}22`, color }}
    >
      {children}
    </span>
  );
}

function ActionBtn({
  onClick,
  disabled,
  children,
}: {
  onClick: () => void;
  disabled: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="text-[10px] px-2 py-1 rounded bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] disabled:opacity-50 transition-colors"
    >
      {children}
    </button>
  );
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
}
