import json

from rr_spike_rv_replay.spike_log_converter import (
    convert_spike_commit_log_to_trace_json,
    parse_spike_commit_log_lines,
)


def test_parse_spike_commit_log_lines_extracts_records() -> None:
    lines = [
        "core   0: 0x0000000080000000 (0x00100293) addi t0,zero,1",
        "core   0: >>>> init",
        "core   1: 0x0000000080000004 (0x00200313) addi t1,zero,2",
    ]

    records = parse_spike_commit_log_lines(lines)

    assert records == [
        {
            "index": 1,
            "pc": "0x0000000080000000",
            "binary": "0x00100293",
            "text": "addi t0,zero,1",
            "hart_id": 0,
        },
        {
            "index": 2,
            "pc": "0x0000000080000004",
            "binary": "0x00200313",
            "text": "addi t1,zero,2",
            "hart_id": 1,
        },
    ]


def test_convert_spike_commit_log_to_trace_json_writes_standard_payload(tmp_path) -> None:
    log_path = tmp_path / "spike.log"
    out_path = tmp_path / "trace.json"
    log_path.write_text(
        "core   0: 0x0000000080000000 (0x00100293) addi t0,zero,1\n",
        encoding="utf-8",
    )

    count = convert_spike_commit_log_to_trace_json(log_path, out_path)

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert count == 1
    assert payload["format"] == "spike-commit-log-v1"
    assert payload["instructions"][0]["index"] == 1
