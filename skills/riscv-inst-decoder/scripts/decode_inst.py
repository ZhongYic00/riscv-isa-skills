#!/usr/bin/env python3
"""Decode RISC-V instructions using gem5's decode tree.

Usage:
    python3 decode_inst.py <hex_instruction>         # single decode
    python3 decode_inst.py <hex1> <hex2> ...         # batch decode

Examples:
    python3 decode_inst.py 0x9e053057
    python3 decode_inst.py fd010113 02113423
"""
import json
import os
import re
import sys

# ── bitfield extraction ──────────────────────────────────────────────────
# gem5 ExtMachInst is 64-bit: bits[63:32] = decoder context, bits[31:0] = instruction
FIELD_BITS = {
    "RVTYPE":      lambda v: (v >> 62) & 0x3,
    "COMPRESSED":  lambda v: (v >> 61) & 0x1,
    "ENABLE_ZCD":  lambda v: (v >> 60) & 0x1,
    "QUADRANT":    lambda v: (v >> 0) & 0x3,
    "OPCODE5":     lambda v: (v >> 2) & 0x1f,
    "FUNCT3":      lambda v: (v >> 12) & 0x7,
    "FUNCT7":      lambda v: (v >> 25) & 0x7f,
    "FUNCT2":      lambda v: (v >> 25) & 0x3,
    "RS1":         lambda v: (v >> 15) & 0x1f,
    "RS2":         lambda v: (v >> 20) & 0x1f,
    "RD":          lambda v: (v >> 7) & 0x1f,
    "COPCODE":     lambda v: (v >> 13) & 0x7,
    "CFUNCT6LOW3": lambda v: (v >> 10) & 0x7,
    "CFUNCT1":     lambda v: (v >> 12) & 0x1,
    "CFUNCT1BIT6": lambda v: (v >> 6) & 0x1,
    "CFUNCT2HIGH": lambda v: (v >> 10) & 0x3,
    "CFUNCT2LOW":  lambda v: (v >> 5) & 0x3,
    "CFUNCT2MID":  lambda v: (v >> 8) & 0x3,
    "VFUNCT6":     lambda v: (v >> 26) & 0x3f,
    "VFUNCT5":     lambda v: (v >> 27) & 0x1f,
    "VFUNCT3":     lambda v: (v >> 27) & 0x7,
    "VFUNCT2":     lambda v: (v >> 25) & 0x3,
    "VS1":         lambda v: (v >> 15) & 0x1f,
    "VS2":         lambda v: (v >> 20) & 0x1f,
    "VD":          lambda v: (v >> 7) & 0x1f,
    "VM":          lambda v: (v >> 25) & 0x1,
    "SIMM3":       lambda v: (v >> 15) & 0x7,
    "SIMM5":       lambda v: (v >> 15) & 0x1f,
    "LUMOP":       lambda v: (v >> 20) & 0x1f,
    "SUMOP":       lambda v: (v >> 20) & 0x1f,
    "WIDTH":       lambda v: (v >> 12) & 0x7,
    "BIT31":       lambda v: (v >> 31) & 0x1,
    "BIT30":       lambda v: (v >> 30) & 0x1,
    "BIT26":       lambda v: (v >> 26) & 0x1,
    "BIT24":       lambda v: (v >> 24) & 0x1,
    "BIT25":       lambda v: (v >> 25) & 0x1,
    "NF":          lambda v: (v >> 29) & 0x7,
    "MEW":         lambda v: (v >> 28) & 0x1,
    "MOP":         lambda v: (v >> 26) & 0x3,
    "ROUND_MODE":  lambda v: (v >> 12) & 0x7,
    "CONV_SGN":    lambda v: (v >> 20) & 0x1f,
    "SHAMT5":      lambda v: (v >> 20) & 0x1f,
    "SHAMT6":      lambda v: (v >> 20) & 0x3f,
    "IMM12":       lambda v: (v >> 20) & 0xfff,
    "IMM5":        lambda v: (v >> 7) & 0x1f,
    "IMM7":        lambda v: (v >> 25) & 0x7f,
    "IMM20":       lambda v: (v >> 12) & 0xfffff,
    "CSRIMM":      lambda v: (v >> 15) & 0x1f,
    "SRTYPE":      lambda v: (v >> 30) & 0x1,
    "RNUM":        lambda v: (v >> 20) & 0xf,
    "KFUNCT5":     lambda v: (v >> 25) & 0x1f,
    "BS":          lambda v: (v >> 30) & 0x3,
    "AMOFUNCT":    lambda v: (v >> 27) & 0x1f,
    "AQ":          lambda v: (v >> 26) & 0x1,
    "RL":          lambda v: (v >> 25) & 0x1,
    "PRED":        lambda v: (v >> 24) & 0xf,
    "SUCC":        lambda v: (v >> 20) & 0xf,
}


# ── bit range (msb, lsb) for each field ─────────────────────────────────
BIT_RANGES = {
    "RVTYPE":      (63, 62), "COMPRESSED":  (61, 61), "ENABLE_ZCD":  (60, 60),
    "QUADRANT":    (1, 0),   "OPCODE5":     (6, 2),
    "FUNCT3":      (14, 12), "FUNCT7":      (31, 25), "FUNCT2":      (26, 25),
    "RS1":         (19, 15), "RS2":         (24, 20), "RD":          (11, 7),
    "COPCODE":     (15, 13), "CFUNCT6LOW3": (12, 10),
    "CFUNCT1":     (12, 12), "CFUNCT1BIT6": (6, 6),
    "CFUNCT2HIGH": (11, 10), "CFUNCT2LOW":  (6, 5),   "CFUNCT2MID":  (9, 8),
    "VFUNCT6":     (31, 26), "VFUNCT5":     (31, 27),
    "VFUNCT3":     (27, 25), "VFUNCT2":     (26, 25),
    "VS1":         (19, 15), "VS2":         (24, 20), "VD":          (11, 7),
    "VM":          (25, 25),
    "SIMM3":       (17, 15), "SIMM5":       (19, 15),
    "LUMOP":       (24, 20), "SUMOP":       (24, 20),
    "WIDTH":       (14, 12),
    "BIT31":       (31, 31), "BIT30":       (30, 30),
    "BIT26":       (26, 26), "BIT24":       (24, 24), "BIT25":       (25, 25),
    "NF":          (31, 29), "MEW":         (28, 28), "MOP":         (27, 26),
    "ROUND_MODE":  (14, 12), "CONV_SGN":    (24, 20),
    "SHAMT5":      (24, 20), "SHAMT6":      (25, 20),
    "IMM12":       (31, 20), "IMM5":        (11, 7),  "IMM7":        (31, 25),
    "IMM20":       (31, 12),
    "CSRIMM":      (19, 15),
    "SRTYPE":      (30, 30),
    "RNUM":        (23, 20), "KFUNCT5":     (29, 25),
    "BS":          (31, 30),
    "AMOFUNCT":    (31, 27), "AQ":          (26, 26), "RL":          (25, 25),
    "PRED":        (27, 24), "SUCC":        (23, 20),
}

# ── operand fields per instruction format ────────────────────────────────
# (field_name, msb, lsb)  — only standard positions, derived from RISC-V spec
FMT_OPERANDS = {
    # scalar arithmetic
    "IOp":          [("rd", 11, 7), ("rs1", 19, 15), ("imm12", 31, 20)],
    "ROp":          [("rd", 11, 7), ("rs1", 19, 15), ("rs2", 24, 20)],
    "UOp":          [("rd", 11, 7), ("imm20", 31, 12)],
    "JOp":          [("rd", 11, 7), ("imm", 31, 12)],
    "Jump":         [("rd", 11, 7), ("rs1", 19, 15), ("imm12", 31, 20)],
    # load / store
    "Load":         [("rd", 11, 7), ("rs1", 19, 15), ("imm12", 31, 20)],
    "Store":        [("rs1", 19, 15), ("rs2", 24, 20),
                     ("imm_lo", 11, 7), ("imm_hi", 31, 25)],
    "BOp":          [("rs1", 19, 15), ("rs2", 24, 20),
                     ("imm", 31, 25)],
    # CSR / system
    "CSROp":        [("rd", 11, 7), ("csr", 31, 20), ("rs1", 19, 15)],
    "SystemOp":     [("rd", 11, 7), ("rs1", 19, 15)],
    "FenceOp":      [("rd", 11, 7), ("rs1", 19, 15), ("pred", 27, 24), ("succ", 23, 20)],
    # float
    "FPROp":        [("fd", 11, 7), ("fs1", 19, 15), ("fs2", 24, 20), ("rm", 14, 12)],
    # AMO
    "AtomicMemOp":  [("rd", 11, 7), ("rs1", 19, 15), ("rs2", 24, 20),
                     ("aq", 26, 26), ("rl", 25, 25)],
    "LoadReserved": [("rd", 11, 7), ("rs1", 19, 15), ("aq", 26, 26), ("rl", 25, 25)],
    "StoreCond":    [("rd", 11, 7), ("rs1", 19, 15), ("rs2", 24, 20),
                     ("aq", 26, 26), ("rl", 25, 25)],
    # hypervisor
    "HyperLoad":    [("rd", 11, 7), ("rs1", 19, 15)],
    "HyperStore":   [("rs1", 19, 15), ("rs2", 24, 20)],
    # Zb* bit-manipulation
    "BSOp":         [("rd", 11, 7), ("rs1", 19, 15), ("rs2", 24, 20)],
    "CBMOp":        [("rd", 11, 7), ("rs1", 19, 15), ("rs2", 24, 20)],
    # M5
    "M5Op":         [],
    # compressed — operand fields are at different bit offsets
    "CIOp":         [("rd_rs1", 11, 7), ("imm", 12, 12)],
    "CJOp":         [("rd_rs1", 11, 7), ("imm", 12, 12)],
    "CBOp":         [("rd_rs1", 11, 7), ("imm", 12, 12)],
    "CROp":         [],
    "CJump":        [("imm", 12, 2)],
    "CIAddi4spnOp": [("rd", 4, 2), ("rs1", 9, 7)],
    "CompressedLoad":  [("rd", 4, 2), ("rs1", 9, 7)],
    "CompressedStore": [("rs1", 9, 7), ("rs2", 4, 2)],
    "CompressedROp":   [("rd", 4, 2), ("rs1", 9, 7), ("rs2", 4, 2)],
    # Zcm*
    "CmJalt":       [],
    "CmMva01s":     [],
    "CmMvsa01":     [],
    "CmPop":        [("rd", 11, 7)],
    "CmPush":       [],
    # vector arithmetic (most formats share vd/vs2/vs1)
    "VectorIntFormat":   [("vd", 11, 7), ("vs2", 24, 20), ("vs1", 19, 15)],
    "VectorFloatFormat": [("vd", 11, 7), ("vs2", 24, 20), ("vs1", 19, 15)],
    "VectorIntMaskFormat":     [("vd", 11, 7), ("vs2", 24, 20), ("vs1", 19, 15)],
    "VectorFloatMaskFormat":   [("vd", 11, 7), ("vs2", 24, 20), ("vs1", 19, 15)],
    "VectorIntWideningFormat": [("vd", 11, 7), ("vs2", 24, 20), ("vs1", 19, 15)],
    "VectorIntNarrowingFormat":[("vd", 11, 7), ("vs2", 24, 20)],
    "VectorFloatWideningFormat":[("vd", 11, 7), ("vs2", 24, 20), ("vs1", 19, 15)],
    "VectorFloatNarrowingCvtFormat": [("vd", 11, 7), ("vs2", 24, 20)],
    "VectorFloatCvtFormat":  [("vd", 11, 7), ("vs2", 24, 20)],
    "VectorIntVxsatFormat":  [("vd", 11, 7), ("vs2", 24, 20), ("vs1", 19, 15)],
    "VectorMaskFormat":      [("vd", 11, 7), ("vs2", 24, 20)],
    "VectorReduceIntFormat": [("vd", 11, 7), ("vs2", 24, 20), ("vs1", 19, 15)],
    "VectorReduceIntWideningFormat": [("vd", 11, 7), ("vs2", 24, 20), ("vs1", 19, 15)],
    "VectorReduceFloatFormat":       [("vd", 11, 7), ("vs2", 24, 20), ("vs1", 19, 15)],
    "VectorReduceFloatWideningFormat":[("vd", 11, 7), ("vs2", 24, 20), ("vs1", 19, 15)],
    "VectorGatherFormat":    [("vd", 11, 7), ("vs2", 24, 20), ("vs1", 19, 15)],
    "VectorSlideUpFormat":   [("vd", 11, 7), ("vs2", 24, 20), ("rs1", 19, 15)],
    "VectorSlideDownFormat": [("vd", 11, 7), ("vs2", 24, 20), ("rs1", 19, 15)],
    "VectorSlideUpVIFormat": [("vd", 11, 7), ("vs2", 24, 20), ("simm", 19, 15)],
    "VectorSlideDownVIFormat":[("vd", 11, 7), ("vs2", 24, 20), ("simm", 19, 15)],
    "VectorSlide1UpFormat":  [("vd", 11, 7), ("vs2", 24, 20), ("rs1", 19, 15)],
    "VectorSlide1DownFormat":[("vd", 11, 7), ("vs2", 24, 20), ("rs1", 19, 15)],
    "VectorCompressFormat":  [("vd", 11, 7), ("vs2", 24, 20), ("vs1", 19, 15)],
    "VectorIntExtFormat":    [("vd", 11, 7), ("vs2", 24, 20)],
    "VectorNonSplitFormat":  [("vd", 11, 7), ("vs2", 24, 20)],
    "VMvWholeFormat":        [("vd", 11, 7), ("vs2", 24, 20)],
    "VectorFloatSlideUpFormat":   [("vd", 11, 7), ("vs2", 24, 20), ("rs1", 19, 15)],
    "VectorFloatSlideDownFormat": [("vd", 11, 7), ("vs2", 24, 20), ("rs1", 19, 15)],
    "VectorFloatWideningCvtFormat":[("vd", 11, 7), ("vs2", 24, 20)],
    "ViotaFormat":         [("vd", 11, 7), ("vs2", 24, 20)],
    "Vector1Vs1RdMaskFormat":  [("vd", 11, 7), ("vs2", 24, 20)],
    "Vector1Vs1VdMaskFormat":  [("vd", 11, 7), ("vs2", 24, 20)],
    # vector load / store
    "VleOp":        [("vd", 11, 7), ("rs1", 19, 15)],
    "VlmOp":        [("vd", 11, 7), ("rs1", 19, 15)],
    "VlSegOp":      [("vd", 11, 7), ("rs1", 19, 15)],
    "VlWholeOp":    [("vd", 11, 7), ("rs1", 19, 15)],
    "VlIndexOp":    [("vd", 11, 7), ("rs1", 19, 15), ("vs2", 24, 20)],
    "VlStrideOp":   [("vd", 11, 7), ("rs1", 19, 15), ("vs2", 24, 20)],
    "VseOp":        [("vs3", 11, 7), ("rs1", 19, 15)],
    "VsmOp":        [("vs3", 11, 7), ("rs1", 19, 15)],
    "VsSegOp":      [("vs3", 11, 7), ("rs1", 19, 15)],
    "VsWholeOp":    [("vs3", 11, 7), ("rs1", 19, 15)],
    "VsIndexOp":    [("vs3", 11, 7), ("rs1", 19, 15), ("vs2", 24, 20)],
    "VsStrideOp":   [("vs3", 11, 7), ("rs1", 19, 15), ("vs2", 24, 20)],
    # vector config
    "VConfOp":      [("rd", 11, 7), ("rs1", 19, 15),
                     ("zimm", 29, 20), ("vlmul", 34, 32), ("vsew", 37, 35)],
}


def extract_field(inst, field):
    fn = FIELD_BITS.get(field)
    return fn(inst) if fn else None


def _infer_format(node):
    """Walk subtree for the first instruction leaf with a real format."""
    if node["kind"] == "instruction":
        f = node.get("format")
        if f and f != "Unknown":
            return f
    for child in node.get("children", []):
        if child["kind"] == "case":
            f = _infer_format(child["target"])
            if f:
                return f
    if "target" in node:
        return _infer_format(node["target"])
    return None


def _collect_subsets(node):
    s = set()
    if node["kind"] == "instruction":
        sub = node.get("subset")
        if isinstance(sub, list):
            for x in sub:
                if x: s.add(x)
        elif sub: s.add(sub)
        elif node.get("format") and node["format"] != "Unknown":
            s.add(node["format"])
    for child in node.get("children", []):
        if child["kind"] == "case":
            s.update(_collect_subsets(child["target"]))
    if "target" in node:
        s.update(_collect_subsets(node["target"]))
    return s


# ── public API ───────────────────────────────────────────────────────────

MAX_LABEL_COUNT = 10


def load_tree(path=None):
    if path is not None:
        with open(path) as f:
            return json.load(f)
    candidates = []
    try:
        candidates.append(os.path.join(os.path.dirname(__file__), "decode_tree.json"))
    except NameError:
        pass
    candidates.append("decode_tree.json")
    for c in candidates:
        if os.path.exists(c):
            with open(c) as f:
                return json.load(f)
    raise FileNotFoundError(
        "decode_tree.json not found. Pass explicit path to load_tree(), "
        "or place it next to this script or in the current directory."
    )


def decode_instruction(inst, tree):
    """Walk the decode tree.

    Returns ``(result, path, info, field_trace)``.

    *path* is a list of formatted step strings (for display).
    *field_trace* is ``[(field, value_int, msb, lsb), ...]`` for bit-level
    breakdown of the decode path.
    """
    node = tree
    path = []
    field_trace = []
    info = None

    while True:
        if node["kind"] == "instruction":
            return node, path, info, field_trace

        if node["kind"] != "block":
            return node, path, info, field_trace

        field = node["field"]
        value = extract_field(inst, field)
        if value is None:
            return {"kind": "instruction", "name": "unknown",
                    "format": "Unknown"}, path, info, field_trace

        matched_target = None
        matched_child = None
        for child in node.get("children", []):
            if child["kind"] == "case":
                for cv in child["case_values"]:
                    try:
                        if value == int(cv, 0):
                            matched_child = child
                            matched_target = child["target"]
                            break
                    except ValueError:
                        pass
                if matched_target:
                    break

        if matched_target is None:
            # record the failed field in field_trace
            msb, lsb = BIT_RANGES.get(field, (None, None))
            field_trace.append((field, value, msb, lsb))

            valid = []
            for child in node.get("children", []):
                if child["kind"] == "case":
                    valid.extend(child["case_values"])
            hexv = []
            for v in valid:
                try:
                    hexv.append(f"0x{int(v, 0):x}")
                except ValueError:
                    hexv.append(v)

            # guess format from sibling instruction leaves
            guessed_fmt = "Unknown"
            for child in node.get("children", []):
                if child["kind"] == "case":
                    f = _infer_format(child["target"])
                    if f:
                        guessed_fmt = f
                        break

            info = {"field": field, "value": f"0x{value:x}", "valid": hexv,
                    "format": guessed_fmt}
            if field == "SIMM3":
                info["hint"] = ("SIMM3 encodes NREG-1; "
                                "legal: 0,1,3,7 (NREG=1,2,4,8)")
            elif field == "LUMOP" and "0xb" in hexv:
                info["hint"] = "LUMOP=0xb is vlm (mask load); WIDTH must be 000"
            path.append(f"{field}=0x{value:x} \u2717 not in {hexv}")
            return {"kind": "instruction", "name": "illegal",
                    "format": guessed_fmt}, path, info, field_trace

        sub = _collect_subsets(matched_target)
        label = "/".join(sorted(sub)) if sub and len(sub) <= MAX_LABEL_COUNT else None
        msb, lsb = BIT_RANGES.get(field, (None, None))
        field_trace.append((field, value, msb, lsb))

        if msb is not None:
            step = f"{field}=0x{value:x} [{msb}:{lsb}]"
        else:
            step = f"{field}=0x{value:x}"
        if label:
            step += f" [{label}]"
        path.append(step)

        node = matched_target


def format_instruction_binary(inst_32, field_trace, result, info=None):
    """Produce a compact one-line binary breakdown of the instruction."""
    bits = inst_32

    # Fields from the decode path, keyed by (msb, lsb)
    shown = {}
    for fld, val, msb, lsb in field_trace:
        if msb is not None and msb <= 31:
            shown[(msb, lsb)] = (fld, val)

    fail_label = None
    if info:
        for fld, val, msb, lsb in field_trace:
            if f"0x{val:x}" == info["value"] and fld == info["field"]:
                fail_label = fld
                break

    # Add format-specific operand fields (from FMT_OPERANDS)
    fmt = result.get("format", "") or (info or {}).get("format", "")
    for fld, fmsb, flsb in FMT_OPERANDS.get(fmt, []):
        if all(msb > fmsb or lsb < flsb for msb, lsb in shown):
            w = fmsb - flsb + 1
            raw = (bits >> flsb) & ((1 << w) - 1)
            shown[(fmsb, flsb)] = (fld, raw)

    # Build the binary string sorted MSB → LSB
    parts = []
    for (msb, lsb), (fld, val) in sorted(shown.items(), reverse=True):
        w = msb - lsb + 1
        raw = (bits >> lsb) & ((1 << w) - 1)
        bin_str = f"{raw:0{w}b}"
        marker = " \u2717" if fld == fail_label else ""
        parts.append(f"{bin_str}<{fld}{marker}>")

    return " ".join(parts)


# ── CLI ──────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <hex_instruction> [<hex> ...]")
        sys.exit(1)

    tree = load_tree()
    if isinstance(tree, list):
        tree = tree[0]

    for arg in sys.argv[1:]:
        try:
            raw = int(arg, 16)
        except ValueError:
            print(f"error: invalid hex '{arg}'", file=sys.stderr)
            continue

        inst = raw | (0x1 << 62) | (0x1 << 60)
        result, path, info, field_trace = decode_instruction(inst, tree)

        print(f"  0x{raw:08x}")
        for step in path:
            print(f"    -> {step}")

        # binary breakdown
        binary = format_instruction_binary(raw, field_trace, result, info)
        print(f"    = {binary}")

        if result["name"] == "illegal":
            print("  ILLEGAL INSTRUCTION")
            if info:
                print(f"  {info['field']}={info['value']} not in {info['valid']}")
                if info.get("hint"):
                    print(f"  hint: {info['hint']}")
        else:
            print(f"  {result['name']}  (format={result['format']})")
        print()


if __name__ == "__main__":
    main()
