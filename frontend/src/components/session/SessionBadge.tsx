interface Props {
  pid: number | null;
  alive: boolean;
  outputLines: number;
}

export function SessionBadge({ pid, alive, outputLines }: Props) {
  if (!pid) return null;

  return (
    <div className="flex items-center gap-1.5 text-[10px] text-[var(--color-text-muted)]">
      <span
        className={`w-1.5 h-1.5 rounded-full ${alive ? "bg-green-400 animate-pulse" : "bg-red-400"}`}
      />
      <span>PID {pid}</span>
      {outputLines > 0 && <span className="opacity-60">{outputLines}L</span>}
    </div>
  );
}
