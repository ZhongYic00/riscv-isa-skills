import pytest

from rr_spike_rv_replay.recorder import build_rr_record_command


def test_build_rr_record_command_wraps_run_command() -> None:
    run_cmd = ["spike", "--isa=rv64imac", "program.elf"]

    command = build_rr_record_command(run_cmd)

    assert command == ["rr", "record", "--", "spike", "--isa=rv64imac", "program.elf"]


def test_build_rr_record_command_rejects_empty_run_command() -> None:
    with pytest.raises(ValueError, match="run_cmd must not be empty"):
        build_rr_record_command([])
