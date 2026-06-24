# Patches

## gem5_decode_tree.patch

Extends gem5's ISA parser (`src/arch/isa_parser/isa_parser.py`) to also emit a
JSON decode tree alongside the regular C++ output.

### What it does

- Adds `DecodeTreeNode` dataclass with recursive `to_dict()` serialization
- Modifies `GenCode` to carry a `tree_node` attribute (propagated through `__add__`)
- Hooks grammar production rules:
  - `p_decode_block` → creates `block(field, children, subset)` nodes
  - `p_decode_stmt_decode/inst` → wraps targets in `case(case_values, target)`
  - `p_inst_0/1` → creates `instruction(name, format, subset)` nodes
- Collects subset labels from instruction arguments (OPIVV, OPFVV, OPMVV, …)
- Propagates subset to parent block nodes when uniform

### Applying

From the gem5 root (the directory containing `src/`):

```bash
patch -p1 < /path/to/gem5_decode_tree.patch
```

Requires: Python 3, PLY (`pip install ply`).

Does NOT affect the C++ output — only adds a `parse.decode_trees` list that can
be serialized to JSON via `parser.parse_isa_desc()` + `json.dump()`.
