# Vietnamese NLP (reference)

`inmem/vietnamese.py` provides the offline, dependency-free Vietnamese handling used by
retrieval, the gates, and the preference prior.

## Capabilities

- **Tone folding** (`strip_tones`): NFD-decompose, drop combining marks, fold `đ→d`. So
  `"Quyết Định"` → `"Quyet Dinh"` and `quyet dinh` matches `quyết định` at recall time.
- **Normalization** (`normalize`): lowercase + tone-fold + whitespace-collapse.
- **Compound-aware tokenization** (`tokenize`): joins known bigrams (e.g. `quyết định` →
  `quyet_dinh`) so compounds survive BM25 as single terms. Extend with `COMPOUNDS.update(...)`.
- **CJK detection** (`is_cjk`): so Chinese/Japanese/Korean text can be handled distinctly.

## Why folding matters

Vietnamese users type with and without tones interchangeably. Folding both the query and the
stored text to a tone-free form makes recall robust to that variation without a heavyweight NLP
dependency.

## Extending

```python
from inmem.vietnamese import COMPOUNDS, _ensure_compounds
_ensure_compounds()
COMPOUNDS.update({"machine_learning"... })  # add domain compounds (tone-folded, space-joined)
```

> Note: importance/persistence is handled by `pinned` + salience, not by any special "eternal"
> token. There is no ETERNAL/ANCHOR type in this system.
