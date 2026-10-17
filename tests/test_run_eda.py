"""Every step in the run-all script must exist and be callable (no data needed)."""

import importlib

from src.data.run_eda import STEPS


def test_all_steps_importable_and_callable():
    for module, func in STEPS:
        assert callable(getattr(importlib.import_module(module), func)), (module, func)
