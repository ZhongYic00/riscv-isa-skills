"""Helpers for jumping to a target instruction entry in rr replay."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from rr_spike_rv_replay.spike_log_converter import convert_spike_commit_log_to_trace_json
from rr_spike_rv_replay.trace_bridge import parse_trace_file


def default_instruction_budget(target_index: int) -> int:
    return max(4096, target_index + 256)


def build_spike_log_command(
    *,
    spike_bin: str,
    elf_path: str,
    log_path: str,
    instruction_budget: int,
    spike_args: list[str] | None = None,
) -> list[str]:
    return [
        spike_bin,
        "-l",
        f"--log={log_path}",
        f"--instructions={instruction_budget}",
        *(spike_args or []),
        elf_path,
    ]


def resolve_target_pc_from_trace(trace_path: str | Path, *, target_index: int, hart_id: int | None = None) -> str:
    for record in parse_trace_file(trace_path):
        if record.index == target_index and (hart_id is None or record.hart_id == hart_id):
            if record.pc is None:
                break
            return record.pc
    raise ValueError(f"target index {target_index} (hart={hart_id}) not found in trace")


def render_gdb_entry_script(*, spike_bin: str, target_pc: str, target_index: int, replay_port: int) -> str:
    return "\n".join(
        [
            "set pagination off",
            "set confirm off",
            f"file {spike_bin}",
            f"target extended-remote :{replay_port}",
            f"# target index: {target_index}",
            f"break ../riscv/execute.cc:308 if pc == {target_pc}",
            "commands",
            "  silent",
            "  printf \"HIT_TARGET_PC=%#lx\\n\", pc",
            "  printf \"READY_FOR_INTERACTIVE_DEBUG\\n\"",
            "end",
            "continue",
            "",
        ]
    )


def goto_instruction_entry(
    *,
    elf_path: str,
    target_index: int,
    work_dir: str | Path,
    spike_bin: str = "/opt/riscv/bin/spike",
    rr_bin: str = "rr",
    gdb_bin: str = "gdb",
    hart_id: int | None = None,
    instruction_budget: int | None = None,
    replay_port: int = 12345,
    spike_args: list[str] | None = None,
) -> int:
    budget = instruction_budget or default_instruction_budget(target_index)
    output_dir = Path(work_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    log_path = output_dir / "spike_commit.log"
    trace_path = output_dir / "spike_trace.json"
    gdb_script_path = output_dir / "goto_entry.gdb"

    spike_log_cmd = build_spike_log_command(
        spike_bin=spike_bin,
        elf_path=elf_path,
        log_path=str(log_path),
        instruction_budget=budget,
        spike_args=spike_args,
    )
    subprocess.run(spike_log_cmd, check=False)

    convert_spike_commit_log_to_trace_json(log_path, trace_path)
    target_pc = resolve_target_pc_from_trace(trace_path, target_index=target_index, hart_id=hart_id)

    gdb_script = render_gdb_entry_script(
        spike_bin=spike_bin,
        target_pc=target_pc,
        target_index=target_index,
        replay_port=replay_port,
    )
    gdb_script_path.write_text(gdb_script, encoding="utf-8")

    subprocess.run([rr_bin, "record", spike_bin, f"--instructions={budget}", *(spike_args or []), elf_path], check=True)
    replay_server = subprocess.Popen([rr_bin, "replay", "-s", str(replay_port)])
    try:
        time.sleep(1)
        return subprocess.run([gdb_bin, "-q", "-x", str(gdb_script_path)], check=False).returncode
    finally:
        replay_server.terminate()
        try:
            replay_server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            replay_server.kill()
