# Repo Publication Audit

Date: 2026-04-14

## Scope reviewed

- Root publication files and compose config
- Existing docs set (core + supplemental)
- Preset/config structure
- CI workflow
- Public-repo safety posture (.env/secrets/ignored artifacts)

## What existed and was reusable

- Strong existing core app structure: `backend/`, `frontend/`, `config/presets/`, `scripts/`, `.github/workflows/ci.yml`
- Working docs baseline with rich content in API, architecture, deployment, security, and audit areas
- Existing generalized Sentinel + SentinelLaw preset direction already in place

## Standardization decisions

### Kept (lightly edited)

- `docs/API.md`
- `.env.example`
- `.gitignore`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `.github/workflows/ci.yml`
- `INSTRUCTIONS.md`
- `deploy.sh`

### Renamed to standardized core docs

- Legacy mixed-case core docs were standardized to uppercase canonical names:
  - `ARCHITECTURE.md`
  - `THREAT_MODEL.md`
  - `QUICKSTART.md`
  - `DEPLOYMENT.md`
  - `DEMO_SCRIPT.md`
  - `RELEASE_CHECKLIST.md`

### New core docs added

- `docs/POLICY_ENGINE.md`
- `docs/AUDIT_AND_LOGGING.md`
- `docs/DECISIONS.md`
- `docs/ROADMAP.md`

### New publication/help docs added

- `docs/GITHUB_PUBLISHING_GUIDE.md`
- `docs/REPO_PUBLICATION_AUDIT.md` (this file)

### Supplemental docs intentionally preserved

- `docs/ProviderRouting.md`
- `docs/DataHandling.md`
- `docs/AuditEventMapping.md`
- `docs/AuditIntegrity.md`
- `docs/LoggingAndRetention.md`
- `docs/Troubleshooting.md`
- `docs/UI-Guide.md`
- `docs/presets.md`
- `docs/demo_modes.md`
- legal-focused reference docs under `docs/Policies/`, `docs/LegalPositioning.md`, `docs/FirmAdminGuide.md`, etc.

Rationale: these remain useful technical/vertical references without diluting the standardized core docs set.

## Root publication files added

- `LICENSE` (MIT)
- `Makefile`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `SECURITY.md`

## Assets structure added

- `assets/screenshots/`
- `assets/diagrams/`
- `assets/demo/`
- plus `.gitkeep` placeholders and `assets/README.md`

## Safety findings and adjustments

- `.env` exists locally and may contain secrets; it is ignored by `.gitignore`.
- `.gitignore` hardened for:
  - `.env` and `.env.*` (with explicit allowlist for `.env.example` and `.env.production.template`)
  - local agent state `.agent/`
  - generated artifacts/logs and build outputs
- `artifacts/` is retained for operational value but ignored for clean public git history.

No intentional secret values were added by these edits.

## Notes on public emphasis

- Core docs now emphasize Sentinel shared platform positioning.
- SentinelLaw remains clearly preserved as a legal preset/vertical edition rather than default product framing.
