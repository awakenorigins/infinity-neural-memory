"""Embedding — a real but simple offline embedder so vector search + RRF are testable
without any API key or native dependency.

HashingEmbedder turns text into a fixed-dim L2-normalized vector using hashed token +
character-trigram features (a "hashing trick" bag-of-features). It is deterministic and
language-agnostic, and good enough to demonstrate hybrid retrieval. For production quality,
implement the Embedder protocol with OpenAI / Ollama / SentenceTransformers and pass it in.

This is intentionally NOT marketed as semantic SOTA — honesty over hype.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

from inmem.vietnamese import tokenize


class Embedder(Protocol):
    dim: int
    def embed(self, text: str) -> list[float]: ...


class HashingEmbedder:
    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        toks = tokenize(text)
        feats: list[str] = list(toks)
        # character trigrams add sub-word robustness (typos, morphology)
        folded = "".join(toks)
        for i in range(len(folded) - 2):
            feats.append("#" + folded[i : i + 3])
        if not feats:
            return vec
        for f in feats:
            h = int(hashlib.md5(f.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return max(-1.0, min(1.0, dot))  # inputs are pre-normalized
