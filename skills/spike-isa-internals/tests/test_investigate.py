from rr_spike_rv_replay.investigate import (
    decide_round_commands,
    parse_evidence_lines,
    render_probe_gdb_script,
    run_interactive_probe,
)


def test_render_probe_gdb_script_contains_forward_reverse_loops() -> None:
    script = render_probe_gdb_script(
        spike_bin="/opt/riscv/bin/spike",
        replay_port=12345,
        target_pc="0x0000000080000016",
        steps_before=3,
        steps_after=4,
    )

    assert "target extended-remote :12345" in script
    assert "break ../riscv/execute.cc:308 if pc == 0x0000000080000016" in script
    assert "while $f < 4" in script
    assert "reverse-continue" in script
    assert "while $r < 3" in script


def test_parse_evidence_lines_extracts_direction_and_pc() -> None:
    lines = [
        "EVIDENCE TARGET pc=0x80000016",
        "EVIDENCE FWD step=1 pc=0x8000001a",
        "EVIDENCE REV step=1 pc=0x80000012",
        "noise",
    ]

    events = parse_evidence_lines(lines)

    assert events == [
        {"phase": "target", "step": 0, "pc": "0x80000016"},
        {"phase": "forward", "step": 1, "pc": "0x8000001a"},
        {"phase": "reverse", "step": 1, "pc": "0x80000012"},
    ]


def test_decide_round_commands_prefers_csr_observation_when_question_mentions_csr() -> None:
    cmds = decide_round_commands(question="which csr changed?", direction="forward")

    assert "x/i $pc" in cmds
    assert "print/x pc" in cmds
    assert "info registers" in cmds


def test_run_interactive_probe_uses_round_trip_gdb_commands() -> None:
    issued: list[str] = []

    class FakeSession:
        def run_command(self, command: str) -> str:
            issued.append(command)
            if command in {"continue", "reverse-continue"}:
                return "stopped"
            return "ok"

    transcript = run_interactive_probe(
        gdb=FakeSession(),
        target_pc="0x80000016",
        question="what happened",
        rounds_before=2,
        rounds_after=2,
    )

    assert issued[0].startswith("break ../riscv/execute.cc:308")
    assert issued[1] == "continue"
    assert issued.count("reverse-continue") == 2
    assert issued.count("continue") >= 3
    assert len(transcript) > 0
