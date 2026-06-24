"""Reporting helpers for replay artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_event_summary(output_dir: str | Path, event: dict[str, Any]) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    event_id = event.get("event_id", "unknown")
    best_candidate = event.get("best_candidate", "unknown")
    fallback = event.get("fallback_candidates", [])
    fallback_text = ", ".join(str(item) for item in fallback)

    body = "\n".join(
        [
            "# Event Summary",
            "",
            f"- Event ID: {event_id}",
            f"- Best Candidate: {best_candidate}",
            f"- Fallback Candidates: {fallback_text}",
            "",
        ]
    )
    summary_path = output_path / "event_summary.md"
    summary_path.write_text(body, encoding="utf-8")
    return summary_path


def write_json_artifact(output_dir: str | Path, filename: str, payload: dict[str, Any]) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    artifact_path = output_path / filename
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact_path
