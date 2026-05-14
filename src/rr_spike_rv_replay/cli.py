"""CLI wiring and config construction for the replay pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from pathlib import PurePosixPath
import shlex
from typing import Any, Literal

try:
    import typer
except ModuleNotFoundError:  # pragma: no cover - fallback for test environments
    class _TyperFallback:
        def __call__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("typer is not installed; install project dependencies to use CLI commands")

        def command(self, *_args: Any, **_kwargs: Any):
            def decorator(func: Any) -> Any:
                return func

            return decorator

    class _TyperModuleFallback:
        Typer = _TyperFallback

        @staticmethod
        def Option(default: Any = None, *_args: Any, **_kwargs: Any) -> Any:
            return default

    typer = _TyperModuleFallback()

from rr_spike_rv_replay.pipeline import run_pipeline
from rr_spike_rv_replay.spike_log_converter import convert_spike_commit_log_to_trace_json
from rr_spike_rv_replay.goto_entry import goto_instruction_entry
from rr_spike_rv_replay.isa_events import extract_isa_events
from rr_spike_rv_replay.investigate import run_investigation
from rr_spike_rv_replay.trace_bridge import parse_trace_file


@dataclass(frozen=True)
class PipelineConfig:
    test_case: str
    run_cmd: str
    trace_path: str | None = None
    target_insn_index: int | None = None
    target_pc: str | None = None
    rv_instr_pattern: str | None = None
    rv_instr: str | None = None
    hart_id: int | None = None
    symbol_offset: str | None = None
    spike_step_symbol: str = "processor_t::step"
    spike_step_address: str | None = None
    spike_step_pattern: str | None = None
    spike_counter_expr: str = "spike_insn_count"
    stop_policy: Literal["first-hit", "nth-hit"] = "first-hit"
    nth: int = 1
    window_before: int = 8
    window_after: int = 8
    llm_mode: Literal["off", "assist"] = "off"


def build_config(
    test_case: str,
    run_cmd: str,
    trace_path: str | None = None,
    target_insn_index: int | None = None,
    target_pc: str | None = None,
    rv_instr_pattern: str | None = None,
    rv_instr: str | None = None,
    hart_id: int | None = None,
    symbol_offset: str | None = None,
    spike_step_symbol: str = "processor_t::step",
    spike_step_address: str | None = None,
    spike_step_pattern: str | None = None,
    spike_counter_expr: str = "spike_insn_count",
    stop_policy: Literal["first-hit", "nth-hit"] = "first-hit",
    nth: int = 1,
    window_before: int = 8,
    window_after: int = 8,
    llm_mode: Literal["off", "assist"] = "off",
) -> PipelineConfig:
    run_tokens = shlex.split(run_cmd)
    if not run_tokens:
        raise ValueError("run_cmd must not be empty")
    first_token = run_tokens[0]
    if PurePosixPath(first_token).name != "spike":
        raise ValueError("run_cmd first token must be a spike executable path ending with 'spike'")

    selectors = [trace_path, target_insn_index, target_pc, rv_instr_pattern, rv_instr, symbol_offset]
    if not any(value is not None and str(value).strip() for value in selectors):
        raise ValueError("at least one target selector must be provided")
    if stop_policy not in {"first-hit", "nth-hit"}:
        raise ValueError("stop_policy must be one of {'first-hit','nth-hit'}")
    if llm_mode not in {"off", "assist"}:
        raise ValueError("llm_mode must be one of {'off','assist'}")
    if nth < 1:
        raise ValueError("nth must be >= 1")
    if window_before < 0:
        raise ValueError("window_before must be >= 0")
    if window_after < 0:
        raise ValueError("window_after must be >= 0")

    return PipelineConfig(
        test_case=test_case,
        run_cmd=run_cmd,
        trace_path=trace_path,
        target_insn_index=target_insn_index,
        target_pc=target_pc,
        rv_instr_pattern=rv_instr_pattern,
        rv_instr=rv_instr,
        hart_id=hart_id,
        symbol_offset=symbol_offset,
        spike_step_symbol=spike_step_symbol,
        spike_step_address=spike_step_address,
        spike_step_pattern=spike_step_pattern,
        spike_counter_expr=spike_counter_expr,
        stop_policy=stop_policy,
        nth=nth,
        window_before=window_before,
        window_after=window_after,
        llm_mode=llm_mode,
    )


app = typer.Typer()


def main() -> None:
    app()


@app.command("run")
def run(
    test_case: str = typer.Option(..., "--test-case"),
    run_cmd: str = typer.Option(..., "--run-cmd"),
    out_dir: Path = typer.Option(Path("./rr_spike_out"), "--out-dir"),
    trace_path: str | None = typer.Option(None, "--trace-path"),
    target_insn_index: int | None = typer.Option(None, "--target-insn-index"),
    target_pc: str | None = typer.Option(None, "--target-pc"),
    rv_instr_pattern: str | None = typer.Option(None, "--rv-instr-pattern"),
    rv_instr: str | None = typer.Option(None, "--rv-instr"),
    hart_id: int | None = typer.Option(None, "--hart-id"),
    symbol_offset: str | None = typer.Option(None, "--symbol-offset"),
    spike_step_symbol: str = typer.Option("processor_t::step", "--spike-step-symbol"),
    spike_step_address: str | None = typer.Option(None, "--spike-step-address"),
    spike_step_pattern: str | None = typer.Option(None, "--spike-step-pattern"),
    spike_counter_expr: str = typer.Option("spike_insn_count", "--spike-counter-expr"),
    stop_policy: str = typer.Option("first-hit", "--stop-policy"),
    nth: int = typer.Option(1, "--nth"),
    window_before: int = typer.Option(8, "--window-before"),
    window_after: int = typer.Option(8, "--window-after"),
    llm_mode: str = typer.Option("off", "--llm-mode"),
) -> dict[str, Any]:
    config = build_config(
        test_case=test_case,
        run_cmd=run_cmd,
        trace_path=trace_path,
        target_insn_index=target_insn_index,
        target_pc=target_pc,
        rv_instr_pattern=rv_instr_pattern,
        rv_instr=rv_instr,
        hart_id=hart_id,
        symbol_offset=symbol_offset,
        spike_step_symbol=spike_step_symbol,
        spike_step_address=spike_step_address,
        spike_step_pattern=spike_step_pattern,
        spike_counter_expr=spike_counter_expr,
        stop_policy=stop_policy,
        nth=nth,
        window_before=window_before,
        window_after=window_after,
        llm_mode=llm_mode,
    )
    result = run_pipeline(config, out_dir)
    return {"config": asdict(config), "result": result}


@app.command("convert-log")
def convert_log(
    log_path: Path = typer.Option(..., "--log-path"),
    out_path: Path = typer.Option(..., "--out-path"),
) -> dict[str, Any]:
    count = convert_spike_commit_log_to_trace_json(log_path, out_path)
    return {"log_path": str(log_path), "out_path": str(out_path), "instruction_count": count}


@app.command("goto")
def goto(
    elf_path: Path = typer.Option(..., "--elf-path"),
    target_index: int = typer.Option(..., "--target-index"),
    work_dir: Path = typer.Option(Path("./rrspike_goto"), "--work-dir"),
    spike_bin: str = typer.Option("/opt/riscv/bin/spike", "--spike-bin"),
    rr_bin: str = typer.Option("rr", "--rr-bin"),
    gdb_bin: str = typer.Option("gdb", "--gdb-bin"),
    hart_id: int | None = typer.Option(None, "--hart-id"),
    instruction_budget: int | None = typer.Option(None, "--instruction-budget"),
    replay_port: int = typer.Option(12345, "--replay-port"),
    spike_args: str | None = typer.Option(None, "--spike-args"),
) -> dict[str, Any]:
    args = shlex.split(spike_args) if spike_args else []
    rc = goto_instruction_entry(
        elf_path=str(elf_path),
        target_index=target_index,
        work_dir=work_dir,
        spike_bin=spike_bin,
        rr_bin=rr_bin,
        gdb_bin=gdb_bin,
        hart_id=hart_id,
        instruction_budget=instruction_budget,
        replay_port=replay_port,
        spike_args=args,
    )
    return {"status": "ok" if rc == 0 else "replay-failed", "return_code": rc, "work_dir": str(work_dir)}


@app.command("inspect-events")
def inspect_events(
    trace_path: Path = typer.Option(..., "--trace-path"),
    target_index: int = typer.Option(..., "--target-index"),
    before: int = typer.Option(16, "--before"),
    after: int = typer.Option(16, "--after"),
    hart_id: int | None = typer.Option(None, "--hart-id"),
    out_path: Path | None = typer.Option(None, "--out-path"),
) -> dict[str, Any]:
    records = parse_trace_file(trace_path)
    events = extract_isa_events(records, target_index=target_index, before=before, after=after, hart_id=hart_id)
    payload = {
        "trace_path": str(trace_path),
        "target_index": target_index,
        "hart_id": hart_id,
        "window": {"before": before, "after": after},
        "event_count": len(events),
        "events": events,
    }
    if out_path is not None:
        Path(out_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


@app.command("investigate")
def investigate(
    elf_path: Path = typer.Option(..., "--elf-path"),
    target_index: int = typer.Option(..., "--target-index"),
    question: str = typer.Option(..., "--question"),
    trace_path: Path | None = typer.Option(None, "--trace-path"),
    work_dir: Path = typer.Option(Path("./rrspike_investigate"), "--work-dir"),
    spike_bin: str = typer.Option("/opt/riscv/bin/spike", "--spike-bin"),
    rr_bin: str = typer.Option("rr", "--rr-bin"),
    gdb_bin: str = typer.Option("gdb", "--gdb-bin"),
    hart_id: int | None = typer.Option(None, "--hart-id"),
    instruction_budget: int | None = typer.Option(None, "--instruction-budget"),
    replay_port: int = typer.Option(12345, "--replay-port"),
    steps_before: int = typer.Option(6, "--steps-before"),
    steps_after: int = typer.Option(6, "--steps-after"),
    spike_args: str | None = typer.Option(None, "--spike-args"),
    out_path: Path | None = typer.Option(None, "--out-path"),
) -> dict[str, Any]:
    args = shlex.split(spike_args) if spike_args else []
    payload = run_investigation(
        elf_path=str(elf_path),
        target_index=target_index,
        work_dir=work_dir,
        question=question,
        trace_path=trace_path,
        spike_bin=spike_bin,
        rr_bin=rr_bin,
        gdb_bin=gdb_bin,
        hart_id=hart_id,
        instruction_budget=instruction_budget,
        replay_port=replay_port,
        steps_before=steps_before,
        steps_after=steps_after,
        spike_args=args,
    )
    if out_path is not None:
        Path(out_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    main()
