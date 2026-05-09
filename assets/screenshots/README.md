# Screenshot Assets

Store real public README and documentation screenshots in this directory.

Do not commit mockups, generated placeholders, screenshots with local secrets, or screenshots that show private customer data.

## Required Screenshots

| File | View | Purpose |
|---|---|---|
| `dashboard.png` | Dashboard | Shows request volume, risk summary, provider/model usage, and recent governance activity. |
| `policy-editor.png` | Policy editor | Shows model allowlists, request limits, policy checks, and publish/version controls. |
| `provider-settings.png` | Provider settings | Shows provider configuration cards, enabled providers, model defaults, and resilience settings. |
| `audit-log.png` | Audit log | Shows filters, event outcomes, risk flags, request IDs, and export controls. |
| `blocked-request-demo.png` | Blocked request demo | Shows a policy-denied request and the corresponding audit evidence. |

## Capture Guidance

Use the seeded demo environment and avoid entering real provider credentials. If a screenshot needs a configured provider state, use demo-safe placeholder values only.

Recommended viewport: desktop Chromium at `1440x1000`.

The optional Playwright capture script writes these files directly into this directory:

```bash
docker compose up --build
cd frontend
CAPTURE_SCREENSHOTS=1 npm run screenshots
```

The script expects the local frontend at `http://localhost:3000` and backend at `http://localhost:8000` unless overridden with `PLAYWRIGHT_BASE_URL` and `E2E_BACKEND_BASE_URL`.
