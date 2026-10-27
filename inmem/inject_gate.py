"""InjectionGate — should this retrieved memory be INJECTED into the agent's context?

This is the gp project's good idea (retrieval-side admission), re-implemented on top of the
Vietnamese-aware tokenizer and the same Redactor, and wired to `Brain.recall`. It complements
`AdmissionGate` (which decides what to WRITE): this decides what to SHOW the model.

Every decision is explainable — score + reasons + the signals behind it. No hidden filtering.

    InjectionGate().evaluate(query, memory_row) -> InjectionDecision
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from inmem.redaction import Redactor
from inmem.vietnamese import tokenize


@dataclass
class InjectionDecision:
    admit: bool
    score: float
    relevance: float
    freshness: float
    sensitive: bool
    superseded: bool
    reasons: list[str] = field(default_factory=list)


def _overlap(query: str, text: str) -> float:
    q = set(tokenize(query))
    m = set(tokenize(text))
    if not q or not m:
        return 0.0
    return len(q & m) / len(q)


def _freshness(created_at: str | None, half_life_days: float = 180.0) -> float:
    if not created_at:
        return 0.5
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        age = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
        return math.exp(-age / half_life_days)
    except Exception:
        return 0.5


class InjectionGate:
    def __init__(self, *, min_score: float = 0.42,
                 w_relevance: float = 0.68, w_freshness: float = 0.22, base: float = 0.10,
                 sensitivity_penalty: float = 0.35, superseded_penalty: float = 0.5) -> None:
        self.min_score = min_score
        self.w_relevance = w_relevance
        self.w_freshness = w_freshness
        self.base = base
        self.sensitivity_penalty = sensitivity_penalty
        self.superseded_penalty = superseded_penalty
        self.redactor = Redactor()

    def evaluate(self, query: str, memory_row, *, pinned_floor: bool = True) -> InjectionDecision:
        content = memory_row["content"]
        relevance = _overlap(query, memory_row["norm_text"])
        freshness = _freshness(memory_row["created_at"])
        sensitive = bool(memory_row["sensitive"]) or self.redactor.redact(content).is_sensitive
        superseded = memory_row["valid_to"] is not None
        pinned = bool(memory_row["pinned"])

        score = (self.w_relevance * relevance) + (self.w_freshness * freshness) + self.base
        if sensitive:
            score -= self.sensitivity_penalty
        if superseded:
            score -= self.superseded_penalty
        score = max(0.0, min(1.0, score))

        reasons: list[str] = []
        reasons.append("strong overlap" if relevance >= 0.45
                       else "partial overlap" if relevance >= 0.2 else "weak overlap")
        if freshness >= 0.7:
            reasons.append("fresh")
        if pinned:
            reasons.append("pinned (rule/identity)")
        if sensitive:
            reasons.append("blocked: sensitive content")
        if superseded:
            reasons.append("blocked: superseded")

        # admit if score clears the bar and it's neither sensitive nor superseded;
        # a pinned, non-sensitive, current memory is always admissible (identity/rules).
        admit = (score >= self.min_score and not sensitive and not superseded) or \
                (pinned_floor and pinned and not sensitive and not superseded)
        return InjectionDecision(admit=admit, score=round(score, 4),
                                 relevance=round(relevance, 4), freshness=round(freshness, 4),
                                 sensitive=sensitive, superseded=superseded, reasons=reasons)
