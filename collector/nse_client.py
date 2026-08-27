"""Fetch and parse NSE index option chain snapshots.

Research data collection only. No trading, no broker, no order logic.

NSE's public JSON API rejects requests that do not carry cookies issued by the
main site, so every session is "primed" by visiting the homepage and the
option-chain page first with browser-like headers.
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

IST = ZoneInfo("Asia/Kolkata")

BASE_URL = "https://www.nseindia.com"
API_URL = BASE_URL + "/api/option-chain-indices"

# Pages visited to obtain cookies before hitting the API.
PRIME_URLS = (
    BASE_URL + "/",
    BASE_URL + "/option-chain",
)

SUPPORTED_SYMBOLS = ("NIFTY", "BANKNIFTY")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

API_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": BASE_URL + "/option-chain",
    "X-Requested-With": "XMLHttpRequest",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# Per-leg fields copied straight out of the API response.
LEG_FIELDS = (
    "openInterest",
    "changeinOpenInterest",
    "pchangeinOpenInterest",
    "totalTradedVolume",
    "impliedVolatility",
    "lastPrice",
    "change",
    "pChange",
    "bidQty",
    "bidprice",
    "askPrice",
    "askQty",
    "underlyingValue",
)

log = logging.getLogger(__name__)


class NSEError(RuntimeError):
    """Raised when a snapshot could not be fetched or parsed."""


class NSEClient:
    """A cookie-primed session against nseindia.com.

    One client can be reused for many polls; cookies are refreshed
    automatically whenever NSE starts rejecting requests.
    """

    def __init__(self, timeout: float = 15.0, max_attempts: int = 4) -> None:
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.session: requests.Session | None = None

    # ---------------------------------------------------------------- cookies

    def prime(self) -> None:
        """Start a fresh session and collect NSE's cookies."""
        session = requests.Session()
        session.headers.update(BROWSER_HEADERS)
        for url in PRIME_URLS:
            resp = session.get(url, timeout=self.timeout)
            log.debug("primed %s -> %s", url, resp.status_code)
            resp.raise_for_status()
            # Be a polite client: never fire requests back to back.
            time.sleep(random.uniform(0.6, 1.2))
        if not session.cookies:
            raise NSEError("NSE returned no cookies while priming the session")
        log.info("session primed, %d cookies", len(session.cookies))
        self.session = session

    def _ensure_session(self) -> requests.Session:
        if self.session is None:
            self.prime()
        assert self.session is not None
        return self.session

    # ------------------------------------------------------------------ fetch

    def fetch_raw(self, symbol: str) -> dict[str, Any]:
        """Return the decoded option-chain JSON for ``symbol``.

        Retries with exponential backoff, re-priming cookies when NSE
        answers 401/403 (expired or missing cookies) and backing off on 429.
        """
        symbol = symbol.upper()
        last_error: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):
            session = self._ensure_session()
            try:
                resp = session.get(
                    API_URL,
                    params={"symbol": symbol},
                    headers=API_HEADERS,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_error = exc
                log.warning("%s attempt %d: network error: %s", symbol, attempt, exc)
                self.session = None
            else:
                if resp.status_code == 200:
                    try:
                        payload = resp.json()
                    except ValueError as exc:
                        # NSE sometimes answers 200 with an HTML block page.
                        last_error = NSEError(f"response was not JSON: {exc}")
                        log.warning("%s attempt %d: non-JSON body", symbol, attempt)
                        self.session = None
                    else:
                        if payload.get("records", {}).get("data"):
                            return payload
                        last_error = NSEError("response contained no chain data")
                        log.warning("%s attempt %d: empty chain", symbol, attempt)
                elif resp.status_code in (401, 403):
                    last_error = NSEError(f"HTTP {resp.status_code} (cookies rejected)")
                    log.warning("%s attempt %d: HTTP %d, re-priming",
                                symbol, attempt, resp.status_code)
                    self.session = None
                elif resp.status_code == 429:
                    last_error = NSEError("HTTP 429 (rate limited)")
                    log.warning("%s attempt %d: rate limited", symbol, attempt)
                else:
                    last_error = NSEError(f"HTTP {resp.status_code}")
                    log.warning("%s attempt %d: HTTP %d", symbol, attempt, resp.status_code)

            if attempt < self.max_attempts:
                delay = 2 ** attempt + random.uniform(0, 1)
                log.info("retrying %s in %.1fs", symbol, delay)
                time.sleep(delay)

        raise NSEError(f"could not fetch {symbol} after {self.max_attempts} attempts: {last_error}")


# ----------------------------------------------------------------------- parse


def parse_chain(payload: dict[str, Any], symbol: str,
                collected_at: datetime | None = None) -> list[dict[str, Any]]:
    """Flatten an option-chain payload into one row per strike/expiry/side.

    Every strike and every expiry the API returns is kept; nothing is
    filtered to an ATM window.
    """
    records = payload.get("records") or {}
    rows_in = records.get("data") or []
    if not rows_in:
        raise NSEError(f"{symbol}: payload has no records.data")

    collected_at = collected_at or datetime.now(IST)
    nse_timestamp = records.get("timestamp")
    spot = records.get("underlyingValue")

    rows: list[dict[str, Any]] = []
    for entry in rows_in:
        strike = entry.get("strikePrice")
        expiry = entry.get("expiryDate")
        for option_type in ("CE", "PE"):
            leg = entry.get(option_type)
            if not leg:
                continue  # not every strike trades both sides
            row = {
                "collected_at_ist": collected_at,
                "symbol": symbol,
                "nse_timestamp": nse_timestamp,
                "spot": spot,
                "expiry_date": expiry,
                "strike_price": strike,
                "option_type": option_type,
            }
            for field in LEG_FIELDS:
                row[field] = leg.get(field)
            rows.append(row)

    if not rows:
        raise NSEError(f"{symbol}: no CE/PE legs found in payload")
    return rows


def fetch_snapshot(symbol: str, client: NSEClient | None = None) -> list[dict[str, Any]]:
    """Fetch one option-chain snapshot for ``symbol`` as a list of row dicts."""
    client = client or NSEClient()
    payload = client.fetch_raw(symbol)
    return parse_chain(payload, symbol.upper())
