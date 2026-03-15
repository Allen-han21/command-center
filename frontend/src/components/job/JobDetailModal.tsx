import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { jobs as jobsApi, type Job, type JobOutputLine } from "../../lib/api";

const STATUS_COLORS: Record<string, string> = {
  queued: "var(--color-queued)",
  scheduled: "var(--color-scheduled)",
  running: "var(--color-running)",
  completed: "var(--color-completed)",
  failed: "var(--color-failed)",
  cancelled: "#94a3b8",
};

const LINE_COLORS: Record<string, { bg: string; text: string }> = {
  assistant: { bg: "#3b82f622", text: "#60a5fa" },
  tool_use: { bg: "#eab30822", text: "#fbbf24" },
  tool_result: { bg: "#10b98122", text: "#34d399" },
  result: { bg: "#22c55e22", text: "#4ade80" },
  raw: { bg: "#64748b22", text: "#94a3b8" },
};

interface Props {
  job: Job;
  onClose: () => void;
  onContinue: () => void;
}

export function JobDetailModal({ job, onClose, onContinue }: Props) {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
  };

  const hasOutput = job.status === "completed" || job.status === "failed";
  const { data: output } = useQuery({
    queryKey: ["job-output", job.id],
    queryFn: () => jobsApi.getOutput(job.id),
    enabled: hasOutput,
  });

  const cancelMut = useMutation({
    mutationFn: () => jobsApi.cancel(job.id),
    onSuccess: () => { invalidate(); onClose(); },
  });
  const retryMut = useMutation({
    mutationFn: () => jobsApi.retry(job.id),
    onSuccess: () => { invalidate(); onClose(); },
  });

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-[var(--color-surface)] rounded-xl w-full max-w-2xl p-6 mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-center gap-2 min-w-0">
            <h2 className="text-lg font-semibold truncate">{job.title}</h2>
            <span
              className="shrink-0 text-[10px] px-2 py-0.5 rounded font-medium text-white"
              style={{ backgroundColor: STATUS_COLORS[job.status] }}
            >
              {job.status}
            </span>
          </div>
          <button onClick={onClose} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] text-xl leading-none">&times;</button>
        </div>

        {/* Metadata grid */}
        <div className="grid grid-cols-3 gap-x-4 gap-y-2 text-xs mb-4">
          <CopyMeta label="ID" value={job.id} />
          <Meta label="Priority" value={`P${job.priority}`} />
          <Meta label="Model" value={job.model} />
          <Meta label="Effort" value={job.effort} />
          <Meta label="Time Slot" value={job.time_slot} />
          <Meta label="Budget" value={`$${job.max_budget.toFixed(1)}`} />
          <Meta label="Timeout" value={`${job.timeout_min}min`} />
          <Meta label="Work Dir" value={job.work_dir} mono />
          <Meta label="Retries" value={`${job.retry_count}/${job.max_retries}`} />
          {job.jira_ticket && <Meta label="JIRA" value={job.jira_ticket} />}
          {job.session_id && <CopyMeta label="Session" value={job.session_id} />}
          {job.parent_job_id && <CopyMeta label="Parent Job" value={job.parent_job_id} />}
          <Meta label="Created" value={formatDT(job.created_at)} />
          {job.started_at && <Meta label="Started" value={formatDT(job.started_at)} />}
          {job.completed_at && <Meta label="Completed" value={formatDT(job.completed_at)} />}
        </div>

        <Divider />

        {/* Prompt */}
        <Section title="Prompt">
          <pre className="text-xs text-[var(--color-text-muted)] whitespace-pre-wrap max-h-40 overflow-y-auto bg-[var(--color-bg)] rounded p-3">
            {job.prompt}
          </pre>
        </Section>

        {/* Result Summary */}
        {job.result_summary && (
          <>
            <Divider />
            <Section title="Result">
              <pre className="text-xs whitespace-pre-wrap max-h-40 overflow-y-auto bg-[var(--color-bg)] rounded p-3 text-green-400">
                {job.result_summary}
              </pre>
            </Section>
          </>
        )}

        {/* Error */}
        {job.error_message && (
          <>
            <Divider />
            <Section title="Error">
              <pre className="text-xs whitespace-pre-wrap bg-red-950/30 rounded p-3 text-red-400">
                {job.error_message}
              </pre>
            </Section>
          </>
        )}

        {/* Output Lines */}
        {hasOutput && output && output.lines.length > 0 && (
          <>
            <Divider />
            <Section title={`Output (${output.lines.length} of ${output.total} lines)`}>
              <div className="max-h-60 overflow-y-auto rounded bg-[var(--color-bg)] p-2 space-y-0.5">
                {output.lines.map((line) => (
                  <OutputLine key={line.index} line={line} />
                ))}
              </div>
            </Section>
          </>
        )}

        {/* Footer Actions */}
        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-lg bg-[var(--color-bg)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors text-sm"
          >
            Close
          </button>
          {(job.status === "queued" || job.status === "scheduled") && (
            <button
              onClick={() => cancelMut.mutate()}
              disabled={cancelMut.isPending}
              className="flex-1 py-2 rounded-lg bg-red-600/20 text-red-400 hover:bg-red-600/30 disabled:opacity-50 text-sm font-medium transition-colors"
            >
              Cancel
            </button>
          )}
          {(job.status === "failed" || job.status === "cancelled") && job.retry_count < job.max_retries && (
            <button
              onClick={() => retryMut.mutate()}
              disabled={retryMut.isPending}
              className="flex-1 py-2 rounded-lg bg-amber-600/20 text-amber-400 hover:bg-amber-600/30 disabled:opacity-50 text-sm font-medium transition-colors"
            >
              Retry
            </button>
          )}
          {job.status === "completed" && (
            <button
              onClick={onContinue}
              className="flex-1 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors"
            >
              Continue &rarr;
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Meta({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <span className="text-[var(--color-text-muted)]">{label}</span>
      <span className={`ml-1.5 text-[var(--color-text)] ${mono ? "font-mono" : ""}`}>{value}</span>
    </div>
  );
}

function CopyMeta({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="col-span-3">
      <span className="text-[var(--color-text-muted)]">{label}</span>
      <button
        onClick={handleCopy}
        className="ml-1.5 font-mono text-[var(--color-text)] hover:text-indigo-400 transition-colors cursor-pointer bg-transparent border-none p-0 text-xs"
        title="Click to copy"
      >
        {value}
        <span className="ml-1.5 text-[10px]">{copied ? "✓ copied" : "📋"}</span>
      </button>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="my-3">
      <h3 className="text-xs font-medium text-[var(--color-text-muted)] mb-2">{title}</h3>
      {children}
    </div>
  );
}

function Divider() {
  return <div className="border-t border-[var(--color-border)]" />;
}

function OutputLine({ line }: { line: JobOutputLine }) {
  const colors = LINE_COLORS[line.type] ?? LINE_COLORS.raw;
  return (
    <div
      className="text-[11px] px-2 py-1 rounded font-mono leading-relaxed"
      style={{ backgroundColor: colors.bg, color: colors.text }}
    >
      <span className="opacity-50 mr-2">{line.type}</span>
      {line.text}
    </div>
  );
}

function formatDT(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
