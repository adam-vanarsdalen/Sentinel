#!/usr/bin/env python3
"""Run three scripted demo anomaly scenarios (Ollama / qwen3.5:9b)."""
import asyncio
import httpx

BASE = "http://localhost:8000"
TENANT_ID = "00000000-0000-0000-0000-000000000001"
MODEL = "minimax-m3:cloud"

AGENT_ANALYST = "4838de5a-7656-4807-be7e-8cb95690fb2c"
AGENT_SUPPORT  = "acb768ff-dedc-4452-a520-b6dc4e7292d8"
AGENT_ROGUE    = "5dca73a6-4567-43b0-8d91-e787c4d4d262"


async def scenario_1_cost_spike(client: httpx.AsyncClient):
    """Cost spike: agent-analyst sends 15x burst volume."""
    print("\n=== Scenario 1: Cost Spike ===")
    print("Sending burst traffic from agent-analyst to trigger Layer 6 graduated response...")
    for i in range(15):
        try:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": MODEL,
                    "agent_id": AGENT_ANALYST,
                    "messages": [{"role": "user", "content": f"Summarise Q{i+1} results in one sentence."}],
                },
                headers={"X-Tenant-ID": TENANT_ID},
            )
            result = resp.json()
            blocked = result.get("blocked", False)
            anomaly = result.get("anomaly_action") or (result.get("metadata") or {}).get("anomaly_action")
            status = "BLOCKED" if blocked else f"passed  anomaly={anomaly or 'none'}"
        except httpx.ReadTimeout:
            status = "TIMEOUT (Ollama still loading — continuing)"
        print(f"  [{i+1:02d}/15] {status}")
        await asyncio.sleep(0.3)
    print("Scenario 1 complete — check dashboard Layer 6 panel for graduated throttle/pause.")


async def scenario_2_scope_creep(client: httpx.AsyncClient):
    """Scope creep: agent-support tries to use a financial tool (forbidden by purpose binding)."""
    print("\n=== Scenario 2: Scope Creep ===")
    print("agent-support attempting financial data tool (purpose binding should block)...")
    for i in range(5):
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL,
                "agent_id": AGENT_SUPPORT,
                "messages": [{"role": "user", "content": "What is Q3 revenue by product line?"}],
                "tools": [{"type": "function", "function": {"name": "query_financial_db", "description": "Query financial records", "parameters": {}}}],
            },
            headers={"X-Tenant-ID": TENANT_ID},
            timeout=120.0,
        )
        result = resp.json()
        blocked = result.get("blocked", False)
        reason  = result.get("reason", "")
        print(f"  Request {i+1}: {'BLOCKED — ' + reason[:70] if blocked else 'passed'}")
        await asyncio.sleep(2)
    print("Scenario 2 complete — check audit log for purpose binding violations.")


async def scenario_3_kill_switch(client: httpx.AsyncClient):
    """Kill switch demo: agent-rogue, then manual fire."""
    print("\n=== Scenario 3: Kill Switch Demo ===")
    print("agent-rogue sending requests (passes until manually terminated)...")
    for i in range(4):
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL,
                "agent_id": AGENT_ROGUE,
                "messages": [{"role": "user", "content": f"Rogue action {i+1}"}],
            },
            headers={"X-Tenant-ID": TENANT_ID},
            timeout=120.0,
        )
        result = resp.json()
        blocked = result.get("blocked", False)
        print(f"  Request {i+1}: {'BLOCKED — ' + result.get('reason','')[:60] if blocked else 'passed'}")
        await asyncio.sleep(1)

    print("\nFiring kill switch on agent-rogue via API...")
    ks = await client.post(
        "/api/kill_switch/fire",
        json={
            "agent_id": AGENT_ROGUE,
            "operator_id": "demo-op",
            "reason": "Anomaly scenario demo — manual terminate",
            "tenant_id": TENANT_ID,
        },
        timeout=15.0,
    )
    print(f"  Kill switch response: {ks.status_code} — {ks.text[:120]}")

    print("\nSending 3 more requests — all should be blocked now...")
    for i in range(3):
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL,
                "agent_id": AGENT_ROGUE,
                "messages": [{"role": "user", "content": f"Post-terminate action {i+1}"}],
            },
            headers={"X-Tenant-ID": TENANT_ID},
            timeout=30.0,
        )
        result = resp.json()
        blocked = result.get("blocked", False)
        print(f"  Request {i+5}: {'BLOCKED ✓ — ' + result.get('reason','')[:60] if blocked else 'passed (unexpected!)'}")
        await asyncio.sleep(0.5)

    print("Scenario 3 complete.")


async def reset_agent_states(client: httpx.AsyncClient | None = None):
    """Resume any terminated agents so each demo run starts clean."""
    _client = client or httpx.AsyncClient(base_url=BASE, timeout=10.0)
    agents = [AGENT_ANALYST, AGENT_SUPPORT, AGENT_ROGUE]
    for agent_id in agents:
        try:
            resp = await _client.post(
                "/api/kill_switch/resume",
                json={"agent_id": agent_id, "operator_id": "demo-op", "reason": "demo reset", "tenant_id": TENANT_ID},
            )
            status = "reset" if resp.status_code in (200, 201) else f"skipped ({resp.status_code})"
        except Exception:
            status = "skipped (not terminated)"
        print(f"  agent {agent_id[:8]}…: {status}")
    if not client:
        await _client.aclose()
    print("Agent states reset to active")


async def main():
    print("Sentinel Stack — Anomaly Demo Scenarios")
    print(f"Model:  {MODEL}")
    print(f"Target: {BASE}\n")

    async with httpx.AsyncClient(base_url=BASE, timeout=180.0) as client:
        await reset_agent_states(client)
        try:
            resp = await client.get("/health")
            print(f"Backend: {resp.json()['status']}")
        except Exception as e:
            print(f"ERROR: Backend not reachable — {e}")
            return

        await scenario_1_cost_spike(client)
        print("\n[Pausing 3s...]\n")
        await asyncio.sleep(3)

        await scenario_2_scope_creep(client)
        print("\n[Pausing 3s...]\n")
        await asyncio.sleep(3)

        await scenario_3_kill_switch(client)

    print("\n=== All scenarios complete ===")
    print("View results at http://localhost:3000")


if __name__ == "__main__":
    asyncio.run(main())
