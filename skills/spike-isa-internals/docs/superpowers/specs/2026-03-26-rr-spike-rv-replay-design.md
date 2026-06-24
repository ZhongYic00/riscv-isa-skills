# rr-spike-rv-replay Design

## Goal

Capture Spike test-case execution with `rr`, then replay deterministically to inspect a target RISC-V instruction and explain exception behavior with concrete evidence (PC, disassembly, register and memory deltas).

## Non-Goals

- Replacing Spike or rr internals
- Full ISA formal verification
- Letting LLM make direct execution decisions

## Architecture

Single CLI entry with two internal stages:

1. `capture/index`: preflight checks, `rr record`, trace metadata extraction, event indexing
2. `replay/analyze`: generate `replay.gdb`, run `rr replay`, collect observations, render report

### Components

- `preflight`: validates rr/gdb/spike availability and runtime prerequisites
- `recorder`: runs `rr record -- <spike cmd>` and emits capture metadata
- `indexer`: builds candidate events around exception anchor points
- `locator`: deterministic rule engine that scores candidate instruction locations
- `gdb_script_builder`: emits reproducible replay script
- `replayer`: executes replay and captures structured observations
- `reporter`: writes markdown and machine-readable summaries
- `llm_assist`: proposes hypotheses and probes, never directly executes actions

## Data Contracts

### Input

- `test_case` (required)
- `run_cmd` (required): complete Spike invocation template
- Target selector (at least one): `target_pc`, `rv_instr_pattern`, `symbol_offset`
- `stop_policy`: `first-hit` or `nth-hit`
- `window_before`, `window_after`
- `exception_filter`
- `llm_mode`: `off` or `assist`

### Output Artifacts

- `capture_meta.json`
- `replay.gdb`
- `event_summary.md`
- `analysis_trace.json`
- `index_snapshot.json`

## Matching and Fallback

1. Prefer exception anchor events
2. Reverse-trace inside configured window
3. Score candidate hits by `pc`, `disasm`, `symbol`, `distance_to_exception`
4. If symbol missing, degrade to `pc + disasm`
5. If target miss, emit top-K nearest observable points and rerun hints

## LLM Coupling Policy

- LLM output is advisory only
- Rule engine validates every suggested probe
- Executed probe set is deterministic and auditable
- `analysis_trace.json` records prompts, model metadata, suggestions, and adopted actions

## Testing Strategy

- Unit tests for argument parsing, scoring logic, fallback behavior
- Snapshot tests for generated `replay.gdb`
- Integration tests with mocked rr/gdb runners for full pipeline
- Determinism tests: same input trace yields same selected events

## Risks and Mitigations

- rr environment incompatibility: fail early with actionable preflight errors
- Ambiguous instruction pattern: require explicit selector precedence
- Large traces: incremental index extraction and bounded window scanning
- LLM hallucination: enforce schema + deterministic policy guard
