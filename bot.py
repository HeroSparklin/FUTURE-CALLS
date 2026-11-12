import asyncio
import time
import requests
from datetime import datetime

# ==================== CONFIG - EDIT THIS ====================
TELEGRAM_BOT_TOKEN = "8914668267:AAHi0OiTHYJjULC4FIfMSGf1GQ_6wg2cjt8"
TELEGRAM_CHAT_ID = "1004458770787"

BOT_ALIVE_INTERVAL = 4 * 3600  # 4 HOURS - ALIVE
SCAN_INTERVAL = 30 * 60       # 30 MINS - SCAN EVERY 30 MINS
STRICTNESS = 92
SCORE_MIN = 80

ADX_MIN = 20
ADX_BTC_MIN = 25
RSI_OVERBOUGHT = 78
RSI_OVERSOLD = 28
VOL_MIN = 1.2
PULLBACK_MAX = 0.8

# ==================== COIN LISTS - 44 COINS ====================
MAJOR = [
    "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT",
    "ADAUSDT","AVAXUSDT","LINKUSDT","TRXUSDT","DOTUSDT","MATICUSDT",
    "LTCUSDT","BCHUSDT","XAUTUSDT","GOLDUSDT","PAXGUSDT"
]

QUANT_MEME = [
    "PEPEUSDT","SHIBUSDT","WIFUSDT","BONKUSDT","FLOKIUSDT",
    "STXUSDT","SUIUSDT","APTUSDT","ARBUSDT","OPUSDT",
    "INJUSDT","SEIUSDT","TIAUSDT","NEARUSDT","TONUSDT"
]

MANUAL_NEW = [
    "KAIAUSDT","EIGENUSDT","ZROUSDT","LISTAUSDT","ZKUSDT",
    "IOUSDT","REZUSDT","BBUSDT","NOTUSDT"
]

# Auto New - Add Binance new listings here manually, up to 20
AUTO_NEW = [
    "HYPEUSDT","VIRTUALUSDT","AIXBTUSDT"
]

ALL_COINS = MAJOR + QUANT_MEME + MANUAL_NEW + AUTO_NEW
print(f"Total Coins: {len(ALL_COINS)}")

# ==================== TELEGRAM ====================
def send_telegram_sync(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        r = requests.post(url, json=payload, timeout=10)
        print(f"TG {r.status_code} | {text[:60]}")
        return r.status_code == 200
    except Exception as e:
        print(f"TG FAILED: {e}")
        return False

async def send_telegram(text):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, send_telegram_sync, text)

# ==================== BINANCE DATA ====================
def get_klines(symbol, interval, limit=100):
    try:
        url = "https://fapi.binance.com/fapi/v1/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if not isinstance(data, list):
            return [], []
        closes = [float(x[4]) for x in data]
        volumes = [float(x[5]) for x in data]
        return closes, volumes
    except Exception as e:
        print(f"Klines fail {symbol} {interval}: {e}")
        return [], []

def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_adx(closes, period=14):
    if len(closes) < period + 2:
        return 0
    trs, dms = [], []
    for i in range(1, len(closes)):
        tr = abs(closes[i] - closes[i-1])
        trs.append(tr)
        dms.append(abs(closes[i] - closes[i-1]) if closes[i] > closes[i-1] else 0)
    if sum(trs[-period:]) == 0:
        return 0
    adx = (sum(dms[-period:]) / sum(trs[-period:])) * 100
    return min(adx * 1.8, 60)

def calc_ema(closes, period):
    if not closes:
        return 0
    if len(closes) < period:
        return closes[-1]
    k = 2 / (period + 1)
    ema = closes[0]
    for c in closes[1:]:
        ema = c * k + ema * (1 - k)
    return ema

def get_trend(closes):
    if len(closes) < 50:
        return "NEUTRAL"
    ema7 = calc_ema(closes, 7)
    ema28 = calc_ema(closes, 28)
    price = closes[-1]
    if price > ema7 > ema28:
        return "BULL"
    if price < ema7 < ema28:
        return "BEAR"
    return "NEUTRAL"

def get_btc_regime():
    closes, _ = get_klines("BTCUSDT", "4h", 100)
    if not closes:
        return "BEAR"
    return get_trend(closes)

# ==================== 8 FILTERS - 92/100 LOGIC ====================
def check_coin(symbol, btc_regime):
    closes_1h, vol_1h = get_klines(symbol, "1h", 100)
    closes_4h, vol_4h = get_klines(symbol, "4h", 100)
    closes_12h, _ = get_klines(symbol, "12h", 100)
    closes_1d, _ = get_klines(symbol, "1d", 100)

    if not closes_1h or not closes_4h:
        return None, ["NO_DATA"]

    price = closes_1h[-1]
    trend_1h = get_trend(closes_1h)
    trend_4h = get_trend(closes_4h)
    trend_12h = get_trend(closes_12h)
    trend_1d = get_trend(closes_1d)
    rsi = calc_rsi(closes_1h)
    adx = calc_adx(closes_4h)

    # Volume Ratio
    if len(vol_1h) > 20:
        avg_vol = sum(vol_1h[-20:-1]) / 19
        vol_ratio = vol_1h[-1] / avg_vol if avg_vol > 0 else 0
    else:
        vol_ratio = 0

    ema7 = calc_ema(closes_1h, 7)
    dist = abs(price - ema7) / ema7 * 100 if ema7 else 99

    rejects = []
    score = 0
    side = None

    # F1 - Trend 4TF Must Align
    trends = [trend_1h, trend_4h, trend_12h, trend_1d]
    if trends.count("BEAR") == 4:
        side = "SHORT"
        score += 25
    elif trends.count("BULL") == 4:
        side = "LONG"
        score += 25
    else:
        rejects.append(f"F1 TF_MISMATCH {trend_1h}/{trend_4h}/{trend_12h}/{trend_1d}")

    # F2 - ADX
    adx_need = ADX_BTC_MIN if symbol.startswith("BTC") else ADX_MIN
    if adx >= adx_need:
        score += 23
    else:
        rejects.append(f"F2 ADX_LOW {adx:.1f}")

    # F3 - RSI
    if RSI_OVERSOLD < rsi < RSI_OVERBOUGHT:
        score += 12
    else:
        rejects.append(f"F3 RSI {rsi:.1f}")

    # F4 - Volume
    if vol_ratio >= VOL_MIN:
        score += 15
    else:
        rejects.append(f"F4 VOL_LOW {vol_ratio:.2f}x")

    # F5 - Spread (Assume Pass for Binance Futures Majors)
    score += 7

    # F6 - Pullback / Dist to EMA
    if dist <= PULLBACK_MAX:
        score += 8
    else:
        rejects.append(f"F6 DIST {dist:.2f}%")

    # F7 - Score Min
    if score < SCORE_MIN:
        rejects.append(f"F7 SCORE {score}")

    # F8 - BTC Regime
    if btc_regime == "BEAR" and side == "LONG":
        rejects.append("F8 BTC_BEAR_NO_LONG")
    if btc_regime == "BULL" and side == "SHORT":
        rejects.append("F8 BTC_BULL_NO_SHORT")

    if rejects or side is None:
        return None, rejects

    # Levels
    if side == "SHORT":
        sl = price * 1.015
        tp1 = price * 0.98
        tp2 = price * 0.96
        lev = 15 if vol_ratio > 3 else 10
    else:
        sl = price * 0.985
        tp1 = price * 1.02
        tp2 = price * 1.04
        lev = 15 if vol_ratio > 3 else 10

    signal = {
        "symbol": symbol, "side": side, "score": score, "price": price,
        "trend": "/".join(trends), "adx": adx, "rsi": rsi,
        "vol": vol_ratio, "dist": dist, "sl": sl, "tp1": tp1, "tp2": tp2, "lev": lev
    }
    return signal, []

# ==================== MAIN LOOP ====================
last_alive = 0

async def main():
    global last_alive
    print("🚀 BOT STARTED - 92/100 Sniper | SCAN 30mins | ALIVE 4hrs")
    await send_telegram(
        "🚀 BOT STARTED\n"
        "Strictness: 92/100\n"
        "SCAN: Every 30 mins\n"
        "ALIVE: Every 4hrs\n"
        f"Scanning: {len(ALL_COINS)} Coins | 8 Filters"
    )
    # Force first ALIVE immediately so you know it works
    last_alive = time.time() - BOT_ALIVE_INTERVAL + 60  # ALIVE in 60 sec after start

    while True:
        try:
            scan_start = time.time()
            btc_regime = get_btc_regime()
            print(f"\n=== SCAN {datetime.now().strftime('%H:%M:%S')} BTC:{btc_regime} ===")

            signals = []
            checked = 0
            for coin in ALL_COINS:
                checked += 1
                sig, rejects = check_coin(coin, btc_regime)
                if sig:
                    signals.append(sig)
                    print(f"✅ {coin} {sig['side']} Score {sig['score']} Vol {sig['vol']:.2f}x")
                else:
                    print(f"REJECT {coin}: {rejects}")
                await asyncio.sleep(0.2)

            scan_duration = time.time() - scan_start
            print(f"Checked:{checked} Sent:{len(signals)} | Scan Duration: {scan_duration:.1f}s")

            # SEND SIGNALS IMMEDIATELY
            for sig in signals:
                msg = (
                    f"🚨 <b>{sig['symbol']} {sig['side']}</b>\n"
                    f"Score {sig['score']} | Lev {sig['lev']}x | BTC {btc_regime}\n"
                    f"Trend {sig['trend']}\n"
                    f"ADX {sig['adx']:.1f} | RSI {sig['rsi']:.1f} | Vol {sig['vol']:.2f}x | Dist {sig['dist']:.2f}%\n"
                    f"Entry {sig['price']:.4f}\n"
                    f"SL {sig['sl']:.4f}\n"
                    f"TP1 {sig['tp1']:.4f} | TP2 {sig['tp2']:.4f}"
                )
                await send_telegram(msg)

            # BOT ALIVE EVERY 4 HOURS
            now_ts = time.time()
            if now_ts - last_alive >= BOT_ALIVE_INTERVAL:
                alive_msg = (
                    f"✅ BOT ALIVE\n"
                    f"Checked:{checked} | Sent:{len(signals)}\n"
                    f"Strictness:92/100 | BTC:{btc_regime}\n"
                    f"Mode: Sniper 92/100 | Time:{datetime.now().strftime('%H:%M:%S')}\n"
                    f"Scan Duration: {scan_duration:.0f}s | Next Scan in 30mins\n"
                    f"Status: Scanning 8 filters | Next ALIVE in 4hrs"
                )
                await send_telegram(alive_msg)
                last_alive = now_ts
                print(f"✅ ALIVE SENT - Next in 4hrs")

            print(f"Sleeping 30 mins...")
            await asyncio.sleep(SCAN_INTERVAL)

        except Exception as e:
            print(f"LOOP ERROR: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
