# KGI Interview: Delta-Neutral Hedging Backtest

## Position & Objective

- **Position:** Short 1 TXO20000P5 (TAIFEX monthly PUT, Strike 20,000, Expiry 2025/04/16)
- **Objective:** Delta-neutral dynamic hedge using TAIFEX TX futures
- **Backtest window:** 2025/03/19 – 2025/04/16 (19 trading days)
- **Execution price rule:** TAIFEX daily settlement price only — no intraday fills

---

## Contract Specifications

| Contract | Multiplier | Unit |
|----------|-----------|------|
| TXO (option) | NT$50 per index point | 1 contract |
| TX (futures) | NT$200 per index point | 1 contract (fractional OK) |

Hedge ratio: for a PUT delta of −d, the short PUT portfolio has delta +d.  
TX contracts to sell = d × (50 / 200) = **d × 0.25**

---

## Data Sources

| Dataset | File | Status | Notes |
|---------|------|--------|-------|
| TXO option chain (Apr 2025) | `data/raw/TXO_20250319-20250416.csv` | ✅ Ready | All 19 trading dates; 86–177 strikes/day (Regular session, 202504 monthly PUT) |
| TX futures (Apr 2025) | `data/raw/TX_20250319-20250416.csv` | ✅ Ready | All 19 dates; `settlement_price` column; expiry day = 0 by TAIFEX convention |
| CBC interest rates | `data/raw/CBC_Interest_Rates.csv` | ✅ Ready | Use **31–90 Day CP Rates in Secondary Market** column; Mar 2025 = 1.60%, Apr 2025 = 1.57% |
| TAIEX price index | `data/raw/^twse_d.csv` | ✅ Ready | Yahoo Finance `^TWII`; 1995-01-05 → 2025-04-16; use `Close` column; date format `YYYY-MM-DD` |
| Final settlement price | `data/raw/Final_settlement_price.png` | ✅ Confirmed | Official TAIFEX 最終結算價 for 202504 = **19,548** |

### Data Notes

**1. Pricing formula — Black's 1976 (implemented)**

TX April-2025 futures price `F_t` is used directly as the forward. Since TXO and TX share the same expiry date, the futures IS the forward — no dividend or carry adjustment needed.

```
d1 = [ln(F/K) + (σ²/2)·T] / (σ·√T)
d2 = d1 − σ·√T
PUT_price = e^(-r·T) · [K·N(-d2) − F·N(-d1)]
PUT_delta  = −e^(-r·T) · N(-d1)   [w.r.t. futures price]
```

**2. Day count convention:** T = calendar days to expiry / 365  
(252 trading-day convention is for HV annualisation only; pricing uses calendar days)

**3. CSV parsing — index_col=False required**

Both TAIFEX CSVs must be read with `index_col=False` to prevent pandas from treating the `date` column as the row index (confirmed issue in Python 3.13 + pandas 2.x).

**4. TX settlement price column**

`TX_20250319-20250416.csv` → `settlement_price` column. Confirm: 2025/03/19 April TX settlement = 22,018.

**5. Expiry-day conventions**

- TX: `settlement_price = 0` on 2025/04/16 → substitute `FINAL_SETTLEMENT = 19_548.0`
- TXO 202504 monthly: `Settlement Price = 0` on 2025/04/16 → substitute intrinsic = max(0, 20000 − 19548) = 452 pts
- Non-zero settlements on Apr 16 belong to weekly contracts (202504W4, 202504W5) that have NOT yet expired

**6. Final settlement — confirmed**

Official TAIFEX 最終結算價 (SOQ) for 202504 = **19,548**  
Cross-check: TXO20000P last traded Close = 452 on Apr 16 → 20,000 − 452 = 19,548 ✓  
Use `FINAL_SETTLEMENT = 19_548.0` throughout the codebase.

**7. Missing trading days (04/03–04/06)**

Gap from 04/02 → 04/07 is correct: 04/03–04/04 were Taiwan market holidays (清明節), 04/05–06 are weekends.

**8. CBC rate interpolation**

Monthly end-of-period data; linearly interpolate to daily. Effectively constant at ~1.58–1.60% annualised over the backtest window.

**9. Vol smile data (for Model 2)**

Filter: `Contract Month(Week) = 202504`, `Call/Put = Put`, `Trading Session = Regular`, `Settlement Price ≥ 0.5` (filter illiquid deep-OTM strikes).  
Resulting smile coverage: 86 strikes on Mar 19 (delta range −0.995 to −0.026) expanding to 177 strikes by Apr 10.

---

## No-Lookahead Rules (enforced in code)

1. On date t, only use data from [t₀, t] — no future prices or vol
2. IV on date t back-solved from same-day settlement price only
3. Hedge trades execute at date t settlement price, using date t Greeks
4. Transaction costs applied on every day with position change (|Δh| > 0)
5. Final settlement = TAIFEX officially published SOQ = 19,548

---

## Transaction Costs

| Item | Amount | Applied |
|------|--------|---------|
| TX (exchange + broker) | NT$100 per contract | Proportional to |Δh| each rebalance day |
| TXO (exchange + broker) | NT$100 per contract | Once at inception (day 0) |
| Slippage | 0 index points | Trading at exact settlement price |

---

## Implemented Models

### Model 1: Black-76 Delta Hedge (Baseline) — ✅ Complete

`notebooks/model1_backtest.ipynb` — 12 sections

- Daily IV back-solved from TXO20000P settlement via bisection
- Delta = BS_delta(F, K=20000, IV, r, T); hedge h = −|delta| × 0.25 TX contracts
- Full P&L attribution: theta, gamma, vega, residual

**Results:**

| Component | NT$ |
|-----------|-----|
| Premium received | +3,400 |
| Option MTM | −19,200 |
| Futures hedge P&L | −18,506 |
| Transaction costs | −161 |
| **Net P&L** | **−34,467** |

**Attribution:**

| Driver | NT$ |
|--------|-----|
| Theta (time decay) | +10,478 |
| Gamma (convexity cost) | −41,219 |
| Vega (vol mark-to-mkt) | −10,990 |
| Delta (futures hedge) | −18,506 |
| Residual | +25,930 |
| **Net** | **−34,467** ✓ |

**Why results differed from expectations (BS null = zero P&L):**
1. Realized vol far exceeded IV on Apr 7–9 (moves 2.1–2.7× breakeven) → gamma dominated theta
2. IV spike from 26% to 62% → vega loss
3. April 7 return z-score = −2.7σ under log-normal BS → fat-tail jump event, not a diffusion

### Model 2: Sticky-Strike vs Sticky-Delta IV Regime — ✅ Complete

`notebooks/model2_sticky_regimes.ipynb` — 8 sections

- **2a Sticky-Strike:** IV from K=20,000 settlement each day (= Model 1)
- **2b Sticky-Delta:** IV interpolated from full vol smile at previous day's delta; fallback to SS when T < 0.008 yr, |δ| > 0.75, or IV_SD > 2 × IV_SS
- For P&L attribution, always use SS-based Greeks (option side identical for both; only futures hedge differs)

**Results:**

| | 2a Sticky-Strike | 2b Sticky-Delta |
|--|--|--|
| Net P&L | −34,467 | −39,278 |
| Futures P&L | −18,506 | −23,309 |
| Option P&L | −15,800 | −15,800 (identical) |

**Key finding:** Sticky-delta was NT$4,811 worse. Mechanism: negative vol skew (lower strikes carry higher IV) causes IV_SD > IV_SS by 5–13 pp pre-crash → larger short futures position → more loss on April 10 recovery (+1,718 pts whipsaw).

**Regime test:** Fixed-strike IV has CV = 32% vs fixed-delta buckets CV = 91–102%. Taiwan equity options follow **sticky-strike** dynamics. Model 2a is the appropriate regime.

---

## Backtest Loop Structure (implemented in `backtest/engine.py`)

```
Day 0 (2025/03/19):
    Sell TXO20000P5 at settlement price P_0 = 68 pts → receive NT$3,400 premium
    Compute IV_0, delta_0, h_0 = −|delta_0| × 0.25 TX contracts
    Pay inception cost = NT$100 (TXO) + NT$100 × |h_0| (TX)

For each trading day t from 2025/03/20 to 2025/04/15:
    1. Load: F_t (TX Apr settlement), P_t (TXO20000P settlement), r_t (CBC CP)
    2. T_t = calendar_days(t, 2025-04-16) / 365
    3. IV_t = implied_vol(F_t, K=20000, r_t, T_t, P_t)  [bisection, Black-76]
    4. Greeks: delta_t, gamma_t, vega_t, theta_t = bs_put_greeks(F_t, K, r_t, T_t, IV_t)
    5. h_t = −|delta_t| × 0.25  [new hedge target, negative = short]
    6. Δh = h_t − h_{t-1}; cost_t = NT$100 × |Δh|
    7. PnL_option_t  = −(P_t − P_{t-1}) × 50
       PnL_futures_t = h_{t-1} × (F_t − F_{t-1}) × 200
       Daily PnL_t   = PnL_option_t + PnL_futures_t − cost_t

Expiry day (2025/04/16):
    8. S_final = 19,548 (official TAIFEX 最終結算價)
    9. PnL_option = −(intrinsic − P_{T-1}) × 50 = −(452 − 258) × 50 = −NT$9,700
    10. PnL_futures = h_{T-1} × (S_final − F_{T-1}) × 200
    11. Close futures position; pay cost = NT$100 × |h_{T-1}|
```

---

## P&L Attribution Framework

| Component | Formula | Sign for short put |
|-----------|---------|-------------------|
| Theta | −Θ_t × OPT_MULT | Positive (earns daily decay) |
| Gamma | −½ × Γ_t × (ΔF)² × OPT_MULT | Negative (suffers large moves) |
| Vega | −V_t × Δσ × OPT_MULT | Negative when vol rises |
| Delta (futures) | h_{t-1} × ΔF × FUT_MULT | Depends on direction |
| Residual | Option PnL − (Theta + Gamma + Vega) | Jump / discrete-hedge error |

Attribution check: Theta + Gamma + Vega + Residual + Delta + Costs = Net PnL ✓

---

## Validation Checklist

- [x] Raw TAIFEX data never mutated; `data/raw/` is read-only
- [x] Settlement price used exclusively (not open/high/low/close)
- [x] Black-76 formula used (futures as forward); no carry adjustment
- [x] IV back-solved from same-day settlement via bisection (no lookahead)
- [x] Day count: calendar days / 365 throughout
- [x] Hedge trades execute at same-day settlement price
- [x] Transaction costs proportional to |Δh| on every rebalance day
- [x] Final settlement = 19,548 (official TAIFEX SOQ, confirmed)
- [x] Multiplier ratio 50/200 = 0.25 applied to convert option delta → TX contracts
- [x] All Greeks recomputed from scratch each day
- [x] `index_col=False` when loading TAIFEX CSVs (prevents date-as-index bug)
- [x] Vol smile built with MIN_PRICE = 0.5 pts filter to exclude illiquid strikes
- [x] Sticky-delta fallback rules: T < 0.008, |δ| > 0.75, IV_SD > 2×IV_SS

---

## Code Directory Layout

```
Delta_Hedging_Strategy/
├── CLAUDE.md
├── README.md
├── models/
│   └── black_scholes.py             # Black-76 price, IV bisection, Greeks
├── backtest/
│   ├── engine.py                    # Main backtest loop (no lookahead)
│   ├── costs.py                     # Transaction cost model
│   └── pnl.py                       # DailyPnL dataclass + attribution
├── notebooks/
│   ├── model1_backtest.ipynb        # Model 1: BS delta (12 sections)
│   ├── model2_sticky_regimes.ipynb  # Model 2: sticky-strike vs sticky-delta (8 sections)
│   ├── fig_cumulative_pnl.png
│   ├── fig_iv_delta.png
│   ├── fig_attribution.png
│   ├── fig_expected_vs_actual.png
│   ├── fig_rv_vs_iv.png
│   ├── fig_jump_risk.png
│   ├── fig_vol_smile.png
│   ├── fig_m2_comparison.png
│   ├── fig_m2_attribution.png
│   ├── fig_m2_iv_spread.png
│   └── fig_m2_regime.png
└── data/
    ├── raw/                         # Immutable source files
    │   ├── TXO_20250319-20250416.csv
    │   ├── TX_20250319-20250416.csv
    │   ├── CBC_Interest_Rates.csv
    │   ├── ^twse_d.csv
    │   └── Final_settlement_price.png
    └── processed/
        ├── model1_results.csv
        ├── model2a_sticky_strike.csv
        └── model2b_sticky_delta.csv
```

---

## Key Assumptions Disclosed

1. **Pricing model:** Black-76 (futures-as-forward); no dividend or carry adjustment needed since TXO and TX share expiry
2. **Risk-free rate:** CBC 31–90 Day CP rate, linearly interpolated daily (~1.58–1.60% annualised)
3. **Day count:** Calendar days / 365 for T in pricing formula
4. **Final settlement:** Official TAIFEX SOQ = 19,548 (confirmed from 盤後資訊)
5. **Fractional futures:** No rounding; e.g., hedge = 0.0221 TX contracts on day 0
6. **Slippage:** Zero (settlement-price execution)
7. **Margin funding cost:** Not modelled (assumed zero)
8. **Sticky-delta fallback:** Falls back to sticky-strike when near-expiry, deep-ITM, or smile extrapolation is unreliable
