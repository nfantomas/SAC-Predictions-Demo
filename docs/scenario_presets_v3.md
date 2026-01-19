# Scenario Presets V3 — HR Cost Focus (Milestone M9)

Single source of truth for the 5 business-ready presets, their drivers, default params, assumptions, and safety bounds.

## Shared assumptions
- Units: monthly total HR costs in EUR.
- t0: cost ≈ 10,000,000 EUR, fixed share = 20%, variable share = 80%, baseline FTE = 800 ⇒ alpha = 2,000,000; beta = 10,000 EUR/FTE/month.
- If data lacks segmentation, use segment_weights below for scenario #3.
- Safety bounds (inputs): impact_magnitude level ∈ [-0.5, 1.0]; growth-mode deltas ∈ [-0.5, 0.5]; drift ∈ [-0.3, 0.3]; beta_multiplier ∈ [0.7, 1.2]; inflation annualized ∈ [-0.1, 0.2] unless explicitly overridden.
- Safety bounds (outputs): projected 10y multiplier should stay within [0.2x, 3x] for demo; clamp/reject otherwise.

## Presets (UI labels)

1) **Freeze hiring**  
   - Intent: halt net hiring; optionally allow mild attrition.  
   - Driver: `fte` (implied from cost via alpha/beta).  
   - Defaults: onset 6m linear; impact_mode `growth`; impact_magnitude ≈ -0.05 (monthly growth delta); growth_delta_pp_per_year ≈ -0.06; duration: permanent (event_duration null).  
   - Segmentation: none.  
   - Bounds: keep annualized growth deltas within [-6 pp, 0].

2) **Convert IT contractors → employees**  
   - Intent: absorb contractor roles; higher headcount, lower beta (cheaper per-FTE mix).  
   - Driver: mixed (fte + beta_multiplier).  
   - Defaults: fte_delta_pct ≈ +0.03 (3% uplift), beta_multiplier ≈ 0.95; onset 3m linear; permanent.  
   - Segmentation: none.  
   - Bounds: beta_multiplier clamp [0.9, 1.0]; fte_delta_pct clamp [-0.05, 0.10].

3) **Inflation: 5% in A, 8% in B + role caps**  
   - Intent: inflation shock by segment with hiring caps.  
   - Driver: cost (inflation ramp) + fte cap (growth mode toward 0).  
   - Defaults: onset 3m linear; event_duration 12m; recovery 12m; inflation_by_segment = {A: 0.05, B: 0.08}; segment_weights = {A: 0.6, B: 0.4} if no data; impact_mode level with impact_magnitude derived from weighted inflation; growth impact caps FTE growth to 0 (growth_delta_pp_per_year ≈ -0.02).  
   - Segmentation: optional A/B; fallback uses weights.  
   - Bounds: inflation annualized clamp [-0.05, 0.1] if no override; beta_multiplier default 1.0.

4) **Outsource 120 FTE from X → Y**  
   - Intent: shift 120 FTE to cheaper location; total FTE constant but variable cost drops.  
   - Driver: cost via beta_multiplier.  
   - Defaults: outsourced_share = 120/800 = 0.15; assumed cost reduction on that share 25% ⇒ net beta_multiplier ≈ 0.9625; lag 1m; step.  
   - Segmentation: optional (X/Y); if absent, apply beta multiplier globally.  
   - Bounds: beta_multiplier clamp [0.8, 1.0].

5) **Reduce workforce cost by 10% → required FTE cuts by seniority**  
   - Intent: hit a 10% cost target using alpha/beta and a simple cut plan.  
   - Driver: `cost_target` with cost_target_pct = -0.10; compute total FTE delta first, then allocate via planner.  
   - Defaults: onset step; permanent; fte_cut_plan uses seniority distribution (Junior 50%, Mid 35%, Senior 15%) and cost multipliers (0.7x/1.0x/1.6x).  
   - Segmentation: none (seniority only).  
   - Bounds: cost_target_pct clamp [-0.3, 0]; ensure category cuts do not exceed headcount share.

## Notes
- If dataset lacks A/B or seniority, use the provided weights and distributions; surface a UI note “using assumed segment mix”.
- All presets should pass the safety validator; if a preset would violate 10y multiplier bounds, clamp impact_magnitude/growth to stay within limits.
