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

Exact TAIFEX schedule (期貨暨選擇權商品相關費用表, `data/raw/Fee.png`), per contract, per side. Broker commission (手續費) is negotiable / institution-specific and excluded.

| Item | Amount | Applied |
|------|--------|---------|
| TX exchange fee | 交易經手費 12 + 結算費 8 = NT$20/contract | Proportional to |Δh| each rebalance |
| TX transaction tax | 0.00002 × (200 × F) per contract | Proportional to |Δh| each rebalance |
| TXO exchange fee | 交易經手費 6 + 結算費 4 = NT$10/contract | Once at inception (day 0) |
| TXO transaction tax | 0.001 × (50 × premium_pts) per contract | Once at inception (day 0) |
| Slippage | 0 index points | Trading at exact settlement price |

TX all-in = **NT$20 + 0.004·F** per contract (≈ NT$88 at F=22,018); TXO all-in = **NT$10 + 0.05·premium_pts** ≈ NT$13 at inception.

---

## Models

| # | Model | Status |
|---|-------|--------|
| 1 | Black-76 Delta Hedge (baseline) | ✅ Complete |
| 2 | Sticky-Strike vs Sticky-Delta IV Regime | ✅ Complete |
| 3 | Minimum Variance Delta | ✅ Complete |
| 4 | Heston Stochastic Volatility | ✅ Complete |
| 5 | Deep Hedging (Buehler et al. 2019) | ✅ Complete |

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
| Transaction costs | −74 |
| **Net P&L** | **−34,380** |

**Attribution:**

| Driver | NT$ |
|--------|-----|
| Theta (time decay) | +10,478 |
| Gamma (convexity cost) | −41,219 |
| Vega (vol mark-to-mkt) | −10,990 |
| Delta (futures hedge) | −18,506 |
| Residual | +25,930 |
| **Net** | **−34,380** ✓ |

**Why results differed from expectations (BS null = zero P&L):**
1. Realized vol far exceeded IV on Apr 7–9 (moves 2.1–2.7× breakeven) → gamma dominated theta
2. IV spike from 26% to 62% → vega loss
3. April 7 return z-score = −2.7σ under log-normal BS → fat-tail jump event, not a diffusion

### Model 2: Sticky-Strike vs Sticky-Delta IV Regime — ✅ Complete

`notebooks/model2_sticky_regimes.ipynb` — 8 sections

- **2a Sticky-Strike:** IV from K=20,000 settlement each day (= Model 1)
- **2b Sticky-Delta:** IV interpolated from full vol smile at previous day's delta; fallback to SS when T < 0.008 yr, |δ| > 0.75, or IV_SD > 2 × IV_SS
- For P&L attribution, always use SS-based Greeks (option side identical for both; only futures hedge differs)

### Model 3: Minimum Variance Delta — ✅ Complete

```
Δ_MV = Δ_BS + Vega_BS × β_σS
```
where `β_σS = Cov(Δσ, ΔS/S) / Var(ΔS/S)` estimated from rolling 60-day regression of daily IV changes on daily index returns (using data prior to t₀ for initialization, updating daily during backtest).

- `^twse_d.csv` close returns + daily IV back-solved from TXO provide the regression inputs
- Initialize from Jan–Mar 2025 (60 trading days before 03/19); update rolling each day
- No lookahead: β_σS at date t uses only data through t−1

### Model 4: Heston Stochastic Volatility — ✅ Complete

- State variables: κ (mean reversion), θ (long-run vol), σ_v (vol of vol), ρ (spot-vol correlation), v₀ (initial variance)
- Calibrate daily using April expiry option chain (all available strikes, 86–177 per day) via COS or Fourier pricing
- Compute Heston delta via finite difference on calibrated model
- Captures smile dynamics that pure BS delta misses

### Model 5: Deep Hedging (Buehler et al. 2019) — ✅ Complete

**Reference paper:** [Buehler et al. 2019, arXiv:1802.03042](https://arxiv.org/abs/1802.03042)  
**Starting point:** `DerivativesHedging.ipynb` (in project root) — a working TF1 implementation for call options on synthetic GBM paths.

#### Compatibility Assessment

The notebook implements the exact paper (policy gradient + LSTM + CVaR objective) and is **directly adaptable** for this project, but requires 6 concrete changes before it can run on our data:

| Issue | Notebook (as-is) | Required for our project |
|-------|-----------------|--------------------------|
| **Framework** | TensorFlow 1.x (`tf.Session`, `tf.placeholder`, `tf.contrib.rnn`) | Migrate to TF2/Keras or PyTorch — TF1 APIs are removed in TF2+ |
| **Option type** | Long CALL: payoff = `max(S_T − K, 0)` | Short PUT: payoff = `−max(K − S_T, 0)`; flip P&L sign |
| **State variables** | `[S_t]` only | `[S_t/K, σ_IV_t, t/T, Δ_{t-1}, cost_per_unit]` — 5 features |
| **Transaction costs** | Not included | TX `(20+0.004·F)×|Δh|` + TXO `(10+0.05·prem)`; affects CVaR objective |
| **Training data** | 50,000 GBM simulated paths | Rolling 19-day windows from `^twse_d.csv` (1995–2024); 7,452 windows available |
| **Multipliers** | Normalized (S_0=100, K=100) | Scale by OPT_MULT=50, FUT_MULT=200; hedge ratio = 0.25 |

#### Adaptation Instructions

**Step 1 — Migrate to TF2/Keras**

Replace the `Agent` class with a standard Keras model:
```python
import tensorflow as tf
from tensorflow import keras

def build_deep_hedge_model(time_steps, n_features, lstm_nodes=[62, 46, 46]):
    inputs = keras.Input(shape=(time_steps, n_features))
    x = inputs
    for n in lstm_nodes[:-1]:
        x = keras.layers.LSTM(n, return_sequences=True)(x)
    x = keras.layers.LSTM(lstm_nodes[-1], return_sequences=True)(x)
    strategy = keras.layers.Dense(1, activation='tanh')(x)   # δ_t ∈ [−1, 1]
    return keras.Model(inputs, strategy)
```

**Step 2 — Change option type and position sign**

The notebook hedges a LONG CALL. We hold a SHORT PUT, so:
```python
# Original (long call):
option_payoff = np.maximum(S_T - K, 0)
hedging_pnl   = -option_payoff + sum(delta_t * dS_t)

# Our project (short put, with multipliers):
option_payoff = np.maximum(K - S_T, 0)                      # put payoff
hedging_pnl   = +option_payoff * OPT_MULT \                 # short put: receive payoff negated
                - sum(delta_t * dF_t * FUT_MULT) \           # short futures: h < 0
                - sum(NT100 * abs(delta_t - delta_{t-1}))    # transaction costs
```

**Step 3 — Expand state variables**

Current state: just `[S_t]`. Required 5-feature state:
```python
# Build state matrix shape (T, n_paths, 5)
state[:, :, 0] = S_t / K                           # moneyness
state[:, :, 1] = IV_t                              # implied vol (back-solve from TXO chain)
state[:, :, 2] = (T - t) / T                       # normalised time remaining
state[:, :, 3] = delta_{t-1}                       # lagged delta (recurrent position)
state[:, :, 4] = TX_COST / (S_t * FUT_MULT * 0.25) # transaction cost ratio
```

**Step 4 — Build training paths from TAIFEX historical data**

Replace `monte_carlo_paths()` with rolling windows from `data/raw/^twse_d.csv`:
```python
spot = pd.read_csv('data/raw/^twse_d.csv')[['Date','Close']]
spot['Date'] = pd.to_datetime(spot['Date'])
spot = spot[spot['Date'] < '2025-01-01'].set_index('Date').sort_index()
# Build rolling 19-day windows (matching backtest length)
WINDOW = 19
paths = np.array([
    spot['Close'].values[i:i+WINDOW]
    for i in range(len(spot) - WINDOW)
])  # shape: (7452, 19)
# To match notebook format: reshape to (T, n_paths, features)
paths_train = paths.T[:, :, np.newaxis]  # shape: (19, 7452, 1)
```
Note: IV for each path can be simulated via BS bisection using the path's rolling HV as σ, or held constant at 26% (inception IV) for a simplified version.

**Step 5 — CVaR loss function (TF2)**

Replace `tf.nn.top_k` with a differentiable CVaR in Keras:
```python
def cvar_loss(alpha=0.95):
    def loss(y_true, pnl):
        # pnl shape: (batch,); CVaR = mean of worst (1-alpha) fraction
        sorted_pnl = tf.sort(pnl)
        n_tail = tf.cast(tf.cast(tf.shape(pnl)[0], tf.float32) * (1 - alpha), tf.int32)
        return -tf.reduce_mean(sorted_pnl[:n_tail])
    return loss
```

**Step 6 — Evaluation on backtest window**

After training, run inference on the actual 2025-03-19 → 2025-04-16 path:
```python
# Real path (19 days, 1 path)
real_path = master['F'].values  # TX April-2025 settlement prices
# Reshape to (19, 1, 5) with proper state features
# Call model.predict(real_path_state)
# Compare daily deltas to Model 1 (BS) deltas
```
Report: RMSE of daily P&L vs. Model 1 baseline, CVaR comparison.

#### Training Configuration

```python
# Match notebook settings, adapted for our data
S_0         = 22018    # TX Apr-2025 settlement on 2025-03-19
K           = 20000    # strike
alpha       = 0.95     # CVaR risk aversion = 95% Expected Shortfall (α=0.50 degenerates to no-hedge; α=0.99 weights rare crashes more)
batch_size  = 256      # rolling windows per batch
epochs      = 200      # increase from notebook's 100 for convergence
lstm_nodes  = [62, 46, 46, 1]   # same as notebook
time_steps  = 19       # backtest window length
n_features  = 5        # expanded state
```

#### Limitations

- RL is data-intensive; 7,478 training windows is marginal — augment with GBM simulation if needed
- The April 7 crash (z = −2.7σ) is a jump event; RL trained on largely diffusion-like paths under-hedges it (held 50–76% of BS delta on Apr 7–9)
- Unlike Models 1–4, the RL strategy is not explainable step-by-step — treat as a black-box benchmark
- CVaR α matters: α=0.50 degenerates to a no-hedge policy; **α=0.95 (95% ES) used here induces a genuine hedge**; α=0.99 would weight rare crashes more but leaves too few tail samples per batch unless batch size is raised

**Results (implemented in `notebooks/model5_deep_hedging.ipynb`):**

| Component | M1 Black-76 | M3 MV Delta | M4 Heston | **M5 Deep Hedging** |
|-----------|-------------|-------------|-----------|---------------------|
| Premium   | +3,400 | +3,400 | +3,400 | +3,400 |
| Option MTM | −19,200 | −19,200 | −19,200 | −19,200 |
| Futures P&L | −18,506 | −16,369 | −22,456 | **−15,585** |
| Costs | −74 | −75 | −74 | −50 |
| **Net P&L** | **−34,380** | **−32,244** | **−38,330** | **−31,434** |

**Key finding:** Trained and evaluated at CVaR₀.₉₅ (95% Expected Shortfall) with the exact TAIFEX cost schedule, the LSTM learns a **genuine hedge** — not the degenerate "do-not-hedge" policy that α=0.50 produces. It runs a **lighter, lower-turnover** book: mean |h| ≈ 0.073 (vs BS 0.097) and **50% less turnover** (0.22 vs 0.43), giving the **lowest cost of any model (−NT$50)** and the **best futures P&L of any directional hedger (−15,585** vs BS −18,506, MV −16,369). It **under-hedges the crash bottom** (holds 33/46/59% of BS delta on Apr 7–9), avoiding most of BS's whipsaw during the crash→rally→crash sequence. Net beats BS by +NT$2,946 — narrowly the best of the five — for the right reason (efficient hedging), not by abstaining. Caveat: the under-hedge at the bottom reflects April 7 being out-of-distribution (<0.5% of training windows), so it helped here partly by luck; the margin over MV delta is only ~NT$810.

**Implementation note:** Uses PyTorch 2.x (not TF2/Keras as originally planned — TF2 not available; PyTorch installed via conda base). Architecture: Input(5) → LSTM-62 → LSTM-46 → Dense(1) → tanh × 0.25. Trained at α=0.95, batch 256, 100 epochs on 7,478 rolling 18-period windows from TAIEX 1995-01-05 → 2025-03-18. Weights cached at `data/processed/model5_weights.pt`.

---

## Backtest Loop Structure (implemented in `backtest/engine.py`)

```
Day 0 (2025/03/19):
    Sell TXO20000P5 at settlement price P_0 = 68 pts → receive NT$3,400 premium
    Compute IV_0, delta_0, h_0 = −|delta_0| × 0.25 TX contracts
    Pay inception cost = TXO (10 + 0.05×P_0) + TX (20 + 0.004×F_0) × |h_0|

For each trading day t from 2025/03/20 to 2025/04/15:
    1. Load: F_t (TX Apr settlement), P_t (TXO20000P settlement), r_t (CBC CP)
    2. T_t = calendar_days(t, 2025-04-16) / 365
    3. IV_t = implied_vol(F_t, K=20000, r_t, T_t, P_t)  [bisection, Black-76]
    4. Greeks: delta_t, gamma_t, vega_t, theta_t = bs_put_greeks(F_t, K, r_t, T_t, IV_t)
    5. h_t = −|delta_t| × 0.25  [new hedge target, negative = short]
    6. Δh = h_t − h_{t-1}; cost_t = (20 + 0.004×F_t) × |Δh|
    7. PnL_option_t  = −(P_t − P_{t-1}) × 50
       PnL_futures_t = h_{t-1} × (F_t − F_{t-1}) × 200
       Daily PnL_t   = PnL_option_t + PnL_futures_t − cost_t

Expiry day (2025/04/16):
    8. S_final = 19,548 (official TAIFEX 最終結算價)
    9. PnL_option = −(intrinsic − P_{T-1}) × 50 = −(452 − 258) × 50 = −NT$9,700
    10. PnL_futures = h_{T-1} × (S_final − F_{T-1}) × 200
    11. Close futures position; pay cost = (20 + 0.004×S_final) × |h_{T-1}|
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
