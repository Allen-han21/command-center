import { useState } from "react";
import { KanbanBoard } from "./components/kanban/KanbanBoard";
import { DayTimeline } from "./components/timeline/DayTimeline";
import { BudgetGauge } from "./components/timeline/BudgetGauge";
import { JobForm } from "./components/job/JobForm";
import { SessionPanel } from "./components/session/SessionPanel";
import { DashboardHeader } from "./components/DashboardHeader";
import { useWebSocket } from "./hooks/useWebSocket";

type Tab = "kanban" | "timeline";

export default function App() {
  const [tab, setTab] = useState<Tab>("kanban");
  const [showForm, setShowForm] = useState(false);
  const { sessions, connected, requestOutput, outputData } = useWebSocket();

  return (
    <div className="min-h-screen">
      <DashboardHeader />

      <div className="px-4 pb-4">
        {/* Tab bar + actions */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex gap-1 rounded-lg bg-[var(--color-surface)] p-1">
            <TabButton active={tab === "kanban"} onClick={() => setTab("kanban")}>
              Kanban
            </TabButton>
            <TabButton active={tab === "timeline"} onClick={() => setTab("timeline")}>
              Timeline
            </TabButton>
          </div>
          <button
            onClick={() => setShowForm(true)}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors"
          >
            + New Job
          </button>
        </div>

        {/* Main content */}
        {tab === "kanban" && <KanbanBoard />}
        {tab === "timeline" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2">
              <DayTimeline />
            </div>
            <div>
              <BudgetGauge />
            </div>
          </div>
        )}

        {/* Live session monitor */}
        <div className="mt-4">
          <SessionPanel
            sessions={sessions}
            connected={connected}
            requestOutput={requestOutput}
            outputData={outputData}
          />
        </div>
      </div>

      {showForm && <JobForm onClose={() => setShowForm(false)} />}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
        active
          ? "bg-indigo-600 text-white"
          : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
      }`}
    >
      {children}
    </button>
  );
}
