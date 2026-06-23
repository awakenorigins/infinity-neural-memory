# Changelog

## V1.0.1 — Patch (2026-06-23) — crown-ready

Applies the P0 fixes from the second lab review (Mula). `python VERIFY.py` → 26/26;
`pytest` → 47 passing (now runnable without setting PYTHONPATH).

### Fixed (P0)
- **Redaction — quoted passwords.** `password = "hello world"` previously leaked `world"`.
  The pattern now captures quoted values (with spaces); output is `password="[REDACTED:secret]"`.
- **Redaction — URL credentials.** `postgres://user:pass@host/db` now masks only the credential
  and preserves the scheme: `postgres://[REDACTED:credential]@host/db` (was a malformed strip).
- **AdmissionGate — supersession policy.** Near-identical content is now a **skip** (duplicate),
  and a memory is **superseded only with an explicit replacement signal** ("thay bằng", "không
  dùng X nữa", "replace", "deprecated") *and* high token-Jaccard overlap. Prevents the brain from
  deactivating related-but-distinct memories. (The fused-score similarity proxy was already
  removed in V1 Final; this hardens the policy further.)

### Tooling
- `pytest` now configured with `pythonpath = ["."]` so `pytest tests/` works without an install.
- Added regression tests (`tests/test_regression_v101.py`) for every fix above, including
  Mula's `test_admission_does_not_supersede_related_but_distinct`.

### Notes (roadmap, acknowledged — not in this patch)
- V1.1: SQLite FTS5 + embedding cache + vector-rerank-top-N (current recall embeds the full
  active set per query; fine to ~few-thousand memories, slows beyond).
- V1.2: `inmem rebuild` (replay timeline → store) + hash-chained events (`event_hash`,
  `prev_event_hash`) for tamper-evident audit.

## V1.0.0 — Final (2026-06-23)

Synthesis of the self-contained `inmem` core and the OpenClaw product shell, applying every fix
from two rounds of audit. `python VERIFY.py` → 26/26; `pytest` → 38 passing; fresh-install verified.

### Added
- **InjectionGate** (`inmem/inject_gate.py`, `Brain.recall_for_context`) — retrieval-side gate:
  relevance + freshness (exp decay) + sensitivity + supersession, explainable.
- **PreferencePrior** (`inmem/preference_prior.py`, `Brain.prefer`) — the V4 idea as honest,
  inspectable code (sources + reasons + decay; `visible_when_asked`).
- **PiiScrubber** (`inmem/pii.py`) — emails / IPv4 / OS user-home paths, on top of secret redaction.
- **Safe seed importer** (`scripts/seed_import.py`) + synthetic sample (`seed/sample/`) + policy.
- **OpenClaw protocol docs** — INSTINCT / SYNC / SESSION-LOGGER / AGENTS-BLOCK + docs/V4-PREFERENCE-PRIOR.
- **Optional engine** — bundled `neural-memory 4.12.0` (attributed in NOTICE.md / LICENSES/) via the
  honest `SubprocessBridge`.

### Fixed
- **AdmissionGate near-duplicate** now uses real token **Jaccard** (was a fused-score proxy that
  could falsely supersede unrelated-but-overlapping memories). Caught by a new test.

### Cleared (debt that the gp lineage still carried)
- Zero ETERNAL/ANCHOR/zero-decay/InfinityTier anywhere in code (verified). 
- No simulated sync, no fake Telegram delivery, no orphaned tests.

## V1.0.0 — Distilled Foundation (2026-06-23)

First release of **Infinity Neural Memory** — a clean reboot that distills the best of
`infinity-neural` (V1→V3.3) and `library-memo`, and applies every fix from two rounds of audit.

### Kept (the essence)
- **Event-sourced append-only timeline** (from infinity-neural V3.3) — now with redaction + file lock.
- **Hybrid BM25 + vector retrieval with RRF** (from library-memo) — offline, deterministic, testable.
- **Vietnamese NLP** (from the V1 fork that V3.x dropped) — tone folding + compound tokenization, re-ported as a real module with tests.
- **Instinct extraction** (from the V3 protocol) — pattern-based fact extraction, regex hardened.
- **Provenance + supersession + temporal validity** (from the engine + Graphiti/Zep influence).

### Added (the fangs)
- **Memory Admission Gate** — explainable write decision (dedupe / sensitivity / confidence).
- **Pre-Action Judgment Gate** — "have we failed at this before?" warnings before risky actions (ProjectMem influence).
- **Redaction layer** — secrets scrubbed on every write path; SHA-256 retained for dedupe.
- **Honest bridge** — `DryRunBridge` (default) never pretends to sync; `SubprocessBridge` reports real success.
- **Honest digest** — pluggable notifiers; `WebhookNotifier` actually posts, `ConsoleNotifier` prints and says so.

### Explicitly removed / not carried over (debt cleared)
- ❌ `NeuronType.ETERNAL` / `ANCHOR` and "zero-decay" — replaced by explicit `pinned` + salience.
- ❌ `InfinityTier` / phantom `engine.relevance` — replaced by self-contained BM25/RRF + tier-by-age.
- ❌ Orphaned scripts/tests that imported a fork the shipped engine lacked (the V3.1/V3.3 packaging bug).
- ❌ Dead-code `VERIFY.py` (the `sys.exit()` that skipped V3.3 checks) — now a single main, no dead code.
- ❌ Simulated "synced += 1" — bridge always reports its true mode.
- ❌ `print()` masquerading as "Telegram DM sent".

### Engineering
- Pure Python stdlib. Zero hard external dependencies. `python VERIFY.py` → 21/21. `pytest` → 29 passing.
- CI runs verify + tests + a secret scan gate before any release is allowed green.

> Lineage note: `infinity-neural` V1.0 was a real fork; V3.1 swapped to upstream `neural-memory 4.12.0`
> without re-porting the fork's custom modules, which is why V3.x docs/tests drifted. This project does
> not fork at all — it owns a small, honest core and bridges out only when explicitly asked.
