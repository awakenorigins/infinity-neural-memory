"""PreferencePrior — the V4 "subconscious" idea, made honest.

The V4 brainstorm wanted memory to bias the agent's choices. Done naively that's a hidden,
un-auditable, poison-prone influence. This module makes the influence **explicit**:

  Implicit Bias Engine   -> Explainable Preference Prior  (this module)
  Associative Priming     -> Traceable Background Recall    (Brain.recall, already traced)
  Dream Consolidation     -> Reported Insight Drafts        (digest, not auto-truth)

Given a set of options and the memory store, it scores each option from past evidence and
returns a **ledger**: the score, the supporting memories, and how recency/trust shaped it.
Influence you can read, question, and override — never a ghost in the machine.

    PreferencePrior(brain).rank(["Opus 4.6", "Sonnet"], context="viết truyện")
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from inmem.retrieval import hybrid_search
from inmem.vietnamese import normalize

# folded sentiment cues
_POS = [normalize(w) for w in ["tốt", "pass", "thành công", "thích", "hiệu quả", "ổn", "win", "depth", "good", "prefer"]]
_NEG = [normalize(w) for w in ["lỗi", "fail", "tệ", "ghét", "chậm", "vỡ", "kém", "thiếu", "bad", "rework"]]


@dataclass
class OptionPrior:
    option: str
    prior_score: float
    support_count: int
    reason_sources: list[str] = field(default_factory=list)  # memory ids
    reasons: list[str] = field(default_factory=list)
    visible_when_asked: bool = True  # influence is always inspectable


def _recency_weight(created_at: str | None, half_life_days: float = 120.0) -> float:
    if not created_at:
        return 0.6
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        age = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
        return math.exp(-age / half_life_days)
    except Exception:
        return 0.6


class PreferencePrior:
    def __init__(self, brain) -> None:
        self.brain = brain

    def rank(self, options: list[str], *, context: str = "", scope: str | None = None,
             top_evidence: int = 6) -> list[OptionPrior]:
        results: list[OptionPrior] = []
        for opt in options:
            query = f"{opt} {context}".strip()
            hits = hybrid_search(self.brain.store, query, top_k=top_evidence,
                                 scope=scope, embedder=self.brain.embedder)
            score = 0.5  # neutral prior
            sources: list[str] = []
            reasons: list[str] = []
            for h in hits:
                text = normalize(h.memory["norm_text"])
                if normalize(opt) not in text:
                    continue  # evidence must actually mention the option
                w = _recency_weight(h.memory["created_at"]) * float(h.memory["confidence"]) \
                    * float(h.memory["trust"])
                pos = any(p in text for p in _POS)
                neg = any(n in text for n in _NEG)
                delta = 0.0
                if pos and not neg:
                    delta = 0.18 * w
                    reasons.append(f"+ positive evidence: «{_clip(h.memory['content'])}»")
                elif neg and not pos:
                    delta = -0.18 * w
                    reasons.append(f"- negative evidence: «{_clip(h.memory['content'])}»")
                else:
                    continue
                score += delta
                sources.append(h.memory["id"])
            score = max(0.0, min(1.0, score))
            if not sources:
                reasons.append("no decisive past evidence — neutral prior")
            results.append(OptionPrior(option=opt, prior_score=round(score, 4),
                                       support_count=len(sources), reason_sources=sources,
                                       reasons=reasons))
        results.sort(key=lambda o: o.prior_score, reverse=True)
        return results


def _clip(s: str, n: int = 80) -> str:
    s = (s or "").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"
