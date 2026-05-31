"""
P&L attribution for the short-PUT delta-neutral backtest.

All monetary amounts in NT$.

Option multiplier  : 50 (TXO)
Futures multiplier : 200 (TX)

Short 1 PUT → portfolio is delta-positive in index points.
Futures hedge is SHORT  → futures P&L = -h_{t-1} × ΔF × 200.
"""

from dataclasses import dataclass, field
from typing import Optional


OPT_MULT = 50    # NT$ per index point, TXO
FUT_MULT = 200   # NT$ per index point, TX


@dataclass
class DailyPnL:
    date: str
    # Core P&L components (NT$)
    option_pnl: float = 0.0      # -ΔP × 50  (short put earns when P falls)
    futures_pnl: float = 0.0     # -h_{t-1} × ΔF × 200
    cost: float = 0.0            # transaction costs (always negative)
    total_pnl: float = 0.0

    # Greeks attribution (NT$)
    theta_pnl: float = 0.0       # Θ_t × Δt × 50
    gamma_pnl: float = 0.0       # ½ × Γ_t × (ΔF)² × 50
    vega_pnl: float = 0.0        # Vega_t × Δσ × 50
    residual_pnl: float = 0.0    # total − (theta + delta_hedge + gamma + vega)

    # State
    futures_position: float = 0.0   # h_t in TX contracts (negative = short)
    delta_hedge_change: float = 0.0  # Δh traded today

    # Greeks at t
    delta: Optional[float] = None
    gamma: Optional[float] = None
    vega: Optional[float] = None
    theta: Optional[float] = None
    iv: Optional[float] = None
    F: Optional[float] = None
    P: Optional[float] = None


def compute_daily_pnl(
    date: str,
    F_prev: float,
    F_curr: float,
    P_prev: float,
    P_curr: float,
    h_prev: float,       # futures position BEFORE today's rebalance (TX contracts, negative = short)
    h_curr: float,       # futures position AFTER today's rebalance
    cost: float,
    greeks_prev: dict,   # Greeks computed at end of previous day (used for attribution)
    delta_F: float,      # F_curr - F_prev
    delta_sigma: float,  # IV_curr - IV_prev
) -> DailyPnL:
    """
    Build a DailyPnL record.

    h is expressed as signed TX contracts:
      h < 0 → short futures (hedge for short put which has positive delta)
    Futures P&L = h_prev × ΔF × 200  (h is negative, so profit when ΔF < 0)
    """
    rec = DailyPnL(date=date)

    # Core P&L
    rec.option_pnl = -(P_curr - P_prev) * OPT_MULT     # short put
    rec.futures_pnl = h_prev * delta_F * FUT_MULT       # short futures (h < 0)
    rec.cost = -cost
    rec.total_pnl = rec.option_pnl + rec.futures_pnl + rec.cost

    # Greeks attribution (using Greeks at t-1, i.e., greeks_prev)
    # greeks are for 1 option contract; multiply by OPT_MULT for NT$
    gamma = greeks_prev.get("gamma", 0.0)
    vega = greeks_prev.get("vega", 0.0)
    theta = greeks_prev.get("theta", 0.0)  # already per calendar day

    rec.theta_pnl = -theta * OPT_MULT                   # short put earns theta
    rec.gamma_pnl = -0.5 * gamma * delta_F**2 * OPT_MULT  # short put loses gamma
    rec.vega_pnl = -vega * delta_sigma * OPT_MULT         # short put loses on vol rise

    # Residual = option P&L not explained by theta/gamma/vega (model error, jumps, etc.)
    greeks_total = rec.theta_pnl + rec.gamma_pnl + rec.vega_pnl
    rec.residual_pnl = rec.option_pnl - greeks_total

    rec.futures_position = h_curr
    rec.delta_hedge_change = h_curr - h_prev

    return rec


def compute_expiry_pnl(
    date: str,
    F_prev: float,
    P_prev: float,        # prior-day option settlement price (for incremental MTM)
    S_final: float,       # TAIEX final settlement (best approx)
    K: float,
    h_prev: float,
    cost: float = 0.0,
) -> DailyPnL:
    """
    Final expiry day P&L.

    Option P&L is the incremental change: -(intrinsic - P_prev) × 50.
    Futures close at S_final approximation.
    """
    rec = DailyPnL(date=date)

    intrinsic = max(0.0, K - S_final)
    rec.option_pnl = -(intrinsic - P_prev) * OPT_MULT   # incremental MTM (short put)
    rec.futures_pnl = h_prev * (S_final - F_prev) * FUT_MULT
    rec.cost = -cost
    rec.total_pnl = rec.option_pnl + rec.futures_pnl + rec.cost
    rec.futures_position = 0.0
    rec.delta_hedge_change = -h_prev

    return rec
