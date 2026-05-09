# Release Checklist

Use this checklist before tagging a public-ready Sentinel release.

## Version and Branch Hygiene

- Choose a release version, for example `v0.1.0`.
- Ensure the release branch is up to date with the intended base branch.
- Confirm the working tree contains only intended release changes.
- Verify `.env`, local agent state, generated artifacts, and secret material are not tracked.

## Validation Gate

From the repository root:

```bash
APP_VERSION=v0.1.0 ./scripts/validate_release.sh
```

Expected outcomes:

- backend tests pass
- frontend lint and build pass
- Docker Compose boot checks pass
- smoke tests pass
- Playwright smoke tests pass
- validation artifacts are written under `artifacts/validate-release/`

## Deployment Checks

- Verify database migrations apply cleanly.
- Verify backend and worker startup succeeds with production configuration.
- Verify health and readiness endpoints respond as expected.
- Verify preset config loads correctly, with `general` as the default and `legal` available as a preset.

## Security Checks

- Confirm no committed secrets, credentials, API keys, JWT secrets, or provider keys.
- Confirm production validation rejects unsafe defaults.
- Confirm auth, RBAC, tenant scope, provider-secret encryption, and audit integrity tests pass.
- Confirm `/metrics` is protected by `METRICS_TOKEN` in production.

## Documentation Checks

- README reflects current product behavior and commands.
- Core docs are consistent and linked from `docs/README.md`.
- Deployment docs include all required production environment variables.
- Screenshot placeholders or final screenshots are present.
- Changelog is updated for the release.

## Optional Operational Drill

- Run backup and restore scripts in a non-production environment.
- Run smoke tests after restore.
- Confirm audit export and integrity verification workflows still work.

## Tag and Publish

```bash
git tag -a v0.1.0 -m "Sentinel v0.1.0"
git push origin v0.1.0
```

Record the release version, commit SHA, tag, validation result, and any known limitations.
