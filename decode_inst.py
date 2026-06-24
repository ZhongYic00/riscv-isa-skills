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


def extract_field(inst, field):
    fn = FIELD_BITS.get(field)
    return fn(inst) if fn else None


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
            info = {"field": field, "value": f"0x{value:x}", "valid": hexv}
            if field == "SIMM3":
                info["hint"] = ("SIMM3 encodes NREG-1; "
                                "legal: 0,1,3,7 (NREG=1,2,4,8)")
            elif field == "LUMOP" and "0xb" in hexv:
                info["hint"] = "LUMOP=0xb is vlm (mask load); WIDTH must be 000"
            path.append(f"{field}=0x{value:x} \u2717 not in {hexv}")
            return {"kind": "instruction", "name": "illegal",
                    "format": "Unknown"}, path, info, field_trace

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


def format_instruction_binary(inst_32, field_trace, info=None):
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

    # Fill gaps with standard register operand fields
    for fld, fmsb, flsb in [("VS2", 24, 20), ("VS1", 19, 15), ("VD", 11, 7)]:
        overlaps = any(msb >= flsb and lsb <= fmsb for msb, lsb in shown)
        if not overlaps:
            w = fmsb - flsb + 1
            val = (bits >> flsb) & ((1 << w) - 1)
            shown[(fmsb, flsb)] = (fld, val)

    # Build the binary string sorted MSB → LSB
    parts = []
    for (msb, lsb), (fld, val) in sorted(shown.items(), reverse=True):
        w = msb - lsb + 1
        raw = (bits >> lsb) & ((1 << w) - 1)
        bin_str = f"{raw:0{w}b}"
        hex_str = f"0x{raw:x}"
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
        binary = format_instruction_binary(raw, field_trace, info)
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
