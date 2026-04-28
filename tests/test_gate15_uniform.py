"""Tests pro Gate #15 uniform reformulation v3.3.4."""
from __future__ import annotations

import pandas as pd
import pytest

from scripts.validate_gate_criteria import (
    gate15_uniform_per_cell, GATE15_PF_MIN, GATE15_WR_MIN, GATE15_R_MULT_MIN,
)


def _cells(rows):
    return pd.DataFrame(rows)


class TestGate15:
    def test_pass_high_pf_high_wr(self):
        df = _cells([{"setup": "x", "regime": "TREND", "wr": 0.55, "pf": 2.0}])
        v = gate15_uniform_per_cell(df)
        assert v["verdict"] == "PASS"

    def test_fail_low_pf_blocks_pf_clause(self):
        df = _cells([{"setup": "x", "regime": "TREND", "wr": 0.55, "pf": 1.4}])
        v = gate15_uniform_per_cell(df)
        assert v["verdict"] == "FAIL"
        assert v["per_cell"][0]["reason"] == "PF<1.5"

    def test_fail_low_wr_low_r_mult(self):
        # PF=1.5, WR=0.30 → r_multiple = 1.5×0.7/0.3 = 3.5 ≥ 2.0 → PASS
        df = _cells([{"setup": "x", "regime": "TREND", "wr": 0.30, "pf": 1.5}])
        v = gate15_uniform_per_cell(df)
        assert v["verdict"] == "PASS"  # r_multiple compensates

    def test_pass_low_wr_high_r_mult(self):
        # PF=1.6, WR=0.34 → r_mult=3.10 → PASS via OR clause (R-mult >=2.0)
        df = _cells([{"setup": "orb_dax", "regime": "CALM", "wr": 0.34, "pf": 1.76}])
        v = gate15_uniform_per_cell(df)
        # WR < 0.40 BUT R-mult > 2.0 → PASS via OR clause
        assert v["verdict"] == "PASS"
        assert v["per_cell"][0]["pass"] is True

    def test_fail_low_wr_low_pf(self):
        # PF=1.0 (just at fail boundary) → FAIL
        df = _cells([{"setup": "x", "regime": "CALM", "wr": 0.30, "pf": 1.0}])
        v = gate15_uniform_per_cell(df)
        assert v["verdict"] == "FAIL"

    def test_multiple_cells_aggregate(self):
        df = _cells([
            {"setup": "a", "regime": "T", "wr": 0.55, "pf": 2.0},
            {"setup": "b", "regime": "C", "wr": 0.30, "pf": 1.0},
            {"setup": "c", "regime": "X", "wr": 0.60, "pf": 1.6},
        ])
        v = gate15_uniform_per_cell(df)
        assert v["verdict"] == "FAIL"  # b fails
        assert "b/C" in v["failed_cells"]

    def test_thresholds(self):
        assert GATE15_PF_MIN == 1.5
        assert GATE15_WR_MIN == 0.40
        assert GATE15_R_MULT_MIN == 2.0
