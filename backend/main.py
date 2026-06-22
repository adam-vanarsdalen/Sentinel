"""Sentinel Stack — FastAPI application entrypoint."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from api import agents, alerts, audit, compliance, dashboard, kill_switch, policies, proxy
from config import settings
from middleware.request_id import RequestIdMiddleware


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
        await pubsub.psubscribe("sentinel:alerts:*")
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                try:
                    data = json.loads(message["data"])
                    await manager.broadcast("alerts", data)
                except Exception:
                    pass

    task = asyncio.create_task(_pubsub_relay())
    yield
    task.cancel()
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


@app.websocket("/ws/metrics")
async def ws_metrics(websocket: WebSocket):
    await manager.connect(websocket, "metrics")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, "metrics")


@app.get("/health")
async def health():
    return {"status": "ok"}
