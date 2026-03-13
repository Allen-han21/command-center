import type { Job } from "../../lib/api";
import { JobCard } from "./JobCard";

interface Props {
  status: Job["status"];
  label: string;
  color: string;
  jobs: Job[];
}

export function KanbanColumn({ label, color, jobs }: Props) {
  return (
    <div className="flex flex-col rounded-xl bg-[var(--color-surface)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-[var(--color-border)]">
        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
        <span className="text-sm font-medium">{label}</span>
        <span className="ml-auto text-xs text-[var(--color-text-muted)] bg-[var(--color-bg)] px-1.5 py-0.5 rounded">
          {jobs.length}
        </span>
      </div>

      {/* Cards */}
      <div className="flex-1 p-2 space-y-2 overflow-y-auto">
        {jobs.length === 0 ? (
          <div className="text-xs text-[var(--color-text-muted)] text-center py-8 opacity-50">
            No jobs
          </div>
        ) : (
          jobs.map((job) => <JobCard key={job.id} job={job} />)
        )}
      </div>
    </div>
  );
}
