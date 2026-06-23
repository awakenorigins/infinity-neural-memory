# Architecture — Infinity Neural Memory V1 Final

Four roles, two source-of-truth layers, two gates, one honest principle.

```
 timeline (events, immutable) ──projection──▶ store (belief, provenance + supersession)
        │ ground truth: "what happened"            │ "what is true now"
        ▼                                          ▼
   session logger                         ┌── recall (BM25 + vector, RRF)
   (redacted, locked)                     │
                                          ├── WRITE gate  : AdmissionGate (dedupe/secret/conf)
                                          ├── INJECT gate : InjectionGate (relevance/fresh/superseded)
                                          ├── PRE-ACTION  : "failed before?" warnings
                                          └── PREFER      : explainable Preference Prior (V4)

 optional engine: neural-memory 4.12.0 via SubprocessBridge → nmem  (heavyweight graph recall)
```

## The principle
**Ship only what runs. Label protocol vs code. No public claim without a passing test.**

## Why two gates (they're different points in the lifecycle)
- **Write-side** (`AdmissionGate`): decides what *enters* the store — dedupe (token Jaccard),
  secret block, confidence floor.
- **Inject-side** (`InjectionGate`): decides what *reaches the model* for a given query —
  relevance overlap, freshness (exp decay), sensitivity, supersession.
A complete system needs both, plus the **pre-action** gate for risky operations.

## Why the engine is optional
The lab audit's hardest lesson: never couple your docs/tests to an engine the shipped artifact
doesn't actually exercise. So the `inmem` core owns retrieval/store/gates as stdlib code, and
`neural-memory` is attached **only** through an explicit bridge that never lies about whether a
write happened.
