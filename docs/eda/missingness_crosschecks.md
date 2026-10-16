# Missingness cross-checks (train split only)

Rows: 184,506. Computed from `data/processed/train.csv` by `src/data/missingness_crosschecks.py`. Numbers only; no interpretation.

## OWN_CAR_AGE missing, by FLAG_OWN_CAR

| FLAG_OWN_CAR | rows | missing_count | missing_pct |
|---|---|---|---|
| N | 121,848 | 121,848 | 100.00 |
| Y | 62,658 | 5 | 0.01 |

## OCCUPATION_TYPE missing, by NAME_INCOME_TYPE

| NAME_INCOME_TYPE | rows | missing_count | missing_pct |
|---|---|---|---|
| Unemployed | 15 | 15 | 100.00 |
| Pensioner | 33,218 | 33,215 | 99.99 |
| Maternity leave | 2 | 1 | 50.00 |
| Student | 8 | 2 | 25.00 |
| Commercial associate | 42,989 | 7,420 | 17.26 |
| State servant | 13,127 | 2,244 | 17.09 |
| Working | 95,140 | 14,994 | 15.76 |
| Businessman | 7 | 1 | 14.29 |

## EXT_SOURCE_1 / EXT_SOURCE_3 missing, by TARGET (0 = repaid, 1 = default)

| column | TARGET | rows | missing_count | missing_pct |
|---|---|---|---|---|
| EXT_SOURCE_1 | 0 | 169,611 | 95,171 | 56.11 |
| EXT_SOURCE_1 | 1 | 14,895 | 8,872 | 59.56 |
| EXT_SOURCE_3 | 0 | 169,611 | 33,142 | 19.54 |
| EXT_SOURCE_3 | 1 | 14,895 | 3,418 | 22.95 |
