#!/usr/bin/env python3
"""
Generate FMT_OPERANDS from riscv-unified-db instruction definitions.

For each gem5 format name (IOp, ROp, …), collect all instructions that
use it, look up their encoding variables in UDB YAML files, and verify
consistency within each format.  Outputs the FMT_OPERANDS dict.
"""
import json
import os
import sys
import yaml
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DECODE_TREE = REPO / "skills" / "riscv-inst-decoder" / "references" / "decode_tree.json"
UDB = Path(os.path.expanduser("~/riscv-sources/spec/riscv-unified-db/spec/std/isa/inst"))


def iter_instructions(tree):
    """Yield all (format, name) pairs from the decode tree."""
    if isinstance(tree, dict):
        if tree.get("kind") == "instruction":
            fmt = tree.get("format", "Unknown")
            name = tree.get("name", "?")
            if fmt != "Unknown":
                yield fmt, name
        for child in tree.get("children", []):
            yield from iter_instructions(child)
        if "target" in tree:
            yield from iter_instructions(tree["target"])
    elif isinstance(tree, list):
        for item in tree:
            yield from iter_instructions(item)


def gem5_to_udb_name(gem5_name):
    """
    Map gem5 instruction name to UDB YAML filename.

    gem5 uses underscores (c_addi), UDB uses dots (c.addi).
    Some names match directly, some need extension prefixes.
    """
    # Direct: most RV32I/RV64I names are the same
    # Compressed: c_addi → c.addi, c_mv → c.mv, etc.
    if gem5_name.startswith("c_"):
        return "C/" + gem5_name.replace("_", ".") + ".yaml"
    # Vector: vadd_vv → V/vadd_vv.yaml or V/vadd.vv.yaml
    if gem5_name.startswith("v"):
        # Try both conventions
        return None  # handled by caller with multiple attempts
    # Standard: add → I/add.yaml, slli → I/slli.yaml
    # Extension: sha256sum1 → Zk/sha256sum1.yaml (need to find ext)
    return None  # signal caller to search


def find_udb_yaml(name):
    """
    Search UDB directory for a YAML file matching the instruction name.
    Returns (path, variables_dict) or None.
    UDB filenames use dots; gem5 names use underscores.
    Rule: replace ALL underscores with dots.
    """
    dot_name = name.replace("_", ".") + ".yaml"
    candidates = []
    if not os.path.isdir(UDB):
        return None, None
    for ext_dir in sorted(os.listdir(UDB)):
        p = UDB / ext_dir / dot_name
        if p.exists():
            candidates.append(p)

    for path in candidates:
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if data and isinstance(data, dict) and data.get("kind") == "instruction":
                return path, data
        except Exception:
            continue
    return None, None


def get_variables(udb_data):
    """
    Extract variable fields from UDB instruction data.
    Returns list of (field_name, msb, lsb) tuples.
    A single UDB variable with non-contiguous location expands to
    multiple entries.
    """
    encoding = udb_data.get("encoding", {})
    if not encoding:
        return []

    # Try RV64-specific encoding first, then RV32, then default
    for key in ("RV64", "RV32"):
        variant = encoding.get(key) if isinstance(encoding, dict) else None
        if variant and "variables" in variant:
            result = []
            for v in variant["variables"]:
                if "location" not in v:
                    continue
                ranges = parse_location(v["location"])
                if len(ranges) == 1:
                    result.append((v["name"], ranges[0][0], ranges[0][1]))
                else:
                    for i, (msb, lsb) in enumerate(ranges):
                        suffix = f"_{msb}" if len(ranges) > 1 else ""
                        result.append((v["name"] + suffix, msb, lsb))
            return result

    # Default (no RV32/RV64 split)
    if isinstance(encoding, dict) and "variables" in encoding:
        result = []
        for v in encoding["variables"]:
            if "location" not in v:
                continue
            ranges = parse_location(v["location"])
            if len(ranges) == 1:
                result.append((v["name"], ranges[0][0], ranges[0][1]))
            else:
                for i, (msb, lsb) in enumerate(ranges):
                    suffix = f"_{msb}" if len(ranges) > 1 else ""
                    result.append((v["name"] + suffix, msb, lsb))
        return result

    return []


def _parse_one(part):
    """Parse a single location segment: '31-20' or '12'."""
    part = part.strip()
    if "-" in part:
        a, b = part.split("-", 1)
        a, b = int(a.strip()), int(b.strip())
        return [(a, b)] if a >= b else [(b, a)]
    return [(int(part), int(part))]

def parse_location(loc):
    """
    Parse UDB location spec into list of (msb, lsb) ranges.

    Supported formats:
      '31-20'             → [(31, 20)]
      '12'                → [(12, 12)]
      '31|7|30'           → [(31,31), (7,7), (30,30)]
      '31|30-25|...'      → [(31,31), (30,25), ...]
    """
    if loc is None:
        return []
    if isinstance(loc, int):
        return [(loc, loc)]
    s = str(loc).strip()

    if "|" in s:
        result = []
        for part in s.split("|"):
            part = part.strip()
            if part:
                result.extend(_parse_one(part))
        return result

    return _parse_one(s)


def fmt_var_key(v):
    """Sort key for a (name, msb, lsb) tuple."""
    return (-v[1], v[2], v[0])  # msb desc, lsb asc, name alpha

def main():
    # 1. Load decode tree
    with open(DECODE_TREE) as f:
        tree = json.load(f)
    if isinstance(tree, list):
        tree = tree[0]

    # 2. Collect (format, name) pairs
    fmt_insts = defaultdict(set)
    for fmt, name in iter_instructions(tree):
        fmt_insts[fmt].add(name)

    print(f"Found {len(fmt_insts)} formats, "
          f"{sum(len(v) for v in fmt_insts.values())} instruction leaves\n")

    # 3. For each format, look up UDB variables
    NOT_FOUND = object()
    all_inst_vars = {}  # inst_name → [(field, msb, lsb), ...]

    for fmt in sorted(fmt_insts.keys()):
        names = sorted(fmt_insts[fmt])
        print(f"\n{'='*60}")
        print(f"Format: {fmt} ({len(names)} instructions)")
        print(f"{'='*60}")

        for name in names:
            path, udb_data = find_udb_yaml(name)
            if udb_data is None:
                all_inst_vars[name] = NOT_FOUND
                print(f"  {name:30s} → NOT FOUND")
                continue
            vars_list = sorted(get_variables(udb_data), key=fmt_var_key)
            all_inst_vars[name] = vars_list
            rel_path = path.relative_to(UDB.parent.parent.parent)
            var_str = ", ".join(f"{n}({msb}:{lsb})" for n, msb, lsb in vars_list)
            print(f"  {name:30s} → {var_str:50s} ({rel_path})")

    # 4. Classify formats: consistent vs inconsistent vs no UDB
    fmt_class = {}  # format → "consistent" | "inconsistent" | "no_udb"
    fmt_udb_vars = {}  # format → common vars (only for consistent)
    inst_udb_vars = {}  # inst_name → vars (for inconsistent formats)
    no_udb_formats = set()
    no_udb_insts = set()

    for fmt in sorted(fmt_insts.keys()):
        names = sorted(fmt_insts[fmt])

        # Collect unique variable sets
        var_sets = set()
        for name in names:
            v = all_inst_vars.get(name, NOT_FOUND)
            if v is not NOT_FOUND:
                var_sets.add(tuple(v))
            else:
                var_sets.add(NOT_FOUND)

        found_var_sets = {v for v in var_sets if v is not NOT_FOUND}
        all_found = all(v is not NOT_FOUND for v in var_sets)
        all_same = len(found_var_sets) <= 1

        if not all_found and not found_var_sets:
            fmt_class[fmt] = "no_udb"
            no_udb_formats.add(fmt)
            for name in names:
                no_udb_insts.add(name)
        elif all_found and all_same:
            fmt_class[fmt] = "consistent"
            common = next(iter(found_var_sets))
            fmt_udb_vars[fmt] = list(common)
        else:
            fmt_class[fmt] = "inconsistent"
            for name in names:
                v = all_inst_vars.get(name, NOT_FOUND)
                if v is not NOT_FOUND:
                    inst_udb_vars[name] = v

    # 5. Report
    print(f"\n\n{'='*60}")
    print("CLASSIFICATION")
    print(f"{'='*60}")
    for fmt in sorted(fmt_insts.keys()):
        cls = fmt_class.get(fmt, "?")
        n = len(fmt_insts[fmt])
        if cls == "consistent":
            vars_list = fmt_udb_vars[fmt]
            var_str = ", ".join(f"{n}({msb}:{lsb})" for n, msb, lsb in vars_list)
            print(f"  ✅ {fmt:30s} ({n:3d} instrs) → {var_str}")
        elif cls == "inconsistent":
            print(f"  ⚠️  {fmt:30s} ({n:3d} instrs) → per-instruction vars")
        else:
            print(f"  ❌ {fmt:30s} ({n:3d} instrs) → not in UDB")

    # 6. Output FMT_OPERANDS + INST_VARIABLES as Python file
    out_path = REPO / "skills" / "riscv-inst-decoder" / "scripts" / "_fmt_udb.py"
    with open(out_path, "w") as f:
        f.write("# Generated by tools/gen_fmt_operands.py\n")
        f.write("# Do not edit manually.\n\n")
        f.write("# Format-level variables (all instructions in format share same fields)\n")
        f.write(f"FMT_OPERANDS = {{\n")
        for fmt in sorted(fmt_udb_vars.keys()):
            vars_list = sorted(fmt_udb_vars[fmt], key=fmt_var_key)
            parts = [f'("{n}", {msb}, {lsb})' for n, msb, lsb in vars_list]
            line = ",\n             ".join(parts)
            f.write(f'    "{fmt}": [{line}],\n')
        f.write("}\n\n")

        f.write("# Per-instruction variables (inconsistent formats with unique fields)\n")
        f.write(f"INST_VARIABLES = {{\n")
        for name in sorted(inst_udb_vars.keys()):
            vars_list = sorted(inst_udb_vars[name], key=fmt_var_key)
            parts = [f'("{n}", {msb}, {lsb})' for n, msb, lsb in vars_list]
            line = ",\n        ".join(parts)
            f.write(f'    "{name}": [{line}],\n')
        f.write("}\n")
    print(f"\n\nWritten {out_path}")

    # 7. Stats
    n_consistent = sum(1 for c in fmt_class.values() if c == "consistent")
    n_inconsistent = sum(1 for c in fmt_class.values() if c == "inconsistent")
    n_no_udb = sum(1 for c in fmt_class.values() if c == "no_udb")
    print(f"Stats: consistent={n_consistent}, inconsistent={n_inconsistent}, no_udb={n_no_udb}")


if __name__ == "__main__":
    main()
