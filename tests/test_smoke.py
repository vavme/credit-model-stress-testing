"""Structural smoke test — confirms the package layout actually imports.

This is not the Phase 3.6 pipeline smoke test (that runs the real
WOE/LR baseline end-to-end once real code exists). This one just catches
a broken scaffold before you've written anything worth testing yet.
"""

import importlib


MODULES = [
    "src",
    "src.data",
    "src.features",
    "src.corruption",
    "src.models",
    "src.eval",
    "src.explain",
]


def test_all_modules_import():
    for name in MODULES:
        importlib.import_module(name)


def test_seed_is_42():
    from src.data.split import SEED

    assert SEED == 42
