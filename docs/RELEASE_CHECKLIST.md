# Release Checklist

Use this checklist before tagging a public-ready release.

## 1. Version and branch hygiene

1. Choose release version (for example `v0.1.0`).
2. Ensure release branch is up to date and clean.
3. Verify `.env` is not tracked.

## 2. Validation gate

From repo root:

```bash
APP_VERSION=v0.1.0 ./scripts/validate_release.sh
```

Expected outcomes:

- backend tests pass
- frontend lint/build pass
- smoke checks pass
- compose boot checks pass

## 3. Deployment checks

- verify migrations apply cleanly
- verify backend and worker startup health
- verify preset config loads correctly (`general` default, `legal` available)

## 4. Security checks

- confirm no committed secrets
- confirm `.env`, `.agent`, artifacts, and local outputs are ignored
- confirm auth and tenant scope still enforced in changed paths

## 5. Docs checks

- README reflects current product behavior
- core docs are consistent and linked
- changelog updated for release

## 6. Optional operational drill

- run backup/restore scripts in non-production environment
- run smoke tests after restore

## 7. Tag and publish

```bash
git tag -a v0.1.0 -m "Sentinel v0.1.0"
git push origin v0.1.0
```

Record:

- commit SHA
- tag
- validation run output/artifacts
