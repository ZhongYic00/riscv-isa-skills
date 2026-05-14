import json
import subprocess

import pytest

from rr_spike_rv_replay.cli import build_config
from rr_spike_rv_replay.pipeline import run_pipeline


def _ok_result(command: list[str], *, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, 0, stdout="", stderr=stderr)


def _all_tools_present(name: str) -> str:
    return f"/usr/bin/{name}"


def _write_trace(path, records) -> None:
    path.write_text(json.dumps(records), encoding="utf-8")


def test_run_pipeline_writes_required_artifacts_and_trace_metadata(tmp_path) -> None:
    trace_path = tmp_path / "trace.json"
    _write_trace(
        trace_path,
        [
            {"index": 1, "pc": "0x100", "text": "addi x1, x0, 1", "hart_id": 0},
            {"index": 2, "pc": "0x104", "text": "addi x2, x0, 2", "hart_id": 0},
        ],
    )
    cfg = build_config(
        test_case="tc",
        run_cmd="spike pk a.out",
        trace_path=str(trace_path),
        target_pc="0x104",
    )

    run_pipeline(
        cfg,
        tmp_path,
        preflight_which=_all_tools_present,
        symbol_checker=lambda _binary, _symbol: True,
        record_runner=lambda command: _ok_result(command, stderr="trace_id: trace-abc\n"),
        replay_runner=lambda command: _ok_result(command),
    )

    assert (tmp_path / "capture_meta.json").exists()
    assert (tmp_path / "replay.gdb").exists()
    assert (tmp_path / "event_summary.md").exists()
    assert (tmp_path / "analysis_trace.json").exists()
    assert (tmp_path / "index_snapshot.json").exists()

    capture_meta = json.loads((tmp_path / "capture_meta.json").read_text(encoding="utf-8"))
    assert capture_meta["trace_source_path"] == str(trace_path)
    assert capture_meta["selected_target"]["index"] == 2
    assert capture_meta["selected_target"]["pc"] == "0x104"
    assert capture_meta["symbol_strategy"] == "symbol"


def test_run_pipeline_selects_nth_hit_by_hart_and_generates_conditional_breakpoint(tmp_path) -> None:
    trace_path = tmp_path / "trace.json"
    _write_trace(
        trace_path,
        [
            {"index": 10, "pc": "0x200", "text": "addi x1, x0, 1", "hart_id": 0},
            {"index": 11, "pc": "0x200", "text": "addi x2, x0, 2", "hart_id": 1},
            {"index": 12, "pc": "0x200", "text": "addi x3, x0, 3", "hart_id": 1},
        ],
    )
    cfg = build_config(
        test_case="tc",
        run_cmd="spike pk a.out",
        trace_path=str(trace_path),
        target_pc="0x200",
        stop_policy="nth-hit",
        nth=2,
        hart_id=1,
        spike_counter_expr="custom_count",
    )

    result = run_pipeline(
        cfg,
        tmp_path,
        preflight_which=_all_tools_present,
        symbol_checker=lambda _binary, _symbol: True,
        record_runner=lambda command: _ok_result(command, stderr="trace_id: trace-nth\n"),
        replay_runner=lambda command: _ok_result(command),
    )

    assert result["status"] == "target-match"
    assert result["selected_target_index"] == 12

    replay_script = (tmp_path / "replay.gdb").read_text(encoding="utf-8")
    assert "condition 1 custom_count == 12 && $hartid == 1" in replay_script


def test_run_pipeline_reports_rerun_hints_when_trace_has_no_match(tmp_path) -> None:
    trace_path = tmp_path / "trace.json"
    _write_trace(trace_path, [{"index": 1, "pc": "0x100", "text": "addi x1, x0, 1", "hart_id": 0}])
    cfg = build_config(
        test_case="tc",
        run_cmd="spike pk a.out",
        trace_path=str(trace_path),
        target_pc="0x999",
    )

    run_pipeline(
        cfg,
        tmp_path,
        preflight_which=_all_tools_present,
        symbol_checker=lambda _binary, _symbol: True,
        record_runner=lambda command: _ok_result(command, stderr="trace_id: trace-miss\n"),
        replay_runner=lambda command: _ok_result(command),
    )

    capture_meta = json.loads((tmp_path / "capture_meta.json").read_text(encoding="utf-8"))
    assert capture_meta["status"] == "no-trace-match"
    assert capture_meta["rerun_hints"]


def test_run_pipeline_raises_when_spike_step_symbol_unavailable_without_fallback(tmp_path) -> None:
    trace_path = tmp_path / "trace.json"
    _write_trace(trace_path, [{"index": 4, "pc": "0x100", "text": "addi x1, x0, 1", "hart_id": 0}])
    cfg = build_config(
        test_case="tc",
        run_cmd="spike pk a.out",
        trace_path=str(trace_path),
        target_insn_index=4,
    )

    with pytest.raises(RuntimeError, match="spike step symbol"):
        run_pipeline(
            cfg,
            tmp_path,
            preflight_which=_all_tools_present,
            symbol_checker=lambda _binary, _symbol: False,
            record_runner=lambda command: _ok_result(command, stderr="trace_id: trace-sym\n"),
            replay_runner=lambda command: _ok_result(command),
        )


def test_run_pipeline_uses_address_fallback_when_symbol_unavailable(tmp_path) -> None:
    trace_path = tmp_path / "trace.json"
    _write_trace(trace_path, [{"index": 7, "pc": "0x100", "text": "addi x1, x0, 1", "hart_id": 2}])
    cfg = build_config(
        test_case="tc",
        run_cmd="spike pk a.out",
        trace_path=str(trace_path),
        target_insn_index=7,
        spike_step_address="0x1234",
    )

    run_pipeline(
        cfg,
        tmp_path,
        preflight_which=_all_tools_present,
        symbol_checker=lambda _binary, _symbol: False,
        record_runner=lambda command: _ok_result(command, stderr="trace_id: trace-fallback\n"),
        replay_runner=lambda command: _ok_result(command),
    )

    capture_meta = json.loads((tmp_path / "capture_meta.json").read_text(encoding="utf-8"))
    assert capture_meta["symbol_strategy"] == "address"
    assert capture_meta["fallback_warnings"]


def test_run_pipeline_generates_per_case_dynamic_script_values(tmp_path) -> None:
    trace_path = tmp_path / "trace.json"
    _write_trace(trace_path, [{"index": 88, "pc": "0x880", "text": "ecall", "hart_id": 5}])
    cfg = build_config(
        test_case="case-88",
        run_cmd="spike pk a.out",
        trace_path=str(trace_path),
        target_insn_index=88,
        hart_id=5,
    )

    run_pipeline(
        cfg,
        tmp_path,
        preflight_which=_all_tools_present,
        symbol_checker=lambda _binary, _symbol: True,
        record_runner=lambda command: _ok_result(command, stderr="trace_id: trace-dynamic\n"),
        replay_runner=lambda command: _ok_result(command),
    )

    replay_script = (tmp_path / "replay.gdb").read_text(encoding="utf-8")
    assert "# case: case-88" in replay_script
    assert "target index: 88" in replay_script
    assert "target pc: 0x880" in replay_script


def test_run_pipeline_defaults_to_symbol_strategy_when_symbol_check_unavailable(tmp_path) -> None:
    trace_path = tmp_path / "trace.json"
    _write_trace(trace_path, [{"index": 9, "pc": "0x900", "text": "addi", "hart_id": 0}])
    cfg = build_config(
        test_case="case-9",
        run_cmd="spike pk a.out",
        trace_path=str(trace_path),
        target_insn_index=9,
    )

    run_pipeline(
        cfg,
        tmp_path,
        preflight_which=_all_tools_present,
        record_runner=lambda command: _ok_result(command, stderr="trace_id: trace-unknown-sym\n"),
        replay_runner=lambda command: _ok_result(command),
    )

    capture_meta = json.loads((tmp_path / "capture_meta.json").read_text(encoding="utf-8"))
    assert capture_meta["symbol_strategy"] == "symbol"
