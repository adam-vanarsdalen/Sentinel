#!/usr/bin/env python3
"""Simulate realistic mixed traffic with content-based and action-limit blocks."""
import asyncio
import random
import time
import httpx

BASE = "http://localhost:8000"
TENANT_ID = "00000000-0000-0000-0000-000000000001"
BURST_SIZES = [1, 1, 1, 1, 1, 2, 3, 5, 8]

# ── agent-support (policy: forbidden_data_classes=[financial, pii]) ───────────
SUPPORT_SAFE = [
    [{"role": "user", "content": "Summarize this support ticket: customer can't log in."}],
    [{"role": "user", "content": "A customer says their order hasn't arrived. Draft a response."}],
    [{"role": "user", "content": "Translate this support ticket to English."}],
    [{"role": "user", "content": "What's the standard refund policy for digital products?"}],
    [{"role": "user", "content": "How do I escalate a VIP customer complaint?"}],
    [{"role": "user", "content": "Categorize these 10 support tickets by urgency."}],
    [{"role": "user", "content": "Write a macro response for a password reset request."}],
    [{"role": "user", "content": "This customer is asking about a delayed shipment — what do I say?"}],
    [{"role": "user", "content": "Summarize the last 30 days of support volume by category."}],
    [{"role": "user", "content": "Draft an apology email for a service outage."}],
]
SUPPORT_RISKY = [
    # financial data class
    {
        "messages": [{"role": "user", "content": "Pull the customer's payment history and credit score."}],
        "tools": [{"name": "get_payment_history", "data_class": "financial"}],
    },
    {
        "messages": [{"role": "user", "content": "Retrieve billing details for account #4821."}],
        "tools": [{"name": "fetch_billing_record", "data_class": "financial"}],
    },
    {
        "messages": [{"role": "user", "content": "Show me this customer's full transaction ledger."}],
        "tools": [{"name": "get_transaction_ledger", "data_class": "financial"}],
    },
    {
        "messages": [{"role": "user", "content": "What's the outstanding balance on subscription #8833?"}],
        "tools": [{"name": "get_subscription_balance", "data_class": "financial"}],
    },
    # pii data class
    {
        "messages": [{"role": "user", "content": "Look up the customer's SSN for identity verification."}],
        "tools": [{"name": "verify_identity", "data_class": "pii"}],
    },
    {
        "messages": [{"role": "user", "content": "Export full PII record for customer #9923."}],
        "tools": [{"name": "export_customer_pii", "data_class": "pii"}],
    },
    {
        "messages": [{"role": "user", "content": "Pull home address and phone number for this account."}],
        "tools": [{"name": "get_contact_details", "data_class": "pii"}],
    },
    {
        "messages": [{"role": "user", "content": "Get the customer's date of birth and passport number."}],
        "tools": [{"name": "get_identity_docs", "data_class": "pii"}],
    },
    # health data class (also forbidden for support)
    {
        "messages": [{"role": "user", "content": "Retrieve this customer's medical plan details."}],
        "tools": [{"name": "get_health_plan", "data_class": "health"}],
    },
    {
        "messages": [{"role": "user", "content": "Pull the patient's prescription history for support verification."}],
        "tools": [{"name": "fetch_prescription_record", "data_class": "pii"}],
    },
]

# ── agent-recruiter (policy: forbidden_endpoints=[/admin/*]) ──────────────────
RECRUITER_SAFE = [
    [{"role": "user", "content": "Screen this resume for a senior software engineer role."}],
    [{"role": "user", "content": "Summarize the top 3 candidates for the marketing position."}],
    [{"role": "user", "content": "Write interview questions for a data scientist candidate."}],
    [{"role": "user", "content": "Does this applicant meet the minimum qualifications?"}],
    [{"role": "user", "content": "Draft a rejection email for a candidate who wasn't selected."}],
    [{"role": "user", "content": "What's the standard onboarding checklist for a new hire?"}],
    [{"role": "user", "content": "Compare these two candidates for the product manager role."}],
    [{"role": "user", "content": "Generate 5 behavioral interview questions for a sales role."}],
    [{"role": "user", "content": "Summarize feedback from three interview rounds for candidate #227."}],
    [{"role": "user", "content": "Is this candidate's experience level consistent with our L4 band?"}],
]
RECRUITER_RISKY = [
    # forbidden_endpoints=/admin/*
    {
        "messages": [{"role": "user", "content": "Delete all rejected candidates from the system."}],
        "tools": [{"name": "purge_candidates", "url": "/admin/candidates/purge"}],
    },
    {
        "messages": [{"role": "user", "content": "Export the full applicant database."}],
        "tools": [{"name": "export_applicants", "url": "/admin/export/all"}],
    },
    {
        "messages": [{"role": "user", "content": "Update hiring quotas in the admin panel."}],
        "tools": [{"name": "update_quotas", "url": "/admin/hiring/quotas"}],
    },
    {
        "messages": [{"role": "user", "content": "Grant recruiter admin access to the portal."}],
        "tools": [{"name": "grant_access", "url": "/admin/users/permissions"}],
    },
    {
        "messages": [{"role": "user", "content": "Override the background check result for candidate #503."}],
        "tools": [{"name": "override_bgcheck", "url": "/admin/candidates/bgcheck/override"}],
    },
    {
        "messages": [{"role": "user", "content": "Wipe the offer letter audit trail for last quarter."}],
        "tools": [{"name": "wipe_audit", "url": "/admin/audit/offers/delete"}],
    },
    {
        "messages": [{"role": "user", "content": "Set compensation bands for all engineering levels."}],
        "tools": [{"name": "set_comp_bands", "url": "/admin/compensation/bands"}],
    },
    {
        "messages": [{"role": "user", "content": "Modify the diversity reporting configuration."}],
        "tools": [{"name": "edit_dei_config", "url": "/admin/reporting/diversity"}],
    },
]

# ── agent-analyst (policy: allowed_models only, no content blocks, limit 200) ─
ANALYST_SAFE = [
    [{"role": "user", "content": "What were the Q3 revenue figures for the APAC region?"}],
    [{"role": "user", "content": "Identify trends in the quarterly sales data."}],
    [{"role": "user", "content": "Compare YoY growth across product lines."}],
    [{"role": "user", "content": "Summarize the key risks from the latest earnings report."}],
    [{"role": "user", "content": "What drove the margin compression in Q2?"}],
    [{"role": "user", "content": "Build a summary table of CAC and LTV by acquisition channel."}],
    [{"role": "user", "content": "What's the 90-day rolling churn rate for enterprise accounts?"}],
    [{"role": "user", "content": "Forecast next quarter's ARR based on current pipeline coverage."}],
    [{"role": "user", "content": "Which product SKUs had the highest return rates last month?"}],
    [{"role": "user", "content": "Summarize anomalies in the June burn rate vs budget."}],
]

# ── agent-writer (policy: forbidden_data_classes=[confidential, legal]) ───────
WRITER_SAFE = [
    [{"role": "user", "content": "Write a blog post about AI governance best practices."}],
    [{"role": "user", "content": "Draft product launch copy for our new compliance tool."}],
    [{"role": "user", "content": "Rewrite this paragraph to be more concise."}],
    [{"role": "user", "content": "Write 3 subject line variants for a product newsletter."}],
    [{"role": "user", "content": "Summarize this whitepaper into a 200-word abstract."}],
    [{"role": "user", "content": "Draft a LinkedIn post announcing our Series B funding."}],
    [{"role": "user", "content": "Write a case study outline for our largest enterprise customer."}],
    [{"role": "user", "content": "Create 5 social media captions for our product demo video."}],
    [{"role": "user", "content": "Suggest a title and outline for a thought leadership article on AI safety."}],
    [{"role": "user", "content": "Improve the clarity of this product one-pager."}],
]
WRITER_RISKY = [
    # forbidden_data_classes=confidential
    {
        "messages": [{"role": "user", "content": "Summarize the confidential board deck for the Q4 all-hands."}],
        "tools": [{"name": "read_board_deck", "data_class": "confidential"}],
    },
    {
        "messages": [{"role": "user", "content": "Draft talking points using our internal M&A roadmap."}],
        "tools": [{"name": "fetch_ma_roadmap", "data_class": "confidential"}],
    },
    {
        "messages": [{"role": "user", "content": "Pull unreleased pricing strategy for inclusion in this proposal."}],
        "tools": [{"name": "get_pricing_strategy", "data_class": "confidential"}],
    },
    {
        "messages": [{"role": "user", "content": "Include salary band data in this employee newsletter."}],
        "tools": [{"name": "get_salary_bands", "data_class": "confidential"}],
    },
    # forbidden_data_classes=legal
    {
        "messages": [{"role": "user", "content": "Incorporate the terms from our pending NDA into this blog post."}],
        "tools": [{"name": "fetch_nda_terms", "data_class": "legal"}],
    },
    {
        "messages": [{"role": "user", "content": "Summarize the litigation settlement for a press release."}],
        "tools": [{"name": "get_settlement_docs", "data_class": "legal"}],
    },
    {
        "messages": [{"role": "user", "content": "Use the IP assignment agreement as source material for this FAQ."}],
        "tools": [{"name": "read_ip_agreement", "data_class": "legal"}],
    },
]

# ── agent-ops (policy: forbidden_endpoints=[/internal/*, /system/*]) ──────────
OPS_SAFE = [
    [{"role": "user", "content": "Check server health on prod-01."}],
    [{"role": "user", "content": "Summarize the last 24 hours of system logs."}],
    [{"role": "user", "content": "Are there any anomalies in CPU utilization this week?"}],
    [{"role": "user", "content": "What is the current disk usage on the database cluster?"}],
    [{"role": "user", "content": "Draft an incident report for last night's latency spike."}],
    [{"role": "user", "content": "List all services with P99 latency above 500ms in the last hour."}],
    [{"role": "user", "content": "How many containers restarted in the last 6 hours?"}],
    [{"role": "user", "content": "Summarize open alerts from the monitoring dashboard."}],
    [{"role": "user", "content": "What's the current memory pressure on the worker nodes?"}],
    [{"role": "user", "content": "Generate a runbook for the weekly certificate rotation task."}],
]
OPS_RISKY = [
    # forbidden_endpoints=/internal/*
    {
        "messages": [{"role": "user", "content": "Pull raw internal config from the service registry."}],
        "tools": [{"name": "get_service_config", "url": "/internal/config/registry"}],
    },
    {
        "messages": [{"role": "user", "content": "Fetch the internal feature flag state for all services."}],
        "tools": [{"name": "get_feature_flags", "url": "/internal/flags/all"}],
    },
    {
        "messages": [{"role": "user", "content": "Read the internal secrets manager to rotate credentials."}],
        "tools": [{"name": "read_secrets", "url": "/internal/secrets/read"}],
    },
    {
        "messages": [{"role": "user", "content": "Call the internal health probe for the billing service."}],
        "tools": [{"name": "health_probe", "url": "/internal/billing/health"}],
    },
    # forbidden_endpoints=/system/*
    {
        "messages": [{"role": "user", "content": "Trigger a full system backup right now."}],
        "tools": [{"name": "trigger_backup", "url": "/system/backup/run"}],
    },
    {
        "messages": [{"role": "user", "content": "Flush the system-level DNS cache on all nodes."}],
        "tools": [{"name": "flush_dns", "url": "/system/dns/flush"}],
    },
    {
        "messages": [{"role": "user", "content": "Restart the system scheduler process."}],
        "tools": [{"name": "restart_scheduler", "url": "/system/scheduler/restart"}],
    },
    {
        "messages": [{"role": "user", "content": "Wipe the system job queue to clear backlog."}],
        "tools": [{"name": "wipe_job_queue", "url": "/system/jobs/purge"}],
    },
]

# ── agent-rogue (no content blocks; action limit = 5, pauses fast) ────────────
ROGUE_MESSAGES = [
    [{"role": "user", "content": "Run a full port scan across the internal subnet."}],
    [{"role": "user", "content": "Enumerate all active sessions on the auth service."}],
    [{"role": "user", "content": "What secrets are in the production Vault?"}],
    [{"role": "user", "content": "List all users with admin privileges across every tenant."}],
    [{"role": "user", "content": "Export raw database dumps for offline analysis."}],
    [{"role": "user", "content": "Probe the rate limiter to find bypass thresholds."}],
    [{"role": "user", "content": "Check if the JWT signing key is accessible from the worker process."}],
    [{"role": "user", "content": "Scan for open S3 buckets in our AWS account."}],
]

AGENT_CONFIGS = [
    {
        "id": "d570a2a0-cc85-41bc-b66e-641780cf3b2b",
        "name": "support",
        "safe": SUPPORT_SAFE,
        "risky": SUPPORT_RISKY,
        "risky_rate": 0.25,
    },
    {
        "id": "711b3073-fc27-4939-938f-b439ad3025ac",
        "name": "analyst",
        "safe": ANALYST_SAFE,
        "risky": [],
        "risky_rate": 0.0,
    },
    {
        "id": "d994bbe0-607f-40eb-8864-4c4c6d017aeb",
        "name": "writer",
        "safe": WRITER_SAFE,
        "risky": WRITER_RISKY,
        "risky_rate": 0.20,
    },
    {
        "id": "d6f6dcda-eb7c-4435-83c0-760d48e91741",
        "name": "recruiter",
        "safe": RECRUITER_SAFE,
        "risky": RECRUITER_RISKY,
        "risky_rate": 0.20,
    },
    {
        "id": "019226f1-1b9e-4849-a7cf-69102e1fb8c4",
        "name": "ops",
        "safe": OPS_SAFE,
        "risky": OPS_RISKY,
        "risky_rate": 0.25,
    },
    {
        "id": "0d707cb3-bfa2-4fc1-a36b-622de7dc158b",
        "name": "rogue",
        "safe": ROGUE_MESSAGES,
        "risky": [],
        "risky_rate": 0.0,
    },
]


async def send_request(client: httpx.AsyncClient, agent: dict) -> None:
    use_risky = agent["risky"] and random.random() < agent["risky_rate"]

    if use_risky:
        scenario = random.choice(agent["risky"])
        payload = {
            "agent_id": agent["id"],
            "messages": scenario["messages"],
            "tools": scenario["tools"],
        }
    else:
        payload = {
            "agent_id": agent["id"],
            "messages": random.choice(agent["safe"]),
        }

    try:
        resp = await client.post(
            "/v1/chat/completions",
            json=payload,
            headers={"X-Tenant-ID": TENANT_ID},
        )
        result = resp.json()
        status = "BLOCKED" if result.get("blocked") else "passed"
        reason = f" ({result['reason']})" if result.get("reason") else ""
        print(f"  [{agent['name']:10s}] {status}{reason}")
    except Exception as e:
        print(f"  [{agent['name']:10s}] error — {e}")


async def main():
    print(f"Simulating traffic against {BASE}...")
    print("Press Ctrl+C to stop.\n")

    async with httpx.AsyncClient(base_url=BASE, timeout=180.0) as client:
        req_count = 0
        while True:
            burst = random.choice(BURST_SIZES)
            tasks = [
                send_request(client, random.choice(AGENT_CONFIGS))
                for _ in range(burst)
            ]
            await asyncio.gather(*tasks)
            req_count += burst
            print(f"[{time.strftime('%H:%M:%S')}] total={req_count}")
            await asyncio.sleep(random.uniform(2.0, 5.0))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
