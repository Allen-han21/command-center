import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { jobs as jobsApi, type Job } from "../../lib/api";
import { KanbanColumn } from "./KanbanColumn";
import { JobDetailModal } from "../job/JobDetailModal";
import { ContinueJobForm } from "../job/ContinueJobForm";

const COLUMNS: { statuses: Job["status"][]; label: string; color: string }[] = [
  { statuses: ["queued"], label: "Queued", color: "var(--color-queued)" },
  { statuses: ["scheduled"], label: "Scheduled", color: "var(--color-scheduled)" },
  { statuses: ["running"], label: "Running", color: "var(--color-running)" },
  { statuses: ["completed"], label: "Completed", color: "var(--color-completed)" },
  { statuses: ["failed", "cancelled"], label: "Failed", color: "var(--color-failed)" },
];

export function KanbanBoard() {
  const { data: allJobs = [], isLoading } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => jobsApi.list(),
  });

  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [showContinue, setShowContinue] = useState(false);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-[var(--color-text-muted)]">
        Loading jobs...
      </div>
    );
  }

  const grouped = COLUMNS.map((col) => ({
    ...col,
    status: col.statuses[0],
    jobs: allJobs
      .filter((j) => col.statuses.includes(j.status))
      .sort((a, b) => a.priority - b.priority),
  }));

  const closeAll = () => {
    setSelectedJob(null);
    setShowContinue(false);
  };

  return (
    <>
      <div className="grid grid-cols-5 gap-3 min-h-[calc(100vh-10rem)]">
        {grouped.map((col) => (
          <KanbanColumn key={col.status} {...col} onJobClick={setSelectedJob} />
        ))}
      </div>

      {selectedJob && !showContinue && (
        <JobDetailModal
          job={selectedJob}
          onClose={closeAll}
          onContinue={() => setShowContinue(true)}
        />
      )}

      {selectedJob && showContinue && (
        <ContinueJobForm parentJob={selectedJob} onClose={closeAll} />
      )}
    </>
  );
}
