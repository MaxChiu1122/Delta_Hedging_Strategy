"""
Heston (1993) stochastic volatility model for European put pricing on futures.

The model dynamics (risk-neutral, futures with zero drift):
    dF/F  = sqrt(v) dW_F
    dv    = κ(θ − v) dt + σ_v sqrt(v) dW_v
    corr(dW_F, dW_v) = ρ

Characteristic function (Albrecher et al. 2007 "Little Trap" form):
    φ(ω) = E^Q[exp(iω log(F_T/F))]
    avoids the branch-cut discontinuity that appears in the original Heston (1993) form.

Put pricing via Gil-Pelaez inversion (verified to reproduce Black-76 as σ_v → 0).
"""

import numpy as np
from scipy.optimize import minimize


def _cf(omega_arr, F, v0, kappa, theta, sigma_v, rho, T):
    """
    Vectorized Heston CF of log(F_T/F) over complex omega_arr.
    Albrecher (2007) form: g = (ξ−h)/(ξ+h), uses exp(−hT) to stay bounded.
    """
    omega = np.asarray(omega_arr, dtype=complex)
    xi   = kappa - rho * sigma_v * 1j * omega
    disc = xi**2 + sigma_v**2 * (1j * omega + omega**2)
    h    = np.sqrt(disc)
    # Force Re(h) ≥ 0 so exp(−hT) decays for large T
    h    = np.where(np.real(h) < 0, -h, h)

    g    = (xi - h) / (xi + h)
    eht  = np.exp(-h * T)

    log_arg = (1.0 - g * eht) / (1.0 - g)
    C = (kappa * theta / sigma_v**2) * ((xi - h) * T - 2.0 * np.log(log_arg))
    D = (xi - h) / sigma_v**2 * (1.0 - eht) / (1.0 - g * eht)

    return np.exp(C + D * v0)


def heston_put_prices_batch(F, K_arr, r, T, v0, kappa, theta, sigma_v, rho, N=256):
    """
    Vectorized Heston European put prices for multiple strikes.

    Formula (Gil-Pelaez two-probability inversion, verified vs Black-76):
        P_put = e^{−rT} · (K·P2 − F·P1)
        P2 = P^Q(F_T < K),  P1 = P^S(F_T < K)

        P_j = 1/2 − (1/π) ∫₀^∞ Im[e^{iωm}·φ_j(ω)] / ω dω
        m   = log(F/K)
        φ_2(ω) = φ(ω)          (risk-neutral CF at real ω)
        φ_1(ω) = φ(ω − i)      (forward-measure CF; φ(−i) = 1 for futures)

    Parameters
    ----------
    N : int  Number of quadrature points (256 is fast and accurate for typical T).
    """
    K_arr = np.asarray(K_arr, dtype=float)
    if T < 1e-6:
        return np.maximum(0.0, K_arr - F) * np.exp(-r * T)

    omega = np.linspace(1e-3, 200.0, N)   # real frequencies, (N,)
    dw    = omega[1] - omega[0]

    cf2 = _cf(omega,        F, v0, kappa, theta, sigma_v, rho, T)  # (N,)
    cf1 = _cf(omega - 1.0j, F, v0, kappa, theta, sigma_v, rho, T)  # (N,)

    m     = np.log(F / K_arr)                            # (M,)
    phase = np.exp(1.0j * omega[None, :] * m[:, None])  # (M, N)

    I2 = np.imag(phase * cf2[None, :]) / omega[None, :]  # (M, N)
    I1 = np.imag(phase * cf1[None, :]) / omega[None, :]  # (M, N)

    P2 = np.clip(0.5 - (dw / np.pi) * np.trapezoid(I2, axis=1), 0.0, 1.0)  # (M,)
    P1 = np.clip(0.5 - (dw / np.pi) * np.trapezoid(I1, axis=1), 0.0, 1.0)  # (M,)

    prices = np.exp(-r * T) * (K_arr * P2 - F * P1)
    return np.maximum(0.0, prices)


def heston_put_price(F, K, r, T, v0, kappa, theta, sigma_v, rho):
    """Single-strike Heston put price."""
    return float(heston_put_prices_batch(F, [K], r, T, v0, kappa, theta, sigma_v, rho)[0])


def heston_put_delta(F, K, r, T, v0, kappa, theta, sigma_v, rho, bump_pct=1e-3):
    """Put delta w.r.t. futures price F via central finite difference."""
    dF  = max(F * bump_pct, 5.0)
    Pup = heston_put_price(F + dF, K, r, T, v0, kappa, theta, sigma_v, rho)
    Pdn = heston_put_price(F - dF, K, r, T, v0, kappa, theta, sigma_v, rho)
    return (Pup - Pdn) / (2.0 * dF)


def _objective(params, F, K_arr, P_mkt, r, T):
    kappa, theta, sigma_v, rho, v0 = params
    feller_slack = 2.0 * kappa * theta - sigma_v**2
    if feller_slack < -0.01:
        return 1e8 + 1e6 * (-feller_slack)
    try:
        P_model = heston_put_prices_batch(F, K_arr, r, T, v0, kappa, theta, sigma_v, rho)
        wt = 1.0 / np.maximum(P_mkt, 1.0)   # relative weighting (down-weights deep OTM)
        return float(np.mean(wt * (P_model - P_mkt) ** 2))
    except Exception:
        return 1e8


def calibrate_heston(F, K_arr, P_mkt, r, T, x0=None, n_starts=3):
    """
    Calibrate [kappa, theta, sigma_v, rho, v0] to market put prices.

    Returns
    -------
    params : ndarray  shape (5,), order [kappa, theta, sigma_v, rho, v0]
    rmse   : float    root-mean-squared pricing error (index points)
    """
    K_arr = np.asarray(K_arr, dtype=float)
    P_mkt = np.asarray(P_mkt, dtype=float)

    bounds = [
        (0.1,  8.0),    # kappa
        (0.005, 0.8),   # theta (long-run variance; sqrt = long-run vol)
        (0.05,  2.0),   # sigma_v (vol-of-vol)
        (-0.99, -0.01), # rho (equity: always negative)
        (0.005, 1.0),   # v0 (initial variance)
    ]

    # Initial variance from ATM option (rough approximation)
    atm_idx = int(np.argmin(np.abs(K_arr - F)))
    P_atm   = float(P_mkt[atm_idx])
    iv_sq0  = np.clip(
        (P_atm / (F * np.sqrt(T / (2 * np.pi)))) ** 2 if T > 1e-6 else 0.04,
        0.005, 0.8
    )

    starts = []
    if x0 is not None:
        starts.append(np.clip(np.asarray(x0, dtype=float),
                              [b[0] for b in bounds], [b[1] for b in bounds]))
    starts += [
        np.array([2.0, iv_sq0,       0.50, -0.70, iv_sq0]),
        np.array([3.0, iv_sq0,       0.80, -0.55, iv_sq0]),
        np.array([1.5, iv_sq0 * 1.2, 0.35, -0.85, iv_sq0]),
    ]

    best, best_fun = None, np.inf
    for s in starts[:n_starts]:
        s = np.clip(s, [b[0] for b in bounds], [b[1] for b in bounds])
        try:
            res = minimize(_objective, s, args=(F, K_arr, P_mkt, r, T),
                           method='L-BFGS-B', bounds=bounds,
                           options={'maxiter': 500, 'ftol': 1e-10})
            if res.fun < best_fun:
                best, best_fun = res, res.fun
        except Exception:
            pass

    if best is None:
        params = np.array([2.0, iv_sq0, 0.5, -0.7, iv_sq0])
        return params, np.nan

    kappa, theta, sigma_v, rho, v0 = best.x
    P_model = heston_put_prices_batch(F, K_arr, r, T, v0, kappa, theta, sigma_v, rho)
    rmse = float(np.sqrt(np.mean((P_model - P_mkt) ** 2)))
    return best.x, rmse
