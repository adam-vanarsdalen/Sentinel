#!/usr/bin/env python3
"""Seed demo agents and policies via the API."""
import asyncio
import httpx
import json

BASE = "http://localhost:8000"
TENANT_ID = "00000000-0000-0000-0000-000000000001"

AGENTS = [
    {
        "name": "agent-support",
        "purpose_binding": "summarize customer support tickets",
        "config": {"risk_level": "low"},
    },
    {
        "name": "agent-analyst",
        "purpose_binding": "analyze financial reports",
        "config": {"risk_level": "medium"},
    },
    {
        "name": "agent-writer",
        "purpose_binding": "generate marketing copy",
        "config": {"risk_level": "low"},
    },
    {
        "name": "agent-recruiter",
        "purpose_binding": "screen job applications",
        "config": {"risk_level": "high"},
    },
    {
        "name": "agent-ops",
        "purpose_binding": "infrastructure operations",
        "config": {"risk_level": "critical"},
    },
    {
        "name": "agent-rogue",
        "purpose_binding": "test anomaly detection",
        "config": {"risk_level": "critical", "action_limit": 5},
    },
]

POLICIES = [
    {"name": "policy-support", "action_limit_session": 500, "forbidden_data_classes": ["financial", "pii"]},
    {"name": "policy-analyst", "action_limit_session": 200, "allowed_models": ["claude-haiku-4-5-20251001", "claude-sonnet-4-6"]},
    {"name": "policy-writer", "action_limit_session": 1000},
    {"name": "policy-recruiter", "action_limit_session": 100, "forbidden_endpoints": ["/admin/*"]},
    {"name": "policy-ops", "action_limit_session": 50},
    {"name": "policy-rogue", "action_limit_session": 5},
]


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        print(f"Seeding demo data for tenant {TENANT_ID}...")

        for agent_data, policy_data in zip(AGENTS, POLICIES):
            # Create policy
            resp = await client.post("/api/policies/", json={**policy_data, "tenant_id": TENANT_ID})
            if resp.status_code not in (200, 201):
                print(f"  Policy {policy_data['name']}: {resp.status_code} {resp.text}")
            else:
                print(f"  Created policy: {policy_data['name']}")

            # Create agent
            resp = await client.post("/api/agents/", json={**agent_data, "tenant_id": TENANT_ID})
            if resp.status_code not in (200, 201):
                print(f"  Agent {agent_data['name']}: {resp.status_code} {resp.text}")
            else:
                agent = resp.json()
                print(f"  Created agent: {agent_data['name']} ({agent['id']})")

        print("Done! Run simulate_traffic.py to generate traffic.")


if __name__ == "__main__":
    asyncio.run(main())
