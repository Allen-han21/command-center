"""Command Center FastAPI 서버"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from command_center import db
from command_center.config import FRONTEND_DIST, HOST, PORT
from command_center.routers import budget, dashboard, ecosystem, jobs, sessions, time_slots
from command_center.services.monitor import start_monitor, stop_monitor

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    logger.info("DB 초기화 완료")
    start_monitor()
    logger.info("Command Center 준비 완료 → http://%s:%d", HOST, PORT)
    yield
    stop_monitor()
    logger.info("Command Center 종료")


app = FastAPI(
    title="Dominium Command Center",
    description="Claude Code 세션 오케스트레이터 - Kanban + Time Slot Scheduler",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "name": "command-center", "version": "0.1.0", "port": PORT}


app.include_router(jobs.router)
app.include_router(time_slots.router)
app.include_router(budget.router)
app.include_router(dashboard.router)
app.include_router(sessions.router)
app.include_router(ecosystem.router)

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


def run():
    uvicorn.run("command_center.main:app", host=HOST, port=PORT, reload=True)


if __name__ == "__main__":
    run()
