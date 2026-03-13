import { useEffect, useRef, useState } from "react";
import type { SessionData, OutputLine } from "../../hooks/useWebSocket";

interface Props {
  sessions: SessionData[];
  connected: boolean;
  requestOutput: (jobId: string, fromLine?: number) => void;
  outputData: { job_id: string; lines: OutputLine[]; total: number } | null;
}

export function SessionPanel({ sessions, connected, requestOutput, outputData }: Props) {
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const outputRef = useRef<HTMLDivElement>(null);

  // 자동 선택: running 세션이 하나면 자동 선택
  useEffect(() => {
    if (sessions.length === 1 && !selectedJob) {
      setSelectedJob(sessions[0].job_id);
    }
    // 선택된 세션이 더 이상 running이 아니면 해제
    if (selectedJob && !sessions.find((s) => s.job_id === selectedJob)) {
      setSelectedJob(null);
    }
  }, [sessions, selectedJob]);

  // 선택 변경 시 output 요청
  useEffect(() => {
    if (selectedJob) {
      requestOutput(selectedJob);
      const interval = setInterval(() => requestOutput(selectedJob), 5000);
      return () => clearInterval(interval);
    }
  }, [selectedJob, requestOutput]);

  // 자동 스크롤
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [outputData]);

  if (sessions.length === 0) {
    return (
      <div className="rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] p-6">
        <div className="flex items-center gap-2 mb-2">
          <h2 className="text-sm font-semibold text-[var(--color-text)]">Live Sessions</h2>
          <StatusDot connected={connected} />
        </div>
        <p className="text-sm text-[var(--color-text-muted)]">No running sessions</p>
      </div>
    );
  }

  const selected = sessions.find((s) => s.job_id === selectedJob);
  const lines = outputData?.job_id === selectedJob ? outputData.lines : [];

  return (
    <div className="rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-[var(--color-text)]">Live Sessions</h2>
          <StatusDot connected={connected} />
          <span className="text-xs text-[var(--color-text-muted)]">
            {sessions.length} running
          </span>
        </div>
      </div>

      {/* Session tabs */}
      {sessions.length > 1 && (
        <div className="flex gap-1 px-4 py-2 border-b border-[var(--color-border)] overflow-x-auto">
          {sessions.map((s) => (
            <button
              key={s.job_id}
              onClick={() => setSelectedJob(s.job_id)}
              className={`px-3 py-1 rounded-md text-xs font-medium whitespace-nowrap transition-colors ${
                selectedJob === s.job_id
                  ? "bg-[var(--color-running)] text-white"
                  : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
              }`}
            >
              {s.title}
            </button>
          ))}
        </div>
      )}

      {/* Session info */}
      {selected && (
        <div className="px-4 py-2 border-b border-[var(--color-border)] flex items-center gap-4 text-xs text-[var(--color-text-muted)]">
          <span>
            PID: <strong className={selected.alive ? "text-green-400" : "text-red-400"}>
              {selected.pid ?? "—"}
            </strong>
          </span>
          <span>Model: {selected.model}</span>
          <span>Lines: {selected.output_lines}</span>
          <span className="truncate max-w-[200px]">{selected.work_dir}</span>
        </div>
      )}

      {/* Output stream */}
      <div
        ref={outputRef}
        className="max-h-80 overflow-y-auto p-4 font-mono text-xs leading-relaxed"
      >
        {lines.length === 0 ? (
          <p className="text-[var(--color-text-muted)]">
            {selectedJob ? "Waiting for output..." : "Select a session above"}
          </p>
        ) : (
          lines.map((line) => <OutputLineRow key={line.index} line={line} />)
        )}
      </div>
    </div>
  );
}

function OutputLineRow({ line }: { line: OutputLine }) {
  const colorMap: Record<string, string> = {
    assistant: "text-blue-300",
    tool_use: "text-yellow-300",
    tool_result: "text-gray-400",
    result: "text-green-300",
    raw: "text-gray-500",
  };

  return (
    <div className={`${colorMap[line.type] ?? "text-[var(--color-text-muted)]"} whitespace-pre-wrap break-all`}>
      <span className="opacity-40 mr-2 select-none">{String(line.index).padStart(3)}</span>
      {line.type !== "raw" && line.type !== "assistant" && (
        <span className="opacity-50">[{line.type}] </span>
      )}
      {line.text}
    </div>
  );
}

function StatusDot({ connected }: { connected: boolean }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${
        connected ? "bg-green-400 animate-pulse" : "bg-red-400"
      }`}
      title={connected ? "WebSocket connected" : "Disconnected"}
    />
  );
}
