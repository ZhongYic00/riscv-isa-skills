from pathlib import Path

import pytest

from rr_spike_rv_replay.goto_entry import (
    build_spike_log_command,
    default_instruction_budget,
    render_gdb_entry_script,
    resolve_target_pc_from_trace,
)


def test_default_instruction_budget_scales_with_index() -> None:
    assert default_instruction_budget(10) == 4096
    assert default_instruction_budget(5000) == 5256


def test_build_spike_log_command_includes_log_and_budget() -> None:
    cmd = build_spike_log_command(
        spike_bin="/opt/riscv/bin/spike",
        elf_path="/tmp/prog.elf",
        log_path="/tmp/commit.log",
        instruction_budget=1234,
        spike_args=["--isa=rv64imafdc"],
    )

    assert cmd == [
        "/opt/riscv/bin/spike",
        "-l",
        "--log=/tmp/commit.log",
        "--instructions=1234",
        "--isa=rv64imafdc",
        "/tmp/prog.elf",
    ]


def test_resolve_target_pc_from_trace_by_index(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        '{"instructions":[{"index":1,"pc":"0x8000","text":"addi","hart_id":0},{"index":2,"pc":"0x8004","text":"csrr","hart_id":0}]}',
        encoding="utf-8",
    )

    assert resolve_target_pc_from_trace(trace_path, target_index=2, hart_id=0) == "0x8004"


def test_resolve_target_pc_from_trace_missing_index_raises(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.json"
    trace_path.write_text('{"instructions":[{"index":1,"pc":"0x8000","hart_id":0}]}', encoding="utf-8")

    with pytest.raises(ValueError, match="target index"):
        resolve_target_pc_from_trace(trace_path, target_index=2, hart_id=0)


def test_render_gdb_entry_script_contains_interactive_break() -> None:
    script = render_gdb_entry_script(
        spike_bin="/opt/riscv/bin/spike",
        target_pc="0x000000008000000a",
        target_index=10,
        replay_port=12345,
    )

    assert "target extended-remote :12345" in script
    assert "break ../riscv/execute.cc:308 if pc == 0x000000008000000a" in script
    assert "printf \"HIT_TARGET_PC=%#lx\\n\", pc" in script
    assert "continue" in script
    assert "quit" not in script
