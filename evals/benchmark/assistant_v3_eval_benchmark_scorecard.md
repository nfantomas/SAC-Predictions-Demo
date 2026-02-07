# Assistant V3 Eval Scorecard

## Summary

- Total matches: 19 / 19
- Total passes: 19 / 19
- Total errors: 1 / 1
- Match rate: 0.7917 / 0.7917
- Pass rate: 0.7917 / 0.7917
- Average answer score: 1.25 / 1.25
- Average latency (ms): N/A (latency not captured in this run)

### Answer Score Distribution

| Score | Count |
|---|---:|
| 0 | 5 / 5 |
| 1 | 9 / 9 |
| 2 | 9 / 9 |
| 3 | 1 / 1 |

## Per Question

### Q01
- Question: reduction of FTEs due to 10% efficiency gains due to implementation of AI
- Expected driver: `fte`
- Predicted driver: `fte`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `1 / 1`
- Warnings: `11 / 11`
- Latency (ms): `N/A / N/A`
- Param sign matches: `1/1 / 1/1`
- Param exact matches: `1/3 / 1/3`
- Error: `-`
- Score note: Really messy: low text coverage and/or high warnings/weak param alignment.

### Q02
- Question: what will happen with FTEs if we want to keep costs at current level
- Expected driver: `cost_target`
- Predicted driver: `cost_target`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `3 / 3`
- Warnings: `2 / 2`
- Latency (ms): `N/A / N/A`
- Param sign matches: `1/1 / 1/1`
- Param exact matches: `0/2 / 0/2`
- Error: `-`
- Score note: Decent match: strong driver/parameter alignment with clear answer quality.

### Q03
- Question: hiring freeze from 2028
- Expected driver: `fte`
- Predicted driver: `fte`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `2 / 2`
- Warnings: `2 / 2`
- Latency (ms): `N/A / N/A`
- Param sign matches: `0/0 / 0/0`
- Param exact matches: `1/2 / 1/2`
- Error: `-`
- Score note: Okayish: mostly aligned but with gaps in coverage or warning noise.

### Q04
- Question: pressure from aging population
- Expected driver: `fte`
- Predicted driver: `cost`
- Driver match: `False`
- Overall pass: `False`
- Answer score: `0 / 0`
- Warnings: `14 / 14`
- Latency (ms): `N/A / N/A`
- Param sign matches: `0/1 / 0/1`
- Param exact matches: `2/3 / 2/3`
- Error: `-`
- Score note: No match: predicted driver differs from expected driver.

### Q05
- Question: If we cap total labor cost growth at 2% YoY, what is the maximum headcount we can support given projected wage inflation?
- Expected driver: `cost_target`
- Predicted driver: `unknown`
- Driver match: `False`
- Overall pass: `False`
- Answer score: `0 / 0`
- Warnings: `0 / 0`
- Latency (ms): `N/A / N/A`
- Param sign matches: `0/0 / 0/0`
- Param exact matches: `0/0 / 0/0`
- Error: `Cost target driver requires cost_target_pct.`
- Score note: No match due to runtime error: Cost target driver requires cost_target_pct.

### Q06
- Question: What FTE reduction is needed to offset 6% wage inflation while keeping total labor cost flat?
- Expected driver: `cost_target`
- Predicted driver: `fte`
- Driver match: `False`
- Overall pass: `False`
- Answer score: `0 / 0`
- Warnings: `5 / 5`
- Latency (ms): `N/A / N/A`
- Param sign matches: `0/0 / 0/0`
- Param exact matches: `0/2 / 0/2`
- Error: `-`
- Score note: No match: predicted driver differs from expected driver.

### Q07
- Question: If we increase average salary by 5% to improve retention, how does that change required hiring volumes and total cost?
- Expected driver: `cost`
- Predicted driver: `cost`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `1 / 1`
- Warnings: `8 / 8`
- Latency (ms): `N/A / N/A`
- Param sign matches: `2/2 / 2/2`
- Param exact matches: `1/3 / 1/3`
- Error: `-`
- Score note: Really messy: low text coverage and/or high warnings/weak param alignment.

### Q08
- Question: What is the FTE and cost impact if attrition rises from 10% to 18% for two years?
- Expected driver: `fte`
- Predicted driver: `fte`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `1 / 1`
- Warnings: `5 / 5`
- Latency (ms): `N/A / N/A`
- Param sign matches: `0/0 / 0/0`
- Param exact matches: `1/3 / 1/3`
- Error: `-`
- Score note: Really messy: low text coverage and/or high warnings/weak param alignment.

### Q09
- Question: What hiring plan is required to maintain headcount if retirement eligibility spikes (e.g., 25% of workforce eligible by 2030)?
- Expected driver: `fte`
- Predicted driver: `fte`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `1 / 1`
- Warnings: `2 / 2`
- Latency (ms): `N/A / N/A`
- Param sign matches: `0/1 / 0/1`
- Param exact matches: `1/3 / 1/3`
- Error: `-`
- Score note: Really messy: low text coverage and/or high warnings/weak param alignment.

### Q10
- Question: What happens if we introduce a 4-day workweek (reduced hours) in one region—what FTE backfill is required?
- Expected driver: `fte`
- Predicted driver: `fte`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `2 / 2`
- Warnings: `2 / 2`
- Latency (ms): `N/A / N/A`
- Param sign matches: `1/1 / 1/1`
- Param exact matches: `1/2 / 1/2`
- Error: `-`
- Score note: Okayish: mostly aligned but with gaps in coverage or warning noise.

### Q11
- Question: If we increase utilization targets from 75% to 82%, how many FTEs can we avoid hiring?
- Expected driver: `fte`
- Predicted driver: `fte`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `2 / 2`
- Warnings: `4 / 4`
- Latency (ms): `N/A / N/A`
- Param sign matches: `0/0 / 0/0`
- Param exact matches: `0/2 / 0/2`
- Error: `-`
- Score note: Okayish: mostly aligned but with gaps in coverage or warning noise.

### Q12
- Question: If sick leave increases by 1.5 days per FTE per year, what is the effective capacity loss and required headcount?
- Expected driver: `fte`
- Predicted driver: `fte`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `2 / 2`
- Warnings: `3 / 3`
- Latency (ms): `N/A / N/A`
- Param sign matches: `1/1 / 1/1`
- Param exact matches: `0/3 / 0/3`
- Error: `-`
- Score note: Okayish: mostly aligned but with gaps in coverage or warning noise.

### Q13
- Question: If we consolidate two departments and remove duplicate management layers, what is the new FTE and cost baseline?
- Expected driver: `fte`
- Predicted driver: `fte`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `1 / 1`
- Warnings: `0 / 0`
- Latency (ms): `N/A / N/A`
- Param sign matches: `1/1 / 1/1`
- Param exact matches: `1/2 / 1/2`
- Error: `-`
- Score note: Really messy: low text coverage and/or high warnings/weak param alignment.

### Q14
- Question: If we outsource a process that currently consumes 80 FTE, what is the expected cost delta?
- Expected driver: `fte`
- Predicted driver: `fte`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `1 / 1`
- Warnings: `0 / 0`
- Latency (ms): `N/A / N/A`
- Param sign matches: `0/1 / 0/1`
- Param exact matches: `2/4 / 2/4`
- Error: `-`
- Score note: Really messy: low text coverage and/or high warnings/weak param alignment.

### Q15
- Question: What happens if we relocate 200 FTE from a high-cost country to a lower-cost country over 3 years?
- Expected driver: `mix_shift`
- Predicted driver: `cost`
- Driver match: `False`
- Overall pass: `False`
- Answer score: `0 / 0`
- Warnings: `0 / 0`
- Latency (ms): `N/A / N/A`
- Param sign matches: `1/1 / 1/1`
- Param exact matches: `1/3 / 1/3`
- Error: `-`
- Score note: No match: predicted driver differs from expected driver.

### Q16
- Question: If union negotiations result in +7% wage increase plus reduced working hours, what is the combined impact?
- Expected driver: `cost`
- Predicted driver: `cost`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `1 / 1`
- Warnings: `10 / 10`
- Latency (ms): `N/A / N/A`
- Param sign matches: `1/1 / 1/1`
- Param exact matches: `1/3 / 1/3`
- Error: `-`
- Score note: Really messy: low text coverage and/or high warnings/weak param alignment.

### Q17
- Question: If we introduce a minimum wage increase affecting 15% of roles, what is the total cost impact?
- Expected driver: `cost`
- Predicted driver: `cost`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `2 / 2`
- Warnings: `0 / 0`
- Latency (ms): `N/A / N/A`
- Param sign matches: `1/1 / 1/1`
- Param exact matches: `1/2 / 1/2`
- Error: `-`
- Score note: Okayish: mostly aligned but with gaps in coverage or warning noise.

### Q18
- Question: If we implement RPA/automation reducing transaction workload by 25% in Finance Ops, what FTE reduction is feasible by 2029?
- Expected driver: `fte`
- Predicted driver: `fte`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `1 / 1`
- Warnings: `10 / 10`
- Latency (ms): `N/A / N/A`
- Param sign matches: `1/1 / 1/1`
- Param exact matches: `2/3 / 2/3`
- Error: `-`
- Score note: Really messy: low text coverage and/or high warnings/weak param alignment.

### Q19
- Question: If we invest in training that improves productivity 2% per quarter for 2 years, what headcount trajectory results?
- Expected driver: `fte`
- Predicted driver: `fte`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `2 / 2`
- Warnings: `3 / 3`
- Latency (ms): `N/A / N/A`
- Param sign matches: `1/1 / 1/1`
- Param exact matches: `3/3 / 3/3`
- Error: `-`
- Score note: Okayish: mostly aligned but with gaps in coverage or warning noise.

### Q20
- Question: If AI adoption is delayed by 18 months, what is the cost of delay in incremental FTE needs?
- Expected driver: `fte`
- Predicted driver: `fte`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `2 / 2`
- Warnings: `4 / 4`
- Latency (ms): `N/A / N/A`
- Param sign matches: `0/0 / 0/0`
- Param exact matches: `0/2 / 0/2`
- Error: `-`
- Score note: Okayish: mostly aligned but with gaps in coverage or warning noise.

### Q21
- Question: If we set a constraint “no layoffs,” how do we achieve a 10% cost reduction (redeployments, hiring slowdown, attrition)?
- Expected driver: `cost_target`
- Predicted driver: `cost_target`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `2 / 2`
- Warnings: `6 / 6`
- Latency (ms): `N/A / N/A`
- Param sign matches: `1/1 / 1/1`
- Param exact matches: `1/2 / 1/2`
- Error: `-`
- Score note: Okayish: mostly aligned but with gaps in coverage or warning noise.

### Q22
- Question: If we set a constraint “keep FTE flat,” what wage/bonus/benefit levers must change to hit a 5% cost reduction?
- Expected driver: `cost`
- Predicted driver: `cost`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `1 / 1`
- Warnings: `0 / 0`
- Latency (ms): `N/A / N/A`
- Param sign matches: `1/1 / 1/1`
- Param exact matches: `1/2 / 1/2`
- Error: `-`
- Score note: Really messy: low text coverage and/or high warnings/weak param alignment.

### Q23
- Question: If we set a constraint “keep total cost flat,” how many FTE must be reduced given expected inflation and promotions?
- Expected driver: `cost_target`
- Predicted driver: `cost_target`
- Driver match: `True`
- Overall pass: `True`
- Answer score: `2 / 2`
- Warnings: `2 / 2`
- Latency (ms): `N/A / N/A`
- Param sign matches: `1/1 / 1/1`
- Param exact matches: `1/2 / 1/2`
- Error: `-`
- Score note: Okayish: mostly aligned but with gaps in coverage or warning noise.

### Q24
- Question: If we simulate an economic downturn (revenue -10%, hiring slowdown, higher attrition), what is the recommended workforce plan to stabilize costs?
- Expected driver: `mix_shift`
- Predicted driver: `cost_target`
- Driver match: `False`
- Overall pass: `False`
- Answer score: `0 / 0`
- Warnings: `4 / 4`
- Latency (ms): `N/A / N/A`
- Param sign matches: `2/2 / 2/2`
- Param exact matches: `3/4 / 3/4`
- Error: `-`
- Score note: No match: predicted driver differs from expected driver.

