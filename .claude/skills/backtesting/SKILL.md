---
name: backtesting
description: Design or audit a quantitative strategy backtest — data hygiene, bias removal, cost modeling, and honest performance reporting. Load when the task involves testing a trading or allocation rule against historical data, evaluating a strategy's track record, or judging whether a backtest result is trustworthy. Not for live trading systems, execution or order routing, portfolio construction, or valuing a single asset.
---

# Backtesting

## The default assumption

Most backtests are wrong in the optimistic direction. Every item below removes a specific way a result flatters itself. Treat a strong result as unproven until each has been addressed.

## Biases to eliminate

| Bias | Cause | Fix |
|---|---|---|
| Look-ahead | Using data not available at decision time | Timestamp every input by availability, not by the period it describes |
| Survivorship | Universe excludes dead names | Point-in-time universe including delisted and bankrupt entities |
| Restatement | Fundamentals as later revised | As-first-reported data with the reporting lag applied |
| Selection | Universe chosen after seeing results | Fix the universe before testing |
| Overfitting | Parameters tuned on the test data | Hold out data untouched until the end |

- Corporate actions (splits, dividends, spin-offs) adjusted consistently across price and volume
- Index membership applied as of the date, never today's membership

## Costs

- Commission, spread, market impact, financing, and borrow cost for shorts — all five, all modeled
- Impact scales with size relative to average volume; a strategy that works at small size may not survive at real size
- Test cost sensitivity explicitly: at what cost level does the edge disappear? Report that number
- Slippage assumed at the traded price is optimistic; use the next available price after the signal

## Validation design

- Split in-sample and out-of-sample before any parameter choice
- Walk-forward analysis for time-varying strategies: fit on a rolling window, test on the next, roll
- Count every parameter combination examined — with enough trials, a strong Sharpe ratio appears by chance
- Report the number of independent trials alongside the result; without it the significance is uninterpretable

## Reporting

- Annualized return, volatility, Sharpe ratio, maximum drawdown, drawdown duration, turnover, hit rate
- Full equity curve, not summary statistics alone
- Performance by sub-period — a strategy that made everything in one 6-month window is not a strategy
- Capacity estimate: at what asset level does the return degrade materially?
- Benchmark comparison, and return net of the benchmark's own exposure

## Honest framing

State plainly what the backtest cannot show: regime changes not present in the sample, crowding after publication, and any structural market change since the period tested. A backtest is evidence about the past, never a forecast — say so in the report rather than implying otherwise.
