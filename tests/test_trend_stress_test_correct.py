"""Tests pro scripts.trend_stress_test_correct."""
from __future__ import annotations

from scripts.trend_stress_test_correct import (
    project, classify, BASELINE_BUFFER_PTS, THRESHOLD_PESSIMISTIC,
)


class TestProjection:
    def test_baseline_no_change(self):
        r = project(3.28, 1.0)
        assert r["delta_buffer"] == 0.0
        assert r["projected_exp_pts"] == 3.28
        assert r["buffer"] == BASELINE_BUFFER_PTS

    def test_mild_1_5x(self):
        r = project(3.28, 1.5)
        # delta = 3.5 × 0.5 = 1.75
        assert r["delta_buffer"] == 1.75
        assert abs(r["projected_exp_pts"] - 1.53) < 1e-6
        assert r["buffer"] == 5.25

    def test_pessimistic_2x(self):
        r = project(3.28, 2.0)
        # delta = 3.5 × 1.0 = 3.5; projected = 3.28 - 3.5 = -0.22
        assert r["delta_buffer"] == 3.5
        assert abs(r["projected_exp_pts"] - (-0.22)) < 1e-6

    def test_extreme_3x(self):
        r = project(3.28, 3.0)
        # delta = 7.0; projected = 3.28 - 7.0 = -3.72
        assert r["delta_buffer"] == 7.0
        assert abs(r["projected_exp_pts"] - (-3.72)) < 1e-6


class TestClassify:
    def test_drop_when_pessimistic_below_05(self):
        scenarios = [
            {"label": "baseline", "multiplier": 1.0, "projected_exp_pts": 3.28,
             "buffer": 3.5, "delta_buffer": 0.0},
            {"label": "mild_x1.5", "multiplier": 1.5, "projected_exp_pts": 1.53,
             "buffer": 5.25, "delta_buffer": 1.75},
            {"label": "pessimistic_x2.0", "multiplier": 2.0, "projected_exp_pts": -0.22,
             "buffer": 7.0, "delta_buffer": 3.5},
            {"label": "extreme_x3.0", "multiplier": 3.0, "projected_exp_pts": -3.72,
             "buffer": 10.5, "delta_buffer": 7.0},
        ]
        v = classify(scenarios)
        assert v["verdict"] == "DROP US-MOM TREND"

    def test_keep_when_pessimistic_above_threshold(self):
        # Strong baseline + small pessimistic delta
        scenarios = [
            {"multiplier": 1.0, "projected_exp_pts": 5.0, "buffer": 0,
             "delta_buffer": 0, "label": "baseline"},
            {"multiplier": 1.5, "projected_exp_pts": 4.5, "buffer": 0,
             "delta_buffer": 0, "label": "mild"},
            {"multiplier": 2.0, "projected_exp_pts": 2.0, "buffer": 0,
             "delta_buffer": 0, "label": "pessimistic"},
            {"multiplier": 3.0, "projected_exp_pts": -1.0, "buffer": 0,
             "delta_buffer": 0, "label": "extreme"},
        ]
        v = classify(scenarios)
        assert "KEEP" in v["verdict"]

    def test_keep_with_warning_borderline(self):
        # Pessimistic exactly above threshold but within +1 band
        scenarios = [
            {"multiplier": 1.0, "projected_exp_pts": 1.5, "buffer": 0,
             "delta_buffer": 0, "label": "baseline"},
            {"multiplier": 2.0, "projected_exp_pts": 0.6, "buffer": 0,
             "delta_buffer": 0, "label": "pessimistic"},
        ]
        v = classify(scenarios)
        assert v["verdict"] == "KEEP with WARNING"

    def test_threshold_constant(self):
        assert THRESHOLD_PESSIMISTIC == 0.5
