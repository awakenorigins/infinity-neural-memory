# Infinity Neural Memory v1.2.0 — Permanent by design

**Forgetting is a decision, not a side effect.** This release makes the project's founding goal
explicit and enforceable: Infinity Neural Memory keeps **every** memory permanently — nothing is
ever auto-deleted, expired, or decayed away. The only way a memory leaves is a human-issued,
logged `forget`.

`python VERIFY.py` → **35/35**. `pytest` → **64 passing**. Fresh-install verified.
See `PROOF-OF-RUN.txt` (includes the permanence proof) and `docs/PERMANENCE.md` (the full contract).

## The Infinity guarantee

- **Append-only timeline** — what happened, stays (events never edited/deleted).
- **Non-destructive supersession** — contradicted facts step aside (`valid_to` set) but remain on
  the record; nothing is erased.
- **No expiry / TTL / garbage collector** — old, cold, low-priority memories persist like fresh
  ones. *(Auditable: a full-tree grep finds zero auto-deletion; the only `DELETE` lives in
  `forget()`.)*
- **One deliberate exit — `forget`** — `Brain.forget(id, reason, actor)` / `inmem forget <id>`
  permanently removes a memory from the store **and** FTS index, and writes a **tombstone** to the
  timeline (who/when/why) so the erasure itself is auditable. For right-to-forget or secret purge.

## Persistence ≠ "zero-decay"

Older systems claimed "zero-decay" by freezing retrieval scores — which buried fresh memories under
stale ones and still didn't guarantee survival. Here the two concerns are separate: **persistence
is absolute** (storage guarantee), while **ranking** uses freshness + relevance so the right
memories surface first. Permanence *and* sharp recall.

## Also in the 1.1 → 1.2 line

- FTS5 + two-stage hybrid retrieval (candidates → vector rerank → RRF) + lazy embedding cache —
  warm queries ~84x faster than V1.0; bulk insert faster than before.
- Pluggable semantic embedders (`OpenAIEmbedder`, `OllamaEmbedder`) via stdlib `urllib` (zero new
  deps); offline `HashingEmbedder` stays default.

## Install

```bash
pip install infinity_neural_memory-1.2.0-py3-none-any.whl
python VERIFY.py        # 35/35
pytest tests/           # 64 passing
```

MIT (first-party). Bundled optional engine: see `NOTICE.md` / `LICENSES/`.
