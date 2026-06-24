"""Recorder command construction helpers."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass


Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def default_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


@dataclass(frozen=True)
class RecordExecution:
    command: list[str]
    trace_id: str | None
    result: subprocess.CompletedProcess[str]


def build_rr_record_command(run_cmd: Sequence[str], rr_binary: str = "rr") -> list[str]:
    if not run_cmd:
        raise ValueError("run_cmd must not be empty")
    return [rr_binary, "record", "--", *run_cmd]


def extract_trace_id(output: str) -> str | None:
    match = re.search(r"trace[_ -]?id\s*[:=]\s*(\S+)", output, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1)


def run_rr_record(run_cmd: Sequence[str], *, runner: Runner = default_runner, rr_binary: str = "rr") -> RecordExecution:
    command = build_rr_record_command(run_cmd, rr_binary=rr_binary)
    result = runner(command)
    trace_id = extract_trace_id((result.stdout or "") + "\n" + (result.stderr or ""))
    return RecordExecution(command=command, trace_id=trace_id, result=result)
