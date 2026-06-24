import subprocess

from rr_spike_rv_replay.replayer import build_rr_replay_command, run_rr_replay


def test_build_rr_replay_command_uses_script_path() -> None:
    command = build_rr_replay_command("/tmp/replay.gdb")

    assert command == ["rr", "replay", "-x", "/tmp/replay.gdb"]


def test_run_rr_replay_invokes_runner_with_command() -> None:
    seen_commands: list[list[str]] = []

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        seen_commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    execution = run_rr_replay("/tmp/replay.gdb", runner=runner)

    assert seen_commands == [["rr", "replay", "-x", "/tmp/replay.gdb"]]
    assert execution.command == ["rr", "replay", "-x", "/tmp/replay.gdb"]
    assert execution.result.returncode == 0
