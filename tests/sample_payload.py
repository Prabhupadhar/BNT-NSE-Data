"""Build a realistic NSE option-chain payload for offline testing.

Mirrors the exact shape and field names of the real
/api/option-chain-indices response so the parser can be exercised
without touching the network.
"""

from __future__ import annotations

from typing import Any


def _leg(strike: float, spot: float, expiry: str, option_type: str) -> dict[str, Any]:
    moneyness = (spot - strike) if option_type == "CE" else (strike - spot)
    last = max(round(moneyness + 120.0, 2), 0.05)
    return {
        "strikePrice": strike,
        "expiryDate": expiry,
        "underlying": "BANKNIFTY",
        "identifier": f"OPTIDXBANKNIFTY{expiry}{option_type}{strike:.0f}",
        "openInterest": 1200 + int(strike) % 900,
        "changeinOpenInterest": (int(strike) % 300) - 150,
        "pchangeinOpenInterest": round(((int(strike) % 300) - 150) / 12.0, 2),
        "totalTradedVolume": 4300 + int(strike) % 2000,
        "impliedVolatility": round(12.5 + (int(strike) % 40) / 10.0, 2),
        "lastPrice": last,
        "change": round((int(strike) % 60) - 30.0, 2),
        "pChange": round(((int(strike) % 60) - 30.0) / 4.0, 2),
        "totalBuyQuantity": 21000,
        "totalSellQuantity": 19500,
        "bidQty": 30 + int(strike) % 60,
        "bidprice": round(last - 1.2, 2),
        "askPrice": round(last + 1.2, 2),
        "askQty": 30 + int(strike) % 45,
        "underlyingValue": spot,
    }


def build_payload(spot: float = 54321.45,
                  expiries: tuple[str, ...] = ("30-Sep-2026", "28-Oct-2026", "25-Nov-2026"),
                  n_strikes: int = 61,
                  step: int = 100,
                  drop_leg: bool = True) -> dict[str, Any]:
    """Return a payload with ``n_strikes`` strikes across ``expiries``."""
    atm = round(spot / step) * step
    strikes = [float(atm + (i - n_strikes // 2) * step) for i in range(n_strikes)]

    data = []
    for expiry in expiries:
        for idx, strike in enumerate(strikes):
            entry: dict[str, Any] = {"strikePrice": strike, "expiryDate": expiry}
            # Deep OTM strikes really do come back with only one side present.
            if not (drop_leg and idx == 0):
                entry["CE"] = _leg(strike, spot, expiry, "CE")
            if not (drop_leg and idx == len(strikes) - 1):
                entry["PE"] = _leg(strike, spot, expiry, "PE")
            data.append(entry)

    return {
        "records": {
            "expiryDates": list(expiries),
            "data": data,
            "timestamp": "27-Aug-2026 14:30:01",
            "underlyingValue": spot,
        },
        "filtered": {"data": [], "CE": {}, "PE": {}},
    }
