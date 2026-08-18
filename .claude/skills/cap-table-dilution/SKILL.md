---
name: cap-table-dilution
description: Model a capitalization table, priced-round dilution, convertible instrument conversion, and exit waterfall. Load when the task involves ownership percentages, pre/post-money math, SAFE or note conversion, option pool sizing, liquidation preferences, or who gets what in a sale. Not for company valuation itself.
---

# Cap table and dilution

## Priced round mechanics

```
post-money = pre-money + amount raised
investor % = amount raised / post-money
price per share = pre-money / fully diluted pre-round shares
```

- "Fully diluted" must be defined explicitly: outstanding + options granted + options available + warrants + convertibles. Ambiguity here is where disputes start
- New shares issued = amount raised / price per share

## Option pool shuffle

- A pool created *pre-money* dilutes existing holders only; created *post-money* dilutes everyone
- Investors typically require the pool inside the pre-money — this lowers the effective price
- **Recompute the price with the new pool in the denominator.** The formula above prices off pre-round fully diluted shares; a pool created pre-money adds shares before the round closes, so pricing off the old count sets the price too high and understates dilution
- Always report the effective pre-money after pool expansion, not just the headline number
- **Anti-dilution is a separate mechanic and it is not modeled above.** A down round triggers it: full ratchet reprices the earlier round to the new price, broad-based weighted average reprices part way. Ask which the docs carry before modeling any down round

## Convertible instruments

| Term | Effect at conversion |
|---|---|
| Valuation cap | Converts at the lower of cap price and round price |
| Discount | Converts at round price × (1 − discount) |
| Cap + discount | Whichever gives the holder more shares |
| MFN | Retroactively adopts better terms from later instruments |

- Pre-money vs post-money SAFEs differ materially — post-money SAFEs fix the holder's percentage and push all dilution onto founders
- Multiple SAFEs with different caps convert simultaneously; model them together, never sequentially
- Accrued interest on notes converts too — include it

## Exit waterfall

Order of payment:

1. Debt
2. Preferred liquidation preference, by seniority (stacked, pari passu, or blended — state which)
3. Participating preferred also shares in the remainder; non-participating chooses preference *or* conversion, whichever is greater
4. Common and converted preferred share pro rata

- Compute each preferred series both ways (take preference vs convert) and apply the better outcome per series
- Participation caps stop double-dipping at a stated multiple
- Identify the exit value where each series flips from preference to conversion — that indifference point is the useful output

## Required checks

- Ownership percentages sum to exactly 100% at every stage
- Share counts reconcile: prior total + new issuances + conversions = new total
- Waterfall payouts sum to exactly the exit proceeds
- Founder ownership traced across all rounds in one visible row

## Output

Show ownership before and after, the dilution attributable to each cause (new money, pool, conversions) separately, and for exits the payout per holder at several exit values — never one.
