"""
Transaction cost and slippage model.

Costs are proportional to notional traded (fractional lots allowed).
"""

TX_COST_PER_CONTRACT = 100.0   # NT$100 per full TX contract (exchange + broker)
TXO_COST_PER_CONTRACT = 100.0  # NT$100 one-time at inception


def tx_transaction_cost(delta_contracts: float) -> float:
    """Cost for changing the futures hedge by delta_contracts TX lots."""
    return TX_COST_PER_CONTRACT * abs(delta_contracts)


def txo_inception_cost(n_contracts: float = 1.0) -> float:
    """One-time cost for selling the TXO option at inception."""
    return TXO_COST_PER_CONTRACT * abs(n_contracts)
