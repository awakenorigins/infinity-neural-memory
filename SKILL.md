---
name: infinity-neural-memory
version: 1.0.0
description: >
  Infinity Neural Memory V1 — honest memory nervous system for agents.
  Append-only timeline (ground truth) + SQLite projection with provenance +
  hybrid BM25/vector recall (RRF) + governance gates (admission + pre-action) +
  secret redaction + Vietnamese NLP. Self-contained Python, zero hard deps, fully tested.
  Use when: deciding WHEN to remember/recall, logging exchanges, checking a risky action
  against past failures, or producing a daily digest.
  Triggers: infinity neural memory, remember this, recall, auto remember, lazy recall,
  pre-action check, memory gate, admission gate, timeline, daily digest, dual brain,
  bộ nhớ, ghi nhớ, nhớ lại, kiểm tra trước khi làm.
---

# Infinity Neural Memory V1 — Skill Protocol

> Two layers, clearly separated (the lesson learned the hard way):
> **CODE** = enforced by Python with tests. **PROTOCOL** = behavior the agent follows.
> Nothing in CODE references a phantom API; nothing in PROTOCOL claims to be enforced.

## ✅ CODE layer (runs, tested: `python VERIFY.py` → 26/26, `pytest` → 47)

| Capability | Entry point | Guarantee |
|---|---|---|
| Append-only timeline | `Timeline.append/read` | redacted on write, file-locked, one file/day |
| Memory store | `MemoryStore` | provenance + temporal validity + supersession |
| Hybrid recall | `hybrid_search` / `Brain.recall` | BM25 + optional vector, RRF fused |
| **Write-side gate** | `AdmissionGate.evaluate` | what to WRITE: dedupe (Jaccard) / sensitive / confidence |
| **Inject-side gate** | `InjectionGate` / `Brain.recall_for_context` | what to SHOW the model: relevance + freshness + sensitive + superseded |
| Risk check | `PreActionGate.judge` | warns on past failures / rules / fragility |
| **Preference Prior** | `PreferencePrior` / `Brain.prefer` | explainable, traceable option ranking (V4 done honestly) |
| Secret scrub | `Redactor.redact` | secrets never persisted; SHA-256 kept |
| **PII scrub** | `PiiScrubber.scrub` | emails / IPs / user-home paths removed |
| **Safe seed import** | `scripts/seed_import.py` | PII-scrub + secret-block + dedupe before store |
| Vietnamese NLP | `inmem.vietnamese` | tone fold + compound tokens |
| Digest | `compute_digest` + notifiers | real counts; honest delivery (Console/Webhook) |
| External engine | `bridge.SubprocessBridge` (→ `nmem`) | reports true mode; DryRun by default |

## ⚠️ PROTOCOL layer (agent behavior — not code-enforced)

### A. WHEN to remember (auto)
Call `brain.remember(...)` (or `log_exchange`) when you observe:

| Trigger | category | salience |
|---|---|---|
| User makes a decision ("chọn X vì Y") | `decision` | 0.75 |
| A rule ("luôn/không bao giờ…") | `instruction` | 0.9 (+ `pinned=True`) |
| Task/chapter completion ("Ch101 xong, score 72/80") | `workflow` | 0.5 |
| A bug/failure | `error` | 0.6 |
| A new fact about user/project | `fact` | 0.5 |

The AdmissionGate will dedupe, block secrets, and reject low confidence automatically — so it
is safe to be eager. Read the returned `admission.reasons` if you need to explain a skip.

### B. WHEN to recall (lazy, token-aware)
1. **Always** do a cheap `recall(query, top_k=3)` on any input with a proper noun, project name,
   or concept. Inject hits into context.
2. If it misses **and** the topic feels previously-seen, widen the query and raise `top_k`.
3. Don't recall on pure greetings or trivially self-contained inputs.

### C. BEFORE a risky action (deploy / edit config / delete / migrate)
Call `brain.pre_action(action, target)`. If `risk == "high"`, surface the warnings to the user
and get confirmation before proceeding. This is governance, not a hard block.

### D. Dual-brain reading (where to look)
| Need | Source |
|---|---|
| What happened today | `timeline.read(today)` |
| What is true now | `MemoryStore.active()` / `recall` |
| What was decided before | `recall(query)` over `decision`/`instruction` |
| End-of-day summary | `brain.digest_text()` |

## Install / Verify
```bash
pip install -e .
python VERIFY.py        # exit 0 == all real features pass
```

## Hard rules (do not violate)
- Never persist a raw secret. (Redactor + AdmissionGate enforce this; don't bypass them.)
- Never edit or delete timeline events. They are immutable ground truth.
- Never claim an external sync happened unless the bridge reports `written > 0`.
- Importance is `pinned` + salience, explicit and visible — there is no "eternal" memory.
