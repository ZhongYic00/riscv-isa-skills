from rr_spike_rv_replay.preflight import find_missing_tools, preflight_report


def test_find_missing_tools_uses_injected_which() -> None:
    tool_paths = {
        "rr": "/usr/bin/rr",
        "gdb": None,
        "spike": None,
    }

    def fake_which(name: str) -> str | None:
        return tool_paths.get(name)

    assert find_missing_tools(fake_which) == ["gdb", "spike"]


def test_preflight_report_returns_found_and_missing() -> None:
    tool_paths = {
        "rr": "/custom/rr",
        "gdb": "/custom/gdb",
        "spike": None,
    }

    report = preflight_report(
        lambda name: tool_paths.get(name),
        spike_binary="/custom/spike",
        spike_step_symbol="processor_t::step",
        symbol_checker=lambda _binary, _symbol: False,
    )

    assert report.found == {"rr": "/custom/rr", "gdb": "/custom/gdb"}
    assert report.missing == ["spike"]
    assert report.ok is False
    assert report.spike_symbol_ready is False
