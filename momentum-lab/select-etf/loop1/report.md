# Batch Research Results

Total runs: 5

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

## Top 20 by Momentum Sharpe (spread=0)


| group_name | n_long | mom0_cagr | mom0_sharpe | mom0_maxdd | bh_cagr | bh_sharpe |
|------------|--------|-----------|-------------|------------|---------|-----------|
| plan_a_quantpedia | 5 | 11.53% | 0.87 | -25.21% | 7.41% | 0.60 |
| plan_d_low_expense | 5 | 11.84% | 0.82 | -34.68% | 8.33% | 0.65 |
| plan_c_long_backtest | 5 | 11.28% | 0.80 | -29.02% | 7.78% | 0.63 |
| plan_e_sector_tilt | 5 | 10.37% | 0.76 | -21.45% | 7.52% | 0.63 |
| plan_b_low_corr | 5 | 8.84% | 0.67 | -25.80% | 5.11% | 0.54 |

## Full Table

| group_name | etfs | n_long | n_short | spread_pct | mom0_cagr | mom0_sharpe | mom0_maxdd | mom_cagr | mom_sharpe | mom_maxdd | bh_cagr | bh_sharpe | bh_maxdd | days |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| plan_a_quantpedia | SPY,IWM,EFA,EEM,IYR,QQQ,LQD,IEF,TIP,GLD,USO,DBC,FXE | 5 | 1 | 0.15 | 11.52750291215483 | 0.8706043427992951 | -25.208256682223784 | 10.518229165358562 | 0.80325359340665 | -25.4548137281854 | 7.41273347158018 | 0.6022583578838455 | -39.141066049595686 | 5067 |
| plan_d_low_expense | SPY,QQQ,IWM,EFA,EEM,TLT,IEF,LQD,GLD,SLV,USO,IYR,VTV | 5 | 1 | 0.15 | 11.844057655619554 | 0.8246104821977636 | -34.67514174071763 | 10.77657390135187 | 0.7602409933913981 | -34.831827332744034 | 8.329053852874125 | 0.6456003492408101 | -38.93198383661205 | 5067 |
| plan_c_long_backtest | SPY,QQQ,IWM,EFA,EEM,VEU,TLT,IEF,LQD,GLD,SLV,USO,FXE | 5 | 1 | 0.15 | 11.276901589265421 | 0.8015867844081599 | -29.01954291839639 | 10.203851342925985 | 0.7351878796943058 | -29.189768281233075 | 7.781306753800998 | 0.633679629060088 | -36.40020608151059 | 5067 |
| plan_e_sector_tilt | SPY,QQQ,IWM,IYR,EFA,EEM,TLT,IEF,LQD,TIP,GLD,USO,DBC,XLU,XLF | 5 | 1 | 0.15 | 10.374356850716548 | 0.7625378409361682 | -21.449236225288615 | 9.233538366093818 | 0.6892913320662205 | -21.661111293721223 | 7.5195829938591086 | 0.6285779721040248 | -39.466041282756095 | 5067 |
| plan_b_low_corr | SPY,EFA,IYR,EEM,TLT,IEF,USO,GLD,UUP,FXE,DBC,TIP,SLV | 5 | 1 | 0.15 | 8.837220187361549 | 0.6700315844349488 | -25.799705489856084 | 7.837973640549367 | 0.6045038068209683 | -26.53115069835913 | 5.111587330304812 | 0.5399933577459682 | -32.47006437385196 | 5067 |