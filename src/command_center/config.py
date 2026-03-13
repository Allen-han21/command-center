"""Command Center 설정"""

import os
from pathlib import Path

# 런타임 데이터 디렉토리 (gitignore)
_data_dir_env = os.environ.get("COMMAND_CENTER_DATA_DIR", "~/.claude/command-center")
DATA_DIR = Path(_data_dir_env).expanduser()
DB_PATH = DATA_DIR / "jobs.db"
EVENTS_LOG = DATA_DIR / "events.jsonl"
TEMPLATES_DIR = DATA_DIR / "templates"
DISPATCHER_LOG = DATA_DIR / "dispatcher.log"

# 프론트엔드 dist
FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

# 서버
HOST = "127.0.0.1"
PORT = int(os.environ.get("COMMAND_CENTER_PORT", "8280"))

# 예산
DAILY_BUDGET_USD = float(os.environ.get("DAILY_BUDGET_USD", "10.0"))

# Claude CLI 기본값
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "sonnet")
DEFAULT_EFFORT = os.environ.get("DEFAULT_EFFORT", "high")

# Time slot 기본값
DEFAULT_TIME_SLOTS = [
    {"name": "sleep", "start_time": "22:00", "end_time": "08:00", "max_concurrent": 2, "enabled": True},
    {"name": "lunch", "start_time": "12:00", "end_time": "13:00", "max_concurrent": 1, "enabled": True},
    {"name": "commute", "start_time": "18:00", "end_time": "19:00", "max_concurrent": 1, "enabled": True},
    {"name": "anytime", "start_time": None, "end_time": None, "max_concurrent": 1, "enabled": False},
]
