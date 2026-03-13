import { useQuery } from "@tanstack/react-query";
import { ecosystem } from "../../lib/api";

export function EcosystemPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ["ecosystem"],
    queryFn: ecosystem.get,
    refetchInterval: 30_000,
  });

  if (isLoading) return <div className="text-sm text-[var(--color-text-muted)]">Loading...</div>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      {/* Sentinel Section */}
      <section>
        <h3 className="text-sm font-medium mb-2 text-[var(--color-text-muted)]">
          Sentinels ({data.sentinels_pending.length}/{data.sentinels_total})
        </h3>
        {data.sentinels_pending.length === 0 ? (
          <p className="text-xs text-[var(--color-text-muted)]">No pending sentinels</p>
        ) : (
          <div className="space-y-1.5">
            {data.sentinels_pending.map((s) => (
              <div
                key={s.session_id}
                className="flex items-center justify-between px-3 py-2 rounded-lg bg-[var(--color-surface)] text-sm"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className={`shrink-0 px-1.5 py-0.5 rounded text-xs font-medium ${
                      s.is_work
                        ? "bg-blue-500/20 text-blue-400"
                        : "bg-purple-500/20 text-purple-400"
                    }`}
                  >
                    {s.is_work ? "Work" : "Personal"}
                  </span>
                  <span className="truncate font-medium">{s.name || s.session_id}</span>
                </div>
                <div className="flex items-center gap-3 shrink-0 text-xs text-[var(--color-text-muted)]">
                  <span className="text-[var(--color-scheduled)]">{s.current_phase}</span>
                  {s.pending_count > 0 && (
                    <span className="text-[var(--color-queued)]">{s.pending_count} pending</span>
                  )}
                  <span>{s.timestamp.slice(5, 10)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Rhythm Section */}
      <section>
        <h3 className="text-sm font-medium mb-2 text-[var(--color-text-muted)]">Work Rhythm</h3>
        {data.rhythm ? (
          <div className="px-3 py-2 rounded-lg bg-[var(--color-surface)] text-sm">
            <div className="flex items-center gap-3">
              <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-green-500/20 text-green-400">
                {data.rhythm.type}
              </span>
              <span className="text-[var(--color-completed)]">{data.rhythm.current_phase || "idle"}</span>
              <span className="text-xs text-[var(--color-text-muted)]">{data.rhythm.date}</span>
            </div>
          </div>
        ) : (
          <p className="text-xs text-[var(--color-text-muted)]">No active rhythm cycle</p>
        )}
      </section>

      {/* PR Watch Section */}
      <section>
        <h3 className="text-sm font-medium mb-2 text-[var(--color-text-muted)]">PR Watch</h3>
        {data.pr_watch ? (
          <div className="px-3 py-2 rounded-lg bg-[var(--color-surface)] text-sm">
            <div className="flex items-center gap-3">
              <span className="text-[var(--color-queued)]">
                {data.pr_watch.pending_prs.length} pending
              </span>
              <span className="text-[var(--color-text-muted)]">
                {data.pr_watch.reviewed_count} reviewed
              </span>
              <span className="text-xs text-[var(--color-text-muted)]">
                Last: {data.pr_watch.last_check.slice(11, 16)}
              </span>
            </div>
          </div>
        ) : (
          <p className="text-xs text-[var(--color-text-muted)]">PR watch not active</p>
        )}
      </section>
    </div>
  );
}
