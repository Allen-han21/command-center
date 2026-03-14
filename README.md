<h1 align="center">
  Command Center
</h1>

<p align="center">
  <strong>Claude Code CLI 세션 오케스트레이터</strong><br/>
  칸반 보드로 AI 작업을 관리하고, 유휴 시간에 자동 실행합니다.
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &middot;
  <a href="#features">Features</a> &middot;
  <a href="#architecture">Architecture</a> &middot;
  <a href="#api-reference">API</a> &middot;
  <a href="#how-it-works">How it Works</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?logo=python&logoColor=white" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/react-19-61DAFB?logo=react&logoColor=white" alt="React 19"/>
  <img src="https://img.shields.io/badge/fastapi-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"/>
  <img src="https://img.shields.io/badge/tests-112%20passed-brightgreen" alt="Tests"/>
</p>

---

## Why Command Center?

Claude Code CLI는 강력하지만, **한 번에 하나의 세션만** 실행할 수 있습니다.

Command Center는 이 한계를 해결합니다:

- 잠자는 시간, 점심시간, 퇴근길에 **AI가 알아서 작업**합니다
- 여러 작업의 **우선순위와 의존성**을 칸반 보드로 관리합니다
- **일일 예산**을 설정하면 과금 걱정 없이 작업을 돌릴 수 있습니다

```
22:00 취침 → Command Center가 sleep 슬롯 감지
            → 대기열에서 우선순위 높은 Job 선택
            → claude --print 으로 자동 실행
            → 완료되면 다음 Job 실행
08:00 기상 → 결과 확인만 하면 됨
```

---

## Features

### Kanban Board

5-column 칸반 보드 (Queued / Scheduled / Running / Completed / Failed)로 모든 Job의 상태를 한눈에 파악합니다.

### Time Slot Scheduling

시간대별 자동 실행 슬롯을 정의합니다. 설정한 시간이 되면 Dispatcher가 자동으로 대기 중인 Job을 실행합니다.

| Slot | 기본 시간 | 동시 실행 | 용도 |
|------|----------|:---------:|------|
| `sleep` | 22:00 - 08:00 | 2 | 대규모 분석, 배치 리뷰, 문서 생성 |
| `lunch` | 12:00 - 13:00 | 1 | 간단한 분석, 뉴스 요약 |
| `commute` | 18:00 - 19:00 | 1 | 티켓 분석, Task 문서 |
| `anytime` | 항상 | 1 | 즉시 실행 |

### Real-time Session Monitor

WebSocket으로 실행 중인 Claude Code 세션의 `stream-json` 출력을 실시간으로 확인합니다.

### Budget Guard

이중 예산 보호 시스템으로 과금을 방지합니다:
- **Job 단위**: `--max-budget-usd`로 개별 Job의 최대 비용 제한
- **일일 합산**: 하루 전체 사용량이 한도를 초과하면 자동 중단

### Dependency Graph

`blocked_by`로 Job 간 의존성을 선언합니다. 선행 Job이 완료되어야 후속 Job이 실행됩니다.

```json
{
  "title": "기능 구현",
  "blocked_by": ["job_abc123"],
  "prompt": "/ai-dev.impl"
}
```

### Ecosystem Panel

Dominium 생태계 상태를 통합 표시합니다 (Sentinel 체크포인트, Work Rhythm 사이클, PR Watch).

### CLI Skill (`/cc`)

대시보드를 열지 않고 터미널에서 바로 Job을 관리합니다.

### launchd Dispatcher

macOS launchd로 10분마다 자동 실행되는 독립 프로세스입니다. 재부팅 후에도 자동 복구됩니다.

---

## Quick Start

### 요구사항

- Python 3.12+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/) (Python 패키지 매니저)
- Claude Code CLI (인증 완료 상태)

### 설치

```bash
git clone https://github.com/Allen-han21/command-center.git
cd command-center

# Python 의존성 설치
uv sync

# Frontend 의존성 설치
cd frontend && npm install && cd ..
```

### 개발 서버 실행

```bash
./scripts/dev.sh

# Backend:  http://localhost:8280
# Frontend: http://localhost:5174
# API Docs: http://localhost:8280/docs
```

### launchd Dispatcher 등록 (선택)

> 등록하면 10분마다 자동으로 대기 중인 Job을 실행합니다.

```bash
./scripts/install_launchd.sh
# 또는 수동으로:
cp com.dominium.command-center.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.dominium.command-center.plist
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Dashboard (React 19)                │
│         Kanban  ·  Timeline  ·  Ecosystem           │
│                    :5174                             │
└──────────────────────┬──────────────────────────────┘
                       │ REST + WebSocket
┌──────────────────────┴──────────────────────────────┐
│                 Backend (FastAPI)                     │
│                     :8280                            │
│                                                      │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐  │
│  │ Scheduler │  │  Budget   │  │    Executor      │  │
│  │           │  │  Guard    │  │                  │  │
│  │ time slot │  │ daily cap │  │ claude --print   │  │
│  │ priority  │  │ per-job   │  │ stream-json      │  │
│  │ deps      │  │ limit     │  │ subprocess       │  │
│  └─────┬─────┘  └─────┬─────┘  └────────┬─────────┘  │
│        │              │                 │            │
│        └──────────────┴────────┬────────┘            │
│                                │                     │
│                    ┌───────────┴──────────┐          │
│                    │   SQLite (aiosqlite) │          │
│                    │   jobs · slots · budget│         │
│                    └──────────────────────┘          │
└─────────────────────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          │   launchd Dispatcher    │
          │  (10분 간격, standalone) │
          │  - pick_next_job()      │
          │  - can_spend() 확인     │
          │  - run_job() 실행       │
          └─────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 · FastAPI · uvicorn · aiosqlite · Pydantic v2 |
| Frontend | React 19 · TypeScript · Vite 7 · Tailwind CSS v4 · React Query v5 |
| Database | SQLite (jobs, time slots, budget) |
| Real-time | WebSocket (session monitor, job status broadcast) |
| Event Log | JSONL (append-only session events) |
| Scheduler | macOS launchd (10분 간격) |
| CLI | Claude Code `--print --output-format stream-json` |

---

## How it Works

> 이 섹션은 Command Center의 핵심 동작 원리를 설명합니다.

### Dispatcher: 유휴 시간 자동 실행의 핵심

Dispatcher는 FastAPI 서버와 **완전히 독립된 프로세스**입니다.

```
launchd (10분마다 트리거)
  └→ python -m command_center.dispatcher
       └→ pick_next_job()   ← 실행할 Job 찾기
       └→ can_spend()       ← 예산 확인
       └→ run_job()         ← claude --print 실행
       └→ (다음 Job 있으면 반복)
       └→ 종료
```

**왜 독립 프로세스인가?**
- FastAPI 서버가 꺼져 있어도 Job이 실행됩니다
- launchd가 관리하므로 재부팅 후에도 자동 복구됩니다
- Claude Code 세션 내부에서 실행되면 `CLAUDECODE` 환경변수를 감지하고 즉시 중단합니다 (무한 재귀 방지)

### Scheduler: Job 선택 알고리즘

`pick_next_job()`은 다음 4단계로 실행할 Job을 결정합니다:

```
1. 현재 활성 Time Slot 확인
   → 22:00~08:00이면 sleep 슬롯 활성
   → 활성 슬롯 없으면 실행하지 않음

2. 동시 실행 수 확인
   → sleep 슬롯은 max_concurrent=2이므로 2개까지 병렬 실행
   → 이미 2개 실행 중이면 대기

3. 의존성 해결 확인
   → blocked_by에 명시된 Job이 모두 completed 상태인지 확인
   → 하나라도 미완료면 skip

4. scheduled_at 확인
   → 특정 시각 이후에만 실행하도록 예약된 Job 확인
   → 아직 시각이 안 됐으면 skip
```

**우선순위**: priority 값이 낮을수록 먼저 실행됩니다 (1=최우선, 10=최후순). 같은 우선순위면 먼저 등록된 Job이 실행됩니다.

### Executor: Claude Code 실행 방식

각 Job은 다음 명령어로 실행됩니다:

```bash
claude --print \
  --output-format stream-json \
  --permission-mode dontAsk \
  --model claude-sonnet-4-6 \
  --max-budget-usd 2.0 \
  --effort high \
  -p "프롬프트 내용"
```

| 플래그 | 설명 |
|--------|------|
| `--print` | 대화형이 아닌 일회성 실행 모드 |
| `--output-format stream-json` | 실시간 스트리밍을 JSONL로 출력 |
| `--permission-mode dontAsk` | 파일 수정 등 자동 승인 (무인 실행용) |
| `--max-budget-usd` | 이 Job에서 사용할 최대 금액 |

**실패 시 재시도**: 기본 2회까지 자동 재시도합니다. 재시도 횟수를 초과하면 `failed` 상태로 전환됩니다.

### Budget Guard: 이중 예산 보호

```
Job 실행 전: can_spend(job.max_budget) 확인
  → 오늘 사용액 + 이 Job 예산 > 일일 한도?
  → 초과하면 Job을 실행하지 않고 루프 종료

Job 실행 후: record_spend(job_id, actual_cost) 기록
  → 일별 사용 내역을 DB에 저장
```

일일 한도 기본값은 $10이며, API 또는 대시보드에서 변경할 수 있습니다.

---

## CLI Usage

`/cc` 스킬로 터미널에서 바로 Job을 관리합니다:

```bash
# 대시보드 열기
/cc

# Job 추가 (현재 디렉토리, anytime 슬롯)
/cc add "PK-12345 분석해줘"

# sleep 슬롯에 예약
/cc add --slot sleep "코드 리뷰 배치 실행"

# 대기 중인 Job 목록
/cc list

# 실행 상태 + 예산 확인
/cc status

# Job 취소
/cc cancel <job-id>

# 오늘 예산 확인 / 변경
/cc budget
/cc budget 15
```

---

## API Reference

Backend는 `http://localhost:8280/docs`에서 Swagger UI로 전체 API를 탐색할 수 있습니다.

### Jobs

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/api/jobs` | Job 목록 (필터: `?status=queued&time_slot=sleep`) |
| `POST` | `/api/jobs` | Job 생성 |
| `GET` | `/api/jobs/{id}` | Job 상세 조회 |
| `PATCH` | `/api/jobs/{id}` | Job 수정 |
| `DELETE` | `/api/jobs/{id}` | Job 삭제 |
| `POST` | `/api/jobs/{id}/cancel` | Job 취소 |
| `POST` | `/api/jobs/{id}/retry` | 실패한 Job 재시도 |

### Time Slots

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/api/time-slots` | 슬롯 목록 |
| `PATCH` | `/api/time-slots/{name}` | 슬롯 설정 변경 |

### Budget

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/api/budget` | 오늘 예산 조회 |
| `PATCH` | `/api/budget` | 일일 한도 변경 |

### Dashboard

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/api/dashboard` | 대시보드 요약 (실행 중/대기/예산/생태계) |

### Ecosystem

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/api/ecosystem` | Sentinel + Rhythm + PR Watch 상태 |

### WebSocket

| Endpoint | 설명 |
|----------|------|
| `ws://localhost:8280/ws` | 실시간 Job 상태 변경 + 세션 출력 스트림 |

---

## Configuration

### 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `COMMAND_CENTER_PORT` | `8280` | Backend API 포트 |
| `COMMAND_CENTER_DATA_DIR` | `~/.claude/command-center` | 런타임 데이터 디렉토리 (DB, 로그, 출력) |
| `DAILY_BUDGET_USD` | `10.0` | 일일 토큰 예산 (USD) |
| `DEFAULT_MODEL` | `sonnet` | 무인 실행 시 기본 모델 (`sonnet` / `opus` / `haiku`) |
| `DEFAULT_EFFORT` | `high` | 기본 effort 수준 (`low` / `medium` / `high` / `max`) |

### Job 생성 시 옵션

```json
{
  "title": "PK-12345 코드 리뷰",
  "prompt": "/ai-dev.review",
  "work_dir": "~/Dev/Repo/kidsnote_ios",
  "priority": 3,
  "time_slot": "sleep",
  "scheduled_at": "2026-03-16T22:00:00",
  "max_budget": 3.0,
  "timeout_min": 60,
  "model": "opus",
  "effort": "high",
  "use_worktree": false,
  "blocked_by": ["job_abc123"],
  "max_retries": 2
}
```

| 필드 | 기본값 | 설명 |
|------|--------|------|
| `priority` | `5` | 우선순위 (1=최우선, 10=최후순) |
| `time_slot` | `anytime` | 실행 시간대 |
| `scheduled_at` | `null` | 특정 시각 이후에만 실행 (ISO 8601) |
| `max_budget` | `2.0` | 이 Job의 최대 비용 (USD) |
| `timeout_min` | `30` | 타임아웃 (분) |
| `model` | `sonnet` | Claude 모델 |
| `use_worktree` | `false` | Git worktree 격리 실행 |
| `blocked_by` | `[]` | 선행 Job ID 목록 |
| `max_retries` | `2` | 최대 재시도 횟수 |

---

## Testing

```bash
# 전체 테스트 실행 (112 tests)
uv run pytest

# 특정 모듈
uv run pytest tests/test_scheduler.py -v

# 커버리지
uv run pytest --cov=command_center
```

### 테스트 구조

```
tests/
├── conftest.py           # 공통 fixture (임시 DB, mock)
├── test_api.py           # API endpoint 통합 테스트
├── test_budget_guard.py  # 예산 로직 단위 테스트
├── test_db.py            # DB CRUD 단위 테스트
├── test_dispatcher.py    # Dispatcher 로직 테스트
├── test_executor.py      # Job 실행 테스트 (mock subprocess)
├── test_integrator.py    # Ecosystem 통합 테스트
├── test_monitor.py       # WebSocket monitor 테스트
├── test_run_job.py       # run_job 통합 테스트
└── test_scheduler.py     # 스케줄러 로직 테스트
```

**테스트 레벨**:
- **Level 1**: Pure function 단위 테스트 (scheduler, budget_guard)
- **Level 2**: DB CRUD 테스트 (임시 SQLite)
- **Level 3**: Service 통합 테스트 (mock subprocess)
- **Level 4**: API endpoint 테스트 (httpx AsyncClient)

---

## Project Structure

```
command-center/
├── src/command_center/
│   ├── main.py              # FastAPI 앱 + lifespan
│   ├── config.py            # 환경변수 + 기본값
│   ├── db.py                # aiosqlite DB layer
│   ├── dispatcher.py        # launchd 독립 실행 엔트리포인트
│   ├── models.py            # Pydantic v2 모델
│   ├── routers/
│   │   ├── jobs.py          # Job CRUD API
│   │   ├── time_slots.py    # Time Slot 관리 API
│   │   ├── budget.py        # 예산 API
│   │   ├── dashboard.py     # 대시보드 집계 API
│   │   ├── sessions.py      # 세션 모니터 API
│   │   └── ecosystem.py     # 생태계 통합 API
│   └── services/
│       ├── scheduler.py     # Job 선택 알고리즘
│       ├── executor.py      # claude --print subprocess
│       ├── budget_guard.py  # 이중 예산 보호
│       ├── monitor.py       # WebSocket 세션 모니터
│       └── integrator.py    # Sentinel + Rhythm 연동
├── frontend/
│   └── src/
│       ├── App.tsx           # 메인 (3-tab: Kanban/Timeline/Ecosystem)
│       ├── components/
│       │   ├── kanban/       # KanbanBoard, KanbanColumn, JobCard
│       │   ├── timeline/     # DayTimeline, BudgetGauge
│       │   ├── job/          # JobForm (Job 생성 모달)
│       │   ├── session/      # SessionPanel, SessionBadge
│       │   └── ecosystem/    # EcosystemPanel
│       ├── hooks/
│       │   └── useWebSocket.ts
│       └── lib/
│           └── api.ts        # React Query + fetch wrapper
├── scripts/
│   ├── dev.sh               # 개발 서버 실행 (backend + frontend)
│   └── install_launchd.sh   # launchd plist 등록
├── tests/                    # pytest 테스트 (112개)
├── docs/
│   └── build-vs-buy.md      # 아키텍처 의사결정 기록
├── pyproject.toml
└── LICENSE                   # MIT
```

---

## Job Lifecycle

```
                    ┌─────────┐
                    │ queued  │ ← Job 생성 시 초기 상태
                    └────┬────┘
                         │  Dispatcher가 선택
                         v
                    ┌──────────┐
                    │ scheduled│ (예약 시각 대기)
                    └────┬─────┘
                         │  실행 시작
                         v
                    ┌─────────┐
               ┌────│ running │────┐
               │    └─────────┘    │
               v                   v
        ┌───────────┐      ┌────────┐
        │ completed │      │ failed │
        └───────────┘      └───┬────┘
                               │  retry_count < max_retries?
                               v
                          ┌─────────┐
                          │ queued  │ (재시도)
                          └─────────┘

        사용자가 직접 취소:
        queued/scheduled → cancelled
```

---

## Inspired By

| Project | 영감을 받은 부분 |
|---------|-----------------|
| [Beads](https://github.com/steveyegge/beads) | `blocked_by` 의존성 기반 Task 선택 패턴 |
| [Symphony](https://github.com/openai/symphony) | 상태 머신 + 지수 백오프 재시도 |
| [Vibe Kanban](https://github.com/nicepkg/vibe-kanban) | AI 코딩 에이전트를 칸반 UI로 오케스트레이션 |

---

## License

[MIT](LICENSE) &copy; 2026 Allen Kim
