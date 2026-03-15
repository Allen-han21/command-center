import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { jobs as jobsApi, type Job, type JobCreate } from "../../lib/api";

interface Props {
  parentJob: Job;
  onClose: () => void;
}

type Mode = "new" | "resume";

export function ContinueJobForm({ parentJob, onClose }: Props) {
  const qc = useQueryClient();
  const canResume = !!parentJob.session_id;
  const [mode, setMode] = useState<Mode>("new");
  const baseTitle = parentJob.title.replace(/^Continue:\s*/g, "");
  const [title, setTitle] = useState(`Continue: ${baseTitle}`);
  const [prompt, setPrompt] = useState("");

  const mutation = useMutation({
    mutationFn: (data: JobCreate) => jobsApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      onClose();
    },
  });

  const handleSubmit = () => {
    const base: JobCreate = {
      title,
      prompt: mode === "new" && parentJob.result_summary
        ? `[이전 작업: ${parentJob.title}]\n${parentJob.result_summary}\n\n---\n\n${prompt}`
        : prompt,
      work_dir: parentJob.work_dir,
      priority: parentJob.priority,
      time_slot: parentJob.time_slot,
      max_budget: parentJob.max_budget,
      timeout_min: parentJob.timeout_min,
      model: parentJob.model,
      effort: parentJob.effort,
      blocked_by: [parentJob.id],
      parent_job_id: parentJob.id,
    };

    if (mode === "resume" && parentJob.session_id) {
      base.resume_session_id = parentJob.session_id;
    }

    mutation.mutate(base);
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-[var(--color-surface)] rounded-xl w-full max-w-lg p-6 mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold mb-4">Continue from Job</h2>

        <div className="space-y-4">
          {/* Mode Selection */}
          <div>
            <label className="block text-xs text-[var(--color-text-muted)] mb-2">Mode</label>
            <div className="flex gap-2">
              <ModeBtn active={mode === "new"} onClick={() => setMode("new")}>
                New Job
              </ModeBtn>
              <ModeBtn
                active={mode === "resume"}
                onClick={() => setMode("resume")}
                disabled={!canResume}
              >
                Resume Session
              </ModeBtn>
            </div>
            <p className="text-[10px] text-[var(--color-text-muted)] mt-1">
              {mode === "new"
                ? "새 세션을 시작하고 이전 결과를 프롬프트에 포함합니다"
                : "이전 세션을 이어받아 대화 맥락을 유지합니다"}
            </p>
          </div>

          {/* Title */}
          <Field label="Title">
            <input
              className="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] text-sm outline-none focus:border-indigo-500"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </Field>

          {/* Prompt */}
          <Field label="Prompt">
            <textarea
              className="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] text-sm outline-none focus:border-indigo-500 min-h-[100px] resize-y"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="후속 작업 지시를 입력하세요"
            />
          </Field>

          {/* Inherited settings */}
          <div className="text-xs text-[var(--color-text-muted)] bg-[var(--color-bg)] rounded-lg p-3 space-y-1">
            <p className="font-medium text-[var(--color-text)] mb-1">Inherited Settings</p>
            <p>Work Dir: <span className="font-mono">{parentJob.work_dir}</span></p>
            <p>Model: {parentJob.model} · Effort: {parentJob.effort} · Budget: ${parentJob.max_budget.toFixed(1)}</p>
            <p>Time Slot: {parentJob.time_slot} · Timeout: {parentJob.timeout_min}min</p>
            <p>Blocked By: <span className="font-mono">{parentJob.id.slice(0, 8)}</span> (parent)</p>
          </div>
        </div>

        {mutation.error && (
          <p className="text-sm text-red-400 mt-3">{(mutation.error as Error).message}</p>
        )}

        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-lg bg-[var(--color-bg)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors text-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!title || !prompt || mutation.isPending}
            className="flex-1 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
          >
            {mutation.isPending ? "Creating..." : "Create Job"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-[var(--color-text-muted)] mb-1">{label}</label>
      {children}
    </div>
  );
}

function ModeBtn({
  active,
  disabled,
  onClick,
  children,
}: {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
        active
          ? "bg-indigo-600 text-white"
          : "bg-[var(--color-bg)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
      } disabled:opacity-30 disabled:cursor-not-allowed`}
    >
      {children}
    </button>
  );
}
