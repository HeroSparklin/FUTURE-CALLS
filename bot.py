import os
import requests
import json
import csv
import time
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_BROADCAST_ID")
BROADCAST_ID = os.getenv("TELEGRAM_BROADCAST_ID") or CHAT_ID

# ===== 85/100 UPGRADE - TOP 25 VOLUME ONLY =====
TOTAL_COINS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT", "BCHUSDT",
    "NEARUSDT", "UNIUSDT", "APTUSDT", "ARBUSDT", "FILUSDT",
    "OPUSDT", "INJUSDT", "STXUSDT", "TIAUSDT", "SUIUSDT",
    "PEPEUSDT", "WIFUSDT", "BONKUSDT", "AAVEUSDT", "TAOUSDT"
]

# ===== LOCKED CONFIG - 12 FILTERS + 3 NEW FIXES =====
STRICTNESS = 92
SCAN_INTERVAL = "15m"
MAX_SPREAD = 0.3
MODE = "LONG + SHORT - 12 FILTERS - 24HRS - 85/100"
ENTRY_START_HOUR = 0
ENTRY_END_HOUR = 24
BTC_EXTREME_VOL = 4.0
COOLDOWN_FILE = "cooldown.json"
COOLDOWN_HOURS = 2
HTF_INTERVAL = "1h"

# --- NEW FIX 1: RISK MANAGEMENT ---
MAX_RISK_PCT = 2.5  # If SL is more than 2.5% away, SKIP trade
MAX_ATR_PCT = 6.0   # Reduced from 8% to 6% - safer

# --- NEW FIX 3: LOGGING ---
LOG_FILE = "signals_log.csv"
# ==============================================

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN or CHAT_ID")
        return
    for cid in set([CHAT_ID, BROADCAST_ID]):
        if not cid:
            continue
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            r = requests.post(url, json={"chat_id": cid, "text": text, "parse_mode": "Markdown"}, timeout=10)
            print(f"TG {r.status_code} | {text[:50]}")
        except Exception as e:
            print(f"TG ERROR: {e}")

def log_signal(symbol, direction, score, entry, sl, tp, rsi, adx, spread, btc_trend, risk_pct):
    try:
        file_exists = os.path.exists(LOG_FILE)
        with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["time", "symbol", "direction", "score", "entry", "sl", "tp", "rsi", "adx", "spread", "btc_trend", "risk_pct", "result"])
            writer.writerow([datetime.utcnow().isoformat(), symbol, direction, score, entry, sl, tp, rsi, adx, spread, btc_trend, risk_pct, ""])
        print(f"LOGGED to {LOG_FILE}")
    except Exception as e:
        print(f"LOG ERROR: {e}")

def get_klines_okx(symbol="BTCUSDT", interval="15m", limit=100):
    try:
        okx_symbol = symbol.replace("USDT", "-USDT") if "-USDT" not in symbol else symbol
        interval_map = {"1m":"1m","3m":"3m","5m":"5m","15m":"15m","30m":"30m","1h":"1H","1H":"1H","4h":"4H","4H":"4H","1d":"1D","1D":"1D"}
        okx_interval = interval_map.get(interval, "15m")
        url = f"https://www.okx.com/api/v5/market/candles?instId={okx_symbol}&bar={okx_interval}&limit={limit}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        data = r.json().get("data", [])
        if not data:
            return []
        klines = []
        for c in reversed(data):
            klines.append({"time": int(c[0]), "open": float(c[1]), "high": float(c[2]), "low": float(c[3]), "close": float(c[4]), "vol": float(c[5])})
        return klines
    except Exception as e:
        print(f"DATA ERROR {symbol}: {e}")
        return []

def get_spread_pct(symbol):
    try:
        okx_symbol = symbol.replace("USDT", "-USDT") if "-USDT" not in symbol else symbol
        url = f"https://www.okx.com/api/v5/market/ticker?instId={okx_symbol}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = r.json().get("data", [])
        if not data:
            return 0
        ask = float(data[0].get("askPx", 0))
        bid = float(data[0].get("bidPx", 0))
        if bid == 0 or ask == 0:
            return 0
        return (ask - bid) / bid * 100
    except Exception as e:
        print(f"SPREAD ERROR {symbol}: {e}")
        return 0

def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains = []
    losses = []
    for i in range(1, period+1):
        diff = closes[-i] - closes[-i-1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))
    avg_gain = sum(gains)/period if gains else 0
    avg_loss = sum(losses)/period if losses else 0.000001
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_atr(klines, period=14):
    if len(klines) < period + 1:
        return 0
    tr_list = []
    for i in range(1, period+1):
        h = klines[-i]["high"]
        l = klines[-i]["low"]
        pc = klines[-i-1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        tr_list.append(tr)
    return sum(tr_list) / len(tr_list)

def calc_adx(klines, period=14):
    if len(klines) < period * 2 + 1:
        return 0, 0, 0
    trs = []
    plus_dm = []
    minus_dm = []
    for i in range(1, len(klines)):
        h = klines[i]["high"]
        l = klines[i]["low"]
        ph = klines[i-1]["high"]
        pl = klines[i-1]["low"]
        pc = klines[i-1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
        up = h - ph
        down = pl - l
        plus_dm.append(up if (up > down and up > 0) else 0)
        minus_dm.append(down if (down > up and down > 0) else 0)
    def wilder_smooth(values, period):
        result = [sum(values[:period])]
        for i in range(period, len(values)):
            result.append(result[-1] - (result[-1]/period) + values[i])
        return result
    tr_smooth = wilder_smooth(trs, period)
    plus_smooth = wilder_smooth(plus_dm, period)
    minus_smooth = wilder_smooth(minus_dm, period)
    min_len = min(len(tr_smooth), len(plus_smooth), len(minus_smooth))
    tr_smooth = tr_smooth[-min_len:]
    plus_smooth = plus_smooth[-min_len:]
    minus_smooth = minus_smooth[-min_len:]
    dx_list = []
    last_plus_di = 0
    last_minus_di = 0
    for i in range(len(tr_smooth)):
        if tr_smooth[i] == 0:
            dx_list.append(0)
            continue
        plus_di = 100 * plus_smooth[i] / tr_smooth[i]
        minus_di = 100 * minus_smooth[i] / tr_smooth[i]
        denom = plus_di + minus_di
        dx = 100 * abs(plus_di - minus_di) / denom if denom != 0 else 0
        dx_list.append(dx)
        if i == len(tr_smooth)-1:
            last_plus_di = plus_di
            last_minus_di = minus_di
    if len(dx_list) < period:
        return 0, last_plus_di, last_minus_di
    adx = sum(dx_list[-period:]) / period
    return adx, last_plus_di, last_minus_di

def is_entry_timing_ok():
    now_utc = datetime.utcnow()
    hour = now_utc.hour
    return ENTRY_START_HOUR <= hour < ENTRY_END_HOUR, hour

def load_cooldown():
    try:
        if os.path.exists(COOLDOWN_FILE):
            with open(COOLDOWN_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"COOLDOWN LOAD ERROR: {e}")
    return {}

def save_cooldown(data):
    try:
        with open(COOLDOWN_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"COOLDOWN SAVE ERROR: {e}")

def is_on_cooldown(symbol, cooldown_data):
    if symbol not in cooldown_data:
        return False, 0
    try:
        last_time_str = cooldown_data[symbol]
        last_time = datetime.fromisoformat(last_time_str)
        diff = datetime.utcnow() - last_time
        cooldown_limit = timedelta(hours=COOLDOWN_HOURS)
        if diff < cooldown_limit:
            minutes_left = int((cooldown_limit - diff).total_seconds() / 60)
            return True, minutes_left
        return False, 0
    except Exception:
        return False, 0

def set_cooldown(symbol, cooldown_data):
    cooldown_data[symbol] = datetime.utcnow().isoformat()
    save_cooldown(cooldown_data)

def check_htf_confirmation(symbol, trend_15m):
    htf_klines = get_klines_okx(symbol, HTF_INTERVAL, 100)
    if len(htf_klines) < 50:
        return False, "HTF_NO_DATA"
    htf_closes = [k["close"] for k in htf_klines]
    htf_sma50 = sum(htf_closes[-50:]) / 50
    htf_price = htf_closes[-1]
    if trend_15m == "BULL":
        if htf_price > htf_sma50:
            return True, f"HTF_OK Price {htf_price:.4f} > 1H SMA50 {htf_sma50:.4f}"
        else:
            return False, f"HTF_REJECT LONG but 1H Price {htf_price:.4f} < 1H SMA50 {htf_sma50:.4f}"
    else:
        if htf_price < htf_sma50:
            return True, f"HTF_OK Price {htf_price:.4f} < 1H SMA50 {htf_sma50:.4f}"
        else:
            return False, f"HTF_REJECT SHORT but 1H Price {htf_price:.4f} > 1H SMA50 {htf_sma50:.4f}"

def get_btc_dynamic():
    btc_klines = get_klines_okx("BTCUSDT", "1H", 100)
    if not btc_klines:
        return "UNKNOWN", 0, "NORMAL", 55, 45, 25, False, "BTC_NO_DATA"
    btc_closes = [k["close"] for k in btc_klines]
    btc_volatility = (btc_closes[-1] - btc_closes[-5]) / btc_closes[-5] * 100 if btc_closes[-5]!=0 else 0
    abs_vol = abs(btc_volatility)
    sma20 = sum(btc_closes[-20:]) / 20
    sma50 = sum(btc_closes[-50:]) / 50
    curr = btc_closes[-1]
    if curr > sma20 > sma50:
        btc_trend = "BULL"
    elif curr < sma20 < sma50:
        btc_trend = "BEAR"
    else:
        btc_trend = "SIDE"
    if abs_vol > BTC_EXTREME_VOL:
        return btc_trend, btc_volatility, "EXTREME", 60, 40, 30, True, f"BTC_EXTREME {btc_volatility:.2f}% > 4% BLOCK ALL"
    elif abs_vol > 2.0:
        return btc_trend, btc_volatility, "VOLATILE", 60, 40, 30, False, "VOLATILE"
    elif abs_vol > 1.0:
        return btc_trend, btc_volatility, "NORMAL", 55, 45, 25, False, "NORMAL"
    else:
        return btc_trend, btc_volatility, "CALM", 50, 50, 20, False, "CALM"

def calc_score(klines, btc_trend="UNKNOWN", btc_volatility=0, btc_regime="NORMAL", rsi_long_min=55, rsi_short_max=45, adx_min=25):
    if len(klines) < 30:
        return None, None, ["NO_DATA <30"], 0, 0, 0
    is_new_listing = len(klines) < 50
    closes = [k["close"] for k in klines]
    vols = [k["vol"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    curr = closes[-1]
    sma20 = sum(closes[-20:]) / 20
    sma50 = sma20 if is_new_listing else sum(closes[-50:]) / 50
    rsi = calc_rsi(closes, 14)
    adx, plus_di, minus_di = calc_adx(klines, 14)
    dyn_mode = btc_regime

    if curr > sma20 > sma50:
        trend = "BULL"
    elif curr < sma20 < sma50:
        trend = "BEAR"
    elif is_new_listing and curr > sma20:
        trend = "BULL"
    elif is_new_listing and curr < sma20:
        trend = "BEAR"
    else:
        return 50, "SIDE", ["50/100 - SIDE NO_TREND"], rsi, 0, adx
    score = 50 + 20

    avg_vol = sum(vols[-20:-1]) / 19 if len(vols) > 20 else sum(vols[:-1])/max(1,len(vols)-1)
    vol_ratio = vols[-1] / avg_vol if avg_vol != 0 else 0
    if vol_ratio < 1.3:
        return score, trend, [f"{score}/100 - {trend} VOL_LOW {vol_ratio:.2f}x"], rsi, 0, adx
    score += 15

    change = (curr - closes[-5]) / closes[-5] * 100 if closes[-5] != 0 else 0
    if trend == "BULL" and change < 1.5:
        return score, trend, [f"{score}/100 - {trend} MOM_LOW {change:.2f}%"], rsi, 0, adx
    if trend == "BEAR" and change > -1.5:
        return score, trend, [f"{score}/100 - {trend} MOM_LOW {change:.2f}%"], rsi, 0, adx
    score += 10

    if trend == "BULL":
        prev_high = max(highs[-21:-1]) if len(highs) >= 21 else max(highs[:-1])
        if curr <= prev_high:
            return score, trend, [f"{score}/100 - {trend} NO_BREAKOUT"], rsi, 0, adx
    else:
        prev_low = min(lows[-21:-1]) if len(lows) >= 21 else min(lows[:-1])
        if curr >= prev_low:
            return score, trend, [f"{score}/100 - {trend} NO_BREAKDOWN"], rsi, 0, adx
    score += 6

    if trend == "BULL":
        if rsi < rsi_long_min:
            if not (rsi < 35 and change > 1.5 and vol_ratio > 1.3):
                return score, trend, [f"{score}/100 - {trend} RSI_LOW {rsi:.0f} < {rsi_long_min} ({dyn_mode})"], rsi, 0, adx
    else:
        if rsi > rsi_short_max:
            if not (rsi > 65 and change < -1.5 and vol_ratio > 1.3):
                return score, trend, [f"{score}/100 - {trend} RSI_HIGH {rsi:.0f} > {rsi_short_max} ({dyn_mode})"], rsi, 0, adx

    atr = calc_atr(klines, 14)
    atr_pct = (atr / curr * 100) if curr != 0 else 0
    if atr_pct < 0.3:
        return score, trend, [f"{score}/100 - {trend} ATR_TOO_LOW {atr_pct:.2f}%"], rsi, atr, adx
    if atr_pct > MAX_ATR_PCT:
        return score, trend, [f"{score}/100 - {trend} ATR_TOO_HIGH {atr_pct:.2f}% > {MAX_ATR_PCT}%"], rsi, atr, adx

    if adx < adx_min:
        return score, trend, [f"{score}/100 - {trend} ADX_WEAK {adx:.1f} < {adx_min} ({dyn_mode})"], rsi, atr, adx
    if trend == "BULL" and plus_di < minus_di:
        return score, trend, [f"{score}/100 - {trend} ADX_DI_WRONG +DI:{plus_di:.1f} < -DI:{minus_di:.1f}"], rsi, atr, adx
    if trend == "BEAR" and minus_di < plus_di:
        return score, trend, [f"{score}/100 - {trend} ADX_DI_WRONG -DI:{minus_di:.1f} < +DI:{plus_di:.1f}"], rsi, atr, adx

    if score > 100:
        score = 100
    tag = "NEW_LISTING" if is_new_listing else "NORMAL"
    reasons = [f"{score}/100 - {trend} ALL_PASS RSI:{rsi:.0f} ADX:{adx:.1f} ATR:{atr_pct:.2f}% BTC:{btc_trend} {dyn_mode} {tag}"]
    return score, trend, reasons, rsi, atr, adx

def main():
    print(f"Total Coins: {len(TOTAL_COINS)} | {MODE} | Strictness: {STRICTNESS} | MAX RISK {MAX_RISK_PCT}% | 85/100 UPGRADE")
    timing_ok, current_hour = is_entry_timing_ok()
    print(f"Timing Check: {current_hour}:00 UTC - {'24HRS ALLOWED' if timing_ok else 'BLOCKED'}")

    btc_trend, btc_volatility, btc_regime, rsi_long_min, rsi_short_max, adx_min, block_all, btc_msg = get_btc_dynamic()
    print(f"=== BTC DYNAMIC: BTC:{btc_trend} VOL:{btc_volatility:.2f}% REGIME:{btc_regime} BLOCK:{block_all} ===")
    if block_all:
        print(f"SCAN STOPPED - {btc_msg}")
        return

    cooldown_data = load_cooldown()
    print(f"=== SCAN {datetime.now().strftime('%H:%M:%S')} UTC {current_hour}:00 BTC:{btc_trend} 24HRS:ON ===")

    found = 0
    for symbol in TOTAL_COINS:
        # --- FIX 2: ANTI RATE-LIMIT DELAY ---
        time.sleep(1.2)

        spread = get_spread_pct(symbol)
        if spread > MAX_SPREAD:
            print(f"REJECT {symbol}: SPREAD_HIGH {spread:.3f}%")
            continue
        klines = get_klines_okx(symbol, "15m", 100)
        score, trend, reasons, rsi, atr, adx = calc_score(klines, btc_trend, btc_volatility, btc_regime, rsi_long_min, rsi_short_max, adx_min)
        if score is None:
            print(f"REJECT {symbol}: ['NO_DATA']")
            continue
        if score >= STRICTNESS:
            htf_ok, htf_msg = check_htf_confirmation(symbol, trend)
            if not htf_ok:
                print(f"REJECT {symbol}: {score}/100 {trend} - {htf_msg}")
                continue

            on_cool, mins_left = is_on_cooldown(symbol, cooldown_data)
            if on_cool:
                print(f"HOLD {symbol}: {score}/100 {trend} - COOLDOWN {mins_left}min left")
                continue

            entry = klines[-1]['close']
            if trend == "BULL":
                direction = "LONG"
                emoji = "🚀"
                sl = entry - (atr * 1.5)
                tp = entry + (atr * 3)
                if sl >= entry:
                    sl = entry * 0.98
                    tp = entry * 1.04
            else:
                direction = "SHORT"
                emoji = "🔻"
                sl = entry + (atr * 1.5)
                tp = entry - (atr * 3)
                if sl <= entry:
                    sl = entry * 1.02
                    tp = entry * 0.96

            # --- FIX 1: RISK MANAGEMENT CHECK ---
            risk_pct = abs(entry - sl) / entry * 100 if entry != 0 else 0
            if risk_pct > MAX_RISK_PCT:
                print(f"REJECT {symbol}: RISK_TOO_HIGH {risk_pct:.2f}% > {MAX_RISK_PCT}% - SL too far")
                continue
            if risk_pct < 0.4:
                print(f"REJECT {symbol}: RISK_TOO_LOW {risk_pct:.2f}% - SL too tight")
                continue

            found += 1
            set_cooldown(symbol, cooldown_data)

            msg = f"{emoji} *{symbol}* {direction} - {score}/100 SNIPER 85/100\nTrend: {trend} | HTF 1H: ✅\nEntry: {entry}\nSL: {sl:.6f} ({risk_pct:.2f}% risk)\nTP: {tp:.6f} (2R)\nSpread: {spread:.3f}%\nADX: {adx:.1f}\nBTC: {btc_trend} {btc_regime}\n{reasons[0]}\nHTF: {htf_msg}\nTime: {datetime.now().strftime('%H:%M:%S')} UTC"
            print(f"FOUND {symbol}: {score}/100 {direction} | Risk {risk_pct:.2f}% | {reasons[0]}")
            send_telegram(msg)
            
            # --- FIX 3: LOG IT ---
            log_signal(symbol, direction, score, entry, sl, tp, rsi, adx, spread, btc_trend, risk_pct)

        else:
            print(f"REJECT {symbol}: {reasons} | Spread {spread:.3f}%")

    if found == 0:
        print(f"SCAN DONE - 0 signals - All filtered correctly")

if __name__ == "__main__":
    main()
