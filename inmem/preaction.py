"""PreActionGate — the deterministic "have we failed at this before?" check.

This is the feature Mula singled out from ProjectMem: before an agent edits a file,
changes config, or deploys, consult memory for (a) past failures involving the target,
(b) explicit rules against the action, (c) fragility warnings. Returns a transparent
verdict the agent can surface to the user.

It NEVER blocks silently — it returns warnings + the supporting memories so a human or
agent can decide. Governance, not censorship.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from inmem.retrieval import hybrid_search
from inmem.vietnamese import normalize

# folded signal words
_FAILURE = [normalize(w) for w in ["fail", "failed", "lỗi", "rework", "sai", "crash", "vỡ", "hỏng", "bug"]]
_PROHIBIT = [normalize(w) for w in ["không", "never", "đừng", "cấm", "tránh", "tuyệt đối không"]]
_FRAGILE = [normalize(w) for w in ["fragile", "mong manh", "dễ vỡ", "cẩn thận", "nhạy cảm", "careful"]]


@dataclass
class PreActionVerdict:
    proceed: bool
    risk: str  # "low" | "medium" | "high"
    warnings: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)  # memory ids


class PreActionGate:
    def __init__(self, *, embedder=None, high_risk_categories=("error", "instruction")) -> None:
        self.embedder = embedder
        self.high_risk_categories = set(high_risk_categories)

    def judge(self, store, action: str, target: str = "", *, scope: str = "global") -> PreActionVerdict:
        query = f"{action} {target}".strip()
        hits = hybrid_search(store, query, top_k=8, scope=scope, embedder=self.embedder)
        warnings: list[str] = []
        related: list[str] = []
        risk_points = 0

        for h in hits:
            text = normalize(h.memory["norm_text"])
            cat = h.memory["category"]
            tags = []
            hit_failure = any(w in text for w in _FAILURE)
            hit_prohibit = any(w in text for w in _PROHIBIT)
            hit_fragile = any(w in text for w in _FRAGILE)
            if hit_prohibit and cat in ("instruction", "decision"):
                warnings.append(f"rule against this: «{_clip(h.memory['content'])}»")
                related.append(h.memory["id"]); risk_points += 3
            elif hit_failure:
                warnings.append(f"past failure recorded: «{_clip(h.memory['content'])}»")
                related.append(h.memory["id"]); risk_points += 2
            elif hit_fragile:
                warnings.append(f"fragility note: «{_clip(h.memory['content'])}»")
                related.append(h.memory["id"]); risk_points += 1

        risk = "high" if risk_points >= 3 else "medium" if risk_points >= 1 else "low"
        proceed = risk != "high"
        if not warnings:
            warnings.append("no prior failures, rules, or fragility notes found for this action")
        return PreActionVerdict(proceed=proceed, risk=risk, warnings=warnings, related=related)


def _clip(s: str, n: int = 90) -> str:
    s = (s or "").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"
