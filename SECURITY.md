# Security Policy

Sentinel is governance and security-oriented AI infrastructure. We take vulnerability handling seriously.

## Supported versions

Security fixes are applied on the active default branch and incorporated into upcoming tagged releases.

## Reporting a vulnerability

Please do not open public issues for suspected security vulnerabilities.

Report privately with:

- a clear description of the issue
- impact assessment (confidentiality/integrity/availability)
- affected components/paths
- reproduction steps or proof-of-concept

Temporary contact channel for this repo: open a private security advisory on GitHub for this repository.

## Response expectations

- Initial triage acknowledgment target: within 3 business days
- Confirmation and severity assessment target: within 7 business days
- Remediation timeline based on severity and exploitability

## Scope notes

- Findings affecting tenant isolation, policy bypass, auth/session handling, provider credential exposure, audit integrity, or unsafe logging are treated as high priority.
- Misconfiguration-only findings should include explicit deployment context.

## Safe harbor

Good-faith security research and responsible disclosure are welcomed.
This safe-harbor statement does not grant rights beyond the repository license.
