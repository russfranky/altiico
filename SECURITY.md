# Security policy

## Supported versions

Altiico Catalog is pre-1.0. Security fixes are applied to the current `main` branch and the latest tagged release, when one exists. Historical generated snapshots are retained for provenance but are not maintained as runnable software versions.

| Version | Supported |
|---|---|
| `main` | Yes |
| Latest tagged release | Yes |
| Older tags and snapshots | No |

## Reporting a vulnerability

Do not disclose a vulnerability in a public issue, pull request, commit, or discussion.

Use GitHub's **Report a vulnerability** flow in the repository Security tab. Include:

- the affected file, workflow, endpoint, or deployment;
- steps to reproduce;
- the security impact;
- any proof of concept kept to the minimum needed;
- suggested remediation, when known.

If private vulnerability reporting is unavailable, open a public issue containing only a request for a private maintainer contact. Do not include exploit details in that issue.

## In scope

Examples include:

- command execution or unsafe parsing of untrusted catalog data;
- secret exposure in GitHub Actions, logs, generated artifacts, or browser assets;
- dependency or workflow supply-chain compromise;
- cross-site scripting or unsafe URL handling in the public catalog;
- authorization bypass in import or staging tooling;
- path traversal, arbitrary file overwrite, or unsafe archive handling;
- a validation flaw that lets an unvalidated file be represented as binary-validated.

Data-quality disputes without a security consequence should use the normal issue templates. Sensitive evidence that could expose private access URLs, credentials, or holder-only assets should still be reported privately.

## Handling reports

The maintainer will acknowledge a valid report through the private channel, investigate impact, and coordinate a fix and disclosure. Timelines depend on severity and reproducibility. Please avoid public disclosure until a fix is available or coordinated disclosure has been agreed.

## Security expectations for contributors

- Use least-privilege workflow permissions.
- Pin runtime and tool versions through maintained major releases or immutable revisions.
- Never execute pull request code in a privileged `pull_request_target` context.
- Keep API keys in GitHub Actions secrets or local environment variables.
- Treat all network responses, metadata, filenames, and archive contents as untrusted.
- Preserve fail-closed validation behavior.
