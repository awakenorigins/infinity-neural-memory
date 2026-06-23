# Seed corpus — policy

**Private by default.** Your real memory corpus is personal data. Do NOT commit it to a public
repo. This folder ships only a small **synthetic sample** (`sample/`) to demonstrate the
importer; the real corpus stays out of git (`.gitignore` blocks `seed/private/`).

## How to bootstrap from your own corpus

```bash
# 1) dry-run: see what PII/secrets would be found (writes nothing)
python scripts/seed_import.py --source seed/private --check

# 2) import for real (PII-scrubbed + secret-blocked + deduped into the store)
python scripts/seed_import.py --source seed/private --db ~/.inmem/memory.db --timeline ~/.inmem/timeline
```

`seed_import.py` scrubs emails / IPs / OS user-home paths (via `inmem.pii`) **and** runs every
chunk through the write-side `AdmissionGate` (secrets are blocked, duplicates skipped). Nothing
raw reaches the store.

See `MANIFEST.json` for the sample inventory.
