---
name: csr-parser
description: |
  Decode RISC-V CSR (Control and Status Register) values into named bitfields
  using the riscv-unified-db specification. Given a CSR name and hex value,
  display each field's name, bit range, binary value, and access type
  (WARL/WLRL/WPRI/WIRI). Also supports XOR-diff analysis to identify which
  fields changed between two CSR values.

  Trigger phrases: "decode CSR", "CSR value", "csr field", "csr bitfield",
  "mstatus", "CSR diff", "csr changed", "what CSR fields", "parse CSR".
---

# CSR Parser

Decode RISC-V CSR values into bitfields using riscv-unified-db.

## Requirements

- Python 3.8+
- `pip install pyyaml`
- Local clones of riscv-unified-db and riscv-config (see README)

## Quick Start

```bash
python scripts_udb_csr_cli.py decode \
  --spec ~/riscv-sources/spec/riscv-unified-db/spec/std/isa/csr \
  --config ~/riscv-sources/spec/riscv-config/examples/rv64i_isa_checked.yaml \
  --csr mstatus --value 0xa00002000
```

## Subcommands

| Command | Description |
|---------|-------------|
| `decode` | Decode a CSR value into named bitfields with access types |
| `diff`   | Given an XOR mask, list which fields changed |
| `compare`| Compare two CSR values and show differing fields |

## Cache

The first run parses YAML/JSON files; subsequent runs load a pickle cache.
Add `--no-cache` to force re-parsing. Cache lives alongside the spec directory.
