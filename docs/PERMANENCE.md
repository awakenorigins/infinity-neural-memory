# PERMANENCE — the Infinity contract

> **Forgetting is a decision, not a side effect.**

This document is the precise, auditable statement of what *permanent memory* means in Infinity
Neural Memory — for users, for auditors, and for any system analyzing the design.

---

## 1. The guarantee, in one sentence

**No memory is ever removed by time, decay, priority, or a background process. The only path that
deletes a memory is an explicit `forget`, called by a human, recorded on the timeline.**

You can verify the first half mechanically:

```bash
grep -rniE "\bdelete\b|drop|purge|expire|\.remove\(|TTL|garbage" inmem/
# -> the only deletion statement in the package is inside forget(); nothing automatic.
```

## 2. Why "Infinity" — the three pillars of permanence

| Pillar | What it means | Where in code |
|---|---|---|
| **Append-only timeline** | Every event is written once and never edited or deleted. It is the immutable ground truth of "what happened." | `inmem/timeline.py` (no update/delete methods) |
| **Non-destructive supersession** | When a new fact contradicts an old one, the old memory is marked *no longer current* (`valid_to` set) — but the row **stays** and remains retrievable as history. | `MemoryStore.supersede` sets `valid_to`; never `DELETE` |
| **No expiry** | There is no TTL, no decay-to-deletion, no cold-storage eviction, no cleanup job. Old, cold, low-salience memories persist exactly like fresh ones. | absence of any expiry path (auditable by grep) |

The store can be fully rebuilt from the timeline because every memory records its
`source_event_id`. Even the *belief layer* is reconstructible from the *ground-truth layer*.

## 3. Persistence is NOT "zero-decay"

A common confusion (and the source of an earlier project's misleading claim) is to equate "never
forget" with "freeze the retrieval score." They are different things, and conflating them produces
a system that is both dishonest and worse at recall.

| | Frozen-activation "zero-decay" (old, rejected) | Infinity Neural Memory (this system) |
|---|---|---|
| Does the data survive? | Unspecified — an activation number says nothing about row existence. | **Yes, absolutely.** Survival is a storage property. |
| How are results ranked? | All memories rank equally forever → stale facts bury fresh ones. | Freshness + relevance decide *order*; pinned rules never fade. |
| Honest? | Often a config/marketing claim not backed by storage. | A guarantee you can `grep` for. |

**Permanence is about what survives. Ranking is about what surfaces. We keep them separate.**

## 4. Recall ≠ retention

An old memory that doesn't appear in a given `recall()` is **not lost** — it simply didn't rank in
the top‑k for *that* query. It is still in the store, still in the timeline, still retrievable:

- ask a more specific query, or raise `top_k`;
- pin it (`pinned=True`) so it never fades from ranking;
- inspect it directly (`store.get(id)`), or list everything (`store.all()`).

Like human memory: you don't *lose* a memory because it didn't come to mind once — it waits for the
right cue.

## 5. The one exit: deliberate `forget`

Permanence by default would be a liability if a secret slipped in or a person exercised their
right to be forgotten. So there is exactly **one** way out, and it is loud, manual, and logged:

```python
brain.forget(memory_id, reason="right-to-forget request", actor="alice")
# or:  inmem forget <memory_id> --reason "purge leaked secret"
```

What `forget` does, and guarantees:

- **Permanently removes** the memory from the store **and** the FTS index — it is gone, not hidden.
- **Records a tombstone** on the append-only timeline: `{type: "forget", mem_id, reason, actor, ts}`
  — **the act of forgetting is itself on the record** (who, when, why), even though the content is
  erased.
- Is **never** invoked automatically. Decay, supersession, time, and cleanup jobs do **not** call
  it. A human (or an explicit instruction) must.

> Note on secrets: the timeline **redacts on write**, so a leaked secret never reaches the
> timeline in raw form — only `[REDACTED:…]`. `forget` then removes the stored memory. The
> realistic "remove a leaked secret" case is therefore fully covered. (Full timeline *compaction*
> — rewriting historical JSONL — is intentionally a separate, rare, future operation, because it
> breaks the append-only guarantee and must be done with eyes open.)

## 6. Summary for the skeptical analyst

- **Claim:** memory is permanent. **Check:** `grep` finds no auto-deletion; only `forget` deletes.
- **Claim:** contradictions don't destroy history. **Check:** `supersede` sets `valid_to`, never
  `DELETE`; `store.all()` returns superseded rows.
- **Claim:** erasure is deliberate and auditable. **Check:** `forget` writes a timeline tombstone;
  `tests/test_forget.py` proves removal + tombstone + that supersession never deletes.
- **Claim:** permanence doesn't dumb down recall. **Check:** ranking uses freshness/relevance
  (`inmem/inject_gate.py`), independent of the storage guarantee.

`python VERIFY.py` exercises all of the above (the "Permanence" checks) and must print all‑pass.
