# Infinity Neural Memory v1.0.1

An honest, local-first **memory nervous system** for long-running agents. Not just memory
retrieval — **memory-as-governance** for agents that must not repeat old mistakes.

Pure-Python (stdlib only). No API key, no native build, no external service required.
`python VERIFY.py` → **26/26**. `pytest` → **47 passing**. Fresh-install verified on a clean venv.

## Highlights

- **Append-only timeline** (event-sourced ground truth, redacted + file-locked) + **SQLite belief
  store** with provenance, temporal validity, and supersession.
- **Hybrid recall** — Okapi BM25 + optional vector, fused with **Reciprocal Rank Fusion**.
- **Two governance gates + one safety gate:**
  - `AdmissionGate` — what to *write* (dedupe / secret-block / confidence).
  - `InjectionGate` — what to *inject into context* (relevance / freshness / sensitivity / supersession).
  - `PreActionGate` — "have we failed at this before?" before deploy / migrate / edit.
- **Explainable Preference Prior** — the "subconscious" idea done honestly: a ranked, **inspectable**
  prior with a reason ledger and sources. No hidden bias.
- **Secret + PII redaction** on every write path (keys, tokens, JWTs, private keys, passwords,
  emails, IPs, user-home paths). Originals never persisted; SHA-256 kept for dedupe.
- **Vietnamese-aware** tone folding + compound tokenization.
- **Optional engine** — bundles `neural-memory 4.12.0` (attributed in `NOTICE.md`), used only via
  an explicit `SubprocessBridge` → `nmem`. The core never imports it; the bridge never fakes a sync.
- **OpenClaw layer** — `SKILL.md`, `INSTINCT-PROTOCOL.md`, `SYNC-PROTOCOL.md`, `SESSION-LOGGER.md`,
  `AGENTS-BLOCK.md`.

## What changed in v1.0.1 (patch)

Applies the P0 fixes from a second lab review:

- **Redaction — quoted passwords.** `password = "hello world"` no longer leaks `world`; the value
  (quoted, with spaces) is fully masked → `password="[REDACTED:secret]"`.
- **Redaction — URL credentials.** `postgres://user:pass@host/db` → `postgres://[REDACTED:credential]@host/db`
  (scheme + host preserved; only the credential masked).
- **AdmissionGate — supersession policy.** Near-identical content is now a **skip** (duplicate);
  a memory is **superseded only on an explicit replacement signal** ("thay bằng", "không dùng X
  nữa", "replace", "deprecated") with high token-Jaccard overlap. Fixes the brain deactivating
  related-but-distinct memories.
- **Tooling.** `pytest` now runs without setting `PYTHONPATH` (`pythonpath = ["."]`), plus
  regression tests for every fix above.

## Honesty notes (what this is NOT)

- ❌ Not a fork of `neural-memory`; the core doesn't import it.
- ❌ No "zero-decay / ETERNAL / ANCHOR" — importance is an explicit `pinned` flag + salience.
- ❌ No `InfinityTier` / phantom `engine.relevance` / inflated test counts.
- ❌ No simulated sync, no fake notification delivery.

## Install

```bash
pip install infinity_neural_memory-1.0.1-py3-none-any.whl
python -m inmem.cli --help
# or run the demo from source:
python examples/demo.py
```

## Verify

```bash
python VERIFY.py        # 26/26, exit 0
pytest tests/           # 47 passing
```

## Known limitations / roadmap (honest)

- **Recall at scale.** BM25 + the offline embedder run over the active set per query — fine to a
  few thousand memories; slower beyond. **v1.1** adds SQLite FTS5, an embedding cache, and
  vector-rerank-of-top-N, plus pluggable semantic embedders (OpenAI / Ollama / SentenceTransformers).
- **Event sourcing.** Timeline → store rebuild and a tamper-evident event hash-chain
  (`event_hash` / `prev_event_hash`) land in **v1.2**.

## License

MIT (first-party code). Bundled engine wheel: see `LICENSES/MIT-neural-memory.txt` and `NOTICE.md`.
