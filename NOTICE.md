# NOTICE

Infinity Neural Memory bundles, as an **optional** heavyweight backend, the third-party
package **neural-memory 4.12.0** (`dist/neural_memory-4.12.0-py3-none-any.whl`).

- The core `inmem` package does **not** import or require it — it is stdlib-only and fully
  functional on its own (see `VERIFY.py`, `pytest`).
- `neural-memory` is used only when you explicitly opt into the external engine via
  `inmem.bridge.SubprocessBridge` (which shells out to the `nmem` CLI) or via an OpenClaw
  agent calling its MCP `nmem_*` tools.
- License for the bundled wheel: see `LICENSES/MIT-neural-memory.txt`.

All first-party code in this repository is MIT-licensed (`LICENSE`).
