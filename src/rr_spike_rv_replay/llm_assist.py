"""Advisory-only helpers for optional LLM probe suggestions."""

from __future__ import annotations

from typing import Any


def suggest_probes(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Return advisory suggestions only; execution stays deterministic."""
    _ = context
    return []


def filter_suggestions(
    suggestions: list[dict[str, Any]],
    allowed_probe_kinds: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    adopted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for suggestion in suggestions:
        if suggestion.get("kind") in allowed_probe_kinds:
            adopted.append(suggestion)
        else:
            rejected.append(suggestion)

    return adopted, rejected
