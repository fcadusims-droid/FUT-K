"""Public benchmark data (product level 11).

The validated, reproducible numbers from `validation/` served as an API payload
so the app (and any consumer) can show them. Each entry cites the report and
the exact command that reproduces it — the numbers are never edited by hand
here without re-running the pipeline.
"""

BENCHMARKS = [
    {
        "dataset": "La Liga 2015/16",
        "matches": 380,
        "target": "goal in next 10 min (in-play)",
        "brier": 0.1951,
        "log_loss": 0.5789,
        "calibration_gap": 0.009,
        "note": "untuned prior already right at scale; ties the constant baseline",
        "source": "validation/results/RESULTS_FIT_LALIGA.md",
        "reproduce": "python scripts/fit_statsbomb.py --competition 11 --season 27 --limit 380 --folds 5",
    },
    {
        "dataset": "World Cup 2018",
        "matches": 64,
        "target": "goal in next 10 min (in-play)",
        "brier": 0.1796,
        "log_loss": 0.5449,
        "calibration_gap": 0.025,
        "note": "walk-forward fitting closed the gap 0.040 → 0.025",
        "source": "validation/results/RESULTS_FIT.md",
        "reproduce": "python scripts/fit_statsbomb.py --competition 43 --season 3 --limit 64 --folds 4",
    },
    {
        "dataset": "La Liga 2015/16 (1X2 vs market)",
        "matches": 320,
        "target": "match outcome (H/D/A)",
        "brier": 0.5802,
        "log_loss": 0.9758,
        "calibration_gap": None,
        "note": "engine Poisson beats Elo (0.9758 vs 1.0073); market ceiling 0.9164",
        "source": "validation/results/RESULTS_BENCHMARK.md",
        "reproduce": "python scripts/benchmark_external.py",
    },
    {
        "dataset": "La Liga 2015/16 (corners)",
        "matches": 380,
        "target": "corner in next 10 min",
        "brier": 0.2246,
        "log_loss": 0.6414,
        "calibration_gap": None,
        "note": "constant train-fit rate; naive pressure-scaling rejected",
        "source": "validation/results/RESULTS_TARGETS.md",
        "reproduce": "python scripts/fit_targets_statsbomb.py",
    },
    {
        "dataset": "Champions League finals 1971–2019",
        "matches": 18,
        "target": "competition fit (goals/90)",
        "brier": None,
        "log_loss": None,
        "calibration_gap": None,
        "note": "2.70 goals/90 vs 2.28 (La Liga); own params beat cross-applied ones",
        "source": "validation/results/RESULTS_COMPARE.md",
        "reproduce": "python scripts/compare_competitions.py",
    },
]
