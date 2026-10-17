"""Run every Phase 1 EDA step in order, so each number can be rebuilt from a clean checkout.

    python -m poetry run python -m src.data.run_eda

Needs data/raw/application_train.csv and data/raw/HomeCredit_columns_description.csv
(see src/data/download_home_credit.py). Step 1 re-derives the seeded 60/20/20 split in memory
and checks it against data/processed/train.csv; run src.data.split first if that file is missing.
Every later step reads data/processed/train.csv only. Outputs go to data/interim/ and reports/eda/.
"""

from __future__ import annotations

import importlib
import time

# (module, function) in dependency order: later steps read CSVs written by earlier ones.
STEPS: list[tuple[str, str]] = [
    ("src.data.integrity", "run"),  # Section 1
    ("src.data.section2_facts", "main"),  # Section 2
    ("src.data.feature_catalog", "main"),  # Section 3
    ("src.data.target_balance", "main"),  # Section 4
    ("src.data.missingness_baseline", "main"),  # Section 5
    ("src.data.eda_section6", "main"),  # Section 6
    ("src.data.shortlist", "main"),  # Section 7 (proposal)
    ("src.data.corruption_candidates_facts", "main"),  # Section 8
]


def main() -> None:
    for module, func in STEPS:
        start = time.time()
        getattr(importlib.import_module(module), func)()
        print(f"\n--- finished {module}.{func} in {time.time() - start:.0f}s ---\n")


if __name__ == "__main__":
    main()
