# Roadmap (honest — not shipped yet)

- **V1.1** — ✅ DONE: FTS5 + two-stage retrieval + embedding cache + pluggable semantic
  embedders (OpenAI / Ollama). (Cross-encoder reranker hook exists; a bundled reranker is future.)
- **V1.2** — `timeline → store` rebuild command (proves event-sourcing); calibrated cosine for
  near-duplicate detection.
- **V1.3** — per-source trust scoring + low-confidence recall rejection (poisoning defense). (Right-to-forget / erasure: ✅ DONE in v1.2.0 via `forget`.)
- **V2.0** — Preference Prior with a decaying, audited influence ledger surfaced in the digest.

Everything above ships only when it runs and has a passing test.
