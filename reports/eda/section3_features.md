# Section 3: feature completeness

Labels: [DATA] verified by code on the train split (numbers in `section3_facts.md`, catalog in `feature_catalog.csv`), [DOC] from `HomeCredit_columns_description.csv`, [GENERAL] domain knowledge, not verified here. Hypotheses are marked as hypotheses.

## Catalog and groups

- `feature_catalog.csv` has 122 rows, one per column. All 122 columns have an entry in the description file, so the official descriptions are real, not inferred. [DATA]
- Group counts add up to 122. [DATA]

| Group | Columns |
|---|---|
| ID and label | 2 |
| Loan terms | 4 |
| Client demographics | 8 |
| Income and employment | 5 |
| Assets | 3 |
| Building / housing attributes (AVG / MODE / MEDI) | 47 |
| External scores | 3 |
| Region and address consistency | 9 |
| Contact flags | 6 |
| Document flags | 20 |
| Social circle | 4 |
| Credit bureau enquiries | 6 |
| Application timing and history | 5 |
| **Total** | **122** |

- Semantic types: 57 numeric continuous, 36 binary flag, 12 numeric count, 11 nominal, 4 ordinal, 1 ID, 1 target. The types come from simple rules plus 4 manual overrides (education level, two region ratings, hour of day). [DATA]
- Missing values: 67 of 122 columns have at least one. 57 have more than 5%. 41 have more than 50%. [DATA]

## The known quirks, checked

| Claim | What the train data shows |
|---|---|
| DAYS_* are negative offsets from the application date | True for 4 of 5 columns. DAYS_BIRTH, DAYS_ID_PUBLISH are 100% negative. DAYS_REGISTRATION is 99.97% negative, rest 0. DAYS_LAST_PHONE_CHANGE is 87.9% negative and 12.1% zero. DAYS_EMPLOYED is the exception (next row). [DATA] |
| DAYS_EMPLOYED has a placeholder | Yes. The value 365243 (about 1,000 years) appears in 33,225 rows (18.01%). It is the only positive value in the column. [DATA] |
| What the placeholder means | The rows are 33,210 pensioners and 15 unemployed. 33,218 rows are pensioners, so only 8 pensioners have a real value. The same 33,225 rows are the ones with ORGANIZATION_TYPE = XNA. So one fact (no current employer) is stored in two columns. Reading it as "not employed" is a hypothesis. [DATA] |
| Placeholder rows differ in default rate | 5.41% (n=33,225) vs 8.66% (n=151,281) for the other rows. [DATA] |
| XNA in categorical columns | CODE_GENDER has 2 XNA rows. ORGANIZATION_TYPE has 33,225 (18.01%). NAME_FAMILY_STATUS has 1 "Unknown". FONDKAPREMONT_MODE has 3,412 "not specified" rows, which are a label, not a NaN. [DATA] |
| Extreme AMT_INCOME_TOTAL | Median 148,500, p99 472,500, max 117,000,000 (788 times the median). 144 rows are above 1,000,000. [DATA] |
| Extreme social circle counts | OBS_30 has median 0, p99 10, max 348. OBS_60 max is 344. DEF_30 max is 34. [DATA] |
| Other extremes found while checking | CNT_CHILDREN max 19. OWN_CAR_AGE max 91. AMT_REQ_CREDIT_BUREAU_MON max 27. [DATA] |
| EXT_SOURCE columns are heavily missing | Only EXT_SOURCE_1 is heavily missing (56.39%). EXT_SOURCE_3 is 19.82%. EXT_SOURCE_2 is 0.22%. So "heavily missing" is true for one of three. [DATA] |
| EXT_SOURCE columns are strongly predictive | They are the 3 strongest numeric columns by absolute Pearson r with TARGET: EXT_SOURCE_3 -0.1765, EXT_SOURCE_2 -0.1598, EXT_SOURCE_1 -0.1533. The next one is DAYS_BIRTH at +0.0779. Default rate falls from 14.31% to 3.00% across EXT_SOURCE_1 quintiles (n=16,093 each), 15.19% to 3.57% for EXT_SOURCE_2 and 16.20% to 3.40% for EXT_SOURCE_3. "Strongly" here means strongest in this table. An r of 0.18 is still modest. [DATA] |
| Many near-duplicate building columns | Yes. 14 stems come in 3 flavours (AVG, MODE, MEDI). Within each stem the 3 columns correlate at 0.965 or higher, and the missing pattern is identical in all 14 stems. Plus 5 other building columns (4 text, TOTALAREA_MODE). 14 x 3 + 5 = 47. [DATA] |

Correction to one assumption: EXT_SOURCE missingness is not a shared trait of the three scores. EXT_SOURCE_2 is almost complete.

## Unusable, redundant or risky

**Near-constant (top value 99% or more of non-missing): 19 columns.** [DATA]
- FLAG_MOBIL (100.00%), FLAG_DOCUMENT_10 and _12 (about 100%), FLAG_CONT_MOBILE (99.81%), AMT_REQ_CREDIT_BUREAU_HOUR (99.41%) and _DAY (99.45%), and 13 more FLAG_DOCUMENT_* columns (full list in `section3_facts.md`).
- Why it matters: with so few rows in the minority value, a bin can hold only a handful of defaults, so any rate computed on it is noisy. Proposed treatment: drop or pool. This is a proposal for Section 7.
- FLAG_DOCUMENT_3 is the opposite: 71.01% are 1, so it carries real variation.

**Redundant pairs (Pearson r, pairwise complete).** [DATA]
- OBS_30 vs OBS_60 social circle: +0.999. AMT_CREDIT vs AMT_GOODS_PRICE: +0.987. REGION_RATING_CLIENT vs _W_CITY: +0.950. CNT_CHILDREN vs CNT_FAM_MEMBERS: +0.879. DEF_30 vs DEF_60: +0.860. LIVE_REGION_NOT_WORK_REGION vs REG_REGION_NOT_WORK_REGION: +0.863.
- Building AVG, MODE and MEDI: keep one flavour per stem at most.
- DAYS_BIRTH vs DAYS_EMPLOYED: -0.616, partly because of the placeholder rows. Moderate, not a duplicate.

**Sensitive attributes. [GENERAL, legal status for Home Credit's markets not verified]**
- CODE_GENDER, DAYS_BIRTH (age), NAME_FAMILY_STATUS, CNT_CHILDREN and CNT_FAM_MEMBERS. Many lenders cannot use gender, and often face limits on age and family status. A real bank would need a legal check before using them.
- DAYS_BIRTH is the strongest non-EXT numeric column (r = +0.0779), so dropping it has a cost. That tension is worth stating in the write-up.
- REGION_* and ORGANIZATION_TYPE can act as proxies for protected traits. This is a hypothesis.

**Leakage suspicion. All hypotheses, none verified.**
- No column name looks like a loan outcome or status. [DATA, checked in Section 2]
- DEF_* and OBS_*_CNT_SOCIAL_CIRCLE count defaults seen among the applicant's contacts. When those defaults were observed relative to this loan is not documented. Hypothesis: it may include post-origination information.
- EXT_SOURCE_1/2/3: the source and the date of each score are not documented. They may embed information that overlaps with the label. Hypothesis.
- FLAG_DOCUMENT_*: whether a document was "provided" may be recorded after the decision. Hypothesis.
- All of these need a question to Vav before the shortlist, because dropping a suspected leak changes the result.

**Quirks that need treatment, not removal**
- DAYS_EMPLOYED placeholder and its twin ORGANIZATION_TYPE = XNA: convert to a missing or "not employed" flag.
- AMT_INCOME_TOTAL max of 117,000,000: cap or use a rank or log scale.
- Column names beginning AMT_REQ_CREDIT_BUREAU_ are counts of enquiries, not amounts. [DOC]

## Is the feature set complete for an application scorecard? [GENERAL unless noted]

No. It is a reasonable first-pass set, but a bank would normally also have:

| A real bank usually has | In this table? |
|---|---|
| Credit bureau history: past loans, delinquencies, balances | No. Only 6 enquiry counts. History sits in the excluded tables. |
| Own repayment behaviour on earlier products | No (excluded tables) |
| Loan term and interest rate | No column named TERM or RATE. [DATA] Term could be roughly inferred from AMT_CREDIT / AMT_ANNUITY. Hypothesis. |
| Loan purpose | No [DATA] |
| Application channel or branch | No [DATA] |
| Existing debt obligations and a debt-to-income calculation | No. Payment to income can be derived from AMT_ANNUITY and AMT_INCOME_TOTAL. |
| Verified income and bank account data | Not stated. Whether AMT_INCOME_TOTAL is verified or self-reported is not documented. |
| Collateral value | Only AMT_GOODS_PRICE |
| Application date | No [DATA] |

What it has in place of that: three external scores, applicant demographics, housing and region information, and document flags. This matters for the project: the data has less direct credit history than a bank would use, so the external scores carry much of the signal. That could make the complexity premium look different from a bank with full history. This is a hypothesis for the write-up.
