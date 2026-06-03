"""
Transaction cost model — exact TAIFEX schedule.

Source: TAIFEX 期貨暨選擇權商品相關費用表 (data/raw/Fee.png), section
"一、交易及結算相關費率". Per contract, per side:

  TX  (臺股期貨):  交易經手費 12 + 結算手續費 8 = NT$20 exchange fee
                  期貨交易稅 0.00002 x notional, notional = 200 x F
  TXO (指數選擇權): 交易經手費 6 + 結算手續費 4 = NT$10 exchange fee
                  期貨交易稅 0.001 x premium, premium = 50 x points

Broker commission (手續費) is negotiable / institution-specific and is NOT in
the published schedule, so it is excluded here (effectively ~0 for an
institutional desk). Settlement-day 交割手續費 (NT$8/4) is treated the same as a
closing trade's 交易經手費 for simplicity; the difference is immaterial.
"""

FUT_MULT = 200.0   # NT$ per index point, TX
OPT_MULT = 50.0    # NT$ per index point, TXO

# Exchange handling fees (交易經手費 + 結算手續費), NT$ per contract
TX_EXCHANGE_FEE = 20.0    # 12 + 8
TXO_EXCHANGE_FEE = 10.0   # 6 + 4

# Transaction tax (期貨交易稅), per side
TX_TAX_RATE = 0.00002     # of futures notional
TXO_TAX_RATE = 0.001      # of option premium


def tx_transaction_cost(delta_contracts: float, futures_price: float) -> float:
    """All-in TX cost to trade ``|delta_contracts|`` at ``futures_price``:
    exchange handling fee + futures transaction tax (broker commission excluded).

    Per contract = 20 + 0.00002 * 200 * F = 20 + 0.004 * F.
    """
    per_contract = TX_EXCHANGE_FEE + TX_TAX_RATE * FUT_MULT * futures_price
    return per_contract * abs(delta_contracts)


def txo_inception_cost(premium_points: float, n_contracts: float = 1.0) -> float:
    """All-in TXO cost to trade ``|n_contracts|`` at option price ``premium_points``:
    exchange handling fee + option transaction tax on premium.

    Per contract = 10 + 0.001 * 50 * premium_points = 10 + 0.05 * premium_points.
    """
    per_contract = TXO_EXCHANGE_FEE + TXO_TAX_RATE * OPT_MULT * premium_points
    return per_contract * abs(n_contracts)
