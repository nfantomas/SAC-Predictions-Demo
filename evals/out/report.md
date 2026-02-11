# Consulting Evals Review Report

## Summary

- Total rows: 5
- Low-score rows (0/1): 0
- Unique question IDs: 5

## Repeated Failure Tags

- None

## Worst 10 Items

### 1
- Score: `2`
- Tags: `clarity`
- Question: Projects slip by 2 months across Europe. What happens to utilization and revenue next quarter?
- Expected answer: Expect a utilization dip during the slip (more bench). Revenue drops roughly in proportion to billable days lost: ΔRevenue ≈ MD_rate × delivery_FTE × workdays × ΔUtilization. If no backfill, margin also falls because fixed overhead stays. Mitigation: redeploy to other programs, pull-forward pipeline, use subcontractors selectively.
- Model summary: Smoke mode deterministic answer.
- Reasoning: Smoke mode stub grader result.

### 2
- Score: `2`
- Tags: `clarity`
- Question: If we raise average utilization from 72% to 78% over 6 months, what’s the revenue upside?
- Expected answer: Revenue scales ~linearly with utilization. Upside ≈ (78%-72%)/72% ≈ +8.3% on delivery revenue once fully achieved (ramped over 6 months). Fixed costs unchanged, so profit/margin typically improves more than revenue.
- Model summary: Smoke mode deterministic answer.
- Reasoning: Smoke mode stub grader result.

### 3
- Score: `2`
- Tags: `clarity`
- Question: Rate pressure: blended day rate down 4% from next month. What’s the 12‑month impact?
- Expected answer: Delivery revenue declines ~4% immediately (after ramp). If costs unchanged, profit drops by about 4% of delivery revenue. To offset: increase utilization, adjust staffing mix (more near/offshore), or renegotiate scope/fees.
- Model summary: Smoke mode deterministic answer.
- Reasoning: Smoke mode stub grader result.

### 4
- Score: `2`
- Tags: `clarity`
- Question: We must keep profit flat despite 3% wage inflation. What levers do we have?
- Expected answer: Profit flat requires compensating uplift: higher utilization, higher rates, or lower capacity cost. If wage costs rise 3% on the variable layer, you need ~3% revenue uplift (rate/utilization) or equivalent cost savings; fixed overhead reductions help but usually lag.
- Model summary: Smoke mode deterministic answer.
- Reasoning: Smoke mode stub grader result.

### 5
- Score: `2`
- Tags: `clarity`
- Question: Client asks: ‘No layoffs’. How do we cut total cost by 5% in 12 months?
- Expected answer: Use attrition + hiring slowdown, reduce subcontractor spend, and cut discretionary overhead. With fixed costs, a 5% total reduction implies a larger reduction in the variable portion; stage it: immediate contractor reductions, then hiring freeze, then redeploy to keep utilization high.
- Model summary: Smoke mode deterministic answer.
- Reasoning: Smoke mode stub grader result.
