# DESIGN — Infinity Neural Memory V1

## The one principle
**Ship only what runs. Label protocol vs code. No claim without a passing test.**

Two predecessor projects taught this the hard way:
- `infinity-neural` had excellent ideas but its shipped engine drifted from its docs/tests
  (a fork was swapped for upstream without re-porting custom modules), and its public README
  advertised features the installed artifact didn't have.
- `library-memo` was coherent and tested, but most "advanced" features were off by default.

V1 keeps the ideas, the discipline, and discards the drift.

## Two-layer truth model

```
        ┌────────────────────────────────────────────┐
        │  TIMELINE  (append-only JSONL, 1 file/day)   │  ← GROUND TRUTH
        │  immutable events, redacted on write, locked │     "what happened"
        └───────────────┬──────────────────────────────┘
                        │ deterministic projection (source_event_id links back)
        ┌───────────────▼──────────────────────────────┐
        │  STORE  (SQLite)                              │  ← CURRENT BELIEF
        │  provenance · valid_from/valid_to · supersede │     "what is true now"
        └───────────────┬──────────────────────────────┘
                        │ read paths
   ┌────────────────────┼─────────────────────────────────┐
   │ RECALL (BM25 + vec, RRF)   GATES (admission, pre-action)│
   └─────────────────────────────────────────────────────────┘
```

If the SQLite projection is ever lost or corrupted, it can be rebuilt by replaying the
timeline — because every memory records the `source_event_id` (the SHA-256 of the originating
event content). This is the event-sourcing guarantee.

## Why no fork, no `neural_memory` dependency
The single biggest failure mode in the lineage was *coupling docs/tests to a fork that the
shipped wheel didn't contain*. V1 removes the coupling entirely: the core is a small,
owned, stdlib-only library. If you want a heavyweight graph engine, attach it through the
explicit `NeuralBridge` adapter — which never lies about whether a write actually happened.

## Why redaction is a precondition, not a feature
A memory backup in the lineage contained plaintext SSH passwords and API keys. Redaction is
therefore wired into *every* write path (timeline append + admission), not offered as an
optional pass. The original content's SHA-256 is retained so exact-duplicate detection still
works without keeping the secret itself.

## Governance gates = the differentiator
- **AdmissionGate** answers "should this be written?" with a transparent reason list. No hidden
  bias: if it skips or blocks, it tells you why. (This is the "preference prior with a residence
  permit" idea from the V4 brainstorm — influence must be explainable, never a ghost.)
- **PreActionGate** answers "have we failed at this before?" before deploy/edit/migrate. It warns
  and shows the supporting memories; it does not silently block. Governance, not censorship.

## Retrieval choices
- BM25 (Okapi, k1=1.5, b=0.75) over the active set, tokenized with Vietnamese folding.
- Optional vector via a pluggable `Embedder`. Default `HashingEmbedder` is deterministic and
  offline so CI is hermetic; swap a semantic embedder in for production.
- **RRF** fuses the two rankings (k=60). Pinned memories get a small, *explicit* additive boost —
  visible in the score breakdown, not a magic "eternal" rank.

## Roadmap (honest, not shipped yet)
- V1.1: pluggable semantic embedder adapters (OpenAI/Ollama) + a real cross-encoder reranker.
- V1.2: timeline→store rebuild command + calibrated near-duplicate cosine.
- V1.3: trust scoring + low-confidence recall rejection (SuperLocalMemory/MemX influence).
- V2.0: subconscious "preference prior" — only as an explainable, decaying, audited ledger.
