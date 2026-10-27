# PUBLISH GUIDE — Infinity Neural Memory v1.2.0

Two scenarios. **Scenario A (recommended)** = a clean new repo. **Scenario B** = overwrite the
existing `infinity-neural` repo in place. Pick one.

> Before anything: unzip `Infinity-Neural-Memory-V1.2.0.zip` and `cd` into the folder
> `infinity-neural-memory-v1.2.0`. Run `python VERIFY.py` once — it must print 35/35.

---

## Step 0 — .gitignore (already done in this package ✅)

This package already scopes the ignore so the optional vendored engine
`dist/neural_memory-4.12.0-py3-none-any.whl` **is tracked**, while your own build outputs
(`dist/infinity_neural_memory-*`) and runtime data (`*.db`, `timeline/`, `seed/private/*`) are
ignored. Nothing to do — just don't re-add a blanket `dist/` rule.

---

## Scenario A — new clean repo `infinity-neural-memory` (recommended)

A fresh repo means no phantom history, no baggage. Create an EMPTY repo on GitHub first
(no README/license), named `infinity-neural-memory`. Then:

```bash
git init
git add .
git status                      # sanity check: no *.db, no timeline/, no seed/private/*
git commit -m "Infinity Neural Memory v1.2.0 — honest, self-contained memory nervous system

Append-only timeline + SQLite belief store, hybrid BM25+vector recall (RRF),
write-side admission + retrieval-side injection + pre-action governance gates,
explainable preference prior, secret+PII redaction, Vietnamese NLP.
No fork, no ETERNAL/zero-decay, no simulated sync. VERIFY 35/35, 64 tests."

git branch -M main
git remote add origin https://github.com/NachaFromMars/infinity-neural-memory.git
git push -u origin main

# tag the release
git tag -a v1.2.0 -m "v1.2.0 — crown-ready patch (redaction + supersession fixes)"
git push origin v1.2.0
```

Then **retire the old repo** so it stops misleading people (see "Step Z" below).

---

## Scenario B — overwrite the existing `infinity-neural` repo in place

Use this if you want to keep the existing repo URL/stars. It replaces the old (phantom) contents
with v1.2.0 and starts a clean main history.

```bash
git init
git add .
git commit -m "Reset to Infinity Neural Memory v1.2.0 — honest, self-contained rewrite

Removes the V1–V3.1 phantom claims (zero-decay, ETERNAL/ANCHOR, schema v21,
'46 MCP tools', inflated test counts). Ships a tested stdlib core + OpenClaw layer.
VERIFY 35/35, 64 tests, fresh-install verified."
git branch -M main
git remote add origin https://github.com/NachaFromMars/infinity-neural.git

# overwrite remote main (history reset). Make sure this is what you want.
git push -u origin main --force

git tag -a v1.2.0 -m "v1.2.0 — honest rebuild"
git push origin v1.2.0
```

> ⚠️ `--force` rewrites the remote. If anyone depends on the old tree, prefer Scenario A.

---

## Step 1 — create the GitHub Release (after pushing the tag)

GitHub → the repo → **Releases → Draft a new release**:

- **Tag:** `v1.2.0`
- **Title:** `Infinity Neural Memory v1.2.0`
- **Body:** paste `RELEASE-NOTES-v1.2.0.md`
- **Attach binaries:** upload your build outputs (they're not committed):
  - `dist/infinity_neural_memory-1.2.0-py3-none-any.whl`
  - `dist/infinity_neural_memory-1.2.0.tar.gz`
- Mark as **latest release**. (Leave "pre-release" unchecked — the P0 fixes make this a real V1.)

CLI alternative (with `gh`):

```bash
gh release create v1.2.0 \
  dist/infinity_neural_memory-1.2.0-py3-none-any.whl \
  dist/infinity_neural_memory-1.2.0.tar.gz \
  --title "Infinity Neural Memory v1.2.0" \
  --notes-file RELEASE-NOTES-v1.2.0.md
```

---

## Step 2 — confirm CI is green

The included `.github/workflows/ci.yml` runs on push: VERIFY + 64 tests on Python 3.10–3.12 +
gitleaks (with the `.gitleaks.toml` fixture allowlist). Check the Actions tab shows a green run.

---

## Step Z — kill the old phantom README (do NOT skip this)

If you went with **Scenario A**, the old `infinity-neural` repo still advertises zero-decay /
ETERNAL / "46 MCP tools" / schema v21. That's the misleading public face. Either:

1. **Archive it** (Settings → Archive this repository) **and** replace its `README.md` with
   `README-OLD-REPO-NOTICE.md` (a short honest "superseded by" pointer), or
2. **Redirect**: replace its `README.md` with that notice and pin an issue linking to the new repo.

```bash
# in a clone of the OLD infinity-neural repo:
cp /path/to/README-OLD-REPO-NOTICE.md README.md
git add README.md
git commit -m "Notice: superseded by infinity-neural-memory v1.2.0 (remove outdated claims)"
git push
```

Shipping clean code while the old README still lies is "two courts in one palace." Close the
second court.
