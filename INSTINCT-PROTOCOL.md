# INSTINCT-PROTOCOL — When to remember, when to recall

⚠️ **PROTOCOL layer** — agent behavior, not code-enforced. The CODE makes it *safe* to follow
eagerly (the AdmissionGate dedupes, blocks secrets, rejects low confidence automatically).

## Auto-remember (call `Brain.remember` / `Brain.log_exchange`)

| You observe | category | salience | note |
|---|---|---|---|
| A decision ("chọn X vì Y") | `decision` | 0.75 | record the *reason*, not just the choice |
| A rule ("luôn/không bao giờ…") | `instruction` | 0.9 | set `pinned=True` |
| Task/chapter done ("Ch101 xong, 72/80") | `workflow` | 0.5 | |
| A bug/failure | `error` | 0.6 | feeds the pre-action gate later |
| New fact about user/project | `fact` | 0.5 | |

Be eager — the gate is your safety net. Read `admission.reasons` if you need to explain a skip.

## Lazy recall (3 tiers, token-aware)

1. **Always** a cheap `recall(query, top_k=3)` on any input with a proper noun, project name, or
   concept. Prefer `recall_for_context` so only safe + fresh + relevant memories are injected.
2. On a miss that *feels* previously-seen, widen the query and raise `top_k`.
3. Skip recall on greetings or trivially self-contained inputs.

## Before a risky action

Call `Brain.pre_action(action, target)`. If `risk == "high"`, surface the warnings and get
confirmation. Governance, not a hard block.

## When choosing between options

Call `Brain.prefer(options, context=...)`. It returns a ranked, **explained** prior from past
evidence. Show the reason ledger if asked — influence here is never hidden.

## Hygiene (every few days)

- Let contradictions create supersession (the gate proposes it on near-duplicates).
- Pinned rules/identity never decay out of recall.
- Never hard-delete unless the user asks or a secret slipped past redaction.
