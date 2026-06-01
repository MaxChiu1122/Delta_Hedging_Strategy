# Delta_Hedging_Strategy

Delta-neutral dynamic hedging backtest for a short TAIFEX index option position, covering data acquisition, Black-76 pricing, daily rebalancing, P&L attribution, and statistical analysis of hedging error.

---

## The Trade

| Field | Detail |
|-------|--------|
| Position | **Short 1 × TXO20000P5** (TAIFEX monthly PUT, K = 20,000, expiry 2025-04-16) |
| Hedge instrument | TX April-2025 futures (fractional lots allowed) |
| Backtest window | **2025-03-19 → 2025-04-16** (19 trading days) |
| Execution rule | TAIFEX daily settlement price only — no intraday fills |
| Option multiplier | NT$50 per index point |
| Futures multiplier | NT$200 per index point |
| Hedge ratio | 50 / 200 = **0.25 TX contracts per option delta unit** |

---

## Models Overview

| Model | Description | Net P&L |
|-------|-------------|---------|
| **Model 1** | Black-76 delta hedge (baseline) | **−NT$34,467** |
| **Model 2a** | Sticky-Strike IV regime | **−NT$34,467** (= Model 1) |
| **Model 2b** | Sticky-Delta IV regime | **−NT$39,278** |

---

## Model 1: Black-76 Delta Hedge (Baseline)

Uses **Black's 1976 formula** with the TX April-2025 futures price as the forward. Since TXO and TX share the same expiry date, the futures price *is* the cost-of-carry-adjusted forward — no dividend or rate adjustment needed.

$$
d_1 = \frac{\ln(F/K) + \frac{1}{2}\sigma^2 T}{\sigma\sqrt{T}}, \quad
\Delta_{\text{put}} = -e^{-rT}\,N(-d_1)
$$

Each day:
1. Back-solve implied volatility (IV) from the put's settlement price via bisection
2. Compute Black-76 delta
3. Rebalance futures position to `h = |Δ| × 0.25` TX contracts (short)
4. Record P&L: option MTM + futures MTM − transaction costs

**Risk-free rate:** CBC 31–90 Day CP rate (linearly interpolated daily; Mar 2025 = 1.60%, Apr 2025 = 1.57%)  
**Day count:** Calendar days / 365

---

## Data Sources

| Dataset | File | Source |
|---------|------|--------|
| TXO option chain (Apr 2025) | `data/raw/TXO_20250319-20250416.csv` | TAIFEX 盤後資訊 |
| TX futures (Apr 2025) | `data/raw/TX_20250319-20250416.csv` | TAIFEX 盤後資訊 |
| TAIEX price index | `data/raw/^twse_d.csv` | Yahoo Finance `^TWII` |
| CBC interest rates | `data/raw/CBC_Interest_Rates.csv` | CBC 統計資料庫 |
| Final settlement price | `data/raw/Final_settlement_price.png` | TAIFEX 選擇權最終結算價 |

**Final settlement (202504):** Official TAIFEX 最終結算價 = **19,548** (confirmed).  
Consistent with TXO20000P last traded Close = 452 on Apr 16 (20,000 − 452 = 19,548 ✓).

---

## Key Results

| Component | NT$ |
|-----------|-----|
| Premium received (day 0) | +3,400 |
| Option MTM changes | −19,200 |
| Futures hedge P&L | −18,506 |
| Transaction costs | −161 |
| **Net P&L** | **−34,467** |

### P&L Attribution

| Driver | NT$ | Interpretation |
|--------|-----|----------------|
| Theta (time decay) | +10,478 | Short put earns daily decay |
| Delta / futures hedge | −18,506 | Whipsaw during crash + recovery |
| Gamma (convexity cost) | −41,219 | Large moves hurt short gamma |
| Vega (vol mark-to-mkt) | −10,990 | IV spike 26% → 62% hurt short vega |
| Residual (model error) | +25,930 | Discrete hedging / jump residual |
| **Net** | **−34,467** | Attribution check ✓ |

---

## Did Results Differ from Expectations?

**Yes — significantly.** In a Black-Scholes world, a perfectly delta-hedged short put earns **zero per day**: theta collected exactly offsets the gamma cost for a move of size $\sigma_{\text{IV}} \cdot F \cdot \sqrt{dt}$.

The actual net P&L was −NT$34,467. Three factors caused the divergence:

### 1. Gamma dominated Theta (realized vol > implied vol)

The gamma cost (−NT$41,219) dwarfed the theta earned (+NT$10,478). This occurs when realized daily moves exceed the breakeven move implied by IV. During the tariff shock (April 7–9), actual moves were **2.1–2.7× the breakeven** — every such day produces a net theta+gamma loss.

![Expected vs Actual](notebooks/fig_expected_vs_actual.png)

### 2. Volatility spike (vega loss)

IV expanded from ~26% (March) to 62% (April 9). As a short vega position, each 1% rise in IV costs ~NT$490 (vega × 50 multiplier). Total vega P&L: −NT$10,990.

![RV vs IV](notebooks/fig_rv_vs_iv.png)

### 3. Jump risk (the root cause)

Expressing each daily return as a z-score under the log-normal BS model with the previous day's IV:

$$
z_t = \frac{\Delta F_t / F_{t-1}}{\sigma_{\text{IV},t-1} \cdot \sqrt{dt}}
$$

The April 7 move (Trump tariff announcement) produced a z-score of **−2.7σ**, with April 8–9 at −2.5σ and −2.1σ respectively. Under a normal distribution, a sequence of three consecutive moves beyond 2σ has probability < 0.01%. This is a fat-tail / jump event that delta-neutral hedging with daily rebalancing **structurally cannot hedge**.

![Jump Risk](notebooks/fig_jump_risk.png)

**Conclusion:** The loss was not caused by a flaw in the hedging model — it was caused by a tail event (geopolitical shock) that lies outside the diffusion-process assumption of Black-Scholes. No daily-rebalancing delta hedge can protect against overnight jumps of this magnitude without explicit jump-risk premium or real-time monitoring.

---

## Model 2: Sticky-Strike vs Sticky-Delta IV Regime

When the index moves, the option's vol can be read off the market in two ways:

| Regime | Assumption | IV used for delta |
|--------|-----------|-------------------|
| **2a Sticky-Strike** | Vol is anchored to the fixed K=20,000 strike | $\sigma_t = \text{IV}_{\text{mkt}}(K=20000,\,t)$ — same as Model 1 |
| **2b Sticky-Delta** | Vol is anchored to a fixed delta bucket; when spot moves, the vol for the same-delta strike stays constant | $\sigma_t = $ smile$(\delta_{t-1})$, interpolated from all available PUT strikes |

The full 86–177 strike TXO option chain is used each day to build a vol smile. Sticky-delta falls back to sticky-strike when near-expiry (T < 0.008 yr), deeply ITM (|δ| > 0.75), or when the interpolated IV exceeds 2× the K=20,000 IV.

### Results

| Component | 2a Sticky-Strike | 2b Sticky-Delta | Difference |
|-----------|-----------------|----------------|------------|
| Option P&L (premium + MTM) | −15,800 | −15,800 | 0 |
| Futures hedge P&L | −18,506 | −23,309 | −4,803 |
| Transaction costs | −161 | −169 | −8 |
| **Net P&L** | **−34,467** | **−39,278** | **−4,811** |

### P&L Attribution

| Driver | 2a SS | 2b SD | Note |
|--------|-------|-------|------|
| Theta | +10,478 | +10,478 | Identical — same option |
| Gamma | −41,219 | −41,219 | Identical — same option |
| Vega | −10,990 | −10,990 | Identical — same option |
| **Delta (futures hedge)** | **−18,506** | **−23,309** | **Only difference** |
| Residual | +25,930 | +25,930 | Identical |
| **Net** | **−34,467** | **−39,278** | Attribution check ✓ |

The option-side Greeks are identical for both models because the same contract (TXO20000P5) is held throughout — only the futures hedge quantity differs.

### Why Did the Two Models Produce Different P&Ls?

**The mechanism:** Taiwan options have **negative skew** — lower strikes carry higher IV (put demand). When the 20,000 PUT is OTM, the same-delta bucket corresponds to a slightly lower strike with *higher* IV. Sticky-delta therefore uses a higher vol → slightly larger short futures position.

- **Pre-crash (Mar 19–28):** IV_SD exceeded IV_SS by 5–13 pp on most days → sticky-delta built a marginally larger short position.
- **During crash (Apr 7–9):** Fallback to sticky-strike triggered (deep ITM, |δ|>0.75). Both models hedge identically.
- **Recovery (Apr 10):** Market bounced +1,718 pts. Sticky-delta's larger prior short position lost significantly more on this whipsaw.

Net result: the extra hedge built pre-crash added ~NT$3,000 gain during the March drop, but cost ~NT$8,000 more on the April recovery — a net disadvantage of NT$4,811.

![IV Spread and Futures P&L Advantage](notebooks/fig_m2_iv_spread.png)

![P&L Attribution Comparison](notebooks/fig_m2_attribution.png)

### Which Regime Fits Taiwan? — Regime Identification Test

**Test:** Under sticky-strike, IV at a fixed strike should be stable. Under sticky-delta, IV at a fixed delta bucket should be stable. We measure the **coefficient of variation (CV = std/mean)** for each:

| Series | Std (pp) | CV | Verdict |
|--------|----------|----|---------|
| IV(K=20,000) — sticky-strike | 10.7 pp | **32%** | ✅ Much more stable |
| IV(10Δ bucket) — sticky-delta | 53.5 pp | 102% | ❌ Highly unstable |
| IV(25Δ bucket) — sticky-delta | 52.3 pp | 91% | ❌ Highly unstable |

The fixed-strike IV is **3× more stable** than any fixed-delta bucket. This is strong empirical evidence that Taiwan equity index options follow **sticky-strike dynamics** — particularly after the crash, where the vol surface anchored to strike levels rather than delta buckets.

![Regime Stability Test](notebooks/fig_m2_regime.png)

**Conclusion:** Model 2a (sticky-strike) is the more appropriate regime for Taiwan. Sticky-delta introduced unnecessary hedge volatility by tracking OTM put vols that fluctuated wildly during and after the crash. The additional NT$4,811 loss in Model 2b is a direct cost of using the wrong regime assumption.

---

## Repository Structure

```
Delta_Hedging_Strategy/
├── CLAUDE.md                          # Full project specification & data notes
├── README.md
├── models/
│   └── black_scholes.py               # Black-76 pricing, IV bisection, Greeks
├── backtest/
│   ├── engine.py                      # Main backtest loop (no lookahead)
│   ├── costs.py                       # Transaction cost model
│   └── pnl.py                         # P&L attribution framework
├── notebooks/
│   ├── model1_backtest.ipynb          # Model 1 analysis (12 sections)
│   │   ├── fig_cumulative_pnl.png
│   │   ├── fig_iv_delta.png
│   │   ├── fig_attribution.png
│   │   ├── fig_expected_vs_actual.png # Theta+gamma vs BS zero benchmark
│   │   ├── fig_rv_vs_iv.png           # Realized vol vs implied vol
│   │   └── fig_jump_risk.png          # Z-score analysis of Apr 7–9 crash
│   └── model2_sticky_regimes.ipynb   # Model 2 analysis (8 sections)
│       ├── fig_vol_smile.png          # Vol smile on 3 key dates
│       ├── fig_m2_comparison.png      # Cum P&L, IV used, hedge positions
│       ├── fig_m2_attribution.png     # Side-by-side attribution bar chart
│       ├── fig_m2_iv_spread.png       # IV_SD−IV_SS spread and futures advantage
│       └── fig_m2_regime.png          # Regime stability test (SS vs SD)
└── data/
    ├── raw/                           # Immutable source data
    └── processed/                     # model1_results.csv, model2a/2b results
```

---

## How to Run

```bash
# Install dependencies
pip install pandas numpy scipy matplotlib jupyter

# Run Model 1 backtest engine (prints per-day table + summary)
python -m backtest.engine

# Launch notebooks
jupyter notebook notebooks/model1_backtest.ipynb   # Model 1: BS delta hedge
jupyter notebook notebooks/model2_sticky_regimes.ipynb  # Model 2: regime comparison
```

---

## Transaction Cost Assumptions

| Item | Assumption |
|------|-----------|
| TX exchange + broker | NT$100 per contract (proportional for fractional lots) |
| TXO exchange + broker | NT$100 one-time at inception |
| Slippage | 0 (trading at exact settlement price) |
