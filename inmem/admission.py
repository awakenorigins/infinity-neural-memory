"""AdmissionGate — decide whether a candidate memory should be WRITTEN, and why.

This is the "memory has a residence permit, not a ghost in the machine" principle.
Every decision returns a transparent breakdown of reasons — no hidden bias.

It guards against:
  * duplicates           -> near-identical active memory exists -> skip or supersede
  * secret leakage       -> redactor found a secret             -> block (or store flagged)
  * low confidence noise -> confidence below floor              -> block
  * stale supersession   -> candidate explicitly supersedes X    -> link, don't duplicate
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from inmem.redaction import Redactor
from inmem.retrieval import hybrid_search
from inmem.vietnamese import normalize, tokenize

# An explicit signal that the new memory REPLACES an old one (vs merely overlapping).
_SUPERSEDE_RE = re.compile(
    r"(thay\s+(cho|bằng|thế)|đổi\s+sang|chuyển\s+sang|không\s+dùng\s+.+\s+nữa|"
    r"bỏ\s+.+\s+dùng|replace[ds]?\b|supersede[ds]?\b|instead of|no longer use|deprecat)",
    re.I,
)


def explicit_supersession(text: str) -> bool:
    return bool(_SUPERSEDE_RE.search(text or ""))


@dataclass
class AdmissionResult:
    admit: bool
    action: str  # "insert" | "supersede" | "skip" | "block"
    scores: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    duplicate_of: str | None = None
    sensitive: bool = False
    found_secrets: list[str] = field(default_factory=list)


class AdmissionGate:
    def __init__(
        self,
        *,
        dup_threshold: float = 0.92,
        supersede_threshold: float = 0.86,
        min_confidence: float = 0.35,
        block_sensitive: bool = True,
        embedder=None,
    ) -> None:
        self.dup_threshold = dup_threshold
        self.supersede_threshold = supersede_threshold
        self.min_confidence = min_confidence
        self.block_sensitive = block_sensitive
        self.embedder = embedder
        self.redactor = Redactor()

    def evaluate(self, store, content: str, *, confidence: float = 0.7, scope: str = "global") -> AdmissionResult:
        reasons: list[str] = []
        scores: dict = {"confidence": round(confidence, 3)}

        # 1) secret scan
        red = self.redactor.redact(content)
        if red.is_sensitive:
            reasons.append(f"secret detected: {', '.join(red.found)}")
            if self.block_sensitive:
                return AdmissionResult(
                    admit=False, action="block", scores=scores, reasons=reasons,
                    sensitive=True, found_secrets=red.found,
                )

        # 2) confidence floor
        if confidence < self.min_confidence:
            reasons.append(f"confidence {confidence:.2f} < floor {self.min_confidence:.2f}")
            return AdmissionResult(admit=False, action="block", scores=scores, reasons=reasons,
                                   sensitive=red.is_sensitive, found_secrets=red.found)

        # 3) exact-hash duplicate (cheap, deterministic)
        exact = store.find_hash(red.original_sha256)
        if exact is not None:
            reasons.append("exact duplicate (same content hash)")
            scores["dup_similarity"] = 1.0
            return AdmissionResult(admit=False, action="skip", scores=scores, reasons=reasons,
                                   duplicate_of=exact["id"], sensitive=red.is_sensitive,
                                   found_secrets=red.found)

        # 4) near-duplicate via retrieval + real token Jaccard (not a fused-score proxy)
        hits = hybrid_search(store, content, top_k=1, scope=scope, embedder=self.embedder)
        if hits:
            top = hits[0]
            cand = set(tokenize(content))
            other = set(tokenize(top.memory["norm_text"]))
            union = cand | other
            sim = (len(cand & other) / len(union)) if union else 0.0
            scores["dup_similarity"] = round(sim, 3)
            # near-identical content is a DUPLICATE -> skip (not a replacement)
            if sim >= self.dup_threshold:
                reasons.append(f"near-duplicate of {top.memory['id']} (jaccard≈{sim:.2f}) -> skip")
                return AdmissionResult(admit=False, action="skip", scores=scores, reasons=reasons,
                                       duplicate_of=top.memory["id"], sensitive=red.is_sensitive,
                                       found_secrets=red.found)
            # only SUPERSEDE on a clear replacement signal + substantial overlap
            if sim >= self.supersede_threshold and explicit_supersession(content):
                reasons.append(f"explicit replacement of {top.memory['id']} "
                               f"(jaccard≈{sim:.2f}, signal) -> supersede")
                return AdmissionResult(admit=True, action="supersede", scores=scores,
                                       reasons=reasons, duplicate_of=top.memory["id"],
                                       sensitive=red.is_sensitive, found_secrets=red.found)

        reasons.append("novel, confident, no secret -> insert")
        return AdmissionResult(admit=True, action="insert", scores=scores, reasons=reasons,
                               sensitive=red.is_sensitive, found_secrets=red.found)
