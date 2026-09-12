"""Download the Home Credit Default Risk dataset from Kaggle.

Kaggle competition data can't be redistributed, so this repo ships this
script instead of the raw CSVs (see 0.7 in the execution tracker). Run it
once, locally, after setting up your Kaggle API credentials:

    1. Create an API token at https://www.kaggle.com/settings -> "Create New Token".
       This downloads kaggle.json.
    2. Place it at ~/.kaggle/kaggle.json (chmod 600 on Linux/Mac).
    3. Accept the competition rules at
       https://www.kaggle.com/c/home-credit-default-risk/rules
       (Kaggle refuses the API download otherwise.)
    4. Run: poetry run python -m src.data.download_home_credit

This only fetches application_train.csv, application_test.csv, and
HomeCredit_columns_description.csv — not the six auxiliary tables, which
are out of scope (see non-goals in the README).
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

COMPETITION = "home-credit-default-risk"
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
WANTED_FILES = {
    "application_train.csv",
    "application_test.csv",
    "HomeCredit_columns_description.csv",
}


def download() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    archive = DATA_DIR / f"{COMPETITION}.zip"

    print(f"Downloading {COMPETITION} via the Kaggle API into {DATA_DIR} ...")
    result = subprocess.run(
        [
            "kaggle",
            "competitions",
            "download",
            "-c",
            COMPETITION,
            "-p",
            str(DATA_DIR),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(
            "Kaggle download failed. Check that ~/.kaggle/kaggle.json exists "
            "and that you've accepted the competition rules on kaggle.com."
        )

    print("Extracting requested files ...")
    with zipfile.ZipFile(archive) as zf:
        members = [m for m in zf.namelist() if Path(m).name in WANTED_FILES]
        if not members:
            raise SystemExit(
                f"None of {WANTED_FILES} found in the downloaded archive — "
                "Kaggle may have changed the file layout."
            )
        zf.extractall(DATA_DIR, members=members)

    archive.unlink(missing_ok=True)
    print(f"Done. Files in {DATA_DIR}:")
    for f in sorted(DATA_DIR.iterdir()):
        print(f"  {f.name}")


if __name__ == "__main__":
    download()
