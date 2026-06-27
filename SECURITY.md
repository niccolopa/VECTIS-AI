# Security Policy

## Supported versions

VECTIS is pre-1.0. Security fixes are applied to `main`.

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Instead, report privately via GitHub's [Security Advisories][advisories]
("Report a vulnerability") on this repository. Include:

- a description of the issue and its impact,
- steps to reproduce or a proof of concept,
- affected component(s) (api / agents / data / models / frontend).

We aim to acknowledge reports within 72 hours and to provide a remediation
timeline after triage.

## Scope & handling notes

- **Secrets**: never commit API keys. VECTIS reads all secrets from the
  environment (`.env`, never tracked). The default LLM provider is `mock` and
  requires no key.
- **LLM safety**: agent outputs are untrusted by default. The Critic agent and
  schema validation (`DecisionReport`) bound what reaches the API surface; do
  not weaken these without review.
- **Data**: the bundled sample is synthetic. Live connectors (FIRMS/ERA5/
  Copernicus) require user-supplied credentials and are opt-in.

[advisories]: https://docs.github.com/en/code-security/security-advisories
