# Build vs Buy: Command Center vs Open Source Alternatives

## Overview

Before implementing Command Center, we evaluated three leading open-source projects to determine whether to build from scratch, fork, or adopt an existing solution.

| Project | Stars | Language | License | Nature |
|---------|-------|----------|---------|--------|
| [Symphony](https://github.com/openai/symphony) (OpenAI) | 12K | Elixir/OTP | Apache 2.0 | Agent orchestration daemon |
| [Vibe Kanban](https://github.com/BloopAI/vibe-kanban) (BloopAI) | 18K+ | Rust + React 19 | Apache 2.0 | AI Kanban + agent executor |
| [Beads](https://github.com/steveyegge/beads) (steveyegge) | 19K | Go + Dolt | MIT | Distributed agent memory |
| **Command Center** | - | Python + React 18 | MIT | CLI session scheduler + dashboard |

---

## Feature Coverage Analysis

| # | Command Center Requirement | Symphony | Vibe Kanban | Beads |
|---|---|:---:|:---:|:---:|
| 1 | Claude CLI subprocess execution | X | O | X |
| 2 | 6-state state machine | O | ~ | X |
| 3 | **Time slot scheduling** | **X** | **X** | **X** |
| 4 | **Budget guard (daily + per-job)** | **X** | **X** | **X** |
| 5 | 5-column Kanban UI | ~ | O | X |
| 6 | WebSocket real-time monitoring | O | O | X |
| 7 | Job dependency (blocked_by) | X | X | O |
| 8 | **launchd 10-min dispatcher** | **X** | **X** | **X** |
| 9 | **Dominium ecosystem integration** | **X** | **X** | **X** |
| 10 | `/cc` CLI skill | X | ~ | O |
| | **Coverage** | **20%** | **30%** | **20%** |

**Key finding**: Requirements #3, #4, #8, #9 - the core value proposition of Command Center - are absent from all three projects.

---

## Per-Project Analysis

### Symphony (OpenAI)

**What it does well:**
- OTP Supervision Tree for automatic crash recovery
- Exponential backoff retry: `min(10000 * 2^(n-1), 300000ms)`
- Concurrency control: `max_concurrent_agents` + per-state limits
- Policy-as-Code via WORKFLOW.md
- SSH remote workers for distributed execution

**Why it doesn't fit:**
- **Event-driven** ("run when Linear issue arrives") vs Command Center's **time-driven** ("run when sleep slot begins") - a philosophical difference
- Codex JSON protocol only, incompatible with Claude CLI
- Elixir stack - zero overlap with Python + FastAPI ecosystem
- No persistent state storage (re-polls Linear on restart)
- Fork cost estimate: **8 weeks** (Elixir learning + 70% rewrite)

**Patterns adopted**: State machine design, exponential backoff, concurrency control, stall detection

### Vibe Kanban (BloopAI)

**What it does well:**
- 10+ agent support (Claude, Codex, Gemini, Cursor...)
- Executor trait pattern (plugin architecture)
- Attempt model (1 Task : N Attempts for A/B comparison)
- Git Worktree isolation per agent
- MCP bidirectional integration
- WebSocket real-time log streaming

**Why it doesn't fit:**
- **Manual trigger** (drag card to "In Progress") vs Command Center's **automatic** (launchd dispatches in time slots)
- No time slot scheduling, no budget guard
- Rust backend requires learning Rust for customization
- 10-agent support adds unnecessary complexity for Claude-only use
- Fork cost estimate: **7 weeks** (Rust learning + scheduler from scratch)

**Patterns adopted**: 5-column Kanban UI layout, WebSocket streaming architecture

### Beads (steveyegge)

**What it does well:**
- 10+ dependency types (blocks, parent-child, conditional-blocks, waits-for...)
- Hash-based adaptive-length IDs (4-7 chars, Birthday Paradox-aware)
- `bd ready` algorithm (priority-weighted unblocked task selection)
- blocked_issues_cache (752ms to 29ms, 25x improvement)
- Gate system (timer, PR merge, manual approval)
- Semantic memory decay for long-term context

**Why it doesn't fit:**
- **Issue tracker** (memory), not a **task executor** (scheduler) - fundamentally different tools
- No execution capability, no subprocess management
- No dashboard UI (CLI only)
- Go + Dolt stack - completely alien to Python ecosystem
- Fork cost estimate: **7+ weeks** (only ~10% code reusable)

**Patterns adopted**: `blocked_by` dependency resolution, hash-based nanoid, `ready` algorithm

---

## Cost Comparison

| Approach | Estimated Cost | Code Ownership | Ecosystem Integration |
|----------|---------------|----------------|----------------------|
| Fork Symphony | 8 weeks + maintenance debt | Partial (Elixir) | Manual |
| Fork Vibe Kanban | 7 weeks + maintenance debt | Partial (Rust) | Manual |
| Fork Beads | 7+ weeks + maintenance debt | Partial (Go) | Manual |
| **Build from scratch** | **5 weeks** | **Full** | **Native** |

Build is ~30% faster than the cheapest fork option, with full code ownership.

---

## Decision: Build (with Pattern Adoption)

### Five Reasons

1. **Core value gap**: All three projects lack time-slot scheduling + budget management (the reason Command Center exists)
2. **Tech stack mismatch**: Elixir/Rust/Go vs Python+FastAPI+React. Fork customization cost exceeds build cost
3. **Ecosystem uniqueness**: Integration with sentinel/tasks/rhythm/pr-watch/skills is Allen-specific
4. **Patterns already adopted**: The optimal hybrid strategy (pattern adoption) is already reflected in the design
5. **Learning value**: Full ownership of subprocess management, state machines, WebSocket, launchd integration

### Adopted Patterns Summary

| Source | Pattern | Applied To |
|--------|---------|-----------|
| Symphony | 6-state FSM, exponential backoff, concurrency control | State machine, retry logic |
| Beads | `blocked_by` dependency, hash nanoid, `ready` algorithm | Job scheduling |
| Vibe Kanban | 5-column Kanban, WebSocket streaming | Dashboard UI |

### Future Considerations (Post-MVP)

| Source | Pattern | When |
|--------|---------|------|
| Symphony | Policy-as-Code (YAML) | Phase 6+ |
| Vibe Kanban | MCP Server exposure | Phase 6+ |
| Beads | Gate system (PR/manual) | Phase 6+ |
| Beads | Semantic memory decay | Phase 6+ |
