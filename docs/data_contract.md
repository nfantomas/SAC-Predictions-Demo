# Data Contract — Demo Series

This document defines the normalized dataset contract used by the demo pipeline.

## Required fields
- `date` (string, ISO-8601 date, aligned to grain)
- `value` (float or numeric string; coerced to float)

## Optional fields
- `dim_*` columns (string). Limit to 1–2 dimensions for the demo.
- Example: `dim_region`, `dim_product`

## Grain rules
The `date` field must be aligned to the configured grain:
- `month`: `YYYY-MM-01` (first day of month)
- `quarter`: `YYYY-Qn` or `YYYY-MM-01` (first month of quarter)
- `year`: `YYYY-01-01`

For the SAC dataset, the raw `Date` column is in `YYYYMM` format and is
normalized to `YYYY-MM-01` before aggregation.

## Allowed dimensions
- Any dimension is allowed if represented as a `dim_*` column.
- Dim values must be non-empty strings when present; use empty string for “unknown”.

## Missing-value policy
- `date` and `value` are required and **must not be missing**.
- Rows with missing `date` or `value` are invalid and should fail validation.
- Optional dimension fields may be missing; treat as empty string.

## Demo fixture
The fixture dataset in `tests/fixtures/sample_series.csv` adheres to this contract
and is used for offline tests.

## SAC dataset mapping
- Raw `Date` (SAC): `YYYYMM` (string)
- Normalized `date`: `YYYY-MM-01`
- Raw measure: `SignedData`
- Normalized `value`: float
- Aggregation: sum by month
