# Contributing to Sentinel

Thanks for contributing.

## Engineering principles

- Keep Sentinel governance-first: policy enforcement, tenancy boundaries, and auditability are non-negotiable.
- Make focused changes; avoid large rewrites when targeted edits are sufficient.
- Preserve shared-platform behavior (`Sentinel`) and legal preset behavior (`SentinelLaw`).
- Update docs alongside behavior changes.

## Local setup

```bash
cp .env.example .env
docker compose up --build -d
```

## Before opening a PR

Run relevant checks:

```bash
make ps
make test
make validate
```

At minimum, verify:

- backend tests pass
- frontend lint/build paths still pass
- no broken docs links in changed docs
- no secrets or local-only files are staged

## Security and secrets

- Never commit `.env` or credential-bearing files.
- Use `.env.example` for configuration shape only.
- If you suspect a leaked secret, rotate it and open a remediation PR immediately.

## Pull request expectations

- Explain what changed and why.
- Call out behavior changes and migration impact.
- Include docs updates for any new operational workflow.
- Keep PRs reviewable and scoped.
