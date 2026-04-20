# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it
responsibly. **Do not open a public issue.**

Email: **security@example.com** (replace with your preferred contact)

Please include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge your report within 48 hours and aim to provide a fix or
mitigation within 7 days for critical issues.

## Scope

This repo contains **prototype** code intended for learning and as starting
points for production systems. The prototypes implement auth, rate limiting,
and other security controls, but they have not been audited for production
deployment.

Before deploying any prototype to production:

1. Replace HS256 JWT signing with RS256 and a proper key management solution
2. Run the bundled Promptfoo security scan (`make security PROTOTYPE=<name>`)
3. Review the agent's tool permissions — ensure MCP servers are scoped minimally
4. Enable TLS termination at your load balancer / reverse proxy
5. Review `docs/security.md` for the agent-specific threat model

## Supported Versions

Only the latest release on `main` is supported with security fixes.

## Dependencies

We pin all dependency versions in `common/versions.md` and use lockfiles
(`uv.lock` / `pnpm-lock.yaml`) for reproducibility. Dependabot is enabled
for automated dependency update PRs.
