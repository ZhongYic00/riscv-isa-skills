# RISC-V Decoder Regression Tests

Run from repo root:

```bash
python3 skills/riscv-inst-decoder/scripts/decode_inst.py <hex> [<hex> ...]
```

Expected output uses `→` prefix (decode path) and a final line with instruction name.

## 1. Standard (Quadrant 3, 32-bit)

### R‑type arithmetic

| hex | instruction | format | spike-dasm |
|-----|------------|--------|------------|
| `0x00A58533` | `add` | ROp | `add a0, a1, a0` |
| `0x40348433` | `sub` | ROp | `sub s0, s1, gp` |
| `0x02113423` | `sd` | Store | `sd ra, 40(sp)` |
| `0x00B57663` | `bgeu` | BOp | `bgeu a0, a1, pc+12` |
| `0x0066c663` | `blt` | BOp | `blt a3, t1, pc+12` |
| `0x0202a023` | `sw` | Store | `sw zero, 32(t0)` |

### I‑type immediate

| hex | instruction | format | spike-dasm |
|-----|------------|--------|------------|
| `0xFD010113` | `addi` | IOp | `addi sp, sp, -48` |
| `0x0010029b` | `addiw` | IOp (RV64) | `addiw t0, zero, 1` |
| `0x0007879b` | `addiw` | IOp | `sext.w a5, a5` (addiw alias) |
| `0x00153513` | `sltiu` | IOp | `seqz a0, a0` (sltiu alias) |
| `0x10101013` | `sha256sum1` | IOp | Zk extension, not slli |

### U‑type / J‑type

| hex | instruction | format | spike-dasm |
|-----|------------|--------|------------|
| `0x000015b7` | `lui` | UOp | `lui a1, 0x1` |
| `0x004000ef` | `jal` | JOp | `jal pc+0x4` |
| `0x00050067` | `jalr` | Jump | `jr a0` (jalr alias) |

### Illegal

| hex | instruction | format | spike-dasm |
|-----|------------|--------|------------|
| `0x9e053057` | `illegal` | — | `unknown` |

## 2. Compressed

### Quadrant 1

| hex | instruction | format |
|-----|------------|--------|
| `0x17c1` | `c_addi` | CIOp |
| `0x57cd` | `c_li` | CIOp |
| `0x61fd` | `c_lui` | CIOp (default branch, RC1≠0,2) |
| `0x6105` | `c_addi16sp` | CIOp (RC1=2) |
| `0x441d` | `c_li` | CIOp |
| `0x470d` | `c_li` | CIOp |
| `0x75`   | `c_addi` | CIOp |
| `0x5d`   | `c_addi` | CIOp |

### Quadrant 2

| hex | instruction | format |
|-----|------------|--------|
| `0x873e` | `c_mv` | CROp (default branch, RC2≠0) |
| `0x8782` | `c_jr` | CJump (RC2=0) |
| `0x97a2` | `c_add` | CompressedROp (default branch, RC2≠0) |

### Quadrant 0 (CIW / CL / CS)

| hex | instruction | format |
|-----|------------|--------|
| `0x4782` | `c_lwsp` | CompressedLoad |

## 3. Vector (OPIVI)

| hex | instruction | format |
|-----|------------|--------|
| `0x9e053057` | `illegal` | — (bad SIMM3) |

## 4. Verification procedure

```bash
python3 -c "
import subprocess, sys
sys.path.insert(0, 'skills/riscv-inst-decoder/scripts')

cases = [
    # 32-bit standard (verfied against spike-dasm)
    ('0x00A58533', ['add']),
    ('0x40348433', ['sub']),
    ('0xFD010113', ['addi']),
    ('0x0010029b', ['addiw']),
    ('0x0007879b', ['addiw']),
    ('0x02113423', ['sd']),
    ('0x0202a023', ['sw']),
    ('0x00B57663', ['bgeu']),
    ('0x0066c663', ['blt']),
    ('0x000015b7', ['lui']),
    ('0x004000ef', ['jal']),
    ('0x00050067', ['jalr']),
    ('0x10101013', ['sha256sum1']),
    ('0x00153513', ['sltiu']),
    # illegal
    ('0x9e053057', ['illegal']),
    # compressed (verified against spike-dasm)
    ('0x17c1',      ['c_addi']),
    ('0x57cd',      ['c_li']),
    ('0x61fd',      ['c_lui']),
    ('0x6105',      ['c_addi16sp']),
    ('0x873e',      ['c_mv']),
    ('0x8782',      ['c_jr']),
    ('0x97a2',      ['c_add']),
    ('0x4782',      ['c_lwsp']),
]

ok = 0
fail = 0
for hex_val, expected_names in cases:
    r = subprocess.run(
        [sys.executable, 'skills/riscv-inst-decoder/scripts/decode_inst.py', hex_val],
        capture_output=True, text=True
    )
    last_line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ''
    if 'ILLEGAL INSTRUCTION' in r.stdout:
        name = 'illegal'
    elif 'unknown' in last_line:
        name = 'unknown'
    else:
        name = last_line.strip()
    match = any(en in name for en in expected_names)
    status = 'OK' if match else 'FAIL'
    if match: ok += 1
    else: fail += 1
    print(f\"  {status} {hex_val:14s} → {name:20s} (expected {expected_names[0]})\")

print(f'\n{ok}/{ok+fail} passed')
" 2>&1
```
