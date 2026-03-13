import { useQuery } from "@tanstack/react-query";
import { budget as budgetApi } from "../../lib/api";

export function BudgetGauge() {
  const { data } = useQuery({ queryKey: ["budget"], queryFn: budgetApi.get });

  if (!data) return null;

  const pct = Math.min((data.spent_usd / data.limit_usd) * 100, 100);
  const isWarning = pct > 80;

  return (
    <div className="rounded-xl bg-[var(--color-surface)] p-4">
      <h2 className="text-sm font-medium mb-3">Daily Budget</h2>

      {/* Gauge ring */}
      <div className="flex justify-center mb-4">
        <div className="relative w-32 h-32">
          <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
            <circle
              cx="18" cy="18" r="15.5"
              fill="none"
              stroke="var(--color-border)"
              strokeWidth="3"
            />
            <circle
              cx="18" cy="18" r="15.5"
              fill="none"
              stroke={isWarning ? "var(--color-failed)" : "var(--color-completed)"}
              strokeWidth="3"
              strokeDasharray={`${pct} ${100 - pct}`}
              strokeLinecap="round"
              className="transition-all duration-500"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-bold">${data.spent_usd.toFixed(2)}</span>
            <span className="text-[10px] text-[var(--color-text-muted)]">of ${data.limit_usd.toFixed(0)}</span>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="space-y-2">
        <StatRow label="Remaining" value={`$${data.remaining_usd.toFixed(2)}`} />
        <StatRow label="Jobs today" value={data.job_count.toString()} />
        <StatRow label="Avg per job" value={data.job_count > 0 ? `$${(data.spent_usd / data.job_count).toFixed(2)}` : "-"} />
      </div>
    </div>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-[var(--color-text-muted)]">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
