import json

from rr_spike_rv_replay.reporter import write_event_summary, write_json_artifact


def test_write_event_summary_creates_markdown_file(tmp_path) -> None:
    event = {
        "event_id": "evt-1",
        "best_candidate": "cand-7",
        "fallback_candidates": ["cand-3", "cand-9"],
    }

    output_file = write_event_summary(tmp_path, event)

    assert output_file.name == "event_summary.md"
    body = output_file.read_text(encoding="utf-8")
    assert "# Event Summary" in body
    assert "- Event ID: evt-1" in body
    assert "- Best Candidate: cand-7" in body
    assert "- Fallback Candidates: cand-3, cand-9" in body


def test_write_json_artifact_writes_sorted_json(tmp_path) -> None:
    payload = {"z": 2, "a": 1}

    output_file = write_json_artifact(tmp_path, "scores.json", payload)

    assert output_file.name == "scores.json"
    loaded = json.loads(output_file.read_text(encoding="utf-8"))
    assert loaded == payload
    assert output_file.read_text(encoding="utf-8").splitlines()[1].startswith('  "a"')
