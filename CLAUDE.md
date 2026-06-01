# KGI Interview: Delta-Neutral Hedging Backtest

## Position & Objective

- **Position:** Short 1 TXO20000P5 (TAIFEX monthly PUT, Strike 20,000, Expiry 2025/04/16)
- **Objective:** Delta-neutral dynamic hedge using TAIFEX TX futures
- **Backtest window:** 2025/03/19 – 2025/04/16
- **Execution price rule:** TAIFEX daily settlement price only — no intraday fills

---

## Contract Specifications

| Contract | Multiplier | Unit |
|----------|-----------|------|
| TXO (option) | NT$50 per index point | 1 contract |
| TX (futures) | NT$200 per index point | 1 contract (fractional OK) |

Hedge ratio conversion: for a PUT delta of −d, the short PUT portfolio has delta +d (in option units).
Futures contracts needed = d × (50 / 200) = d × 0.25 TX contracts (sell to hedge positive delta).

---

## Data Sources & Fetching

### Data Status (as of 2025-05-31)

| Dataset | File | Status | Notes |
|---------|------|--------|-------|
| TXO option chain (April 2025) | `data/raw/TXO_20250319-20250416.csv` | ✅ Ready | All 19 trading dates; TXO20000P settlement confirmed on all dates; 60+ strikes/day for Heston calibration |
| TX futures (April 2025 contract) | `data/raw/TX_20250319-20250416.csv` | ✅ Ready | All 19 dates; settlement prices in `settlement_price` column (col 11); expiry day shows 0 — see note below |
| CBC interest rates | `data/raw/CBC_Interest_Rates.csv` | ✅ Ready | Monthly through 2025.12; use 31–90 Day CP rate: Mar 2025 = 1.60%, Apr 2025 = 1.57% |
| TAIEX price index | `data/raw/^twse_d.csv` | ✅ Ready | Yahoo Finance `^TWII` daily OHLCV; 1995-01-05 → 2025-04-16 (7,536 rows); confirmed price index (close 03/19 ≈ 21,961 matches TX settlement 22,018 ✓); use `Close` column as S; date format: `YYYY-MM-DD` |
| **Final settlement price (Apr 16)** | `data/raw/Final_settlement_price.png` | ✅ Confirmed | Official TAIFEX 最終結算價 for 202504 = **19,548**. Verified from TAIFEX 盤後資訊 → 選擇權最終結算價. PUT payoff = (20,000 − 19,548) × 50 = **NT$22,600**. |

### Critical Data Notes

**1. Use Black's 1976 formula (preferred) or standard BS with TAIEX spot**

Two valid approaches:

*Option A — Black's 1976 formula (cleaner)*: Use the TX April 2025 futures settlement price `F_t` directly as the forward. Since TXO and TX share the same expiry date, the futures IS the forward and no cost-of-carry adjustment is needed:

```
d1 = [ln(F/K) + (σ²/2)·T] / (σ·√T)
d2 = d1 − σ·√T
PUT_price = e^(-r·T) · [K·N(-d2) − F·N(-d1)]
PUT_delta_futures = −e^(-r·T) · N(-d1)   [delta w.r.t. futures price]
```

The futures hedge size (in TX contracts) = `|PUT_delta_futures| × 0.25`

*Option B — Standard BS with TAIEX spot*: Use `^twse_d.csv` `Close` column as S, CBC CP rate as r, and standard BS formula. Cross-check: on 03/19, TAIEX close ≈ 21,961 vs TX settlement = 22,018 (basis ≈ 57 pts ≈ carry cost for 28-day period at 1.60% ≈ 25 pts + dividend adjustment). Both approaches should give nearly identical deltas given the short expiry.

**2. TX April 2025 settlement price column**

In `TX_20250319-20250416.csv`, the header is:
`date, contract, contract month, open, high, low, last, Change, %, Volume, settlement_price, open_interest, ...`

→ Settlement price = **column 11 (`$11` in awk)**. Column 10 is Volume. Confirm by checking: 2025/03/19 April TX settlement = 22,018.

**3. Final settlement price — confirmed**

On 2025/04/16, all monthly 202504 TXO rows show `settlement_price = 0`. This is TAIFEX's expiry-day file format convention — the official 最終結算價 is published in a separate report.

The non-zero settlement prices visible on April 16 belong to **weekly contracts** that have NOT yet expired:
- `202504W4` — expires April 23, 2025 (4th Wednesday of April)
- `202504W5` — expires April 30, 2025 (5th Wednesday of April)

These are valid daily mark-to-market settlements for still-alive options, not final settlement payoffs.

**Confirmed final settlement (source: `data/raw/Final_settlement_price.png`):**
| Source | Value | PUT Payoff (K=20,000) |
|--------|-------|----------------------|
| **TAIFEX 最終結算價 (official SOQ), Apr 16** | **19,548** | **(20,000 − 19,548) × 50 = NT$22,600** ✅ |
| TXO20000P last traded price, Apr 16 | 452 pts | confirms: 20,000 − 452 = 19,548 ✓ |
| TAIEX closing price, April 16 | 19,468 | (20,000 − 19,468) × 50 = NT$26,600 (not used) |
| TAIEX opening price, April 16 | 19,737 | (20,000 − 19,737) × 50 = NT$13,150 (not used) |

The official settlement (SOQ = 19,548) is confirmed and consistent with the option's last traded price of 452 pts on April 16. Use `FINAL_SETTLEMENT = 19_548.0` throughout the codebase.

**4. Missing trading days (2025/04/03–04/06)**

The TX/TXO data jumps from 04/02 (Wed) to 04/07 (Mon). This is correct: 04/03 and 04/04 were Taiwan market holidays (清明節 bridge day + Tomb Sweeping Day), and 04/05–06 are weekends. No data is missing.

### Extended TAIEX History — Usage by Model

`^twse_d.csv` covers 1995–2025. Use the pre-backtest window as follows:

| Model | Required pre-backtest data | Window |
|-------|---------------------------|--------|
| Historical vol (HV) baseline | `^twse_d.csv` close returns | Rolling 20 or 60 days ending at t−1 |
| MV delta β_σS regression | `^twse_d.csv` close + IV series (back-solved from TXO) | 60 trading days before 03/19 → Jan 2025 |
| Heston warm-start calibration | Full TXO chain (not available pre-03/19); use HV as v₀ proxy | — |
| Deep Hedging training | `^twse_d.csv` full history 1995–2024 | 30 years of daily returns |

For the MV delta β_σS regression initialization, estimate from `^twse_d.csv` daily returns and any available TXO IV data from Jan–Mar 2025. Update the rolling estimate daily during the backtest using only past data.

Date format in `^twse_d.csv` is `YYYY-MM-DD`; TAIFEX files use `YYYY/MM/DD` — align when merging.

### CBC Rate Handling
- Data is monthly end-of-period; interpolate linearly between March and April for daily r
- Use the **31–90 Day CP Rates in Secondary Market** column (second-to-last column)
- For the backtest, r is effectively constant at ~1.58–1.60% annualized

### Implied Volatility Extraction
- Use Black's formula with F = TX April 2025 settlement price (col 11, Regular session), r = CBC CP rate, T = calendar days to expiry / 365
- Alternatively use TAIEX closing price from `^twse_d.csv` (`Close` column) as S with standard BS
- Back-solve σ via bisection given observed TXO20000P settlement price
- Filter: Regular session only (not After-Hours) for both TX and TXO
- Flag and skip IV calculation on the final expiry day (April 16); use prior-day IV for any Greeks needed on that day

---

## No Look-Ahead Bias Rules (CRITICAL)

These rules must be enforced in code, not just documentation.

1. **On date t, only use data from [t₀, t].** No future settlement prices, no future vol.
2. **IV on date t** is computed from the settlement price published at end of day t — never from t+1 onwards.
3. **Historical volatility** (if used for any model) uses a rolling window of *past* returns only: `HV_t = std(log(S_{t-n}/S_{t-n-1}), ..., log(S_t/S_{t-1}))`.
4. **Model calibration** (e.g., Heston) on date t uses only the option chain quoted at end of day t.
5. **Hedge trades execute at date t settlement price**, decided using date t Greeks. Do not use t+1 price to improve the fill.
6. **Vol-of-vol and ρ estimates** (for MV delta) are estimated from a rolling window ending at t−1.
7. **Final settlement price** (2025/04/16) is the TAIFEX officially published TWSE index settlement value, not any intraday quote.

---

## Market Simulation Costs

### Transaction Costs

| Item | Assumption | Rationale |
|------|-----------|-----------|
| TX exchange fee | NT$40 per full contract | TAIFEX published rate |
| TX broker commission | NT$60 per full contract | Competitive institutional rate |
| **TX total** | **NT$100 per contract traded** | Applied proportionally to fractional lots |
| TXO exchange fee | NT$50 per contract | TAIFEX published rate |
| TXO broker commission | NT$50 per contract | One-time at trade inception |
| **TXO total** | **NT$100 per contract** | Paid on day 0 only (initial sale) |

For fractional futures: `cost = NT$100 × |Δhedge_units|` (proportional to notional traded).

### Slippage

| Scenario | Slippage Assumption |
|----------|-------------------|
| Base case | 0 index points (trading at exact settlement) |
| Conservative case | ±1 index point per futures trade (half bid-ask) |

Settlement-price trading has near-zero slippage for institutional flow; the 1-point case is a sensitivity check. Document which assumption is used in the backtest report.

### Margin & Funding Cost
- TX initial margin ≈ NT$120,000 per full contract (TAIFEX published, subject to change)
- Funding cost on margin: apply Taiwan overnight rate (TAIBOR or CBC rate) to daily margin balance
- Default: model margin funding cost as zero unless stated otherwise; note the assumption

### Dividend & Corporate Action Adjustment
- TAIFEX index options are on the price index (not total return); no dividend adjustment needed

---

## Model Implementations

### Model 1: Black-Scholes Delta (Baseline)
```
d1 = [ln(S/K) + (r + σ²/2)·T] / (σ·√T)
Δ_long_put = N(d1) − 1
Portfolio delta (short PUT) = +(1 − N(d1))
Futures to sell = (1 − N(d1)) × 0.25  [in TX contracts]
```
- σ = IV backed out from settlement price each day
- Rebalance daily; record Δhedge = new position − old position and apply cost

### Model 2: Sticky-Strike vs. Sticky-Delta IV Regime
- Sticky-strike: re-imply σ from the **same strike 20000** each day (standard BS rehedge)
- Sticky-delta: re-imply σ from the **same option delta** (i.e., find the strike that had delta d on day t)
- Run both; compare cumulative hedging error; Taiwan equity index tends toward sticky-strike post-shock

### Model 3: Minimum Variance Delta
```
Δ_MV = Δ_BS + Vega_BS × β_σS
```
where `β_σS = Cov(Δσ, ΔS/S) / Var(ΔS/S)` estimated from rolling 60-day regression of daily IV changes on daily index returns (using data prior to t₀ for initialization, updating daily during backtest).

### Model 4: Heston Stochastic Volatility
- State variables: κ (mean reversion), θ (long-run vol), σ_v (vol of vol), ρ (spot-vol correlation), v₀ (initial variance)
- Calibrate daily using April expiry option chain (all available strikes) via COS or Fourier pricing
- Compute Heston delta via finite difference on calibrated model
- Captures smile dynamics that pure BS delta misses

### Model 5: Deep Hedging (ML — Buehler et al. 2019)
- Architecture: LSTM or feedforward with recurrence in position variable
- Objective: minimize `CVaR_{α}(terminal hedging P&L)` with risk aversion parameter λ
- Input features per day: `[S_t/K, σ_IV_t, t/T, Δ_{t-1}, cost_per_unit]`
- Training data: TAIFEX historical paths 2015–2024 (simulate or use actual)
- Evaluate on 2025 out-of-sample; report RMSE of daily P&L vs. BS baseline
- Note: this is the frontier approach; include as comparison, not primary strategy

---

## Backtest Loop Structure

```
For each trading day t from 2025/03/19 to 2025/04/16:

    1. Load settlement prices: S_t, F_t (TX), P_t (TXO20000P5)
    2. Compute time to expiry: T_t = calendar_days(t, 2025-04-16) / 365
    3. Solve IV_t from P_t using BS bisection
    4. Compute Greeks: Δ_t, Γ_t, Vega_t, Θ_t
    5. Compute required hedge: h_t = model_delta(t) × 0.25  [TX contracts]
    6. Trade: Δh = h_t − h_{t-1}; apply cost = NT$100 × |Δh|
    7. Record: P&L_option = −(P_t − P_{t-1}) × 50  [short PUT]
               P&L_futures = h_{t-1} × (F_t − F_{t-1}) × 200 × (−1)  [short futures]
               Daily P&L = P&L_option + P&L_futures − cost_t

Final day (2025/04/16 expiry):
    8. Option payoff = max(0, 20000 − S_final) × 50  [paid by short PUT seller]
    9. Futures settled at F_final
    10. Net P&L = premium_received_day0 − cumulative_payoff − cumulative_costs
```

---

## P&L Attribution Framework

Break down total P&L into:

| Component | Formula | Interpretation |
|-----------|---------|----------------|
| Theta P&L | Θ_t × Δt | Time decay earned (benefit of short option) |
| Delta hedge P&L | h_{t-1} × ΔF × 200 × (−1) | Gain/loss from futures hedge |
| Gamma P&L | ½ × Γ_t × (ΔS)² × 50 | Cost of gamma (negative for short gamma) |
| Vega P&L | Vega_t × Δσ × 50 | Vol mark-to-market P&L |
| Residual | Total − (Θ + Delta + Gamma + Vega) | Model error, jumps, discrete rehedge cost |

Theta + Gamma P&L should roughly cancel in a BS world (Theta earned ≈ Gamma cost). Deviations from this explain the hedging shortfall.

---

## Validation Checklist

- [ ] Raw TAIFEX data stored with download timestamp; never mutated
- [ ] Settlement price used exclusively (not open/high/low/close of intraday)
- [ ] IV computation uses S = TAIEX spot at close, same-day settlement option price
- [ ] Hedge trade executes at same-day settlement; not next-day open
- [ ] Transaction costs applied only on days with position change (|Δh| > 0)
- [ ] Final expiry payoff uses TAIFEX-published final settlement index (TWSE index at 1:30 PM on expiry day)
- [ ] Multiplier ratio 50/200 = 0.25 applied when converting option delta to TX contracts
- [ ] All Greeks recomputed from scratch each day (no carry-forward from prior day)
- [ ] Option chain data used for Heston calibration is from same-day settlement only

---

## Code Directory Layout

```
kgi-interview/
├── CLAUDE.md
├── data/
│   ├── fetch_taifex_options.py      # TXO settlement scraper
│   ├── fetch_taifex_futures.py      # TX settlement scraper
│   ├── fetch_spot.py                # TAIEX spot via yfinance or TWSE
│   ├── raw/                         # Immutable raw CSVs (timestamped)
│   └── processed/                   # Cleaned & merged datasets
├── models/
│   ├── black_scholes.py             # BS price, IV bisection, Greeks
│   ├── minimum_variance.py          # MV delta estimation
│   ├── heston.py                    # Heston calibration & delta
│   └── deep_hedging.py              # LSTM hedger (train + infer)
├── backtest/
│   ├── engine.py                    # Main backtest loop (no lookahead)
│   ├── costs.py                     # Transaction cost & slippage model
│   └── pnl.py                       # P&L attribution (greeks breakdown)
├── notebooks/
│   └── results_analysis.ipynb       # Charts, comparison across models
└── report/
    └── slides.pdf                   # 5-minute presentation output
```

---

## Key Assumptions to Disclose in Presentation

1. **Underlying proxy:** TAIEX spot index used as S (not futures price); minor basis exists
2. **Risk-free rate:** CBC 91-day CP rate, treated as constant over the period
3. **No transaction cost on final expiry:** Option expires; no closing trade needed
4. **Fractional futures:** As specified, no rounding applied to hedge quantity
5. **Vol surface for Heston:** If only one or two strikes available near 20000, Heston calibration is ill-conditioned; document data availability
6. **Deep Hedging training:** Pre-trained on 2015–2024 TAIFEX paths; 2025 is strictly out-of-sample
7. **Settlement vs. TAIEX basis:** TX futures price may differ from TAIEX spot by basis; when using futures price in Black-Scholes, adjust with cost-of-carry if significant
