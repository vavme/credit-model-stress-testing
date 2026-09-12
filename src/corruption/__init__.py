"""Data quality corruption simulator — the project's centerpiece (Phase 3).

Owns: the three corruption scenarios (MNAR missingness, label lag/noise,
distributional/schema drift) as pure, seeded functions — clean dataframe
+ severity in, corrupted dataframe out — plus their validation checks.
"""
