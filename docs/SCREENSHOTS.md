# Screenshots

Public release screenshots should be captured into `assets/screenshots/`.

Do not commit fake screenshots, local-only mockups, real secrets, provider keys, or customer data.

## Expected Files

| File | README placement | Documentation placement | Capture target |
|---|---|---|---|
| `assets/screenshots/dashboard.png` | First product screenshot in README once available. | Dashboard section in this file. | Dashboard overview with request volume, risk summary, provider/model usage, and recent governance activity. |
| `assets/screenshots/policy-editor.png` | Product screenshot gallery in README once available. | Policy Editor section in this file. | Policy editor with model allowlists, request limits, preflight rules, postflight checks, and publish/version controls. |
| `assets/screenshots/provider-settings.png` | Product screenshot gallery in README once available. | Provider Settings section in this file. | Provider settings with configured providers, enabled models, tenant defaults, and resilience settings. |
| `assets/screenshots/audit-log.png` | Product screenshot gallery in README once available. | Audit Log section in this file. | Audit log with filters, event outcomes, risk flags, request IDs, and export controls. |
| `assets/screenshots/blocked-request-demo.png` | Product screenshot gallery in README once available. | Blocked Request Demo section in this file. | Policy-denied gateway request with the corresponding audit event detail. |

## Local Capture

Playwright is configured for the frontend. To capture the required screenshots from a seeded local environment:

```bash
docker compose up --build
cd frontend
CAPTURE_SCREENSHOTS=1 npm run screenshots
```

Defaults:

- frontend URL: `http://localhost:3000`
- backend URL: `http://localhost:8000`
- username: `admin@demoorg.com`
- password: `ChangeMe!12345`
- output directory: `assets/screenshots/`

Override these when needed:

```bash
PLAYWRIGHT_BASE_URL=http://localhost:3000 \
E2E_BACKEND_BASE_URL=http://localhost:8000 \
E2E_EMAIL=admin@demoorg.com \
E2E_PASSWORD='ChangeMe!12345' \
SCREENSHOT_DIR=../assets/screenshots \
CAPTURE_SCREENSHOTS=1 \
npm run screenshots
```

The capture script creates a demo API key and sends a mock blocked request so the audit log and blocked-request screenshots contain real local demo data.

## Dashboard

Expected file: `assets/screenshots/dashboard.png`

Status: pending real capture.

## Policy Editor

Expected file: `assets/screenshots/policy-editor.png`

Status: pending real capture.

## Provider Settings

Expected file: `assets/screenshots/provider-settings.png`

Status: pending real capture.

## Audit Log

Expected file: `assets/screenshots/audit-log.png`

Status: pending real capture.

## Blocked Request Demo

Expected file: `assets/screenshots/blocked-request-demo.png`

Status: pending real capture.
