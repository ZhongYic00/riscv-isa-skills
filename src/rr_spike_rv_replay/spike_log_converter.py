"""Convert Spike commit logs into trace JSON records."""

from __future__ import annotations

import json
import re
from pathlib import Path

COMMIT_LINE_RE = re.compile(
    r"^core\s+(?P<hart>\d+):\s+0x(?P<pc>[0-9a-fA-F]+)\s+\(0x(?P<binary>[0-9a-fA-F]+)\)\s+(?P<text>.+?)\s*$"
)


def parse_spike_commit_log_lines(lines: list[str]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    index = 1
    for line in lines:
        match = COMMIT_LINE_RE.match(line)
        if not match:
            continue
        records.append(
            {
                "index": index,
                "pc": f"0x{match.group('pc').lower()}",
                "binary": f"0x{match.group('binary').lower()}",
                "text": match.group("text").strip(),
                "hart_id": int(match.group("hart")),
            }
        )
        index += 1
    return records


def convert_spike_commit_log_to_trace_json(log_path: str | Path, out_path: str | Path) -> int:
    log_lines = Path(log_path).read_text(encoding="utf-8", errors="ignore").splitlines()
    records = parse_spike_commit_log_lines(log_lines)
    payload = {
        "format": "spike-commit-log-v1",
        "instructions": records,
    }
    Path(out_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return len(records)
