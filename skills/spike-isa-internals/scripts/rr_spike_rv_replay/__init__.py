"""Core package for rr_spike_rv_replay."""

from rr_spike_rv_replay.cli import PipelineConfig, build_config
from rr_spike_rv_replay.gdb_script_builder import build_gdb_script
from rr_spike_rv_replay.goto_entry import (
    build_spike_log_command,
    default_instruction_budget,
    goto_instruction_entry,
    render_gdb_entry_script,
    resolve_target_pc_from_trace,
)
from rr_spike_rv_replay.isa_events import classify_isa_event, extract_isa_events
from rr_spike_rv_replay.investigate import parse_evidence_lines, render_probe_gdb_script, run_investigation
from rr_spike_rv_replay.llm_assist import filter_suggestions, suggest_probes
from rr_spike_rv_replay.locator import Candidate, ScoreWeights, score_candidate, select_best_and_fallback
from rr_spike_rv_replay.pipeline import run_pipeline
from rr_spike_rv_replay.preflight import PreflightReport, find_missing_tools, preflight_report
from rr_spike_rv_replay.recorder import build_rr_record_command, run_rr_record
from rr_spike_rv_replay.replayer import build_rr_replay_command, run_rr_replay
from rr_spike_rv_replay.reporter import write_event_summary, write_json_artifact
from rr_spike_rv_replay.spike_log_converter import convert_spike_commit_log_to_trace_json, parse_spike_commit_log_lines
from rr_spike_rv_replay.trace_bridge import TraceRecord, parse_trace_file, resolve_target_from_trace

__all__ = [
    "Candidate",
    "PipelineConfig",
    "PreflightReport",
    "ScoreWeights",
    "TraceRecord",
    "build_config",
    "build_gdb_script",
    "build_spike_log_command",
    "build_rr_record_command",
    "build_rr_replay_command",
    "default_instruction_budget",
    "filter_suggestions",
    "find_missing_tools",
    "classify_isa_event",
    "extract_isa_events",
    "convert_spike_commit_log_to_trace_json",
    "parse_spike_commit_log_lines",
    "preflight_report",
    "goto_instruction_entry",
    "parse_evidence_lines",
    "render_probe_gdb_script",
    "run_investigation",
    "render_gdb_entry_script",
    "resolve_target_pc_from_trace",
    "run_pipeline",
    "run_rr_record",
    "run_rr_replay",
    "parse_trace_file",
    "resolve_target_from_trace",
    "score_candidate",
    "select_best_and_fallback",
    "suggest_probes",
    "write_event_summary",
    "write_json_artifact",
]
