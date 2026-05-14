"""Agent-driven rr/gdb probing helpers for scenario-2 investigations."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

import pexpect

from rr_spike_rv_replay.goto_entry import (
    build_spike_log_command,
    default_instruction_budget,
    resolve_target_pc_from_trace,
)
from rr_spike_rv_replay.spike_log_converter import convert_spike_commit_log_to_trace_json


def render_probe_gdb_script(
    *,
    spike_bin: str,
    replay_port: int,
    target_pc: str,
    steps_before: int,
    steps_after: int,
) -> str:
    return "\n".join(
        [
            "set pagination off",
            "set confirm off",
            f"file {spike_bin}",
            f"target extended-remote :{replay_port}",
            f"break ../riscv/execute.cc:308 if pc == {target_pc}",
            "commands",
            "  silent",
            "  printf \"EVIDENCE TARGET pc=%#lx\\n\", pc",
            "  delete 1",
            "  break ../riscv/execute.cc:308",
            "  set $r = 0",
            f"  while $r < {steps_before}",
            "    reverse-continue",
            "    set $r = $r + 1",
            "    printf \"EVIDENCE REV step=%d pc=%#lx\\n\", $r, pc",
            "  end",
            "  set $f = 0",
            f"  while $f < {steps_after}",
            "    continue",
            "    set $f = $f + 1",
            "    printf \"EVIDENCE FWD step=%d pc=%#lx\\n\", $f, pc",
            "  end",
            "  quit",
            "end",
            "continue",
            "",
        ]
    )


TARGET_RE = re.compile(r"^EVIDENCE TARGET pc=(0x[0-9a-fA-F]+)$")
FWD_RE = re.compile(r"^EVIDENCE FWD step=(\d+) pc=(0x[0-9a-fA-F]+)$")
REV_RE = re.compile(r"^EVIDENCE REV step=(\d+) pc=(0x[0-9a-fA-F]+)$")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def parse_evidence_lines(lines: list[str]) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for line in lines:
        line = ANSI_RE.sub("", line).replace("\r", "").strip()
        target = TARGET_RE.match(line)
        if target:
            events.append({"phase": "target", "step": 0, "pc": target.group(1).lower()})
            continue
        forward = FWD_RE.match(line)
        if forward:
            events.append({"phase": "forward", "step": int(forward.group(1)), "pc": forward.group(2).lower()})
            continue
        reverse = REV_RE.match(line)
        if reverse:
            events.append({"phase": "reverse", "step": int(reverse.group(1)), "pc": reverse.group(2).lower()})
    return events


class PexpectGdbSession:
    def __init__(self, *, gdb_bin: str, spike_bin: str, replay_port: int, timeout: int = 30) -> None:
        self._proc = pexpect.spawn(f"{gdb_bin} -q", encoding="utf-8", timeout=timeout)
        self._proc.expect_exact("(gdb) ")
        self.run_command("set pagination off")
        self.run_command("set height 0")
        self.run_command("set width 0")
        self.run_command(f"file {spike_bin}")
        self.run_command(f"target extended-remote :{replay_port}")

    def run_command(self, command: str) -> str:
        self._proc.sendline(command)
        chunks: list[str] = []
        while True:
            idx = self._proc.expect_exact(
                ["(gdb) ", "--Type <RET> for more, q to quit, c to continue without paging--"]
            )
            chunks.append(self._proc.before)
            if idx == 0:
                break
            self._proc.sendline("c")
        return "".join(chunks).strip()

    def close(self) -> None:
        if not self._proc.isalive():
            return
        self._proc.sendline("quit")
        try:
            self._proc.expect(pexpect.EOF)
        except Exception:
            self._proc.close(force=True)


def decide_round_commands(*, question: str, direction: str) -> list[str]:
    commands = [
        "x/i $pc",
        "print/x pc",
    ]
    lowered = question.lower()
    if "csr" in lowered or "fcsr" in lowered or "mstatus" in lowered:
        commands.append("info registers")
    if direction == "reverse":
        commands.append("reverse-continue")
    else:
        commands.append("continue")
    return commands


def run_interactive_probe(
    *,
    gdb: PexpectGdbSession,
    target_pc: str,
    question: str,
    rounds_before: int,
    rounds_after: int,
) -> list[dict[str, object]]:
    transcript: list[dict[str, object]] = []

    for command in [
        f"break ../riscv/execute.cc:308 if pc == {target_pc}",
        "continue",
        'printf "EVIDENCE TARGET pc=%#lx\\n", pc',
        "break ../riscv/execute.cc:308",
    ]:
        output = gdb.run_command(command)
        transcript.append({"phase": "target", "step": 0, "command": command, "output": output})

    for step in range(1, rounds_before + 1):
        for command in decide_round_commands(question=question, direction="reverse"):
            output = gdb.run_command(command)
            transcript.append({"phase": "reverse", "step": step, "command": command, "output": output})
        evidence = gdb.run_command(f'printf "EVIDENCE REV step={step} pc=%#lx\\n", pc')
        transcript.append({"phase": "reverse", "step": step, "command": "evidence", "output": evidence})

    for step in range(1, rounds_after + 1):
        for command in decide_round_commands(question=question, direction="forward"):
            output = gdb.run_command(command)
            transcript.append({"phase": "forward", "step": step, "command": command, "output": output})
        evidence = gdb.run_command(f'printf "EVIDENCE FWD step={step} pc=%#lx\\n", pc')
        transcript.append({"phase": "forward", "step": step, "command": "evidence", "output": evidence})

    return transcript


def run_investigation(
    *,
    elf_path: str,
    target_index: int,
    work_dir: str | Path,
    question: str,
    trace_path: str | Path | None = None,
    spike_bin: str = "/opt/riscv/bin/spike",
    rr_bin: str = "rr",
    gdb_bin: str = "gdb",
    hart_id: int | None = None,
    instruction_budget: int | None = None,
    replay_port: int = 12345,
    steps_before: int = 6,
    steps_after: int = 6,
    spike_args: list[str] | None = None,
) -> dict[str, object]:
    budget = instruction_budget or default_instruction_budget(target_index)
    output = Path(work_dir)
    output.mkdir(parents=True, exist_ok=True)

    log_path = output / "spike_commit.log"
    generated_trace_path = output / "spike_trace.json"
    gdb_log_path = output / "investigate.gdb.log"
    replay_log_path = output / "investigate.rr.log"

    if trace_path is None:
        spike_log_cmd = build_spike_log_command(
            spike_bin=spike_bin,
            elf_path=elf_path,
            log_path=str(log_path),
            instruction_budget=budget,
            spike_args=spike_args,
        )
        subprocess.run(spike_log_cmd, check=False)
        convert_spike_commit_log_to_trace_json(log_path, generated_trace_path)
        effective_trace_path = generated_trace_path
    else:
        effective_trace_path = Path(trace_path)

    target_pc = resolve_target_pc_from_trace(effective_trace_path, target_index=target_index, hart_id=hart_id)

    subprocess.run([rr_bin, "record", spike_bin, f"--instructions={budget}", *(spike_args or []), elf_path], check=True)

    replay_file = replay_log_path.open("w", encoding="utf-8")
    replay_server = subprocess.Popen([rr_bin, "replay", "-s", str(replay_port)], stdout=replay_file, stderr=subprocess.STDOUT)
    transcript: list[dict[str, object]] = []
    gdb_exit_code = 0
    try:
        time.sleep(1)
        session = PexpectGdbSession(gdb_bin=gdb_bin, spike_bin=spike_bin, replay_port=replay_port)
        try:
            transcript = run_interactive_probe(
                gdb=session,
                target_pc=target_pc,
                question=question,
                rounds_before=steps_before,
                rounds_after=steps_after,
            )
        finally:
            session.close()
    except Exception:
        gdb_exit_code = 1
        raise
    finally:
        replay_server.terminate()
        try:
            replay_server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            replay_server.kill()
        replay_file.close()

    combined_output_lines: list[str] = []
    for item in transcript:
        combined_output_lines.append(f"## {item['phase']}[{item['step']}] {item['command']}")
        combined_output_lines.append(str(item["output"]))
    gdb_log_path.write_text("\n".join(combined_output_lines) + "\n", encoding="utf-8")
    flat_lines: list[str] = []
    for entry in combined_output_lines:
        flat_lines.extend(str(entry).splitlines())
    evidence = parse_evidence_lines(flat_lines)
    return {
        "question": question,
        "target_index": target_index,
        "target_pc": target_pc,
        "hart_id": hart_id,
        "steps_before": steps_before,
        "steps_after": steps_after,
        "gdb_exit_code": gdb_exit_code,
        "trace_path": str(effective_trace_path),
        "gdb_script_path": "interactive",
        "gdb_log_path": str(gdb_log_path),
        "gdb_reverse_log_path": str(gdb_log_path),
        "gdb_forward_log_path": str(gdb_log_path),
        "transcript": transcript,
        "events": evidence,
    }
