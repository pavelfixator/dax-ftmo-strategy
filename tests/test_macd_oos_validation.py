"""Tests pro scripts.macd_oos_validation classify()."""
from __future__ import annotations

from scripts.macd_oos_validation import classify, PASS_RATIO, MARGINAL_RATIO


class TestClassify:
    def test_pass_when_ratio_above_07(self):
        train = {"expectancy": 10.0, "n_trades": 100, "wr": 0.5}
        test = {"expectancy": 8.0, "n_trades": 30, "wr": 0.5}
        v = classify(train, test)
        assert v["verdict"] == "PASS"
        assert v["ratio"] == 0.8

    def test_marginal_in_05_07_band(self):
        train = {"expectancy": 10.0, "n_trades": 100, "wr": 0.5}
        test = {"expectancy": 6.0, "n_trades": 30, "wr": 0.5}
        v = classify(train, test)
        assert v["verdict"] == "MARGINAL"

    def test_fail_below_05(self):
        train = {"expectancy": 10.0, "n_trades": 100, "wr": 0.5}
        test = {"expectancy": 4.0, "n_trades": 30, "wr": 0.5}
        v = classify(train, test)
        assert v["verdict"] == "FAIL"

    def test_fail_when_train_negative(self):
        train = {"expectancy": -5.0, "n_trades": 100, "wr": 0.4}
        test = {"expectancy": 5.0, "n_trades": 30, "wr": 0.5}
        v = classify(train, test)
        assert v["verdict"] == "FAIL"
        assert "train expectancy <= 0" in v["reason"]

    def test_fail_when_test_negative(self):
        train = {"expectancy": 10.0, "n_trades": 100, "wr": 0.5}
        test = {"expectancy": -2.0, "n_trades": 30, "wr": 0.5}
        v = classify(train, test)
        assert v["verdict"] == "FAIL"

    def test_thresholds(self):
        assert PASS_RATIO == 0.7
        assert MARGINAL_RATIO == 0.5
