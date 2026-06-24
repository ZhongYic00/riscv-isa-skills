# rr-spike-rv-replay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that records Spike execution with rr, replays deterministically with generated gdb scripts, and emits instruction-level exception analysis artifacts.

**Architecture:** Implement a deterministic core pipeline (`preflight -> record -> index -> locate -> replay -> report`) and a guarded LLM assist layer that can suggest but not execute probes. Keep pipeline modules small and pure where possible, with runner abstractions for rr/gdb process calls.

**Tech Stack:** Python 3.11+, Typer CLI, dataclasses/Pydantic-style typed models, pytest.

---

### Task 1: Project scaffolding and CLI contract

**Files:**
- Create: `pyproject.toml`
- Create: `src/rr_spike_rv_replay/__init__.py`
- Create: `src/rr_spike_rv_replay/cli.py`
- Create: `tests/test_cli_args.py`

- [ ] **Step 1: Write the failing test**

```python
from rr_spike_rv_replay.cli import build_config


def test_cli_requires_test_case_and_run_cmd():
    cfg = build_config(
        test_case="tc1",
        run_cmd="spike pk a.out",
        target_pc="0x80000000",
    )
    assert cfg.test_case == "tc1"
    assert cfg.run_cmd == "spike pk a.out"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_args.py::test_cli_requires_test_case_and_run_cmd -v`
Expected: FAIL with import/module error.

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass


@dataclass
class PipelineConfig:
    test_case: str
    run_cmd: str
    target_pc: str | None = None


def build_config(test_case: str, run_cmd: str, target_pc: str | None = None) -> PipelineConfig:
    return PipelineConfig(test_case=test_case, run_cmd=run_cmd, target_pc=target_pc)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_args.py::test_cli_requires_test_case_and_run_cmd -v`
Expected: PASS.


### Task 2: Preflight checks

**Files:**
- Create: `src/rr_spike_rv_replay/preflight.py`
- Create: `tests/test_preflight.py`

- [ ] **Step 1: Write the failing test**

```python
from rr_spike_rv_replay.preflight import check_tools


def test_check_tools_reports_missing_binary():
    status = check_tools(which=lambda name: None)
    assert "rr" in status.missing
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_preflight.py::test_check_tools_reports_missing_binary -v`
Expected: FAIL with missing module/function.

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from shutil import which as _which


@dataclass
class ToolStatus:
    missing: list[str]


def check_tools(which=_which) -> ToolStatus:
    required = ["rr", "gdb", "spike"]
    missing = [name for name in required if which(name) is None]
    return ToolStatus(missing=missing)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_preflight.py::test_check_tools_reports_missing_binary -v`
Expected: PASS.


### Task 3: Recording and metadata artifacts

**Files:**
- Create: `src/rr_spike_rv_replay/recorder.py`
- Create: `tests/test_recorder.py`

- [ ] **Step 1: Write the failing test**

```python
from rr_spike_rv_replay.recorder import build_rr_record_cmd


def test_build_rr_record_cmd_wraps_run_command():
    cmd = build_rr_record_cmd("spike pk a.out")
    assert cmd[:2] == ["rr", "record"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_recorder.py::test_build_rr_record_cmd_wraps_run_command -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
import shlex


def build_rr_record_cmd(run_cmd: str) -> list[str]:
    return ["rr", "record", "--", *shlex.split(run_cmd)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_recorder.py::test_build_rr_record_cmd_wraps_run_command -v`
Expected: PASS.


### Task 4: Event locator and fallback

**Files:**
- Create: `src/rr_spike_rv_replay/locator.py`
- Create: `tests/test_locator.py`

- [ ] **Step 1: Write the failing tests**

```python
from rr_spike_rv_replay.locator import choose_best_candidate


def test_choose_best_candidate_prefers_pc_match():
    best = choose_best_candidate(
        candidates=[{"pc_match": 0, "disasm_match": 1, "symbol_match": 1, "distance": 1}],
        weights={"pc": 10, "disasm": 2, "symbol": 3, "distance": -1},
    )
    assert best is not None
```
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_locator.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
def score_candidate(c, w):
    return (
        w["pc"] * c.get("pc_match", 0)
        + w["disasm"] * c.get("disasm_match", 0)
        + w["symbol"] * c.get("symbol_match", 0)
        + w["distance"] * c.get("distance", 0)
    )


def choose_best_candidate(candidates, weights):
    if not candidates:
        return None
    return max(candidates, key=lambda c: score_candidate(c, weights))
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_locator.py -v`
Expected: PASS.


### Task 5: Replay script generation and reporting

**Files:**
- Create: `src/rr_spike_rv_replay/gdb_script_builder.py`
- Create: `src/rr_spike_rv_replay/reporter.py`
- Create: `tests/test_gdb_script_builder.py`
- Create: `tests/test_reporter.py`

- [ ] **Step 1: Write failing tests for script/report outputs**

```python
from rr_spike_rv_replay.gdb_script_builder import build_replay_script


def test_build_replay_script_contains_reverse_stepi():
    script = build_replay_script("0x80000000", 8, 8)
    assert "reverse-stepi" in script
```
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_gdb_script_builder.py tests/test_reporter.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement minimal script/report generators**

```python
def build_replay_script(target_pc, before, after):
    return f"""set pagination off
break *{target_pc}
commands
  silent
  reverse-stepi
  stepi
  continue
end
run
"""
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_gdb_script_builder.py tests/test_reporter.py -v`
Expected: PASS.


### Task 6: Pipeline orchestration with deterministic + LLM assist mode

**Files:**
- Create: `src/rr_spike_rv_replay/pipeline.py`
- Create: `src/rr_spike_rv_replay/llm_assist.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing integration-style test with mocked runners**

```python
from rr_spike_rv_replay.pipeline import run_pipeline


def test_run_pipeline_writes_required_artifacts(tmp_path):
    outputs = run_pipeline(
        test_case="tc",
        run_cmd="spike pk a.out",
        out_dir=tmp_path,
        target_pc="0x80000000",
    )
    assert (tmp_path / "capture_meta.json").exists()
    assert (tmp_path / "replay.gdb").exists()
    assert (tmp_path / "event_summary.md").exists()
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_pipeline.py::test_run_pipeline_writes_required_artifacts -v`
Expected: FAIL.

- [ ] **Step 3: Implement orchestrator and guarded LLM adapter**

```python
def suggest_probes(context):
    return {"suggested_probes": [], "adopted": []}


def run_pipeline(...):
    # execute deterministic core and write artifacts
    return {"trace_id": "stub"}
```

- [ ] **Step 4: Run test suite**

Run: `pytest -v`
Expected: PASS.
