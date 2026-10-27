"""Embedding (V1.1) — pluggable embedders with a cache signature.

Default `HashingEmbedder` stays offline/deterministic so tests and CI are hermetic. V1.1 adds
optional **real semantic** adapters that talk HTTP via stdlib `urllib` (no SDK dependency), so
the package core remains zero-dependency:

  * OpenAIEmbedder  — OpenAI-compatible /v1/embeddings (set api_key or OPENAI_API_KEY).
  * OllamaEmbedder  — local Ollama /api/embeddings (default http://localhost:11434).

Each embedder exposes `.sig` (name + model + dim) so the store can invalidate cached vectors
when the embedder changes. `embed_batch` lets the retrieval layer amortize calls.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import urllib.request
from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    dim: int
    sig: str
    def embed(self, text: str) -> list: ...


class HashingEmbedder:
    """Offline, deterministic hashing-trick embedder (default). Not semantic SOTA — honest."""
    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        self.sig = f"hashing:{dim}"

    def embed(self, text: str) -> list:
        from inmem.vietnamese import tokenize
        vec = [0.0] * self.dim
        toks = tokenize(text)
        feats = list(toks)
        folded = "".join(toks)
        for i in range(len(folded) - 2):
            feats.append("#" + folded[i:i + 3])
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

    def embed_batch(self, texts: list) -> list:
        return [self.embed(t) for t in texts]


def _l2(vec: list) -> list:
    n = math.sqrt(sum(v * v for v in vec))
    return [v / n for v in vec] if n > 0 else vec


class _HTTPEmbedder:
    """Shared HTTP plumbing for OpenAI-compatible / Ollama embedders."""
    def __init__(self, url: str, model: str, dim: int, headers: dict, timeout: float) -> None:
        self.url = url
        self.model = model
        self.dim = dim
        self.headers = headers
        self.timeout = timeout
        self.sig = f"{self.__class__.__name__}:{model}:{dim}"

    def _post(self, payload: dict) -> dict:  # pragma: no cover - network
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.url, data=data,
                                     headers={"Content-Type": "application/json", **self.headers})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


class OpenAIEmbedder(_HTTPEmbedder):
    def __init__(self, model: str = "text-embedding-3-small", dim: int = 1536,
                 api_key: str | None = None, base_url: str = "https://api.openai.com/v1",
                 timeout: float = 20.0) -> None:
        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        super().__init__(f"{base_url}/embeddings", model, dim,
                         {"Authorization": f"Bearer {key}"}, timeout)

    def embed(self, text: str) -> list:  # pragma: no cover - network
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list) -> list:  # pragma: no cover - network
        out = self._post({"model": self.model, "input": texts})
        return [_l2(item["embedding"]) for item in out["data"]]


class OllamaEmbedder(_HTTPEmbedder):
    def __init__(self, model: str = "nomic-embed-text", dim: int = 768,
                 base_url: str = "http://localhost:11434", timeout: float = 20.0) -> None:
        super().__init__(f"{base_url}/api/embeddings", model, dim, {}, timeout)

    def embed(self, text: str) -> list:  # pragma: no cover - network
        out = self._post({"model": self.model, "prompt": text})
        return _l2(out["embedding"])

    def embed_batch(self, texts: list) -> list:  # pragma: no cover - network
        return [self.embed(t) for t in texts]


def cosine(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return max(-1.0, min(1.0, dot))  # inputs are pre-normalized
