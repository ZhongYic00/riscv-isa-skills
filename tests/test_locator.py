from rr_spike_rv_replay.locator import Candidate, ScoreWeights, score_candidate, select_best_and_fallback


def test_score_candidate_uses_weighted_components() -> None:
    candidate = Candidate(
        candidate_id="A",
        pc_match=1.0,
        disasm_match=0.5,
        symbol_match=0.25,
        distance=1,
        observable=True,
    )
    weights = ScoreWeights(pc=0.4, disasm=0.3, symbol=0.2, distance=0.1)

    score = score_candidate(candidate, weights)

    # distance factor is 1 / (1 + distance) -> 0.5
    assert score == 0.4 + 0.15 + 0.05 + 0.05


def test_select_best_and_fallback_prefers_highest_score_and_nearest_observable() -> None:
    candidates = [
        Candidate("best-unobservable", 0.9, 0.9, 0.9, 0, observable=False),
        Candidate("obs-near", 0.8, 0.7, 0.6, 1, observable=True),
        Candidate("obs-far", 0.8, 0.9, 0.6, 7, observable=True),
    ]

    best, fallback = select_best_and_fallback(candidates)

    assert best.candidate_id == "best-unobservable"
    assert [item.candidate_id for item in fallback] == ["obs-near", "obs-far"]
