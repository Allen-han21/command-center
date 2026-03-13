import { useEffect, useRef, useCallback, useState } from "react";

export interface SessionData {
  job_id: string;
  title: string;
  pid: number | null;
  alive: boolean;
  started_at: string | null;
  output_lines: number;
  last_output: string | null;
  model: string;
  work_dir: string;
}

export interface JobStatusEvent {
  type: "job_status";
  job_id: string;
  title: string;
  status: string;
}

export interface OutputLine {
  index: number;
  type: string;
  text: string;
}

export interface OutputData {
  job_id: string;
  lines: OutputLine[];
  total: number;
}

type WSMessage =
  | { type: "sessions"; data: SessionData[]; timestamp: string }
  | JobStatusEvent
  | { type: "output"; job_id: string; lines: OutputLine[]; total: number };

interface UseWebSocketReturn {
  sessions: SessionData[];
  connected: boolean;
  lastEvent: JobStatusEvent | null;
  requestOutput: (jobId: string, fromLine?: number) => void;
  outputData: OutputData | null;
}

export function useWebSocket(): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const [sessions, setSessions] = useState<SessionData[]>([]);
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<JobStatusEvent | null>(null);
  const [outputData, setOutputData] = useState<OutputData | null>(null);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = import.meta.env.DEV ? "localhost:8280" : window.location.host;
    const ws = new WebSocket(`${protocol}//${host}/ws/sessions`);

    ws.onopen = () => {
      setConnected(true);
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        if (msg.type === "sessions") {
          setSessions(msg.data);
        } else if (msg.type === "job_status") {
          setLastEvent(msg as JobStatusEvent);
        } else if (msg.type === "output") {
          setOutputData({
            job_id: msg.job_id,
            lines: msg.lines,
            total: msg.total,
          });
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => ws.close();
    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const requestOutput = useCallback((jobId: string, fromLine = 0) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: "get_output", job_id: jobId, from_line: fromLine })
      );
    }
  }, []);

  return { sessions, connected, lastEvent, requestOutput, outputData };
}
