<p align="center">
  <h1 align="center">Command Center</h1>
  <p align="center">
    Kanban-style dashboard for orchestrating Claude Code CLI sessions
    <br />
    <em>Schedule jobs for sleep, lunch, and commute hours &mdash; let AI work while you rest.</em>
  </p>
</p>

---

## Screenshots

> Coming soon &mdash; run `./scripts/dev.sh` and visit `http://localhost:5174` to see the dashboard live.

## Features

- **Kanban Board** &mdash; 5-column board (Queued / Scheduled / Running / Completed / Failed) with drag-and-drop job management
- **Time Slot Scheduling** &mdash; Define idle windows (sleep, lunch, commute) and queue jobs that auto-execute during those periods
- **Real-time Session Monitor** &mdash; WebSocket-powered live view of Claude Code `stream-json` output as jobs run
- **Budget Guard** &mdash; Daily token budget with per-job limits (`--max-budget-usd`) to prevent overspending
- **Dependency Graph** &mdash; Jobs can declare `blocked_by` dependencies (inspired by [Beads](https://github.com/steveyegge/beads))
- **Job Templates** &mdash; Pre-defined templates for common tasks (code review, ticket analysis, docs generation)
- **Ecosystem Panel** &mdash; Unified view of Dominium ecosystem state (sentinels, work rhythm, PR watch)
- **CLI Skill (`/cc`)** &mdash; Manage jobs directly from Claude Code without opening the dashboard
- **launchd Dispatcher** &mdash; macOS-native scheduler that auto-dispatches jobs every 10 minutes, surviving reboots

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Claude Code CLI installed and authenticated

### Installation

```bash
# Clone the repository
git clone https://github.com/Allen-han21/command-center.git
cd command-center

# Install Python dependencies
uv sync

# Install frontend dependencies
cd frontend && npm install && cd ..

# Copy environment config
cp .env.example .env
# Edit .env with your preferences
```

### Development

```bash
# Start both backend and frontend
./scripts/dev.sh

# Backend: http://localhost:8280
# Frontend: http://localhost:5174
```

### Register launchd Dispatcher (auto-schedule)

```bash
# Install the dispatcher to run every 10 minutes
cp com.dominium.command-center.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.dominium.command-center.plist
```

## Architecture

```
                    Dashboard (React + Vite)
                          :5174
                            |
                     REST + WebSocket
                            |
                    Backend (FastAPI)
                         :8280
                       /       \
              SQLite              claude --print
            (jobs.db)           --output-format stream-json
                                --permission-mode dontAsk
                                --max-budget-usd <limit>
                                      |
                              launchd Dispatcher
                           (every 10 min, standalone)
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, uvicorn, aiosqlite, Pydantic v2 |
| Frontend | React 19, TypeScript, Vite 7, Tailwind CSS v4, React Query v5 |
| Database | SQLite (jobs, time slots, budget) |
| Event Log | JSONL (append-only session events) |
| Scheduler | macOS launchd (10-minute interval) |
| CLI | Claude Code `--print --output-format stream-json` |

## Job Scheduling

### Time Slots

Jobs are assigned to time slots that define when they can auto-execute:

| Slot | Default Hours | Max Concurrent | Use Case |
|------|--------------|----------------|----------|
| `sleep` | 22:00 - 08:00 | 2 | Large analyses, batch reviews, docs generation |
| `lunch` | 12:00 - 13:00 | 1 | Quick analyses, news digests |
| `commute` | 18:00 - 19:00 | 1 | Ticket analysis, task docs |
| `anytime` | Always | 1 | On-demand jobs |

Time slots are fully configurable via the dashboard or API.

### Job Lifecycle

```
queued --> scheduled --> running --> completed
                           |
                           +--> failed --> (retry with backoff)
                           |
                           +--> cancelled
```

### Dependency Resolution

Jobs can declare dependencies using `blocked_by` (inspired by [Beads](https://github.com/steveyegge/beads)):

```json
{
  "title": "Implement feature",
  "blocked_by": ["job_abc123"],
  "prompt": "/ai-dev.impl"
}
```

The scheduler automatically skips blocked jobs until dependencies complete.

## CLI Usage

The `/cc` skill provides terminal access without opening the dashboard:

```bash
/cc                            # Open dashboard in browser
/cc add "analyze PK-12345"     # Add job (current dir, anytime)
/cc add --slot sleep "prompt"  # Schedule for sleep hours
/cc list                       # Show pending jobs
/cc status                     # Running sessions + budget
/cc cancel <id>                # Cancel a job
/cc budget                     # View today's budget
/cc budget 15                  # Set daily limit to $15
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMMAND_CENTER_PORT` | `8280` | Backend API port |
| `COMMAND_CENTER_DATA_DIR` | `~/.claude/command-center` | Runtime data directory |
| `DAILY_BUDGET_USD` | `10.0` | Default daily token budget |
| `DEFAULT_MODEL` | `sonnet` | Default model for unattended jobs |
| `DEFAULT_EFFORT` | `high` | Default effort level |

### Job Templates

Pre-define templates in `templates/` for one-click job creation:

```json
{
  "code-review-batch": {
    "title": "Batch Code Review",
    "prompt": "/loop-prs check --full",
    "time_slot": "sleep",
    "max_budget": 3.0,
    "timeout_min": 60
  }
}
```

## Safety

- **Budget Guard**: Dual protection via `--max-budget-usd` per job + daily aggregate limit
- **Permission Mode**: Uses `--permission-mode dontAsk` (auto-approve with audit trail)
- **Work Dir Whitelist**: Only trusted directories are allowed for job execution
- **Watchdog**: Stale processes are auto-killed after `timeout_min`
- **Session Lock**: Checks `scheduled_tasks.lock` before launching to avoid conflicts

## Inspired By

- [Beads](https://github.com/steveyegge/beads) &mdash; Git-native distributed issue tracker with dependency-aware task selection
- [Symphony](https://github.com/openai/symphony) &mdash; Multi-agent orchestration with state machines and exponential backoff
- [Vibe Kanban](https://github.com/nicepkg/vibe-kanban) &mdash; AI coding agent orchestration with kanban UI

## License

[MIT](LICENSE)
