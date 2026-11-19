# Security policy

## Reporting a vulnerability
Please **do not open a public issue**. Use GitHub's private vulnerability reporting (Security tab → *Report a vulnerability*) on this
repository. Include what you found, how to reproduce it, and the impact you believe it has. You will get an acknowledgement; this is a
small project, so please allow a few days, and expect a fix and a coordinated disclosure rather than a bounty.

In scope: authentication/session handling, authorization (reading or changing another user's data), the code-execution sandbox and
executor, injection, secrets exposure, the browser extension's token handling. Out of scope: findings that need a compromised host,
volumetric DoS, and missing best-practice headers with no demonstrated impact.

## What exists, and what does not
The current controls, the adversarial sandbox tests and the **known gaps** are documented honestly in [`docs/SECURITY.md`](docs/SECURITY.md)
and [`docs/CODE_EXECUTION.md`](docs/CODE_EXECUTION.md). Notable open items: session tokens still live in `localStorage`, the CSP is
partial (Next.js and Monaco need inline/eval script), the Docker socket on the executor host is root-equivalent, and MFA has no recovery codes.

## Secrets
Never commit `.env` or keys (the repository ignores them). CI scans dependencies weekly and images on every build.
