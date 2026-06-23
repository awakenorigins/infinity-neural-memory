# SYNC-PROTOCOL — Dual-Brain (Timeline / Store / Library / Engine)

Infinity Neural Memory keeps memory in layers with clear roles. This doc says **where to read**
and **how they stay in sync**.

## The layers

| Layer | Role | Source of truth for | Backed by |
|---|---|---|---|
| **Timeline** | append-only event log | "what happened" | `inmem.timeline` (JSONL, 1/day) |
| **Store** | current belief, projection | "what is true now" | `inmem.store` (SQLite + provenance) |
| **Library** | human-readable daily notes | "status at a glance" | markdown files (optional) |
| **Engine** | heavyweight graph recall | cross-time association | `neural-memory` via `nmem` (optional) |

## Where to read

| Need | Read from |
|---|---|
| What happened today | `Timeline.read(today)` |
| What is true now | `MemoryStore.active()` / `Brain.recall` |
| What was decided before | `Brain.recall` filtered to `decision` / `instruction` |
| What to inject into context | `Brain.recall_for_context` (passes the inject gate) |
| Which option to prefer | `Brain.prefer` (explainable prior) |
| Deep cross-time association | engine via `nmem` (if attached) |

## Sync rules (honest)

1. **Timeline is ground truth.** Never edit or delete events. The store is rebuildable from it.
2. **Store is a projection.** Every memory records `source_event_id`. A corrupted store can be
   replayed from the timeline.
3. **Engine sync is explicit.** `bridge.sync_timeline(timeline, bridge)` pushes high-salience
   facts outward. The report's `mode` is always the truth:
   - `DryRunBridge` → `mode="dry-run"`, `written=0` (nothing left the process).
   - `SubprocessBridge` → real `nmem` writes; `written` = actual count.
   **There is no "simulate" path that reports success while doing nothing.**
4. **Library is derived.** Daily markdown is a convenience view, never authoritative over the
   store.

## Conflict / supersession

When a new fact contradicts an old one, the `AdmissionGate` near-duplicate check (token Jaccard)
proposes `supersede`: the old memory's `valid_to` is set (it leaves the active set but is
**retained** for history), and the new memory records `supersedes`. The inject gate then refuses
to surface superseded memories into context.
