import os
import requests
from datetime import datetime

# --- CONFIG FROM GITHUB SECRETS ---
# DO NOT type token/chat id here, it reads from Secrets
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_BROADCAST_ID")
BROADCAST_ID = os.getenv("TELEGRAM_BROADCAST_ID") or CHAT_ID

TOTAL_COINS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT",
    "TRXUSDT", "DOTUSDT", "BCHUSDT", "NEARUSDT", "UNIUSDT",
    "ETCUSDT", "XLMUSDT", "HBARUSDT", "APTUSDT", "ARBUSDT",
    "FILUSDT", "OPUSDT", "INJUSDT", "STXUSDT", "TIAUSDT",
    "SUIUSDT", "PEPEUSDT", "RENDRUSDT", "SEIUSDT", "WIFUSDT",
    "BONKUSDT", "SHIBUSDT", "FLOKIUSDT", "AAVEUSDT", "MKRUSDT",
    "ATOMUSDT", "GRTUSDT", "RUNEUSDT", "FTMUSDT", "ALGOUSDT",
    "VETUSDT", "QNTUSDT", "ENAUSDT", "TAOUSDT"
]

STRICTNESS = 92
SCAN_INTERVAL = "15m"

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN or CHAT_ID - check Secrets")
        return
    for cid in set([CHAT_ID, BROADCAST_ID]):
        if not cid:
            continue
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            r = requests.post(url, json={"chat_id": cid, "text": text, "parse_mode": "Markdown"}, timeout=10)
            if r.status_code == 200:
                print(f"TG 200 | {text[:40]}")
            else:
                print(f"TG {r.status_code} | {r.text[:120]}")
        except Exception as e:
            print(f"TG ERROR: {e}")

def get_klines_okx(symbol="BTCUSDT", interval="15m", limit=100):
    try:
        okx_symbol = symbol.replace("USDT", "-USDT") if "-USDT" not in symbol else symbol
        interval_map = {"1m":"1m","3m":"3m","5m":"5m","15m":"15m","30m":"30m","1h":"1H","1H":"1H","4h":"4H","4H":"4H","1d":"1D","1D":"1D"}
        okx_interval = interval_map.get(interval, "15m")
        url = f"https://www.okx.com/api/v5/market/candles?instId={okx_symbol}&bar={okx_interval}&limit={limit}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
        j = r.json()
        data = j.get("data", [])
        if not data:
            return []
        klines = []
        for c in reversed(data):
            klines.append({
                "time": int(c[0]),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "vol": float(c[5]),
            })
        return klines
    except Exception as e:
        print(f"DATA ERROR {symbol}: {e}")
        return []

def calc_score(klines):
    if len(klines) < 50:
        return None, None, ["NO_DATA"]
    closes = [k["close"] for k in klines]
    vols = [k["vol"] for k in klines]
    sma20 = sum(closes[-20:]) / 20
    sma50 = sum(closes[-50:]) / 50
    curr = closes[-1]

    score = 50
    if curr > sma20 > sma50:
        score += 20
        trend = "BULL"
    elif curr < sma20 < sma50:
        score -= 10
        trend = "BEAR"
    else:
        trend = "SIDE"

    avg_vol = sum(vols[-20:-1]) / 19 if len(vols) > 20 else 1
    if vols[-1] > avg_vol * 1.5:
        score += 15

    change = (curr - closes[-5]) / closes[-5] * 100 if closes[-5] != 0 else 0
    if change > 1.5:
        score += 10
    if change < -1.5:
        score -= 5

    # Bonus for strong breakout
    if curr > max([k["high"] for k in klines[-20:-1]]):
        score += 10

    if score > 100:
        score = 100

    reasons = [f"{score}/100 - {trend}"]
    return score, trend, reasons

def main():
    print(f"Total Coins: {len(TOTAL_COINS)}")
    start_msg = f"🚀 BOT STARTED - {STRICTNESS}/100 Sniper | SCAN {SCAN_INTERVAL} | {len(TOTAL_COINS)} coins"
    print(start_msg)
    send_telegram(start_msg)
    print(f"Strictness: {STRICTNESS}/100")
    print(f"SCAN: Every 15 mins")
    print(f"ALIVE:")

    btc_klines = get_klines_okx("BTCUSDT", "1H", 100)
    if not btc_klines:
        btc_trend = "UNKNOWN"
    else:
        _, btc_trend, _ = calc_score(btc_klines)
        if btc_trend is None:
            btc_trend = "UNKNOWN"

    print(f"=== SCAN {datetime.now().strftime('%H:%M:%S')} BTC:{btc_trend} ===")

    found = 0
    for symbol in TOTAL_COINS:
        klines = get_klines_okx(symbol, "15m", 100)
        score, trend, reasons = calc_score(klines)
        if score is None:
            print(f"REJECT {symbol}: ['NO_DATA']")
            continue
        if score >= STRICTNESS:
            found += 1
            entry = klines[-1]['close']
            sl = klines[-1]['low']
            tp = entry + (entry - sl) * 2 if entry > sl else entry * 1.02
            msg = f"🔥 *{symbol}* - {score}/100 SNIPER\nTrend: {trend}\nEntry: {entry}\nSL: {sl}\nTP: {tp}\nTime: {datetime.now().strftime('%H:%M:%S')}"
            print(f"FOUND {symbol}: {score}/100 {trend}")
            send_telegram(msg)
        else:
            print(f"REJECT {symbol}: {reasons}")

    if found == 0:
        print(f"SCAN DONE - 0 signals (92/100 is strict, normal)")

if __name__ == "__main__":
    main()
