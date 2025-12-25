# UI QA Checklist — HR Cost Demo

Capture the following screenshots and validate expected content:

1) **Provenance panel**
   - Provider ID
   - Metric name (`hr_cost`)
   - Unit + currency
   - Measure + aggregation
   - Filters (visible)

2) **Baseline chart with boundary**
   - Actual vs forecast line distinction
   - Boundary line at last actual date
   - Y-axis labeled “HR cost (currency)”

3) **Preset cards**
   - Preset name + description
   - Visible parameter values (growth, shock, duration, drift)

4) **Scenario assistant panel**
   - Suggested parameters shown with mode (template/llm)
   - Apply button visible

5) **Narrative panel**
   - Title references HR cost
   - Bullets rendered as bullet points (not a list string)

## Expected validations
- “Last actual (monthly)” KPI equals the last row in `data/cache/sac_export.csv`.
- Preset selection updates the highlighted scenario line.
- Refresh button does not auto-run on rerenders.
