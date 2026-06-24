---
name: riscv-inst-decoder
description: |
  Decode RISC-V instructions using gem5's decode tree.
  Use when the user asks to decode a RISC-V instruction hex, identify an illegal
  instruction encoding, show the decode path and instruction subset hierarchy,
  or analyse which field caused an illegal instruction exception.

  Trigger phrases: "decode instruction", "illegal instruction", "instruction
  encoding", "decode tree", "decode path", "instruction subset", "opcode decode".

  The bundled decode_tree.json was extracted from gem5's RISC-V decoder.isa
  and covers RV64GC (scalar integer, float, compressed, vector).
  It does NOT depend on gem5 at runtime.
---

# RISC-V Instruction Decoder

A self-contained tool that decodes RISC-V instruction encodings using gem5's
decode tree. The decode tree is pre-extracted and bundled as
`decode_tree.json` — no gem5 dependency at runtime.

## Files

| file | purpose |
|------|---------|
| `decode_tree.json` | Pre-generated decode tree (~637 KB, RV64GC + V) |
| `decode_inst.py`   | Standalone decoder script (stdlib only) |

## Quick start

```bash
python3 /path/to/skill/decode_inst.py 0x9e053057
```

Output:

```
  0x9e053057
    -> QUADRANT=0x3 [OPFVF/OPFVV/OPIVI/OPIVV/OPIVX/OPMVV]
    -> OPCODE5=0x15 [OPFVF/OPFVV/OPIVI/OPIVV/OPIVX/OPMVV]
    -> FUNCT3=0x3 [OPIVI]
    -> VFUNCT6=0x27 [OPIVI]
    -> VM=0x1 [OPIVI]
    -> SIMM3=0x2 ✗ not in ['0x0', '0x1', '0x3', '0x7']
  ILLEGAL INSTRUCTION
  SIMM3=0x2 not in ['0x0', '0x1', '0x3', '0x7']
  hint: SIMM3 encodes NREG-1; legal: 0,1,3,7 (NREG=1,2,4,8)
```

Multiple instructions:

```bash
python3 /path/to/skill/decode_inst.py 0x9e053057 0x0007879b
```

## Python API

```python
from decode_inst import load_tree, make_inst, decode_instruction

tree = load_tree()            # loads bundled decode_tree.json
inst = make_inst(0x9e053057)  # wrap 32-bit hex → 64-bit ExtMachInst
result, path, info = decode_instruction(inst, tree)

print(result["name"])                     # "illegal" | "addiw" | …
print(result["format"])                   # "VMvWholeFormat" | "IOp" | …

if info:
    print(info["field"], info["value"])   # e.g. SIMM3, 0x2
    print(info["valid"])                  # ["0x0", "0x1", "0x3", "0x7"]
    print(info.get("hint"))               # semantic explanation
```

## Interpreting the output

### Decode path (lines with `→`)

Each step shows `field=value [subset]`:

- `QUADRANT=0x3` — 32-bit instruction (compressed instructions are 0x0/0x1/0x2)
- `OPCODE5=0x15` — OP-V (vector arithmetic) instruction space
- `FUNCT3=0x3 [OPIVI]` — entering **OPIVI** (vector-immediate) subset
- `VFUNCT6=0x27` — within VFUNCT6 range
- `SIMM3=0x2 ✗ not in [...]` — illegal: value 0x2 has no matching case

The `[subset]` label is **path-local** — it shows only the subset of instructions
reachable via the **matched** case, excluding sibling branches. This avoids
"subset pollution" from unrelated instruction paths.

Labels with more than 10 items (root-level unions with no narrowing) are
suppressed to reduce noise.

### Subset labels

Labels come from two sources:

1. **RISC-V V spec subset** (from instruction definition's 2nd argument):
   `OPIVV` / `OPFVV` / `OPMVV` / `OPIVI` / `OPIVX` / `OPFVF` / `OPMVX`

2. **Format name fallback** (for non-vector instructions that lack subset):

   | label | meaning |
   |-------|---------|
   | `IOp` | integer immediate arithmetic |
   | `ROp` | integer register arithmetic |
   | `BOp` | branch |
   | `Load` / `Store` | load / store |
   | `UOp` / `JOp` / `Jump` | upper-immediate / jump / indirect jump |
   | `FPROp` | floating-point arithmetic |
   | `CSROp` / `SystemOp` | CSR access / system instructions |
   | `HyperLoad` / `HyperStore` | hypervisor memory access |
   | `AtomicMemOp` / `LoadReserved` / `StoreCond` | AMO / LR / SC |
   | `FenceOp` | memory barrier |
   | `BSOp` / `CBMOp` | bit-manipulation (Zb*) |
   | `CompressedLoad` / `CompressedStore` | compressed load/store |
   | `CJOp` / `CIOp` / `CBOp` / `CROp` | compressed branches/immediates |
   | `VleOp` / `VlmOp` / `VlSegOp` | vector load variants |
   | `VseOp` / `VsmOp` / `VsSegOp` | vector store variants |
   | `VConfOp` | vector configuration (vsetvli) |

### Illegal instruction

Three pieces of information:

1. **Failure field**: the `field=value` that doesn't match
2. **Valid values**: what the tree accepts (from the decode tree case values)
3. **Hint**: semantic explanation of the constraint (e.g. "SIMM3 encodes NREG-1")

## Context flags (64-bit ExtMachInst)

gem5 wraps the 32-bit instruction in a 64-bit `ExtMachInst` that includes
decoder-specific context bits. The `make_inst()` helper sets these:

- **bit[63:62] = rv_type**: 0=RV32, 1=RV64, 2=RV128 (default RV64)
- **bit[61] = compressed**: whether the instruction was fetched as 16-bit
- **bit[60] = enable_zcd**: whether Zcd extension is enabled (default on)

These affect which decode-tree branches are reachable (e.g. `addiw` requires
rv_type=1, Zcd compressed instructions require enable_zcd=1).

## Limitations

- The bundled `decode_tree.json` was generated from gem5's `decoder.isa`
  for RV64GC + V. Instructions from other ISAs (Zk*, Zb*, …) are included
  if they were present in that decoder.isa.
- Regeneration requires the gem5 ISA parser (not bundled here).
- 16-bit compressed instructions are currently passed as 32-bit values
  (zero-extended high bits). The QUADRANT field correctly identifies them.
