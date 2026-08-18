---
name: three-statement-model
description: Build or audit a linked income statement, balance sheet, and cash flow model. Load when the task involves building a financial model from scratch, forecasting financials, linking statements, or checking why a model does not balance. Not for valuation (use dcf-valuation) or SaaS metrics (use saas-metrics-cohorts).
---

# Three-statement model

## Build order

1. Historicals first — at least 3 periods, entered as reported, never adjusted in place
2. Drivers sheet — every assumption lives here, nothing hardcoded downstream
3. Income statement to EBITDA
4. Working capital schedule (AR, inventory, AP as days)
5. Fixed asset schedule (capex, depreciation)
6. Debt schedule (draws, repayments, interest)
7. Cash flow statement
8. Balance sheet last — it is the check, not the input

## Linkage rules

- Net income flows to retained earnings and to the top of cash flow
- Depreciation appears in two places: income statement expense, cash flow add-back — from one source, the fixed asset schedule
- Every balance sheet change must appear in cash flow; an unexplained change is why models break
- Ending cash on the cash flow statement equals cash on the balance sheet — same cell reference, never retyped

## Circularity

- Interest depends on debt, debt depends on cash, cash depends on interest
- Two acceptable resolutions: average-balance interest with iterative calculation enabled, or beginning-balance interest with no circularity
- Prefer beginning balance unless precision genuinely matters — it survives file transfers and never produces zeros
- Never resolve circularity by hardcoding an interest figure

## Conventions

| Element | Rule |
|---|---|
| Inputs | One color, one place, never inside a formula |
| Sign | Costs negative throughout, or positive throughout — never mixed |
| Periods | One column per period, identical formula across the row |
| Time | No mixed frequency on one sheet |
| Units | Stated in the header, consistent, never mixed within a statement |

## Required checks

- Balance check row: assets − (liabilities + equity), every period, must read exactly zero
- Cash tie: cash flow ending cash − balance sheet cash, every period, zero
- No hardcodes in the projection region — audit for constants typed into formula cells
- Sum rows recalculated, not extended by hand

## Common failures

- Model balances in year 1 and drifts later → a balance sheet item with no cash flow counterpart
- Interest reads zero → circularity broken by a disabled iterative setting
- Working capital swings wildly → days assumptions applied to the wrong revenue or cost base
- Deferred tax and other non-cash items skipped, leaving the tie broken by a constant amount

## Reporting

State which drivers move the outcome most, where historicals were adjusted and why, and every check's status. A model delivered without its balance and cash checks passing is not delivered.
