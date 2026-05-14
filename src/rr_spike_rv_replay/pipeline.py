"""Deterministic pipeline orchestration for replay artifacts."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any, Callable

from rr_spike_rv_replay.gdb_script_builder import build_gdb_script
from rr_spike_rv_replay.llm_assist import filter_suggestions
from rr_spike_rv_replay.preflight import SymbolChecker, preflight_report
from rr_spike_rv_replay.recorder import Runner, run_rr_record
from rr_spike_rv_replay.replayer import run_rr_replay
from rr_spike_rv_replay.reporter import write_event_summary, write_json_artifact
from rr_spike_rv_replay.trace_bridge import TraceRecord, parse_trace_file, resolve_target_from_trace


def _raise_on_failure(stage: str, result: Any) -> None:
    if result.returncode == 0:
        return
    raise RuntimeError(
        f"{stage} failed with return code {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}"
    )


def _resolve_symbol_strategy(config: Any, spike_symbol_ready: bool | None) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    if spike_symbol_ready:
        return "symbol", config.spike_step_symbol, warnings
    if spike_symbol_ready is None:
        warnings.append("Spike symbol readiness was not checked; attempting symbolic breakpoint")
        return "symbol", config.spike_step_symbol, warnings
    if config.spike_step_address:
        warnings.append("Spike symbol unavailable; using spike_step_address fallback")
        return "address", config.spike_step_address, warnings
    if config.spike_step_pattern:
        warnings.append("Spike symbol unavailable; using spike_step_pattern fallback")
        return "pattern", config.spike_step_pattern, warnings
    raise RuntimeError(
        "spike step symbol is unavailable in the Spike binary and no spike_step_address/spike_step_pattern fallback was provided"
    )


def _resolve_trace(config: Any) -> tuple[list[TraceRecord], TraceRecord | None, str, list[str]]:
    if not config.trace_path:
        return [], None, "no-trace-input", ["Provide trace_path to target replay by instruction index"]
    records = parse_trace_file(config.trace_path)
    selected, status, hints = resolve_target_from_trace(
        records,
        target_insn_index=config.target_insn_index,
        target_pc=config.target_pc,
        rv_instr_pattern=config.rv_instr_pattern,
        rv_instr=config.rv_instr,
        stop_policy=config.stop_policy,
        nth=config.nth,
        hart_id=config.hart_id,
    )
    return records, selected, status, hints


def run_pipeline(
    config: Any,
    out_dir: str | Path,
    *,
    candidates: list[dict[str, Any]] | None = None,
    llm_suggestions: list[dict[str, Any]] | None = None,
    allowed_probe_kinds: set[str] | None = None,
    record_runner: Runner | None = None,
    replay_runner: Runner | None = None,
    preflight_which: Callable[[str], str | None] | None = None,
    symbol_checker: SymbolChecker | None = None,
) -> dict[str, Any]:
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_cmd_list = shlex.split(config.run_cmd)
    spike_binary = run_cmd_list[0]

    if preflight_which:
        report = preflight_report(
            which=preflight_which,
            spike_binary=spike_binary,
            spike_step_symbol=config.spike_step_symbol,
            symbol_checker=symbol_checker,
        )
    else:
        report = preflight_report(
            spike_binary=spike_binary,
            spike_step_symbol=config.spike_step_symbol,
            symbol_checker=symbol_checker,
        )
    if not report.ok:
        raise RuntimeError(f"preflight failed: missing tools {', '.join(report.missing)}")

    breakpoint_strategy, breakpoint_value, fallback_warnings = _resolve_symbol_strategy(config, report.spike_symbol_ready)

    record_execution = run_rr_record(run_cmd_list, runner=record_runner) if record_runner else run_rr_record(run_cmd_list)
    _raise_on_failure("rr record", record_execution.result)

    trace_records, selected, status, rerun_hints = _resolve_trace(config)
    target_insn_index = selected.index if selected else config.target_insn_index or 0

    replay_script = build_gdb_script(
        binary_path=config.test_case,
        breakpoint_strategy=breakpoint_strategy,
        breakpoint_value=breakpoint_value,
        target_insn_index=target_insn_index,
        spike_counter_expr=config.spike_counter_expr,
        hart_id=config.hart_id,
        window_before=config.window_before,
        window_after=config.window_after,
        registers=["pc", "ra", "sp"],
        memory_ranges=[],
        case_id=config.test_case,
        target_pc=selected.pc if selected else config.target_pc,
    )
    replay_script_path = output_dir / "replay.gdb"
    replay_script_path.write_text(replay_script, encoding="utf-8")

    replay_execution = run_rr_replay(replay_script_path, runner=replay_runner) if replay_runner else run_rr_replay(replay_script_path)
    _raise_on_failure("rr replay", replay_execution.result)

    write_json_artifact(
        output_dir,
        "capture_meta.json",
        {
            "test_case": config.test_case,
            "run_cmd": config.run_cmd,
            "record_command": record_execution.command,
            "replay_command": replay_execution.command,
            "trace_id": record_execution.trace_id,
            "status": status,
            "trace_source_path": config.trace_path,
            "selected_target": {
                "index": selected.index if selected else None,
                "pc": selected.pc if selected else None,
                "hart_id": selected.hart_id if selected else config.hart_id,
            },
            "symbol_strategy": breakpoint_strategy,
            "fallback_warnings": fallback_warnings,
            "rerun_hints": rerun_hints,
            "preflight": {
                "ok": report.ok,
                "found": report.found,
                "missing": report.missing,
                "spike_symbol_ready": report.spike_symbol_ready,
            },
        },
    )

    write_json_artifact(
        output_dir,
        "index_snapshot.json",
        {
            "candidates": candidates or [],
            "trace_records": [record.__dict__ for record in trace_records],
        },
    )

    write_event_summary(
        output_dir,
        {
            "event_id": config.test_case,
            "best_candidate": str(selected.index) if selected else "none",
            "fallback_candidates": [item.index for item in trace_records[:3]],
            "status": status,
        },
    )

    advisory = llm_suggestions or []
    adopted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    if config.llm_mode == "assist":
        adopted, rejected = filter_suggestions(advisory, allowed_probe_kinds or set())

    write_json_artifact(
        output_dir,
        "analysis_trace.json",
        {
            "status": status,
            "selected_target_index": selected.index if selected else None,
            "llm": {
                "mode": config.llm_mode,
                "suggestions": advisory,
                "adopted": adopted,
                "rejected": rejected,
            },
        },
    )

    return {
        "status": status,
        "selected_target_index": selected.index if selected else None,
        "artifact_dir": str(output_dir),
    }
