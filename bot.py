import os
import requests
import time
import statistics

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# === CONFIG - YOUR REQUEST ===
LEVERAGE_TEXT = "10x Isolated" # RETAINED
MIN_VOLUME_USD = 2_000_000 # Filter out low volume scam coins
MIN_PRICE = 0.01 # Filter out coins under 1 cent
SL_PCT = 0.03 # Changed from 1.5% to 3% - you were getting wicked out
TP1_PCT = 0.03 # Changed from 2% to 3% = 1:1
TP2_PCT = 0.06 # Changed from 4.5% to 6%
TP3_PCT = 0.09 # Changed from 7% to 9%

OKX_TICKER_URL = "https://www.okx.com/api/v5/market/tickers?instType=SWAP"
OKX_CANDLE_URL = "https://www.okx.com/api/v5/market/candles"

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing secrets")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"TG Error {e}")

def get_candles(instId, limit=100):
    try:
        params = {"instId": instId, "bar": "15m", "limit": str(limit)}
        r = requests.get(OKX_CANDLE_URL, params=params, timeout=10).json()
        if r.get("code") == "0":
            # data: [ts, o, h, l, c, vol,...] newest first in OKX, reverse it
            data = list(reversed(r["data"]))
            closes = [float(c[4]) for c in data]
            return closes
    except:
        pass
    return []

def get_btc_trend():
    """Returns 'UP', 'DOWN', 'FLAT' based on BTC 15m EMA 20"""
    closes = get_candles("BTC-USDT-SWAP", 50)
    if len(closes) < 25:
        return "FLAT"
    ema20 = sum(closes[-20:]) / 20
    current = closes[-1]
    if current > ema20 * 1.001:
        return "UP"
    if current < ema20 * 0.999:
        return "DOWN"
    return "FLAT"

def score_coin(ticker, btc_trend):
    try:
        instId = ticker["instId"] # e.g. W-USDT-SWAP
        last = float(ticker["last"])
        vol24 = float(ticker["vol24h"]) * last # approx USD vol
        change24 = float(ticker.get("change24h", 0)) * 100 if ticker.get("change24h") else 0

        # === NEW FILTERS TO STOP LOSING ===
        if last < MIN_PRICE: return None
        if vol24 < MIN_VOLUME_USD: return None
        if "USDT" not in instId: return None

        # Avoid leveraged tokens and weird pairs
        if "BULL" in instId or "BEAR" in instId or "3L" in instId or "3S" in instId:
            return None

        closes = get_candles(instId, 50)
        if len(closes) < 30: return None

        volatility = statistics.stdev(closes[-20:]) / closes[-1] * 100
        if volatility > 25 or volatility < 1: # Too wild or dead
            return None

        # Scoring
        score = 50
        if abs(change24) > 4: score += 15
        if volatility > 3 and volatility < 12: score += 15 # healthy volatility
        if closes[-1] > sum(closes[-20:])/20:
            trend = "LONG"
            score += 10
        else:
            trend = "SHORT"
            score += 10

        # === BTC FILTER - This is why you lost 90/100 ===
        if btc_trend == "UP" and trend == "SHORT": score -= 30
        if btc_trend == "DOWN" and trend == "LONG": score -= 30
        if score < 80: return None

        # Momentum check
        if btc_trend == "UP" and trend!= "LONG": return None
        if btc_trend == "DOWN" and trend!= "SHORT": return None

        return {
            "symbol": instId.replace("-SWAP","").replace("-",""),
            "pair": instId,
            "entry": last,
            "trend": trend,
            "score": min(score, 95),
            "change24": change24,
            "volat": round(volatility, 1),
            "vol_usd": vol24
        }
    except Exception as e:
        return None

def main():
    print("=== OKX Futures 80/100 Strict - FIXED RISK v2 ===")
    try:
        data = requests.get(OKX_TICKER_URL, timeout=15).json()
        tickers = data["data"]
        print(f"Status: 200")
        print(f"Scanning {len(tickers)} coins")

        btc_trend = get_btc_trend()
        print(f"BTC Trend 15m: {btc_trend}")

        signals = []
        for t in tickers:
            s = score_coin(t, btc_trend)
            if s:
                signals.append(s)

        # Sort by score
        signals = sorted(signals, key=lambda x: x["score"], reverse=True)[:3] # Only top 3, no spam

        if not signals:
            print("No 80/100 setup that passes BTC + Volume filter")
            return

        for sig in signals:
            entry = sig["entry"]
            if sig["trend"] == "LONG":
                tp1 = entry * (1 + TP1_PCT)
                tp2 = entry * (1 + TP2_PCT)
                tp3 = entry * (1 + TP3_PCT)
                sl = entry * (1 - SL_PCT)
            else:
                tp1 = entry * (1 - TP1_PCT)
                tp2 = entry * (1 - TP2_PCT)
                tp3 = entry * (1 - TP3_PCT)
                sl = entry * (1 + SL_PCT)

            msg = (
                f"✅ 80/100 STRICT | {sig['symbol']} | {sig['trend']}\n\n"
                f"*ENTRY:* `{entry:.6f}`\n"
                f"*LEVERAGE:* {LEVERAGE_TEXT}\n\n"
                f"*TP1:* `{tp1:.6f}` (+{TP1_PCT*100:.0f}%)\n"
                f"*TP2:* `{tp2:.6f}` (+{TP2_PCT*100:.0f}%)\n"
                f"*TP3:* `{tp3:.6f}` (+{TP3_PCT*100:.0f}%)\n\n"
                f"*SL:* `{sl:.6f}` (-{SL_PCT*100:.0f}%)\n\n"
                f"Score: {sig['score']}/100 | 24h: {sig['change24']:.2f}% | Volat: {sig['volat']}%\n"
                f"Vol: ${sig['vol_usd']/1e6:.1f}M | BTC: {btc_trend}\n"
                f"Pair: {sig['pair']} (OKX Futures = Bybit Futures pair)"
            )
            print(msg)
            send_telegram(msg)
            time.sleep(1)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
