"""Data acquisition and splitting.

Owns: downloading application_train.csv, verifying integrity (row counts,
dtypes), and carving the single stratified 60/20/20 train/val/test split
that every other module builds on. application_test.csv is out of scope —
it has no public labels (see README, "Data").
"""
