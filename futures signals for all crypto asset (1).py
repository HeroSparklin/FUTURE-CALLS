#!/usr/bin/env python3
"""
Crypto futures signal notifier that scans ALL USDT perpetual futures.

Combines RSI, EMA crossover and MACD. Once per candle close it scans every
listed coin and sends one alert digest for coins where at least MIN_AGREE
indicators point the same way within the last LOOKBACK closed candles.

Signals are informational only, not financial advice.

Setup:
  pip install requests pandas numpy
  export TELEGRAM_BOT_TOKEN="123:abc"   # from @BotFather
  export TELEGRAM_CHAT_ID="123456789"   # from @userinfobot
  python futures_signals.py
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

# ---------- Settings ----------
INTERVAL = "15m"                 # 1m, 5m, 15m, 30m, 1h, 4h, 1d
MIN_QUOTE_VOLUME = 5_000_000     # skip coins trading < $5M/24h (set 0 for truly all)
EXCLUDE = set()                  # e.g. {"BTCUSDT"} to skip specific symbols
LOOKBACK = 3                     # indicator events count if within last N candles
MIN_AGREE = 2                    # how many of the 3 indicators must agree
RSI_PERIOD, RSI_LOW, RSI_HIGH = 14, 30, 70
EMA_FAST, EMA_SLOW = 9, 21
WORKERS = 8                      # parallel requests (keep modest for rate limits)
SYMBOL_REFRESH_SEC = 3600        # re-check the coin list hourly (new listings)

BASE = "https://fapi.binance.com"  # public endpoints, no API key needed
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")

INTERVAL_SEC = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800,
                "1h": 3600, "4h": 14400, "1d": 86400}


# ---------- Indicators ----------
def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def ema(close: pd.Series, n: int) -> pd.Series:
    return close.ewm(span=n, adjust=False).mean()


def macd(close: pd.Series):
    line = ema(close, 12) - ema(close, 26)
    signal = line.ewm(span=9, adjust=False).mean()
    return line, signal


def crossed_up(a: pd.Series, b) -> pd.Series:
    b = b if isinstance(b, pd.Series) else pd.Series(b, index=a.index)
    return (a > b) & (a.shift(1) <= b.shift(1))


def crossed_down(a: pd.Series, b) -> pd.Series:
    b = b if isinstance(b, pd.Series) else pd.Series(b, index=a.index)
    return (a < b) & (a.shift(1) >= b.shift(1))


def evaluate(close: pd.Series):
    """Return (direction, reasons) for the latest closed candle."""
    r = rsi(close, RSI_PERIOD)
    fast, slow = ema(close, EMA_FAST), ema(close, EMA_SLOW)
    m_line, m_sig = macd(close)

    def recent(s: pd.Series) -> bool:
        return bool(s.iloc[-LOOKBACK:].any())

    bull = {
        f"RSI up through {RSI_LOW}": recent(crossed_up(r, RSI_LOW)),
        f"EMA{EMA_FAST} above EMA{EMA_SLOW}": recent(crossed_up(fast, slow)),
        "MACD above signal": recent(crossed_up(m_line, m_sig)),
    }
    bear = {
        f"RSI down through {RSI_HIGH}": recent(crossed_down(r, RSI_HIGH)),
        f"EMA{EMA_FAST} below EMA{EMA_SLOW}": recent(crossed_down(fast, slow)),
        "MACD below signal": recent(crossed_down(m_line, m_sig)),
    }
    bull_hits = [k for k, v in bull.items() if v]
    bear_hits = [k for k, v in bear.items() if v]

    if len(bull_hits) >= MIN_AGREE and len(bull_hits) > len(bear_hits):
        return "LONG", bull_hits
    if len(bear_hits) >= MIN_AGREE and len(bear_hits) > len(bull_hits):
        return "SHORT", bear_hits
    return None, []


# ---------- Exchange data ----------
def api_get(path: str, params=None):
    """GET with basic rate-limit handling."""
    for attempt in range(4):
        resp = requests.get(BASE + path, params=params, timeout=15)
        if resp.status_code in (418, 429):
            wait = int(resp.headers.get("Retry-After", 30))
            print(f"Rate limited, sleeping {wait}s", flush=True)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"Too many rate-limit retries for {path}")


def get_symbols() -> list:
    """All actively trading USDT perpetuals above the volume floor."""
    info = api_get("/fapi/v1/exchangeInfo")["symbols"]
    live = {
        s["symbol"] for s in info
        if s["contractType"] == "PERPETUAL"
        and s["status"] == "TRADING"
        and s["quoteAsset"] == "USDT"
    }
    vols = {t["symbol"]: float(t["quoteVolume"]) for t in api_get("/fapi/v1/ticker/24hr")}
    syms = [s for s in live if vols.get(s, 0) >= MIN_QUOTE_VOLUME and s not in EXCLUDE]
    return sorted(syms)


def fetch_closes(symbol: str) -> pd.Series:
    rows = api_get("/fapi/v1/klines",
                   {"symbol": symbol, "interval": INTERVAL, "limit": 200})[:-1]
    return pd.Series([float(x[4]) for x in rows], index=[x[6] for x in rows])


def scan_one(symbol: str):
    try:
        close = fetch_closes(symbol)
        if len(close) < 60:  # too little history (new listing)
            return None
        direction, reasons = evaluate(close)
        if direction:
            return symbol, direction, float(close.iloc[-1]), reasons, close.index[-1]
    except Exception as e:
        print(f"{symbol}: {e}", flush=True)
    return None


# ---------- Notifications ----------
def notify(text: str):
    print(text, flush=True)
    if not (TG_TOKEN and TG_CHAT):
        return
    # Telegram messages max out at 4096 chars, so split long digests
    chunks, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > 3800:
            chunks.append(cur)
            cur = ""
        cur += line + "\n"
    chunks.append(cur)
    for c in chunks:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                          data={"chat_id": TG_CHAT, "text": c}, timeout=10)
        except requests.RequestException as e:
            print(f"Telegram send failed: {e}", flush=True)


def fmt(sig) -> str:
    sym, direction, price, reasons, _ = sig
    return f"{sym} @ {price:g}: {', '.join(reasons)}"


# ---------- Main loop ----------
def main():
    step = INTERVAL_SEC[INTERVAL]
    symbols, refreshed = get_symbols(), time.time()
    notify(f"Signal bot started: scanning {len(symbols)} USDT perpetuals on {INTERVAL}")
    last_alert = {}  # symbol -> (direction, candle close time)

    while True:
        # Wait for the next candle close (+5s so the exchange has finalised it)
        time.sleep(step - (time.time() % step) + 5)

        if time.time() - refreshed > SYMBOL_REFRESH_SEC:
            try:
                symbols, refreshed = get_symbols(), time.time()
            except Exception as e:
                print(f"Symbol refresh failed: {e}", flush=True)

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            results = [r for r in pool.map(scan_one, symbols) if r]

        longs, shorts = [], []
        for sig in results:
            sym, direction, _, _, candle = sig
            if last_alert.get(sym) == (direction, candle):
                continue
            last_alert[sym] = (direction, candle)
            (longs if direction == "LONG" else shorts).append(sig)

        if longs or shorts:
            msg = f"Signals ({INTERVAL}, {len(symbols)} coins scanned)\n"
            if longs:
                msg += "\nLONG:\n" + "\n".join(fmt(s) for s in longs) + "\n"
            if shorts:
                msg += "\nSHORT:\n" + "\n".join(fmt(s) for s in shorts) + "\n"
            msg += "\nNot financial advice. Check the chart and use a stop."
            notify(msg)


if __name__ == "__main__":
    main()
