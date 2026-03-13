import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { jobs as jobsApi, type JobCreate } from "../../lib/api";

interface Props {
  onClose: () => void;
}

export function JobForm({ onClose }: Props) {
  const qc = useQueryClient();
  const [form, setForm] = useState<JobCreate>({
    title: "",
    prompt: "",
    work_dir: "~",
    priority: 5,
    time_slot: "anytime",
    max_budget: 2.0,
    timeout_min: 30,
    model: "sonnet",
    effort: "high",
    max_retries: 2,
  });

  const mutation = useMutation({
    mutationFn: jobsApi.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      onClose();
    },
  });

  const set = <K extends keyof JobCreate>(key: K, value: JobCreate[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-[var(--color-surface)] rounded-xl w-full max-w-lg p-6 mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold mb-4">New Job</h2>

        <div className="space-y-4">
          <Field label="Title">
            <input
              className="input-field"
              value={form.title}
              onChange={(e) => set("title", e.target.value)}
              placeholder="e.g., Analyze PK-12345"
            />
          </Field>

          <Field label="Prompt">
            <textarea
              className="input-field min-h-[80px] resize-y"
              value={form.prompt}
              onChange={(e) => set("prompt", e.target.value)}
              placeholder="The prompt to send to Claude CLI"
            />
          </Field>

          <Field label="Work Directory">
            <input
              className="input-field"
              value={form.work_dir}
              onChange={(e) => set("work_dir", e.target.value)}
            />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Time Slot">
              <select
                className="input-field"
                value={form.time_slot}
                onChange={(e) => set("time_slot", e.target.value as JobCreate["time_slot"])}
              >
                <option value="anytime">Anytime</option>
                <option value="sleep">Sleep (22-08)</option>
                <option value="lunch">Lunch (12-13)</option>
                <option value="commute">Commute (18-19)</option>
              </select>
            </Field>

            <Field label="Model">
              <select
                className="input-field"
                value={form.model}
                onChange={(e) => set("model", e.target.value as JobCreate["model"])}
              >
                <option value="sonnet">Sonnet</option>
                <option value="opus">Opus</option>
                <option value="haiku">Haiku</option>
              </select>
            </Field>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <Field label="Priority (1-10)">
              <input
                type="number"
                className="input-field"
                min={1}
                max={10}
                value={form.priority}
                onChange={(e) => set("priority", parseInt(e.target.value) || 5)}
              />
            </Field>

            <Field label="Budget ($)">
              <input
                type="number"
                className="input-field"
                step={0.5}
                min={0.1}
                value={form.max_budget}
                onChange={(e) => set("max_budget", parseFloat(e.target.value) || 2.0)}
              />
            </Field>

            <Field label="Timeout (min)">
              <input
                type="number"
                className="input-field"
                min={1}
                value={form.timeout_min}
                onChange={(e) => set("timeout_min", parseInt(e.target.value) || 30)}
              />
            </Field>
          </div>

          <Field label="Effort">
            <div className="flex gap-2">
              {(["low", "medium", "high", "max"] as const).map((level) => (
                <button
                  key={level}
                  onClick={() => set("effort", level)}
                  className={`flex-1 py-1.5 rounded text-xs font-medium transition-colors ${
                    form.effort === level
                      ? "bg-indigo-600 text-white"
                      : "bg-[var(--color-bg)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                  }`}
                >
                  {level}
                </button>
              ))}
            </div>
          </Field>

          <Field label="JIRA Ticket (optional)">
            <input
              className="input-field"
              value={form.jira_ticket ?? ""}
              onChange={(e) => set("jira_ticket", e.target.value || undefined)}
              placeholder="PK-12345"
            />
          </Field>
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
            onClick={() => mutation.mutate(form)}
            disabled={!form.title || !form.prompt || mutation.isPending}
            className="flex-1 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
          >
            {mutation.isPending ? "Creating..." : "Create Job"}
          </button>
        </div>
      </div>

      <style>{`
        .input-field {
          width: 100%;
          padding: 0.5rem 0.75rem;
          border-radius: 0.5rem;
          border: 1px solid var(--color-border);
          background: var(--color-bg);
          color: var(--color-text);
          font-size: 0.875rem;
          outline: none;
          transition: border-color 0.15s;
        }
        .input-field:focus {
          border-color: #6366f1;
        }
        .input-field::placeholder {
          color: var(--color-text-muted);
          opacity: 0.5;
        }
      `}</style>
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
