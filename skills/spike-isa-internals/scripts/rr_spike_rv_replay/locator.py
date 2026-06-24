"""Candidate scoring and selection utilities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreWeights:
    pc: float = 0.45
    disasm: float = 0.3
    symbol: float = 0.2
    distance: float = 0.05


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    pc_match: float
    disasm_match: float
    symbol_match: float
    distance: int
    observable: bool


def score_candidate(candidate: Candidate, weights: ScoreWeights = ScoreWeights()) -> float:
    distance_score = 1.0 / (1 + max(candidate.distance, 0))
    return (
        candidate.pc_match * weights.pc
        + candidate.disasm_match * weights.disasm
        + candidate.symbol_match * weights.symbol
        + distance_score * weights.distance
    )


def select_best_and_fallback(
    candidates: list[Candidate],
    weights: ScoreWeights = ScoreWeights(),
) -> tuple[Candidate | None, list[Candidate]]:
    if not candidates:
        return None, []

    ranked = sorted(
        candidates,
        key=lambda c: (score_candidate(c, weights), -c.distance),
        reverse=True,
    )
    best = ranked[0]

    fallback = sorted(
        [candidate for candidate in candidates if candidate.observable],
        key=lambda c: c.distance,
    )
    return best, fallback
