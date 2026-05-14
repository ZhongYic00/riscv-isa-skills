"""Preflight checks for required external tools."""

from __future__ import annotations

from dataclasses import dataclass
from shutil import which as system_which
from typing import Callable

REQUIRED_TOOLS: tuple[str, ...] = ("rr", "gdb", "spike")
SymbolChecker = Callable[[str, str], bool]


@dataclass(frozen=True)
class PreflightReport:
    found: dict[str, str]
    missing: list[str]
    spike_symbol_ready: bool | None = None

    @property
    def ok(self) -> bool:
        return not self.missing


def find_missing_tools(
    which: Callable[[str], str | None] = system_which,
    required_tools: tuple[str, ...] = REQUIRED_TOOLS,
) -> list[str]:
    return [tool for tool in required_tools if which(tool) is None]


def preflight_report(
    which: Callable[[str], str | None] = system_which,
    required_tools: tuple[str, ...] = REQUIRED_TOOLS,
    *,
    spike_binary: str | None = None,
    spike_step_symbol: str | None = None,
    symbol_checker: SymbolChecker | None = None,
) -> PreflightReport:
    found: dict[str, str] = {}
    missing: list[str] = []
    for tool in required_tools:
        location = which(tool)
        if location is None:
            missing.append(tool)
        else:
            found[tool] = location
    spike_symbol_ready: bool | None = None
    if spike_binary and spike_step_symbol and symbol_checker:
        spike_symbol_ready = symbol_checker(spike_binary, spike_step_symbol)
    return PreflightReport(found=found, missing=missing, spike_symbol_ready=spike_symbol_ready)
