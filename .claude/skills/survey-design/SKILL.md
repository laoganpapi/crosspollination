---
name: survey-design
description: Survey construction and analysis — sampling honesty, question wording, scales, minimum sample sizes, crosstab discipline, the PMF question. Load when designing a questionnaire, choosing sample sizes, or analyzing survey results. Not for interview design (customer-discovery) or price-specific instruments (pricing-research).
---

# Survey design

## Cases against a survey

- A survey measures constructs you already understand; it cannot discover them. Before qualitative interviewing you don't know the right questions, the respondents' vocabulary, or the answer options — a premature survey returns confident garbage.
- Sequence: interviews to find the categories, survey to size them.
- Also wrong for: complex causal questions, anything respondents can't accurately self-report (future behavior, precise past spend), and decisions where n will be too small to split.

## Sampling honesty

- You may only generalize to the population the sample was drawn from. A survey of your mailing list describes your mailing list, not the market.
- Name the target population first; then trace how each respondent got in and who was systematically excluded (non-customers, churned users, email-ignorers).
- Self-selected samples skew toward the engaged and the annoyed. Convenience-frame results get reported as directional, and say so.

## Question construction

- One concept per question — "easy to set up and use" is two questions; split every "and".
- No leading or loaded wording; small changes swing results by double digits ("welfare" vs. "assistance to the poor" moved support 20+ points). Pretest wording.
- Balanced scales: equal positive and negative options, a true midpoint, a "don't know" wherever honest ignorance exists.
- Randomize item order within batteries — prior questions shift later answers. Sensitive and demographic items last.
- Ask about specific, recent, bounded behavior ("in the past 30 days"), never "typical" behavior.

## Scales and screening

- 5- or 7-point fully labeled scales; one direction throughout. Prefer behavioral or categorical answers over agree/disagree batteries — agreement invites acquiescence bias.
- Screeners qualify on behavior without telegraphing the desired answer; hide the qualifying option among plausible alternatives. Add an attention check in panel samples.

## Satisficing

- Rises with length, grids, and repetitive scales. Under ~10 minutes; break up grids; vary formats.
- Before analysis, remove straight-liners (identical answers down a battery) and speeders (under ~40% of median completion time).

## Minimum n

| Use | Completes |
|---|---|
| Directional read, one segment | ~100 |
| Comparing two segments | 100–150 per cell |
| Margin of error | n=100 ≈ ±10 points; n=400 ≈ ±5 |

Decide the crosstab cells before fielding and size for the smallest. Can't reach cell sizes? Don't field — interview instead.

## Analysis discipline

- Crosstabs before any modeling: every key question by segment, source, and screener status. Most findings — and most artifacts — show up there.
- Significance honesty: with 20 comparisons, one clears p<.05 by chance. Declare primary questions in advance; everything else is exploratory; never report a hunted-for subgroup difference as confirmatory.
- Base sizes on every chart.

## The PMF question

"How would you feel if you could no longer use this product?" — very / somewhat / not disappointed. The 40%-very-disappointed benchmark signals product-market fit.

- Ask only recent, repeated users; meaningless pre-launch or on non-users.
- Segment the very-disappointed group to find who the product truly fits — it's a compass for iteration, not a market-demand measure.

## Failure modes

Surveying before discovery · double-barrels and leading stems · generalizing a convenience sample · n=12 cells reported as findings · stated intent treated as forecast · non-response bias ignored · twenty-minute questionnaires answered by straight-lining · cherry-picking the one significant crosstab
