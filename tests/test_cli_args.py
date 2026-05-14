import inspect

import pytest

from rr_spike_rv_replay import cli
from rr_spike_rv_replay.cli import PipelineConfig, build_config


def test_build_config_populates_defaults_and_fields() -> None:
    cfg = build_config(test_case="tc1", run_cmd="/opt/riscv/bin/spike pk a.out", target_pc="0x80000000")

    assert isinstance(cfg, PipelineConfig)
    assert cfg.test_case == "tc1"
    assert cfg.run_cmd == "/opt/riscv/bin/spike pk a.out"
    assert cfg.target_pc == "0x80000000"
    assert cfg.rv_instr_pattern is None
    assert cfg.symbol_offset is None
    assert cfg.stop_policy == "first-hit"
    assert cfg.nth == 1
    assert cfg.window_before == 8
    assert cfg.window_after == 8
    assert cfg.llm_mode == "off"
    assert cfg.trace_path is None
    assert cfg.target_insn_index is None
    assert cfg.rv_instr is None
    assert cfg.hart_id is None
    assert cfg.spike_step_symbol == "processor_t::step"
    assert cfg.spike_step_address is None
    assert cfg.spike_step_pattern is None
    assert cfg.spike_counter_expr == "spike_insn_count"


def test_build_config_accepts_non_pc_selector() -> None:
    cfg = build_config(test_case="tc2", run_cmd="spike pk b.out", rv_instr_pattern="ecall")

    assert cfg.target_pc is None
    assert cfg.rv_instr_pattern == "ecall"


def test_build_config_requires_at_least_one_target_selector() -> None:
    with pytest.raises(ValueError, match="at least one target selector"):
        build_config(test_case="tc3", run_cmd="spike pk c.out")


def test_build_config_accepts_trace_path_without_other_selectors() -> None:
    cfg = build_config(test_case="tc3", run_cmd="spike pk c.out", trace_path="/tmp/trace.json")

    assert cfg.trace_path == "/tmp/trace.json"


@pytest.mark.parametrize("run_cmd", ["python app.py", "/usr/bin/qemu-riscv64 demo.elf", ""]) 
def test_build_config_rejects_non_spike_run_command(run_cmd: str) -> None:
    with pytest.raises(ValueError, match="run_cmd"):
        build_config(test_case="tcx", run_cmd=run_cmd, target_pc="0x1")


@pytest.mark.parametrize("stop_policy", ["last-hit", ""])
def test_build_config_rejects_invalid_stop_policy(stop_policy: str) -> None:
    with pytest.raises(ValueError, match="stop_policy"):
        build_config(test_case="tc4", run_cmd="spike pk d.out", target_pc="0x1", stop_policy=stop_policy)


@pytest.mark.parametrize("llm_mode", ["on", ""])
def test_build_config_rejects_invalid_llm_mode(llm_mode: str) -> None:
    with pytest.raises(ValueError, match="llm_mode"):
        build_config(test_case="tc5", run_cmd="spike pk e.out", target_pc="0x1", llm_mode=llm_mode)


def test_build_config_rejects_nth_less_than_one() -> None:
    with pytest.raises(ValueError, match="nth"):
        build_config(test_case="tc6", run_cmd="spike pk f.out", target_pc="0x1", nth=0)


@pytest.mark.parametrize("field_name", ["window_before", "window_after"])
def test_build_config_rejects_negative_windows(field_name: str) -> None:
    kwargs = {field_name: -1}
    with pytest.raises(ValueError, match=field_name):
        build_config(test_case="tc7", run_cmd="spike pk g.out", target_pc="0x1", **kwargs)


def test_main_invokes_typer_app(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"value": False}

    def fake_app() -> None:
        called["value"] = True

    monkeypatch.setattr(cli, "app", fake_app)

    cli.main()

    assert called["value"] is True


def test_cli_run_accepts_option_style_arguments(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    typer_testing = pytest.importorskip("typer.testing")
    runner = typer_testing.CliRunner()

    captured: dict[str, object] = {}

    def fake_run_pipeline(config: PipelineConfig, out_dir) -> dict[str, str]:
        captured["config"] = config
        captured["out_dir"] = out_dir
        return {"status": "ok"}

    monkeypatch.setattr(cli, "run_pipeline", fake_run_pipeline)

    result = runner.invoke(
        cli.app,
        [
            "run",
            "--test-case",
            "tc-opt",
            "--run-cmd",
            "spike pk demo.elf",
            "--trace-path",
            "/tmp/trace.json",
            "--target-insn-index",
            "12",
            "--out-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert isinstance(captured["config"], PipelineConfig)
    assert str(captured["out_dir"]) == str(tmp_path)


def test_cli_run_exposes_key_inputs_as_options() -> None:
    sig = inspect.signature(cli.run)

    assert sig.parameters["test_case"].default is not inspect._empty
    assert sig.parameters["run_cmd"].default is not inspect._empty
    assert sig.parameters["out_dir"].default is not inspect._empty


def test_cli_goto_exposes_key_inputs_as_options() -> None:
    sig = inspect.signature(cli.goto)

    assert sig.parameters["elf_path"].default is not inspect._empty
    assert sig.parameters["target_index"].default is not inspect._empty
    assert sig.parameters["work_dir"].default is not inspect._empty


def test_cli_inspect_events_exposes_key_inputs_as_options() -> None:
    sig = inspect.signature(cli.inspect_events)

    assert sig.parameters["trace_path"].default is not inspect._empty
    assert sig.parameters["target_index"].default is not inspect._empty
    assert sig.parameters["before"].default is not inspect._empty
    assert sig.parameters["after"].default is not inspect._empty


def test_inspect_events_accepts_string_out_path(tmp_path) -> None:
    trace_path = tmp_path / "trace.json"
    out_path = tmp_path / "events.json"
    trace_path.write_text(
        '{"instructions":[{"index":1,"pc":"0x8000","text":"csrr a0, mstatus","hart_id":0}]}',
        encoding="utf-8",
    )

    result = cli.inspect_events(
        trace_path=trace_path,
        target_index=1,
        before=0,
        after=0,
        hart_id=0,
        out_path=str(out_path),
    )

    assert result["event_count"] == 1
    assert out_path.exists()


def test_cli_investigate_exposes_key_inputs_as_options() -> None:
    sig = inspect.signature(cli.investigate)

    assert sig.parameters["elf_path"].default is not inspect._empty
    assert sig.parameters["target_index"].default is not inspect._empty
    assert sig.parameters["question"].default is not inspect._empty
    assert sig.parameters["trace_path"].default is not inspect._empty
    assert sig.parameters["steps_before"].default is not inspect._empty
    assert sig.parameters["steps_after"].default is not inspect._empty
