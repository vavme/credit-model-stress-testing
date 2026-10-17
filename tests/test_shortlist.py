"""Unit tests for the shortlist consistency check (synthetic names only)."""

from src.data.shortlist import CORE, EXCLUDE, OPTIONS, PENDING, validate


def test_validate_flags_bad_count_overlap_and_gaps():
    cols = [f"c{i}" for i in range(60)]
    assert validate(cols[:30], [], [], cols[30:], cols) == []
    assert any("outside" in p for p in validate(cols[:5], [], [], cols[5:], cols))
    assert any("overlap" in p for p in validate(cols[:30], [], [cols[0]], cols[30:], cols))
    assert any("not covered" in p for p in validate(cols[:30], [], [], cols[31:], cols))


def test_curated_lists_do_not_overlap_and_size_is_in_range():
    names = [c for c, _ in CORE] + [c for c, _ in PENDING]
    assert 25 <= len(names) <= 40
    assert len(set(names)) == len(names)
    assert not set(names) & (set(OPTIONS) | set(EXCLUDE))
    assert not set(OPTIONS) & set(EXCLUDE)
