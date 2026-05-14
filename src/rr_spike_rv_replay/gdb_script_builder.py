"""Build gdb scripts for replay analysis."""

from __future__ import annotations

from collections.abc import Sequence

SCRIPT_PREAMBLE = [
    "set pagination off",
    "set confirm off",
]


def _break_command(strategy: str, value: str) -> str:
    if strategy == "symbol":
        return f"break {value}"
    if strategy == "address":
        return f"break *{value}"
    if strategy == "pattern":
        return f"rbreak {value}"
    raise ValueError(f"unknown breakpoint strategy: {strategy}")


def build_gdb_script(
    *,
    binary_path: str,
    breakpoint_strategy: str,
    breakpoint_value: str,
    target_insn_index: int,
    spike_counter_expr: str,
    hart_id: int | None,
    window_before: int,
    window_after: int,
    registers: Sequence[str],
    memory_ranges: Sequence[str],
    case_id: str | None = None,
    target_pc: str | None = None,
) -> str:
    register_format = " ".join(f"{register}=%#lx" for register in registers)
    register_args = ", ".join(f"${register}" for register in registers)
    condition = f"{spike_counter_expr} == {target_insn_index}"
    if hart_id is not None:
        condition += f" && $hartid == {hart_id}"

    lines = [
        *SCRIPT_PREAMBLE,
        f"file {binary_path}",
        f"# case: {case_id or 'unknown'}",
        f"# target index: {target_insn_index}",
        f"# target pc: {target_pc or 'unknown'}",
        _break_command(breakpoint_strategy, breakpoint_value),
        f"condition 1 {condition}",
        f"reverse-stepi {window_before}",
        f"stepi {window_after}",
        f'printf "{register_format}\\n", {register_args}',
    ]
    lines.extend(f"x/4gx {entry}" for entry in memory_ranges)
    return "\n".join(lines) + "\n"
