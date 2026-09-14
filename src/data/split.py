"""Carve the single stratified 60/20/20 train/val/test split (tracker 1.2/1.3).

Reads data/raw/application_train.csv, stratifies on TARGET, and writes
data/processed/{train,val,test}.csv. Seed is fixed at 42 (0.10). This split
is carved once — the test slice stays untouched until Phase 5 (0.4).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

SEED = 42

RAW_PATH = Path(__file__).resolve().parents[2] / "data" / "raw" / "application_train.csv"
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

TRAIN_FRAC = 0.6
VAL_FRAC = 0.2
TEST_FRAC = 0.2


def make_split(
    df: pd.DataFrame, seed: int = SEED
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Stratified 60/20/20 split on TARGET. Pure — no I/O, no side effects."""
    train_df, temp_df = train_test_split(
        df,
        train_size=TRAIN_FRAC,
        stratify=df["TARGET"],
        random_state=seed,
    )
    val_df, test_df = train_test_split(
        temp_df,
        train_size=VAL_FRAC / (VAL_FRAC + TEST_FRAC),
        stratify=temp_df["TARGET"],
        random_state=seed,
    )
    return train_df, val_df, test_df


def summarize(name: str, split_df: pd.DataFrame, total_rows: int) -> str:
    n = len(split_df)
    rate = split_df["TARGET"].mean()
    return (
        f"{name:>5}: {n:>7,} rows ({n / total_rows:.1%})  "
        f"default rate = {rate:.4%}  positives = {int(split_df['TARGET'].sum()):,}"
    )


def run() -> None:
    df = pd.read_csv(RAW_PATH)
    train_df, val_df, test_df = make_split(df)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(PROCESSED_DIR / "train.csv", index=False)
    val_df.to_csv(PROCESSED_DIR / "val.csv", index=False)
    test_df.to_csv(PROCESSED_DIR / "test.csv", index=False)

    total = len(df)
    print(f"Source: {RAW_PATH} ({total:,} rows)")
    print(f"Overall default rate: {df['TARGET'].mean():.4%}")
    print(summarize("train", train_df, total))
    print(summarize("val", val_df, total))
    print(summarize("test", test_df, total))
    print(f"Written to {PROCESSED_DIR}")


if __name__ == "__main__":
    run()
