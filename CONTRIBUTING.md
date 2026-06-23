# Contributing

Thanks for helping. This project has one non-negotiable law:

> **Ship only what runs. Label protocol vs code. No public claim without a passing test.**

Every PR is checked against it.

## Setup

```bash
git clone <your fork>
cd infinity-neural-memory
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install        # local secret scan + verify gate
```

## Before you open a PR

```bash
make verify    # python VERIFY.py  -> must be 21/21, exit 0
make test      # pytest tests/     -> all green
make build     # wheel + sdist build cleanly
```

CI runs the same on Python 3.10–3.12 plus a `gitleaks` secret scan. PRs that fail any of these
will not be merged.

## Rules of the road

1. **No phantom API.** Do not reference a module/class/field that the shipped package does not
   contain. If you add a capability, add it as real code *and* a test in the same PR.
2. **Tests are the spec.** New behavior ⇒ new test. If a claim in the README/SKILL.md isn't
   covered by a test, either add the test or remove the claim.
3. **Honesty over hype.** If something is a stub, label it a stub (see `DryRunBridge`,
   `ConsoleNotifier`). Never print success while doing nothing.
4. **Secrets never persist.** Anything touching a write path must go through `Redactor` and
   respect the `AdmissionGate`. Add a redaction test for new sinks.
5. **Keep the core dependency-free.** The `inmem` package is stdlib-only by design. Heavy/
   optional integrations go behind an explicit adapter (see `inmem/bridge.py`) and as
   `[project.optional-dependencies]`.
6. **Type hints + `py.typed`.** Public functions are typed.

## Commit & PR style

- Small, focused commits. Conventional-ish subjects are appreciated (`feat:`, `fix:`, `docs:`).
- Fill in the PR template checklist. Reference the issue you're closing.
- Update `CHANGELOG.md` under an *Unreleased* section.

## Adding a fact extractor / language

Extraction lives in `inmem/brain.py` (`extract_facts` + regex lists) and tokenization in
`inmem/vietnamese.py`. Add patterns with a test case that proves they fire (and don't over-fire).
