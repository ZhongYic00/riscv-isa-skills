"""Replay command construction helpers."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from rr_spike_rv_replay.recorder import Runner, default_runner


@dataclass(frozen=True)
class ReplayExecution:
    command: list[str]
    result: subprocess.CompletedProcess[str]


def build_rr_replay_command(gdb_script_path: str | Path, rr_binary: str = "rr") -> list[str]:
    return [rr_binary, "replay", "-x", str(gdb_script_path)]


def run_rr_replay(
    gdb_script_path: str | Path,
    *,
    runner: Runner = default_runner,
    rr_binary: str = "rr",
) -> ReplayExecution:
    command = build_rr_replay_command(gdb_script_path, rr_binary=rr_binary)
    result = runner(command)
    return ReplayExecution(command=command, result=result)
