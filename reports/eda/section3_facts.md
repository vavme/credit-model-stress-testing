# Section 3 facts (train split only)

## Group counts

| Group | Columns |
|---|---|
| ID and label | 2 |
| Loan terms | 4 |
| Client demographics | 8 |
| Income and employment | 5 |
| Assets | 3 |
| Building / housing attributes | 47 |
| External scores | 3 |
| Region and address consistency | 9 |
| Contact flags | 6 |
| Document flags | 20 |
| Social circle | 4 |
| Credit bureau enquiries | 6 |
| Application timing and history | 5 |
| **Total** | **122** (file has 122) |

## Semantic types

| Type | Columns |
|---|---|
| numeric continuous | 57 |
| binary flag | 36 |
| numeric count | 12 |
| nominal | 11 |
| ordinal | 4 |
| ID | 1 |
| target | 1 |

## Missingness headline (detail is Section 5)

- Columns with any missing value: 67 of 122
- Columns with more than 5% missing: 57; more than 50% missing: 41

## Description file coverage

- Train columns without an entry in the description file: none
- Description entries with no train column: none

## Quirk 1: DAYS_* columns

| Column | min | median | max | % negative | % positive | % zero |
|---|---|---|---|---|---|---|
| DAYS_BIRTH | -25,200 | -15,736 | -7,673 | 100.00% | 0.00% | 0.00% |
| DAYS_EMPLOYED | -17,583 | -1,212 | 365,243 | 81.99% | 18.01% | 0.00% |
| DAYS_REGISTRATION | -24,672 | -4,514 | 0 | 99.97% | 0.00% | 0.03% |
| DAYS_ID_PUBLISH | -6,551 | -3,263 | 0 | 100.00% | 0.00% | 0.00% |
| DAYS_LAST_PHONE_CHANGE | -4,292 | -761 | 0 | 87.90% | 0.00% | 12.10% |

## Quirk 2: DAYS_EMPLOYED placeholder

- Rows equal to 365243: 33,225 (18.01%). Other positive values: 0.
- Distinct values among positives: [365243]
- Median of DAYS_EMPLOYED without the placeholder: -1,648 days (min -17,583, max 0).
- Placeholder rows by NAME_INCOME_TYPE: {'Pensioner': 33210, 'Unemployed': 15}
- Placeholder rows with ORGANIZATION_TYPE = XNA: 33,225 of 33,225; XNA rows that are not placeholder: 0
- Default rate: placeholder rows 5.41% (n=33,225) vs other rows 8.66% (n=151,281).
- Pensioners with a real (non-placeholder) DAYS_EMPLOYED: 8 of 33,218

## Quirk 3: XNA and unknown-style labels in text columns

| Column | XNA rows | % | other odd labels |
|---|---|---|---|
| CODE_GENDER | 2 | 0.00% |  |
| NAME_FAMILY_STATUS | 0 | 0.00% | {'Unknown': 1} |
| ORGANIZATION_TYPE | 33,225 | 18.01% |  |
| FONDKAPREMONT_MODE | 0 | 0.00% | {'not specified': 3412} |

## Quirk 4: extreme values

| Column | p50 | p99 | p99.9 | max | max / median |
|---|---|---|---|---|---|
| AMT_INCOME_TOTAL | 148,500 | 472,500 | 900,000 | 117,000,000 | 787.9 |
| OBS_30_CNT_SOCIAL_CIRCLE | 0 | 10 | 17 | 348 | inf |
| DEF_30_CNT_SOCIAL_CIRCLE | 0 | 2 | 4 | 34 | inf |
| OBS_60_CNT_SOCIAL_CIRCLE | 0 | 10 | 16 | 344 | inf |
| DEF_60_CNT_SOCIAL_CIRCLE | 0 | 2 | 3 | 24 | inf |
| AMT_REQ_CREDIT_BUREAU_QRT | 0 | 2 | 4 | 19 | inf |
| CNT_CHILDREN | 0 | 3 | 4 | 19 | inf |
| AMT_CREDIT | 514,822 | 1,850,544 | 2,517,300 | 4,050,000 | 7.9 |

- AMT_INCOME_TOTAL rows above 1,000,000: 144; the largest 5 values: [117000000.0, 18000090.0, 9000000.0, 6750000.0, 4500000.0]

## Quirk 5: EXT_SOURCE_* (missingness and signal)

| Column | missing % | Pearson r with TARGET | rank by abs(r) of 104 numeric columns |
|---|---|---|---|
| EXT_SOURCE_1 | 56.39% | -0.1533 | 3 |
| EXT_SOURCE_2 | 0.22% | -0.1598 | 2 |
| EXT_SOURCE_3 | 19.82% | -0.1765 | 1 |

Default rate by EXT_SOURCE quintile (quintiles on non-missing rows; n per bin):

| Column | Q1 (lowest) | Q3 | Q5 (highest) | missing |
|---|---|---|---|---|
| EXT_SOURCE_1 | 14.31% (n=16,093) | 6.45% (n=16,093) | 3.00% (n=16,093) | 8.53% (n=104,043) |
| EXT_SOURCE_2 | 15.19% (n=36,819) | 7.02% (n=36,818) | 3.57% (n=36,818) | 8.23% (n=413) |
| EXT_SOURCE_3 | 16.20% (n=29,591) | 5.78% (n=29,644) | 3.40% (n=28,835) | 9.35% (n=36,560) |

Top 8 numeric columns by abs(Pearson r) with TARGET (pairwise complete):

- EXT_SOURCE_3: -0.1765
- EXT_SOURCE_2: -0.1598
- EXT_SOURCE_1: -0.1533
- DAYS_BIRTH: +0.0779
- REGION_RATING_CLIENT_W_CITY: +0.0621
- REGION_RATING_CLIENT: +0.0600
- DAYS_LAST_PHONE_CHANGE: +0.0530
- REG_CITY_NOT_WORK_CITY: +0.0512

## Quirk 6: building columns in AVG / MODE / MEDI flavours

- Stems with an _AVG and _MEDI column: 14. Building-group columns: 47.

| Stem | columns found | min corr among variants | identical missing mask |
|---|---|---|---|
| APARTMENTS | 3 | 0.973 | True |
| BASEMENTAREA | 3 | 0.974 | True |
| COMMONAREA | 3 | 0.976 | True |
| ELEVATORS | 3 | 0.979 | True |
| ENTRANCES | 3 | 0.978 | True |
| FLOORSMAX | 3 | 0.985 | True |
| FLOORSMIN | 3 | 0.986 | True |
| LANDAREA | 3 | 0.975 | True |
| LIVINGAPARTMENTS | 3 | 0.965 | True |
| LIVINGAREA | 3 | 0.973 | True |
| NONLIVINGAPARTMENTS | 3 | 0.968 | True |
| NONLIVINGAREA | 3 | 0.968 | True |
| YEARS_BEGINEXPLUATATION | 3 | 0.968 | True |
| YEARS_BUILD | 3 | 0.989 | True |

- Building text columns (no AVG/MEDI twin): ['FONDKAPREMONT_MODE', 'HOUSETYPE_MODE', 'WALLSMATERIAL_MODE', 'EMERGENCYSTATE_MODE']; numeric TOTALAREA_MODE.

## Near-constant columns (top value share >= 99% of non-missing)

{'FLAG_MOBIL': 1.0, 'FLAG_DOCUMENT_12': 1.0, 'FLAG_DOCUMENT_10': 1.0, 'FLAG_DOCUMENT_2': 0.9999, 'FLAG_DOCUMENT_4': 0.9999, 'FLAG_DOCUMENT_7': 0.9998, 'FLAG_DOCUMENT_17': 0.9997, 'FLAG_DOCUMENT_21': 0.9997, 'FLAG_DOCUMENT_20': 0.9995, 'FLAG_DOCUMENT_19': 0.9994, 'FLAG_DOCUMENT_15': 0.9989, 'FLAG_CONT_MOBILE': 0.9981, 'FLAG_DOCUMENT_14': 0.997, 'FLAG_DOCUMENT_13': 0.9967, 'FLAG_DOCUMENT_11': 0.9962, 'FLAG_DOCUMENT_9': 0.9962, 'AMT_REQ_CREDIT_BUREAU_DAY': 0.9945, 'AMT_REQ_CREDIT_BUREAU_HOUR': 0.9941, 'FLAG_DOCUMENT_18': 0.9919}

## Pairs suspected to be redundant (Pearson r, pairwise complete)

| A | B | r |
|---|---|---|
| AMT_CREDIT | AMT_GOODS_PRICE | +0.987 |
| AMT_ANNUITY | AMT_CREDIT | +0.770 |
| REGION_RATING_CLIENT | REGION_RATING_CLIENT_W_CITY | +0.950 |
| OBS_30_CNT_SOCIAL_CIRCLE | OBS_60_CNT_SOCIAL_CIRCLE | +0.999 |
| DEF_30_CNT_SOCIAL_CIRCLE | DEF_60_CNT_SOCIAL_CIRCLE | +0.860 |
| CNT_CHILDREN | CNT_FAM_MEMBERS | +0.879 |
| DAYS_BIRTH | DAYS_EMPLOYED | -0.616 |
| REG_REGION_NOT_LIVE_REGION | REG_REGION_NOT_WORK_REGION | +0.453 |
| LIVE_REGION_NOT_WORK_REGION | REG_REGION_NOT_WORK_REGION | +0.863 |
| REG_CITY_NOT_LIVE_CITY | REG_CITY_NOT_WORK_CITY | +0.439 |
| AMT_REQ_CREDIT_BUREAU_MON | AMT_REQ_CREDIT_BUREAU_QRT | -0.013 |

- FLAG_DOCUMENT_* share of 1s: D2 0.01%, D3 71.01%, D4 0.01%, D5 1.51%, D6 8.79%, D7 0.02%, D8 8.17%, D9 0.38%, D10 0.00%, D11 0.38%, D12 0.00%, D13 0.33%, D14 0.30%, D15 0.11%, D16 1.00%, D17 0.03%, D18 0.81%, D19 0.06%, D20 0.05%, D21 0.03%

## Completeness probe: column names containing typical bank fields

- 'TERM': none
- 'RATE': none
- 'PURPOSE': none
- 'CHANNEL': none
- 'DEBT': none
- 'SAVING': none
- 'BALANCE': none
- 'DELINQ': none
- 'INSTAL': none
- 'PREV': none
- 'DATE': none

