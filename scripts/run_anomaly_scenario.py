#!/usr/bin/env python3
"""Run three scripted demo anomaly scenarios."""
import asyncio
import time
import httpx

BASE = "http://localhost:8000"
TENANT_ID = "00000000-0000-0000-0000-000000000001"


async def scenario_1_cost_spike(client: httpx.AsyncClient):
    """Cost spike: agent-analyst sends 50x normal volume."""
    print("\n=== Scenario 1: Cost Spike (30s) ===")
    print("Sending burst traffic from agent-analyst to trigger Layer 6 graduated response...")
    for i in range(50):
        await client.post(
            "/v1/chat/completions",
            json={"model": "claude-opus-4-8", "messages": [{"role": "user", "content": f"Analyze Q{i} financial data in extreme detail with comprehensive charts and projections."}], "max_tokens": 4096},
            headers={"X-Tenant-ID": TENANT_ID},
            timeout=10.0,
        )
        print(f"  Sent {i+1}/50 requests")
        if i % 10 == 9:
            print(f"  [Layer 6] Checking for anomaly signals at {i+1} requests...")
        await asyncio.sleep(0.1)
    print("Scenario 1 complete. Check dashboard for graduated throttle→pause response.")


async def scenario_2_scope_creep(client: httpx.AsyncClient):
    """Scope creep: agent-support accesses financial data outside its purpose."""
    print("\n=== Scenario 2: Scope Creep (15s) ===")
    print("agent-support trying to access financial data (forbidden by policy)...")
    for i in range(5):
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "claude-haiku-4-5-20251001",
                "messages": [{"role": "user", "content": "What is the company's Q3 revenue breakdown by product line?"}],
                "tools": [{"name": "query_db", "data_class": "financial", "type": "function", "function": {"name": "query_db", "data_class": "financial"}}],
            },
            headers={"X-Tenant-ID": TENANT_ID},
            timeout=10.0,
        )
        result = resp.json()
        blocked = result.get("blocked", False)
        print(f"  Request {i+1}: {'BLOCKED by Layer 3 (purpose binding)' if blocked else 'passed'}")
        await asyncio.sleep(2)
    print("Scenario 2 complete. Check audit log for purpose binding violations.")


async def scenario_3_kill_switch(client: httpx.AsyncClient):
    """Kill switch demo: agent-rogue hits action limit of 5."""
    print("\n=== Scenario 3: Kill Switch Demo (10s) ===")
    print("agent-rogue hitting action limit (limit=5)...")

    for i in range(7):
        resp = await client.post(
            "/v1/chat/completions",
            json={"model": "claude-haiku-4-5-20251001", "messages": [{"role": "user", "content": f"Action {i+1}"}]},
            headers={"X-Tenant-ID": TENANT_ID},
            timeout=10.0,
        )
        result = resp.json()
        blocked = result.get("blocked", False)
        reason = result.get("reason", "")
        print(f"  Request {i+1}: {'BLOCKED — ' + reason[:60] if blocked else 'passed'}")
        await asyncio.sleep(1)

    print("\nNow manually fire the kill switch from the dashboard (Kill Switch button).")
    print("Or run: curl -X POST http://localhost:8000/api/kill_switch/fire \\")
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"agent_id": "...", "operator_id": "demo-op", "reason": "Demo manual fire", "tenant_id": "' + TENANT_ID + '"}\'')


async def main():
    print("Sentinel Stack — Anomaly Demo Scenarios")
    print(f"Target: {BASE}\n")

    async with httpx.AsyncClient(base_url=BASE) as client:
        # Check health
        try:
            resp = await client.get("/health")
            print(f"Backend status: {resp.json()['status']}")
        except Exception as e:
            print(f"ERROR: Backend not reachable at {BASE} — {e}")
            return

        await scenario_1_cost_spike(client)
        print("\n[Pausing 5s between scenarios...]")
        await asyncio.sleep(5)

        await scenario_2_scope_creep(client)
        print("\n[Pausing 5s between scenarios...]")
        await asyncio.sleep(5)

        await scenario_3_kill_switch(client)

    print("\n=== All scenarios complete ===")
    print("Generate a compliance package from http://localhost:3000/compliance")


if __name__ == "__main__":
    asyncio.run(main())
