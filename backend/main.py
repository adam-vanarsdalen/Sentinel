"""Sentinel Stack — FastAPI application entrypoint."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from api import agents, alerts, audit, compliance, dashboard, kill_switch, policies, proxy
from config import settings
from database import AsyncSessionLocal
from middleware.request_id import RequestIdMiddleware
from models.audit_entry import AuditEntry


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {
            "requests": [], "alerts": [], "metrics": []
        }

    async def connect(self, ws: WebSocket, channel: str):
        await ws.accept()
        self.active.setdefault(channel, []).append(ws)

    def disconnect(self, ws: WebSocket, channel: str):
        self.active.get(channel, []).remove(ws) if ws in self.active.get(channel, []) else None

    async def broadcast(self, channel: str, data: dict[str, Any]):
        dead = []
        for ws in self.active.get(channel, []):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active[channel].remove(ws)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = await aioredis.from_url(settings.redis_url, decode_responses=False)
    app.state.redis = redis

    async def _pubsub_relay():
        pubsub = redis.pubsub()
        await pubsub.psubscribe("sentinel:alerts:*", "sentinel:requests:*")
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                try:
                    pattern = message["pattern"]
                    if isinstance(pattern, bytes):
                        pattern = pattern.decode()
                    data = json.loads(message["data"])
                    if ":alerts:" in pattern:
                        await manager.broadcast("alerts", data)
                    elif ":requests:" in pattern:
                        await manager.broadcast("requests", data)
                except Exception:
                    pass

    async def _metrics_broadcast():
        while True:
            await asyncio.sleep(2)
            if not manager.active.get("metrics"):
                continue
            try:
                cutoff = datetime.utcnow() - timedelta(seconds=60)
                async with AsyncSessionLocal() as session:
                    layer_rows = await session.execute(
                        select(AuditEntry.layer, func.count().label("cnt"))
                        .where(AuditEntry.created_at >= cutoff)
                        .group_by(AuditEntry.layer)
                    )
                    layer_rps = {
                        row.layer: round(row.cnt / 60, 3)
                        for row in layer_rows
                    }
                    total_row = await session.execute(
                        select(func.count())
                        .select_from(AuditEntry)
                        .where(
                            AuditEntry.created_at >= cutoff,
                            AuditEntry.action.in_(["pipeline_complete", "request_blocked"]),
                        )
                    )
                    total_rps = round((total_row.scalar() or 0) / 60, 3)
                await manager.broadcast("metrics", {
                    "layer_throughputs": layer_rps,
                    "total_rps": total_rps,
                })
            except Exception:
                pass

    relay_task = asyncio.create_task(_pubsub_relay())
    metrics_task = asyncio.create_task(_metrics_broadcast())
    yield
    relay_task.cancel()
    metrics_task.cancel()
    await redis.aclose()


app = FastAPI(title="Sentinel Stack", version="1.0.0", lifespan=lifespan)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(proxy.router)
app.include_router(agents.router)
app.include_router(policies.router)
app.include_router(alerts.router)
app.include_router(audit.router)
app.include_router(compliance.router)
app.include_router(dashboard.router)
app.include_router(kill_switch.router)


@app.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    await manager.connect(websocket, "alerts")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, "alerts")


@app.websocket("/ws/requests")
async def ws_requests(websocket: WebSocket):
    await manager.connect(websocket, "requests")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, "requests")


async def _send_current_metrics(ws: WebSocket) -> None:
    try:
        cutoff = datetime.utcnow() - timedelta(seconds=60)
        async with AsyncSessionLocal() as session:
            layer_rows = await session.execute(
                select(AuditEntry.layer, func.count().label("cnt"))
                .where(AuditEntry.created_at >= cutoff)
                .group_by(AuditEntry.layer)
            )
            layer_rps = {row.layer: round(row.cnt / 60, 3) for row in layer_rows}
            total_row = await session.execute(
                select(func.count()).select_from(AuditEntry)
                .where(
                    AuditEntry.created_at >= cutoff,
                    AuditEntry.action.in_(["pipeline_complete", "request_blocked"]),
                )
            )
            total_rps = round((total_row.scalar() or 0) / 60, 3)
        await ws.send_json({"layer_throughputs": layer_rps, "total_rps": total_rps})
    except Exception:
        pass


@app.websocket("/ws/metrics")
async def ws_metrics(websocket: WebSocket):
    await manager.connect(websocket, "metrics")
    await _send_current_metrics(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, "metrics")


@app.get("/health")
async def health():
    return {"status": "ok"}
