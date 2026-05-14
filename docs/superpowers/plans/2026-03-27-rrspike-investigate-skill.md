# rrspike Investigate Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a true agent-driven investigation skill where the agent reaches target instruction entry and interactively explores forward/reverse execution with rr/gdb evidence.

**Architecture:** Introduce a small investigation backend that can generate gdb command scripts and parse textual evidence logs, then add a `rrspike investigate` CLI command and a skill guide that enforces observation-hypothesis-probe loops. Keep existing `goto` and `inspect-events` as helpers, not final reasoning.

**Tech Stack:** Python 3.11+, Typer CLI, pytest, rr/gdb process orchestration.

---

### Task 1: Investigation parser and report model

**Files:**
- Create: `src/rr_spike_rv_replay/investigate.py`
- Test: `tests/test_investigate.py`

- [ ] **Step 1: Write failing tests for parser and report extraction**
- [ ] **Step 2: Run tests to verify failure**
- [ ] **Step 3: Implement minimal parser for gdb evidence lines and report assembly**
- [ ] **Step 4: Run tests to verify pass**


### Task 2: CLI command for scenario-2 investigation

**Files:**
- Modify: `src/rr_spike_rv_replay/cli.py`
- Modify: `src/rr_spike_rv_replay/__init__.py`
- Test: `tests/test_cli_args.py`

- [ ] **Step 1: Add failing tests for `rrspike investigate` signature/options**
- [ ] **Step 2: Run tests to verify failure**
- [ ] **Step 3: Implement `investigate` command (entry reach + probe loop script + evidence output)**
- [ ] **Step 4: Run tests to verify pass**


### Task 3: Skill doc for agent-driven probing

**Files:**
- Create: `skills/rrspike-investigate.md`

- [ ] **Step 1: Write skill doc with required loop (observe -> hypothesize -> probe -> verify)**
- [ ] **Step 2: Include explicit rr/gdb command templates and evidence requirements**


### Task 4: Subagent validation runs

**Files:**
- Modify: `docs/PROJECT_GUIDE_CN.md`

- [ ] **Step 1: Run subagent query for CSR events using new skill workflow**
- [ ] **Step 2: Run subagent query for trap causality using new skill workflow**
- [ ] **Step 3: Capture friction and update docs with known caveats**


### Task 5: Final verification

**Files:**
- Test: `tests/test_investigate.py`
- Test: `tests/test_cli_args.py`

- [ ] **Step 1: Run targeted tests for new module and CLI changes**
- [ ] **Step 2: Run full suite `python3 -m pytest -q` and ensure no regressions**
