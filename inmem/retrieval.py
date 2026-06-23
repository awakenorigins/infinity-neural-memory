"""Retrieval — hybrid BM25 + vector with Reciprocal Rank Fusion (library-memo's core idea).

BM25 (Okapi) runs over the active memory set, tokenized with Vietnamese-aware folding.
Vector search is optional: pass an embedder to enable it; otherwise BM25 alone is used.
Results are fused with RRF and may be passed through an optional cross-encoder reranker.

Everything is offline and deterministic for testing. No external service required.
"""

from __future__ import annotations

import math
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from inmem.embedding import Embedder, cosine
from inmem.vietnamese import tokenize


@dataclass
class Hit:
    memory: sqlite3.Row
    score: float
    bm25_rank: int | None = None
    vec_rank: int | None = None


class Reranker(Protocol):
    def rerank(self, query: str, hits: list[Hit]) -> list[Hit]: ...


def _bm25_rank(query: str, rows: list[sqlite3.Row], k1: float = 1.5, b: float = 0.75) -> list[tuple[str, float]]:
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
    scores: dict[str, float] = {}
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


def _vec_rank(query: str, rows: list[sqlite3.Row], embedder: Embedder) -> list[tuple[str, float]]:
    qv = embedder.embed(query)
    scored = [(r["id"], cosine(qv, embedder.embed(r["norm_text"]))) for r in rows]
    scored = [(i, s) for i, s in scored if s > 0]
    return sorted(scored, key=lambda x: x[1], reverse=True)


def _rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return fused


def hybrid_search(
    store,
    query: str,
    *,
    top_k: int = 5,
    scope: str | None = None,
    embedder: Embedder | None = None,
    reranker: Reranker | None = None,
    pinned_boost: float = 0.15,
) -> list[Hit]:
    rows = store.active(scope=scope)
    if not rows:
        return []
    by_id = {r["id"]: r for r in rows}

    bm = _bm25_rank(query, rows)
    bm_order = [d for d, _ in bm]
    rankings = [bm_order]
    vec_order: list[str] = []
    if embedder is not None:
        vec = _vec_rank(query, rows, embedder)
        vec_order = [d for d, _ in vec]
        rankings.append(vec_order)

    fused = _rrf(rankings)
    # pinned memories get a small, explicit, traceable boost (not zero-decay magic)
    for doc_id, row in by_id.items():
        if row["pinned"]:
            fused[doc_id] = fused.get(doc_id, 0.0) + pinned_boost

    hits: list[Hit] = []
    for doc_id, score in fused.items():
        hits.append(Hit(
            memory=by_id[doc_id],
            score=score,
            bm25_rank=(bm_order.index(doc_id) if doc_id in bm_order else None),
            vec_rank=(vec_order.index(doc_id) if doc_id in vec_order else None),
        ))
    hits.sort(key=lambda h: h.score, reverse=True)
    hits = hits[: max(top_k * 3, top_k)]
    if reranker is not None:
        hits = reranker.rerank(query, hits)
    return hits[:top_k]
