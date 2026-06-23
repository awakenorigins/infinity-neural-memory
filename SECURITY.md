# Security Policy

Infinity Neural Memory exists partly *because* a predecessor leaked plaintext secrets.
We take security seriously and bake it into the code (`inmem/redaction.py`, the AdmissionGate),
but defense-in-depth still needs you.

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅        |

## Reporting a vulnerability

**Do not open a public issue for security problems.**

Please report privately via GitHub Security Advisories ("Report a vulnerability" on the
repository's *Security* tab), or by email to the maintainer listed in `pyproject.toml`.

Include: affected version, reproduction steps, and impact. We aim to acknowledge within
72 hours and to ship a fix or mitigation for confirmed issues as a patch release.

## Data-handling expectations (read this)

- The **timeline** (`timeline/`) and **store** (`*.db`) are **private by default**. They may
  contain user content. **Never commit them** — `.gitignore` and the CI gate both block this.
- `Redactor` scrubs common secret formats (API keys, tokens, JWTs, private keys, password
  key/values) on every write path and keeps only a SHA-256 of the original. This **reduces**
  risk; it is **not** a guarantee. Do not feed known secrets into memory intentionally.
- The `AdmissionGate` **blocks** writing any content in which a secret is detected
  (`block_sensitive=True` by default). Keep it on.
- Run the secret scanner in CI (`gitleaks`) and locally (`pre-commit`). Both are pre-wired.

## Threat model (V1, honest scope)

In scope: accidental secret persistence, accidental commit of private memory, basic
duplicate/poisoning hygiene via the AdmissionGate.

Not yet in scope (roadmap): adversarial memory-poisoning defense, per-source trust scoring,
low-confidence recall rejection, and cryptographic erasure / right-to-forget. Track these in
`references/DESIGN.md` → Roadmap.
