---
name: dcf-valuation
description: Build or review a discounted cash flow valuation — free cash flow projection, discount rate, terminal value, and the bridge from enterprise to equity value. Load when the task involves valuing a company or asset by DCF, setting WACC, or sanity-checking a valuation output. Not for comparable-company or precedent-transaction analysis.
---

# DCF valuation

## Cash flow definition

Unlevered free cash flow, the standard build:

```
EBIT
× (1 − tax rate)          → NOPAT
+ depreciation & amortization
− capital expenditure
− increase in net working capital
= unlevered free cash flow
```

- Unlevered pairs with WACC and yields enterprise value
- Levered (after interest and debt flows) pairs with cost of equity and yields equity value directly
- Never mix the two — discounting unlevered cash flow at cost of equity is the most common fatal error

## Discount rate

- WACC = (E/V × cost of equity) + (D/V × cost of debt × (1 − tax rate))
- Cost of equity via CAPM: risk-free + beta × equity risk premium
- Use target capital structure, not today's snapshot, when the structure is expected to change
- Unlever and relever comparable betas rather than borrowing a levered beta directly
- Weights at market value, not book

## Terminal value

Two methods — compute both, reconcile the gap:

| Method | Formula | Watch for |
|---|---|---|
| Perpetuity growth | FCF(n) × (1+g) / (WACC − g) | g above long-run GDP is indefensible |
| Exit multiple | Terminal-year metric × multiple | Implied g should be checked and stated |

- Terminal year must be a steady state: capex ≈ depreciation, working capital growing with revenue
- If terminal value exceeds ~75% of total value, say so — the valuation rests on assumption, not projection

## Discounting

- Mid-year convention when cash flows arrive through the year; state which convention is used
- Discount period counts from the valuation date, not the fiscal year start
- Stub period handled explicitly when valuing mid-year

## Enterprise to equity bridge

```
Enterprise value
− total debt
− capitalized lease liabilities (IFRS 16 / ASC 842)
− preferred equity, minority interest
+ cash and equivalents
+ non-operating assets not in the projected cash flows
= equity value
÷ diluted shares (treasury method)
= value per share
```

- **Take a position on stock-based compensation and state it.** Treating it as a non-cash add-back while diluted shares stay flat counts the same cost zero times. Either expense it in the cash flows or grow the share count — never neither.

## Sanity checks

- Terminal value as a share of total — state it
- Implied exit multiple from the perpetuity method, and implied growth from the exit multiple method — both should be defensible
- Implied multiples versus trading comparables
- WACC versus the range for the sector; a rate outside it needs a stated reason

## Output

Report the value as a range from an explicit sensitivity on WACC and terminal assumption, never a single number. Name the two or three inputs the answer actually hinges on.
