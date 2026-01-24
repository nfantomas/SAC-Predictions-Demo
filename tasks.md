# Task: Remove redundant left-side filters and rely on Plotly native zoom

## Background
The current left-side filter panel (Version, Currency, Region, timeframe selection, etc.) is confusing and does not reflect how the demo actually works:
- The demo operates on the full SAP dataset slice (no meaningful interactive slicing implemented for those controls).
- The timeframe selector does not drive the Plotly chart (chart does not react).
- Plotly already provides zoom/pan/range controls, making extra timeframe filters redundant.
- The “Refresh from SAC” action already exists in Advanced Options, so duplicating maintenance controls is unnecessary.

## Goal
Simplify the UI for senior-manager demos by **removing non-functional or misleading filters** and keeping only controls that:
1) clearly impact the displayed numbers, and  
2) reinforce the “SAC data → forecast + scenarios → AI scenario assistant” story.

## Requirements
### 1) Remove the entire left filter panel UI
- Remove/hide:
  - Version selector
  - Currency selector
  - Region selector
  - Year/Q selectors
  - Any timeframe slider/dropdown intended to filter the chart
- Ensure there are **no dead controls** (nothing that visually suggests filtering if it is not implemented).

### 2) Chart interaction relies on Plotly only
- Use Plotly zoom/pan/range selector (if desired) as the *only* timeframe interaction.
- Default view should show the intended focus window (e.g., 2024–2030), but users can zoom out if they want.
- No separate “timeframe” Streamlit inputs unless they actually change the query and are wired end-to-end.

### 3) Keep “Refresh SAC data” only as maintenance control
- Keep the SAC refresh button **only inside Advanced Options** (or another clearly “maintenance” area).
- Label it clearly as maintenance (e.g., “Maintenance: Refresh SAC cache”).
- If the refresh is expensive or slow, show a small note (e.g., “For demo maintenance; not needed for normal use”).

### 4) UX check
After removal, the top-to-bottom narrative should be:
1) “We load HR cost actuals from SAC”
2) “We forecast baseline”
3) “We apply scenarios / AI scenario assistant”
4) “We compare and extract KPIs”

## Acceptance criteria
- No left panel filters remain (or the panel itself is removed).
- The Plotly chart responds only to Plotly interactions (zoom/pan/rangeslider) and default viewport is correct.
- “Refresh SAC data” exists in Advanced Options only, clearly marked as maintenance.
- No UI control is present that does not affect the output.

## Implementation notes (for developer)
- If the left panel is implemented via `st.sidebar`, remove that block or gate behind a feature flag (off by default).
- If any filter values are still used indirectly, replace them with fixed defaults and document them in “Model assumptions”.
- If future slicing is planned, keep it out of the main demo flow and add later as “Optional: Filters (beta)”.
