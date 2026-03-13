import { useQuery } from "@tanstack/react-query";
import { timeSlots as slotsApi, jobs as jobsApi, type TimeSlot } from "../../lib/api";

const HOURS = Array.from({ length: 24 }, (_, i) => i);

const SLOT_COLORS: Record<string, string> = {
  sleep: "rgba(99,102,241,0.15)",
  lunch: "rgba(245,158,11,0.15)",
  commute: "rgba(251,146,60,0.15)",
};

export function DayTimeline() {
  const { data: slots = [] } = useQuery({ queryKey: ["time-slots"], queryFn: slotsApi.list });
  const { data: allJobs = [] } = useQuery({ queryKey: ["jobs"], queryFn: () => jobsApi.list() });

  const now = new Date();
  const currentHour = now.getHours() + now.getMinutes() / 60;

  const runningJobs = allJobs.filter((j) => j.status === "running");

  return (
    <div className="rounded-xl bg-[var(--color-surface)] p-4">
      <h2 className="text-sm font-medium mb-3">24h Timeline</h2>
      <div className="relative">
        {/* Hour grid */}
        <div className="grid grid-cols-24 gap-0">
          {HOURS.map((h) => (
            <div key={h} className="relative h-20 border-r border-[var(--color-border)] last:border-0">
              <span className="absolute -top-5 left-0 text-[10px] text-[var(--color-text-muted)]">
                {h.toString().padStart(2, "0")}
              </span>
              {/* Slot background */}
              {slots
                .filter((s) => s.enabled && isHourInSlot(h, s))
                .map((s) => (
                  <div
                    key={s.name}
                    className="absolute inset-0"
                    style={{ backgroundColor: SLOT_COLORS[s.name] ?? "rgba(100,100,100,0.1)" }}
                    title={s.name}
                  />
                ))}
            </div>
          ))}
        </div>

        {/* Now indicator */}
        <div
          className="absolute top-0 h-20 w-0.5 bg-red-500 z-10"
          style={{ left: `${(currentHour / 24) * 100}%` }}
        >
          <div className="absolute -top-1 -left-1 w-2.5 h-2.5 rounded-full bg-red-500" />
        </div>

        {/* Running job markers */}
        {runningJobs.map((job) => {
          const startH = job.started_at ? getHourFromISO(job.started_at) : currentHour;
          return (
            <div
              key={job.id}
              className="absolute top-6 h-8 rounded bg-green-600/30 border border-green-500/50 flex items-center px-1.5 text-[10px] text-green-300 overflow-hidden"
              style={{
                left: `${(startH / 24) * 100}%`,
                width: `${(Math.max((currentHour - startH), 0.3) / 24) * 100}%`,
              }}
              title={job.title}
            >
              {job.title}
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex gap-4 mt-4">
        {slots.filter((s) => s.enabled && s.name !== "anytime").map((s) => (
          <div key={s.name} className="flex items-center gap-1.5 text-xs text-[var(--color-text-muted)]">
            <div
              className="w-3 h-3 rounded"
              style={{ backgroundColor: SLOT_COLORS[s.name] ?? "#666" }}
            />
            <span>{s.name} ({s.start_time}-{s.end_time})</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function isHourInSlot(hour: number, slot: TimeSlot): boolean {
  if (!slot.start_time || !slot.end_time) return false;
  const start = parseInt(slot.start_time.split(":")[0]);
  const end = parseInt(slot.end_time.split(":")[0]);
  if (start > end) {
    // midnight crossing (e.g. 22:00-08:00)
    return hour >= start || hour < end;
  }
  return hour >= start && hour < end;
}

function getHourFromISO(iso: string): number {
  const d = new Date(iso);
  return d.getHours() + d.getMinutes() / 60;
}
