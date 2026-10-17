"""Unit test for the label-flip arithmetic (synthetic numbers)."""

import pytest

from src.data.corruption_candidates_facts import label_flip_table


def test_label_flip_table():
    t = label_flip_table(1000, 100)
    assert t["positives"].tolist() == pytest.approx([100, 90, 75, 50])
    assert t["default_rate_pct"].iloc[-1] == pytest.approx(5.0)
    assert t["ratio_0_to_1"].iloc[0] == pytest.approx(9.0)
