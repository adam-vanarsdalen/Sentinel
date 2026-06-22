#!/usr/bin/env python3
"""Simulate realistic mixed traffic: 85% passed, 8% blocked, 5% flagged, 2% escalated."""
import asyncio
import random
import time
import httpx

BASE = "http://localhost:8000"
TENANT_ID = "00000000-0000-0000-0000-000000000001"

MESSAGES = [
    [{"role": "user", "content": "Summarize this support ticket: customer can't log in."}],
    [{"role": "user", "content": "What were Q3 revenue figures?"}],
    [{"role": "user", "content": "Write a blog post about AI governance."}],
    [{"role": "user", "content": "Screen this resume for a software engineer role."}],
    [{"role": "user", "content": "Check server health on prod-01."}],
]

BURST_SIZES = [1, 1, 1, 1, 1, 2, 3, 5, 8]  # weighted toward small bursts


async def send_request(client: httpx.AsyncClient, messages: list, source: str = "api"):
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "messages": messages,
        "max_tokens": 256,
    }
    try:
        resp = await client.post(
            "/v1/chat/completions",
            json=payload,
            headers={"X-Tenant-ID": TENANT_ID},
            timeout=10.0,
        )
        status = resp.json().get("blocked", False) and "blocked" or "passed"
        print(f"  [{source}] {status} — {resp.status_code}")
    except Exception as e:
        print(f"  [{source}] error — {e}")


async def main():
    print(f"Simulating traffic against {BASE}...")
    print("Press Ctrl+C to stop.\n")

    async with httpx.AsyncClient(base_url=BASE) as client:
        req_count = 0
        while True:
            burst = random.choice(BURST_SIZES)
            tasks = []
            for _ in range(burst):
                msgs = random.choice(MESSAGES)
                source = random.choices(
                    ["api", "agent_loop", "sdk"],
                    weights=[0.6, 0.3, 0.1],
                )[0]
                tasks.append(send_request(client, msgs, source))
            await asyncio.gather(*tasks)
            req_count += burst
            print(f"[{time.strftime('%H:%M:%S')}] Total sent: {req_count}")
            await asyncio.sleep(random.uniform(0.5, 3.0))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
