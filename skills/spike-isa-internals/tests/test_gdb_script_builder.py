from rr_spike_rv_replay.gdb_script_builder import build_gdb_script


def test_build_gdb_script_contains_breakpoints_window_and_register_template() -> None:
    script = build_gdb_script(
        binary_path="/tmp/program.elf",
        breakpoint_strategy="symbol",
        breakpoint_value="processor_t::step",
        target_insn_index=42,
        spike_counter_expr="spike_insn_count",
        hart_id=3,
        window_before=3,
        window_after=5,
        registers=["pc", "ra", "sp"],
        memory_ranges=["0x1000", "0x2000"],
    )

    assert "file /tmp/program.elf" in script
    assert "break processor_t::step" in script
    assert "condition 1 spike_insn_count == 42 && $hartid == 3" in script
    assert "reverse-stepi 3" in script
    assert "stepi 5" in script
    assert 'printf "pc=%#lx ra=%#lx sp=%#lx\\n", $pc, $ra, $sp' in script
    assert "x/4gx 0x1000" in script
    assert "x/4gx 0x2000" in script
