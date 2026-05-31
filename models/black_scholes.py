"""
Black-76 (futures-based) option pricing, IV bisection, and Greeks.

Uses Black's 1976 formula with TX April futures price F as the forward.
Since TXO and TX share the same expiry, F is the true forward — no
cost-of-carry adjustment needed.
"""

import math
from scipy.stats import norm


def _d1d2(F: float, K: float, r: float, T: float, sigma: float):
    sqrtT = math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sigma**2 * T) / (sigma * sqrtT)
    d2 = d1 - sigma * sqrtT
    return d1, d2


def bs_put_price(F: float, K: float, r: float, T: float, sigma: float) -> float:
    """Black-76 put price. Returns index points."""
    if T <= 0:
        return max(0.0, K - F)
    d1, d2 = _d1d2(F, K, r, T, sigma)
    disc = math.exp(-r * T)
    return disc * (K * norm.cdf(-d2) - F * norm.cdf(-d1))


def bs_put_delta(F: float, K: float, r: float, T: float, sigma: float) -> float:
    """
    Black-76 put delta w.r.t. futures price F.

    For a long put: delta_F = -e^(-rT) * N(-d1)   (negative, ∈ [-1, 0])
    Short put portfolio delta = +e^(-rT) * N(-d1)   (positive)
    """
    if T <= 0:
        return -1.0 if F < K else 0.0
    d1, _ = _d1d2(F, K, r, T, sigma)
    return -math.exp(-r * T) * norm.cdf(-d1)


def bs_put_greeks(F: float, K: float, r: float, T: float, sigma: float) -> dict:
    """
    Returns delta, gamma, vega, theta for a long put (Black-76).

    delta: w.r.t. futures price, annualised
    gamma: second derivative w.r.t. F (index units)
    vega:  sensitivity per 1% move in vol (multiply by 0.01 for Δσ=1pp)
    theta: daily time decay (divide by 365)
    """
    if T <= 0:
        payoff = max(0.0, K - F)
        return {"delta": -1.0 if F < K else 0.0, "gamma": 0.0,
                "vega": 0.0, "theta": 0.0, "price": payoff}

    d1, d2 = _d1d2(F, K, r, T, sigma)
    disc = math.exp(-r * T)
    sqrtT = math.sqrt(T)
    phi_d1 = norm.pdf(d1)

    price = disc * (K * norm.cdf(-d2) - F * norm.cdf(-d1))
    delta = -disc * norm.cdf(-d1)                          # long put, w.r.t. F
    gamma = disc * phi_d1 / (F * sigma * sqrtT)            # w.r.t. F, per index pt
    vega = F * disc * phi_d1 * sqrtT                       # per unit σ (not per 1%)
    # theta in annualised units; divide by 365 for daily
    theta = (-F * disc * phi_d1 * sigma / (2 * sqrtT)
             - r * disc * (K * norm.cdf(-d2) - F * norm.cdf(-d1)))

    return {
        "price": price,
        "delta": delta,
        "gamma": gamma,
        "vega": vega,            # per unit vol (multiply by Δσ directly)
        "theta": theta / 365,    # per calendar day
    }


def implied_vol(
    F: float,
    K: float,
    r: float,
    T: float,
    market_price: float,
    tol: float = 1e-6,
    max_iter: int = 200,
) -> float | None:
    """
    Back-solve IV via bisection given an observed market price (Black-76 put).

    Returns None if the price is outside the no-arbitrage bounds or if
    bisection fails to converge.
    """
    if T <= 0:
        return None

    intrinsic = max(0.0, math.exp(-r * T) * (K - F))
    upper_bound = math.exp(-r * T) * K
    if market_price <= intrinsic or market_price >= upper_bound:
        return None

    lo, hi = 1e-6, 10.0  # vol bounds: 0.0001% to 1000%

    def objective(sigma):
        return bs_put_price(F, K, r, T, sigma) - market_price

    if objective(lo) * objective(hi) > 0:
        return None

    for _ in range(max_iter):
        mid = (lo + hi) / 2
        val = objective(mid)
        if abs(val) < tol or (hi - lo) / 2 < tol:
            return mid
        if val * objective(lo) < 0:
            hi = mid
        else:
            lo = mid

    return (lo + hi) / 2
