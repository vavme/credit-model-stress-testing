# Missingness summary (train split only)

Rows: 184,506. Columns: 122.
Computed from `data/processed/train.csv` by `src/data/missingness.py`. Numbers only; no judgement about which columns matter (that is 1.5).

## Columns by missingness

| Threshold | Columns |
|---|---|
| > 50% missing | 41 |
| > 30% missing | 50 |
| > 10% missing | 57 |
| any missing | 67 |

## By column family (grouped by column name only)

| Family | Columns | Any missing | > 10% | > 30% | > 50% |
|---|---|---|---|---|---|
| building/housing attributes (_AVG/_MODE/_MEDI) | 47 | 47 | 47 | 47 | 39 |
| other (ungrouped) | 42 | 7 | 2 | 2 | 1 |
| AMT_REQ_CREDIT_BUREAU_* | 6 | 6 | 6 | 0 | 0 |
| *_SOCIAL_CIRCLE | 4 | 4 | 0 | 0 | 0 |
| EXT_SOURCE_* | 3 | 3 | 2 | 1 | 1 |
| FLAG_DOCUMENT_* | 20 | 0 | 0 | 0 | 0 |

## Ungrouped columns with any missing

| Column | Missing % |
|---|---|
| OWN_CAR_AGE | 66.04 |
| OCCUPATION_TYPE | 31.38 |
| NAME_TYPE_SUITE | 0.42 |
| AMT_GOODS_PRICE | 0.09 |
| AMT_ANNUITY | 0.00 |
| CNT_FAM_MEMBERS | 0.00 |
| DAYS_LAST_PHONE_CHANGE | 0.00 |
