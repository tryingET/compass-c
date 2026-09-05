---
summary: "Runtime-local documentation seed for self-contained ROCS consumer artifacts."
read_when:
  - "Inspecting the files embedded into a bootstrapped ROCS consumer runtime."
type: "reference"
---

# ROCS self-contained consumer runtime

This file is packaged as an immutable bootstrap seed. `rocs bootstrap` publishes a
hash-complete consumer artifact under `tools/rocs-cli/` and records every runtime
file in `VENDORED_HASHES.json`.

Consumers execute `rocs.py` with isolated system Python (`python3 -I -S -B`). The
artifact does not discover a source checkout, use ambient `PYTHONPATH`, require
`uv`, fetch dependencies, or contact a remote service.

The generated `scripts/ci/full.sh` embeds the expected digest of
`VENDORED_HASHES.json` and verifies the complete artifact before importing ROCS.
