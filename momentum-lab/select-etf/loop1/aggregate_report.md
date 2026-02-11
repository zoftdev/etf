# Aggregate: 5 Plans × Batch Optimize

Total configs: 475

## Params Used (`optimal-13etf.json`)

| Param | Value |
|-------|-------|
| corr_long_days | 250 |
| corr_short_days | 10 |
| corr_threshold | 1.0 |
| long_weight | 1.0 |
| lookback_years | 20 |
| mom_periods_days | [21, 63, 126, 189, 252] |
| n_long | 5 |
| n_short | 1 |
| short_weight | 0.2 |
| spread_pct | 0.15 |

## Top 30 by Momentum Sharpe

| plan | group_name | n_long | mom0_cagr | mom0_sharpe | mom0_maxdd |
|------|------------|--------|-----------|-------------|------------|
| plan_a | plan_a-F2-n5-ct08 | 5 | 11.54% | 0.87 | -25.21% |
| plan_a | plan_a-A-n5 | 5 | 11.53% | 0.87 | -25.21% |
| plan_a | plan_a-F1-n5-sw02-m5 | 5 | 11.53% | 0.87 | -25.21% |
| plan_a | plan_a-F2-n5-ct10 | 5 | 11.53% | 0.87 | -25.21% |
| plan_b | plan_b-D-mom126 | 4 | 13.31% | 0.87 | -26.88% |
| plan_c | plan_c-D-mom63-126 | 4 | 13.43% | 0.86 | -30.22% |
| plan_d | plan_d-A-n6 | 6 | 11.82% | 0.86 | -33.74% |
| plan_c | plan_c-A-n6 | 6 | 11.49% | 0.86 | -30.65% |
| plan_a | plan_a-F1-n5-sw03-m5 | 5 | 11.97% | 0.85 | -24.06% |
| plan_d | plan_d-F1-n5-sw02-m252 | 5 | 12.18% | 0.84 | -30.25% |
| plan_a | plan_a-F1-n5-sw02-m4 | 5 | 10.99% | 0.83 | -23.34% |
| plan_e | plan_e-D-mom21-63-126-189 | 4 | 12.46% | 0.83 | -20.88% |
| plan_d | plan_d-F1-n5-sw02-m4 | 5 | 11.90% | 0.83 | -32.57% |
| plan_d | plan_d-F2-n5-ct12 | 5 | 11.72% | 0.83 | -34.68% |
| plan_c | plan_c-D-mom126 | 4 | 13.14% | 0.83 | -32.93% |
| plan_a | plan_a-F1-n5-sw02-m252 | 5 | 10.82% | 0.83 | -24.70% |
| plan_d | plan_d-F1-n5-sw02-m5 | 5 | 11.84% | 0.82 | -34.68% |
| plan_d | plan_d-F2-n5-ct10 | 5 | 11.84% | 0.82 | -34.68% |
| plan_d | plan_d-A-n5 | 5 | 11.84% | 0.82 | -34.68% |
| plan_d | plan_d-F1-n5-sw0-m252 | 5 | 11.65% | 0.82 | -30.25% |
| plan_d | plan_d-F2-n5-ct08 | 5 | 11.72% | 0.82 | -29.32% |
| plan_e | plan_e-F2-n5-ct12 | 5 | 11.05% | 0.82 | -21.45% |
| plan_d | plan_d-F1-n5-sw03-m252 | 5 | 12.34% | 0.82 | -30.25% |
| plan_c | plan_c-F1-n5-sw02-m252 | 5 | 11.59% | 0.82 | -29.02% |
| plan_a | plan_a-F1-n5-sw0-m5 | 5 | 10.40% | 0.82 | -28.42% |
| plan_d | plan_d-F1-n5-sw03-m5 | 5 | 12.22% | 0.81 | -34.68% |
| plan_c | plan_c-D-mom21-63-126-189 | 4 | 12.40% | 0.81 | -27.09% |
| plan_d | plan_d-F1-n5-sw03-m4 | 5 | 12.17% | 0.81 | -32.57% |
| plan_d | plan_d-D-mom63-126 | 4 | 12.80% | 0.81 | -32.79% |
| plan_e | plan_e-D-mom63 | 4 | 12.18% | 0.81 | -35.73% |

## Best per Plan

| plan | group_name | mom0_sharpe | mom0_cagr | mom0_maxdd |
|------|------------|-------------|-----------|------------|
| plan_a | plan_a-F2-n5-ct08 | 0.87 | 11.54% | -25.21% |
| plan_b | plan_b-D-mom126 | 0.87 | 13.31% | -26.88% |
| plan_c | plan_c-D-mom63-126 | 0.86 | 13.43% | -30.22% |
| plan_d | plan_d-A-n6 | 0.86 | 11.82% | -33.74% |
| plan_e | plan_e-D-mom21-63-126-189 | 0.83 | 12.46% | -20.88% |