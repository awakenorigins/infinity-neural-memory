# V4 — Subconscious done honestly: the Explainable Preference Prior

The V4 brainstorm ("Tiềm thức AI") wanted memory to bias the agent's choices. Done naively that
is a hidden, un-auditable, poison-prone influence. V1 Final ships the **safe translation**, and
ships it as **real, tested code** (`inmem/preference_prior.py`, `Brain.prefer`).

```text
Implicit Bias Engine   →  Explainable Preference Prior   (inmem.preference_prior)
Associative Priming     →  Traceable Background Recall     (Brain.recall — already traced)
Dream Consolidation     →  Reported Insight Drafts         (digest — never auto-truth)
```

## How the prior works

Given options + a context, for each option it gathers supporting memories (hybrid recall),
keeps only evidence that *actually mentions* the option, and nudges a neutral 0.5 prior up/down
by **recency × confidence × trust**-weighted positive/negative evidence. It returns an
`OptionPrior` with:

```json
{
  "option": "Opus 4.6",
  "prior_score": 0.68,
  "support_count": 2,
  "reason_sources": ["<memory id>", "<memory id>"],
  "reasons": ["+ positive evidence: «Opus depth tốt, novel pass»"],
  "visible_when_asked": true
}
```

## The rules (non-negotiable)

- **No hidden influence.** Every prior carries its sources and reasons. `visible_when_asked` is
  always true.
- **No irreversible bias.** Evidence decays (recency weight) and can be superseded.
- **No poison amplification.** Low-confidence / low-trust memories contribute little; secrets
  never enter the store to begin with.
- **The prior advises, it does not decide.** The agent (and the user) can always override and
  inspect the ledger.

> A subconscious with a residence permit — inspectable, decaying, overridable — not a ghost.
