import { useQuery } from "@tanstack/react-query";
import { dashboard } from "../lib/api";

export function DashboardHeader() {
  const { data } = useQuery({ queryKey: ["dashboard"], queryFn: dashboard.get });

  return (
    <header className="px-4 py-3 border-b border-[var(--color-border)]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold tracking-tight">Command Center</h1>
          <span className="text-xs text-[var(--color-text-muted)]">Dominium</span>
        </div>
        {data && (
          <div className="flex items-center gap-4 text-sm">
            <Stat label="Running" value={data.running_jobs} color="var(--color-running)" />
            <Stat label="Queued" value={data.queued_jobs} color="var(--color-queued)" />
            <Stat
              label="Budget"
              value={`$${data.today_spent_usd.toFixed(1)}/$${data.today_limit_usd.toFixed(0)}`}
              color={
                data.today_spent_usd / data.today_limit_usd > 0.8
                  ? "var(--color-failed)"
                  : "var(--color-completed)"
              }
            />
            {data.next_slot && (
              <span className="text-[var(--color-text-muted)]">
                Next: <span className="text-[var(--color-scheduled)]">{data.next_slot}</span>
              </span>
            )}
          </div>
        )}
      </div>
    </header>
  );
}

function Stat({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[var(--color-text-muted)]">{label}</span>
      <span className="font-medium" style={{ color }}>
        {value}
      </span>
    </div>
  );
}
