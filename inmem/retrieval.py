"""Retrieval (V1.1) — two-stage hybrid: FTS5 candidates -> cached-vector rerank -> RRF.

The V1.0 path embedded the entire active set on every query (Mula flagged this). V1.1:
  1. FTS5 returns the top-N lexical candidates (or in-memory BM25 if FTS5 is unavailable).
  2. Only those candidates are vector-reranked, using the store's embedding cache (lazily
     filled on miss) — so we never re-embed the whole store.
  3. The two rankings are fused with Reciprocal Rank Fusion; pinned memories get a small,
     explicit boost; an optional cross-encoder reranker can run last.
"""

from __future__ import annotations

import math
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from inmem.embedding import cosine
from inmem.vietnamese import tokenize


@dataclass
class Hit:
    memory: sqlite3.Row
    score: float
    bm25_rank: int | None = None
    vec_rank: int | None = None


class Reranker(Protocol):
    def rerank(self, query: str, hits: list) -> list: ...


def _bm25_rank(query: str, rows: list, k1: float = 1.5, b: float = 0.75) -> list:
    """In-memory Okapi BM25 — the fallback when FTS5 is unavailable."""
    docs = {r["id"]: tokenize(r["norm_text"]) for r in rows}
    if not docs:
        return []
    N = len(docs)
    avgdl = sum(len(t) for t in docs.values()) / N
    df: Counter = Counter()
    for toks in docs.values():
        for term in set(toks):
            df[term] += 1
    q_terms = tokenize(query)
    scores: dict = {}
    for doc_id, toks in docs.items():
        tf = Counter(toks)
        dl = len(toks)
        s = 0.0
        for term in q_terms:
            if term not in tf:
                continue
            idf = math.log(1 + (N - df[term] + 0.5) / (df[term] + 0.5))
            denom = tf[term] + k1 * (1 - b + b * dl / avgdl)
            s += idf * (tf[term] * (k1 + 1)) / denom
        if s > 0:
            scores[doc_id] = s
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def _rrf(rankings: list, k: int = 60) -> dict:
    fused: dict = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return fused


def _candidates(store, query: str, scope, candidate_k: int):
    """Stage 1: lexical candidates. Returns (ordered_ids, rows_by_id, used_fts)."""
    fts = store.fts_candidates(query, limit=candidate_k, scope=scope)
    if fts:
        ids = [i for i, _ in fts]
        rows = {i: store.get(i) for i in ids}
        rows = {i: r for i, r in rows.items() if r is not None}
        return [i for i in ids if i in rows], rows, True
    # fallback: in-memory BM25 over the active set
    active = store.active(scope=scope)
    rows = {r["id"]: r for r in active}
    bm = _bm25_rank(query, active)
    order = [d for d, _ in bm]
    if not order:  # no lexical hit; keep active set so vector search can still help
        order = list(rows.keys())[:candidate_k]
    return order[:candidate_k], rows, False


def _vector_rerank(store, query, embedder, cand_ids, rows):
    """Stage 2: vector rerank candidates using the embedding cache (lazy-fill on miss)."""
    qv = embedder.embed(query)
    scored = []
    for mid in cand_ids:
        v = store.get_embedding(mid, embedder.sig)
        if v is None:
            v = embedder.embed(rows[mid]["norm_text"])
            try:
                store.set_embedding(mid, v, embedder.sig)
            except Exception:
                pass
        s = cosine(qv, v)
        if s > 0:
            scored.append((mid, s))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [d for d, _ in scored]


def hybrid_search(store, query: str, *, top_k: int = 5, scope: str | None = None,
                  embedder=None, reranker=None, pinned_boost: float = 0.15,
                  candidate_k: int = 200) -> list:
    cand_ids, rows, _used_fts = _candidates(store, query, scope, candidate_k)
    if not cand_ids:
        return []

    rankings = [cand_ids]
    vec_order: list = []
    if embedder is not None:
        vec_order = _vector_rerank(store, query, embedder, cand_ids, rows)
        if vec_order:
            rankings.append(vec_order)

    fused = _rrf(rankings)
    for mid in cand_ids:
        if rows[mid]["pinned"]:
            fused[mid] = fused.get(mid, 0.0) + pinned_boost

    hits = []
    for mid, sc in fused.items():
        hits.append(Hit(memory=rows[mid], score=sc,
                        bm25_rank=(cand_ids.index(mid) if mid in cand_ids else None),
                        vec_rank=(vec_order.index(mid) if mid in vec_order else None)))
    hits.sort(key=lambda h: h.score, reverse=True)
    hits = hits[: max(top_k * 3, top_k)]
    if reranker is not None:
        hits = reranker.rerank(query, hits)
    return hits[:top_k]
