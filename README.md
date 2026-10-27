# Infinity Neural Memory — V1.2 (1.2.0)

![CI](https://img.shields.io/badge/CI-verify%2035%20%2B%2064%20tests-brightgreen)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Deps](https://img.shields.io/badge/dependencies-0%20(stdlib)-success)
![Memory](https://img.shields.io/badge/memory-permanent%20by%20design-blueviolet)

> A self-contained, **honest**, testable memory nervous system for long-running agents.
> **Permanent memory** · append-only timeline · hybrid recall · explainable governance gates · zero hard dependencies.

---

## ⏳ The Infinity guarantee — memory that does not evaporate

**In Infinity Neural Memory, forgetting is a decision — never a side effect.**

Your agent's past is *permanent by design*. Nothing fades because time passed. Nothing is dropped
by a background cleanup. Nothing decays into oblivion.

- **The timeline is append-only.** What happened, stays. Events are written once and never edited.
- **Contradictions supersede — they do not erase.** When a new fact replaces an old one, the old
  truth steps aside (marked *no longer current*) but remains permanently on the record.
- **No expiry. No TTL. No garbage collector.** There is no code path that deletes a memory because
  it grew old, cold, or low-priority. *(Verified: a full-tree search finds zero auto-deletion.)*
- **The only way a memory ever leaves is an explicit `forget`** — issued by a human, for a real
  reason (right-to-forget, or purging a leaked secret), and itself written to the timeline as a
  **tombstone**. Erasure is deliberate, rare, and auditable.

This is what **"Infinity"** means: the system keeps everything you let in, for as long as you
exist — **until you, and only you, decide otherwise.**

> Permanence *and* sharp recall — not one at the cost of the other. Everything is kept; relevance
> and freshness decide what **surfaces** for a given query, never what **survives**. An old memory
> doesn't disappear — it waits for the right question.

### For anyone analyzing this: persistence ≠ "zero-decay"

Older systems claimed "zero-decay" by *freezing retrieval scores* — which ranked stale memories as
high as fresh ones, hurt recall, and still never guaranteed the data survived (an activation number
says nothing about whether a row exists). Infinity Neural Memory keeps the two concerns separate:

| Concern | Infinity Neural Memory |
|---|---|
| **Persistence** — does the memory survive? | **Absolute.** Nothing is ever auto-deleted. Only an explicit, logged `forget` removes anything. |
| **Retrieval ranking** — does it surface *now*? | Freshness + relevance decide order; pinned rules/identity never fade. |

So "permanent" is a **storage guarantee you can audit** — not a frozen-clock trick. See
[`docs/PERMANENCE.md`](docs/PERMANENCE.md) for the full contract.

---

Distilled from two prior projects and two rounds of deep audit:

- **infinity-neural** → event-sourced timeline, instinct-recall protocol, Vietnamese NLP, dual-brain idea.
- **library-memo** → hybrid BM25+vector retrieval with RRF, self-contained discipline, admission concept.
- **Both audits** → the fixes: redaction, file-lock, real-vs-stub honesty, single-main VERIFY, provenance + supersession, memory admission gate, pre-action gate.

**Design law:** *ship only what runs; label protocol vs code; no public claim without a passing test.*

### What V1 Final adds (the synthesis)

This is the merge of the self-contained engine and the OpenClaw product shell, with both audits' fixes applied:

- **Two gates, not one.** Write-side `AdmissionGate` (what to store) **plus** retrieval-side `InjectionGate` (what to inject into context). They guard different points in the lifecycle.
- **Explainable Preference Prior** (`Brain.prefer`) — the V4 "subconscious" idea as real, tested, *inspectable* code. No hidden bias.
- **PII scrub** (`inmem.pii`) on top of secret redaction — fixes the seed-corpus leak the lab audit found.
- **Safe seed importer** (`scripts/seed_import.py`) — bootstrap from a private corpus with PII-scrub + secret-block + dedupe; nothing raw reaches the store.
- **OpenClaw protocol layer** — `SKILL.md`, `INSTINCT-PROTOCOL.md`, `SYNC-PROTOCOL.md`, `SESSION-LOGGER.md`, `AGENTS-BLOCK.md`.
- **Scale & semantic recall (V1.1).** FTS5 + a two-stage pipeline (lexical candidates → vector
  rerank of only those → RRF) + a lazy embedding cache: warm queries ~84x faster than V1.0 and
  bulk insert faster than before. Swap in `OpenAIEmbedder` / `OllamaEmbedder` for semantic recall
  (zero new deps; the offline `HashingEmbedder` stays the default).
- **Optional engine, honest bridge** — bundles `neural-memory 4.12.0` (attributed in `NOTICE.md`), used only via `SubprocessBridge` → `nmem`. The core never imports it; the bridge never fakes a sync.

---

## What it IS

- A pure-Python (stdlib-only) library + CLI you can `pip install` and run anywhere — no API key, no native build, no external service required to pass tests.
- An **event-sourced** memory: the append-only JSONL **timeline** is ground truth; the SQLite **store** is a rebuildable projection with first-class **provenance** (`source_event_id`, `valid_from/valid_to`, `supersedes`, `confidence`, `trust`).
- **Hybrid retrieval**: Okapi BM25 + optional vector (offline `HashingEmbedder` by default), fused with **Reciprocal Rank Fusion**, optional reranker hook.
- **Governance gates** (the "fangs"):
  - **AdmissionGate** — explainable decision before writing (dedupe / sensitivity / confidence). Every decision returns its reasons.
  - **PreActionGate** — "have we failed at this before?" check before deploy/edit/config. Surfaces warnings + supporting memories; never blocks silently.
- **Security by construction**: a **Redactor** scrubs secrets on every write path; raw secrets never reach disk. The original SHA-256 is kept for dedupe without keeping the secret.
- **Vietnamese-aware**: tone folding + compound tokenization so `quyet dinh` matches `quyết định`.

## What it is NOT

- ❌ Not a fork of `neural-memory`. It does **not** import any `neural_memory` API. (An optional, honest bridge can push to an external engine if you have one — see below.)
- ❌ No "zero-decay" *activation trick* and no `ETERNAL` neuron type. Permanence here is a **storage guarantee** (nothing is auto-deleted — see "The Infinity guarantee" above), not a frozen retrieval score. Recency/importance is handled by `pinned` + salience + freshness ranking.
- ❌ Not a semantic-SOTA embedder out of the box. The default `HashingEmbedder` is deterministic and good enough for hybrid demo/recall; swap in OpenAI/Ollama/SentenceTransformers for production quality.
- ❌ Not a Telegram bot. The digest has pluggable notifiers (`ConsoleNotifier` default; `WebhookNotifier` does a real HTTP POST). Nothing prints to console while claiming it "sent a DM".

## Install & Verify

```bash
pip install -e .            # or: pip install dist/infinity_neural_memory-1.0.0-*.whl
python VERIFY.py            # 35/35 checks, exit 0 on success
pytest tests/ -q            # 64 tests
```

## Quickstart (CLI)

```bash
python -m inmem.cli remember "Chọn Opus 4.6 vì Sonnet thiếu depth" --category decision
python -m inmem.cli log --user "Ch101 hoàn thành, score 72/80" --agent "ok"
python -m inmem.cli recall "model nào dùng viết truyện"
python -m inmem.cli preaction --action deploy --target prod      # -> high risk if a rule exists
python -m inmem.cli digest
python -m inmem.cli sync                                          # honest dry-run by default
```

## Quickstart (API)

```python
from inmem.brain import Brain

brain = Brain(db_path="memory.db", timeline_dir="./timeline")
brain.remember("Quy tắc: luôn redact secret trước khi log", category="instruction", pinned=True)
brain.log_exchange("Chọn FalkorDB vì graph-native", "đã ghi nhận", session_id="s1")

for hit in brain.recall("graph database"):
    print(hit.score, hit.memory["content"])

verdict = brain.pre_action("deploy", "prod")
print(verdict.risk, verdict.warnings)
```

## Optional external bridge (honest)

The core needs no engine. If you run an external graph memory exposing an `nmem` CLI,
`SubprocessBridge` will push high-salience facts to it and report **real** success counts.
`DryRunBridge` (default) performs no external I/O and says so (`mode="dry-run"`, `written=0`).

## Known limitations (V1)

- BM25 is computed over the active set in memory — great to ~10⁴ memories; shard or move to a
  vector DB beyond that.
- Default embedder is a hashing trick, not semantic. Provide a real `Embedder` for quality recall.
- Near-duplicate similarity in the AdmissionGate is a fused-score proxy, not calibrated cosine.
- Single-process file lock (POSIX `flock`); cross-host concurrency needs an external lock.

## Security warning

Treat the timeline + store as **private by default**. Redaction reduces risk but is not a
guarantee — do not commit `*.db` or `timeline/` to a public repo. Run a secret scanner in CI
(see `.github/workflows/ci.yml`).

## License

MIT — see `LICENSE`.
