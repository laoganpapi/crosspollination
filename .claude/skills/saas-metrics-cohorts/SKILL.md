---
name: saas-metrics-cohorts
description: Calculate and audit recurring-revenue metrics — ARR movements, net and gross retention, CAC payback, cohort curves, and efficiency ratios. Load when the task involves subscription business metrics, churn analysis, cohort retention, unit economics, or a metrics section of a board deck or diligence pack. Not for building the financial model itself, valuation, pricing research, or non-recurring revenue.
---

# SaaS metrics and cohorts

## ARR movement bridge

Every period reconciles:

```
opening ARR
+ new (first-time customers)
+ expansion (upsell, seat growth, price)
− contraction (downgrades)
− churn (full loss)
= closing ARR
```

- These five components must tie exactly to closing ARR; a plug figure means the underlying data is wrong
- Expansion and contraction are separate lines, never netted
- **This bridge assumes committed subscription revenue.** Usage-based revenue has no contracted run-rate, so annualizing a spike reads as expansion and a quiet month reads as churn. Where revenue is consumption-priced, state the annualization window and hold it fixed, or report it separately from ARR

## Retention

| Metric | Formula | Reads as |
|---|---|---|
| Gross revenue retention | (opening − contraction − churn) / opening | Ceiling of 100%; measures leakage |
| Net revenue retention | (opening + expansion − contraction − churn) / opening | Can exceed 100%; measures the base's growth |
| Logo retention | customers retained / opening customers | Ignores value, useful for SMB |

- Always state the cohort basis and window — NRR on a trailing-12-month basis differs materially from annualized monthly
- Exclude new customers from the denominator; including them inflates retention

## Efficiency

- CAC = fully loaded sales and marketing spend / new customers acquired in the same period, lagged for sales cycle
- CAC payback (months) = CAC / (new ARR × gross margin) × 12 — gross margin, not revenue
- Magic number = (current quarter ARR − prior quarter ARR) × 4 / prior quarter S&M spend
- Rule of 40 = growth rate % + profitability margin % — state which margin
- LTV: treat with suspicion. It requires a churn rate stable enough to extrapolate, which early-stage data rarely supports. Report payback period instead when the history is short

## Cohort analysis

- Group by acquisition month or quarter, track each cohort's retained revenue over months since acquisition
- Plot retention curves by cohort to expose whether newer cohorts behave differently — the flattening point matters more than the level
- Segment before averaging: blending SMB and enterprise hides both

## Common errors

- Blended CAC across channels obscures that one channel is unprofitable
- Annual contracts counted as ARR at signature while churn measures monthly — mismatched bases
- Churn rate computed on customers but applied to revenue, or the reverse
- Expansion revenue from a single large account presented as a trend

## Output

Show the movement bridge, retention on a stated basis, and payback. Name the metric definition used for each — most disagreements are definitional, not factual.
