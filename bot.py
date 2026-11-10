# bot.py - FUTURE-CALLS - Locked Version
# 60 coins | 80/100 STRICT | BTC Dynamic | 4hr Alive | 4hr Cooldown + 2%
import os
import json
import time
import ccxt
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone

# ============ CONFIG ============
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BROADCAST_ID = os.getenv("TELEGRAM_BROADCAST_ID", "")

SEEN_FILE = "seen.json"
ALIVE_FILE = "last_alive.txt"

# 60 coins: 25 MAJOR/ALT + 20 QUANT + 15 NEW auto
MAJOR_ALT = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT",
    "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT", "MATIC/USDT",
    "NEAR/USDT", "APT/USDT", "ARB/USDT", "OP/USDT", "ATOM/USDT",
    "LTC/USDT", "BCH/USDT", "FIL/USDT", "HBAR/USDT", "INJ/USDT",
    "SUI/USDT", "SEI/USDT", "TIA/USDT", "PEPE/USDT", "WIF/USDT"
]

QUANT = [
    "ENA/USDT", "PENDLE/USDT", "ONDO/USDT", "JUP/USDT", "STRK/USDT",
    "ZK/USDT", "TAO/USDT", "RENDER/USDT", "FET/USDT", "IMX/USDT",
    "MANTA/USDT", "ALT/USDT", "PYTH/USDT", "DYM/USDT", "BEAM/USDT",
    "LDO/USDT", "AAVE/USDT", "UNI/USDT", "STX/USDT", "GALA/USDT"
]

NEW_EXTRA = [
    "INIT/USDT", "EIGEN/USDT", "EIGEN/USDT", "SCR/USDT", "DRIFT/USDT",
    "ZRO/USDT", "LISTA/USDT", "ME/USDT", "MOVE/USDT", "S/USDT",
    "BABY/USDT", "PUMP/USDT", "HYPE/USDT", "VIRTUAL/USDT", "AERO/USDT"
]

ALL_COINS = list(dict.fromkeys(MAJOR_ALT + QUANT + NEW_EXTRA))  # 60

# Filters
MIN_SCORE = 80
ADX_MIN_5M = 20
ADX_MIN_15M = 20
COOLDOWN_HOURS = 4
PRICE_MOVE_OVERRIDE = 0.02  # 2%
ALIVE_EVERY_HOURS = 4
DEAD_HOURS_UTC = [0, 1]  # 01:00-02:00 Lagos = dead, no trade

# ============ EXCHANGE ============
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

def send_telegram(msg):
    if not TOKEN or not CHAT_ID:
        print("No Telegram creds")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    for cid in [CHAT_ID, BROADCAST_ID]:
        if not cid:
            continue
        try:
            requests.post(url, json={"chat_id": cid, "text": msg, "parse_mode": "HTML"}, timeout=10)
        except Exception as e:
            print(f"TG error {e}")

# ============ CACHE ============
def load_seen():
    try:
        with open(SEEN_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f)

def should_send_alive():
    try:
        with open(ALIVE_FILE) as f:
            last = float(f.read().strip())
        hours = (time.time() - last) / 3600
        return hours >= ALIVE_EVERY_HOURS
    except:
        return True

def mark_alive():
    with open(ALIVE_FILE, "w") as f:
        f.write(str(time.time()))

# ============ INDICATORS ============
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def adx(df, period=14):
    high = df['high']; low = df['low']; close = df['close']
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    return dx.rolling(period).mean().iloc[-1]

def get_ohlcv(symbol, tf, limit=100):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
        df['ema7'] = ema(df['close'], 7)
        df['ema14'] = ema(df['close'], 14)
        df['ema28'] = ema(df['close'], 28)
        df['ma7'] = df['close'].rolling(7).mean()
        df['ma14'] = df['close'].rolling(14).mean()
        # Bollinger
        df['boll_mid'] = df['close'].rolling(20).mean()
        df['boll_std'] = df['close'].rolling(20).std()
        df['boll_up'] = df['boll_mid'] + 2*df['boll_std']
        df['boll_low'] = df['boll_mid'] - 2*df['boll_std']
        return df
    except Exception as e:
        print(f"{symbol} {tf} error {e}")
        return None

def trend_of(df):
    if df is None: return "NEUTRAL"
    last = df.iloc[-1]
    if last['close'] > last['ema7'] > last['ema14'] > last['ema28']:
        return "BULL"
    if last['close'] < last['ema7'] < last['ema14'] < last['ema28']:
        return "BEAR"
    return "NEUTRAL"

# ============ BTC DYNAMIC ============
def get_btc_status():
    try:
        df = get_ohlcv("BTC/USDT", "4h", 50)
        if df is None: return "NEUTRAL", 0
        return trend_of(df), df.iloc[-1]['close']
    except:
        return "NEUTRAL", 0

def is_alt_season_dynamic():
    try:
        # Compare alts vs BTC last 24h
        tickers = exchange.fetch_tickers(["PEPE/USDT","WIF/USDT","SOL/USDT","ARB/USDT","OP/USDT","BTC/USDT"])
        alt_changes = []
        for s in ["PEPE/USDT","WIF/USDT","SOL/USDT","ARB/USDT","OP/USDT"]:
            if s in tickers and tickers[s].get('percentage') is not None:
                alt_changes.append(tickers[s]['percentage'])
        btc_chg = tickers["BTC/USDT"]['percentage'] if "BTC/USDT" in tickers else 0
        if not alt_changes: return False, 0, btc_chg
        avg_alt = sum(alt_changes)/len(alt_changes)
        diff = avg_alt - btc_chg
        print(f"BTC DOM Alt {avg_alt:.1f}% vs BTC {btc_chg:.1f}% AltSeason={diff>4.5}")
        return diff > 4.5, avg_alt, btc_chg
    except Exception as e:
        print(f"Alt season error {e}")
        return False, 0, 0

# ============ SCORING ============
def score_coin(symbol, cat, btc_status, alt_season):
    df_5m = get_ohlcv(symbol, "5m", 100)
    df_15m = get_ohlcv(symbol, "15m", 100)
    df_30m = get_ohlcv(symbol, "30m", 100)
    df_4h = get_ohlcv(symbol, "4h", 100)
    if df_5m is None or df_15m is None or df_30m is None or df_4h is None:
        return None

    t_5 = trend_of(df_5m); t_15 = trend_of(df_15m)
    t_30 = trend_of(df_30m); t_4h = trend_of(df_4h)

    # Need 4TF alignment
    if t_5 == t_15 == t_30 == t_4h and t_5 in ["BULL","BEAR"]:
        direction = "LONG" if t_5 == "BULL" else "SHORT"
        trend_score = 25
    else:
        # 3TF partial still considered but low
        return None

    # BTC Dynamic Filter
    if not alt_season:
        if btc_status == "BEAR" and direction == "LONG" and cat != "NEW":
            print(f"{symbol} blocked: BTC BEAR blocks LONG")
            return None
        if btc_status == "BULL" and direction == "SHORT" and cat != "NEW":
            print(f"{symbol} blocked: BTC BULL blocks SHORT")
            return None

    # ADX
    adx_5 = adx(df_5m); adx_15 = adx(df_15m)
    if adx_5 < ADX_MIN_5M or adx_15 < ADX_MIN_15M:
        return None
    adx_score = 25 if adx_5 > 30 else 15

    # Volume - 20 period avg
    vol = df_5m.iloc[-1]['volume']
    vol_avg = df_5m['volume'].rolling(20).mean().iloc[-1]
    if vol < vol_avg * 1.2:
        return None
    vol_score = 20

    # Spread + Imbalance from orderbook
    try:
        ob = exchange.fetch_order_book(symbol, limit=10)
        best_bid = ob['bids'][0][0] if ob['bids'] else 0
        best_ask = ob['asks'][0][0] if ob['asks'] else 0
        spread = (best_ask - best_bid) / best_bid if best_bid else 1
        if spread > 0.001:  # 0.1% max
            return None
        spread_score = 15
        bid_vol = sum([b[1] for b in ob['bids']])
        ask_vol = sum([a[1] for a in ob['asks']])
        total = bid_vol + ask_vol
        imb = (bid_vol - ask_vol) / total if total else 0
        if direction == "LONG" and imb < -0.1:  # sell pressure
            return None
        if direction == "SHORT" and imb > 0.1:
            return None
        imb_score = 10
    except Exception as e:
        print(f"{symbol} OB error {e}")
        return None

    # Time filter - active hours
    time_score = 5  # already filtered dead hours in main

    total_score = trend_score + adx_score + vol_score + spread_score + imb_score + time_score
    # NEW bonus for new listings
    if cat == "NEW":
        total_score += 0  # no bonus, must earn it

    if total_score < MIN_SCORE:
        return None

    price = df_5m.iloc[-1]['close']
    # TP/SL: 1.5% SL, TP1 2%, TP2 4%, TP3 6%
    if direction == "LONG":
        sl = price * 0.985
        tp1 = price * 1.02; tp2 = price * 1.04; tp3 = price * 1.06
    else:
        sl = price * 1.015
        tp1 = price * 0.98; tp2 = price * 0.96; tp3 = price * 0.94

    return {
        "symbol": symbol, "direction": direction, "score": total_score,
        "price": price, "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3,
        "adx5": round(adx_5,1), "adx15": round(adx_15,1), "cat": cat
    }

def format_signal(s):
    emoji = "🟢" if s['direction']=="LONG" else "🔴"
    return (
        f"{emoji} <b>{s['symbol']} {s['direction']}</b> | {s['cat']}\n"
        f"Score: {s['score']}/100 | ADX 5m {s['adx5']} 15m {s['adx15']}\n"
        f"Entry: {s['price']:.5f}\n"
        f"SL: {s['sl']:.5f} (-1.5%)\n"
        f"TP1: {s['tp1']:.5f} (+2%)\n"
        f"TP2: {s['tp2']:.5f} (+4%)\n"
        f"TP3: {s['tp3']:.5f} (+6%)\n"
        f"Leverage: 10x | Risk 1%"
    )

# ============ MAIN ============
def main():
    now_utc = datetime.now(timezone.utc)
    hour_utc = now_utc.hour
    lagos = now_utc.strftime("%H:%M")
    print(f"Run start UTC {now_utc} Lagos {lagos}")

    seen = load_seen()
    btc_status, btc_price = get_btc_status()
    alt_season, avg_alt, btc_chg = is_alt_season_dynamic()
    print(f"BTC STATUS: {btc_status} AltSeason={alt_season}")

    # Dead hours check
    is_dead = hour_utc in DEAD_HOURS_UTC
    if is_dead:
        if should_send_alive():
            send_telegram(f"🤖 <b>Bot Alive</b>\nDead hours {hour_utc} UTC - No trade\nBTC: {btc_status} ${btc_price:.0f}\nAltSeason: {alt_season}")
            mark_alive()
        print("Dead hours - no scan")
        return

    sent = 0
    checked = 0

    # Build list with categories
    jobs = []
    for s in MAJOR_ALT: jobs.append((s, "MAJOR/ALT"))
    for s in QUANT: jobs.append((s, "QUANT"))
    for s in NEW_EXTRA: jobs.append((s, "NEW"))

    for symbol, cat in jobs:
        checked += 1
        # Cooldown check
        if symbol in seen:
            last_time = seen[symbol].get("time", 0)
            last_price = seen[symbol].get("price", 0)
            hours_since = (time.time() - last_time) / 3600
            # need current price to check 2% move - get quickly from 5m already in score, skip if too soon
            if hours_since < COOLDOWN_HOURS:
                # We still allow if price moved >2% - we check in score, but to save time, skip unless we know price
                # Let score function run if we want override - we do lightweight check: fetch ticker
                try:
                    ticker = exchange.fetch_ticker(symbol)
                    cur = ticker['last']
                    if last_price and abs(cur - last_price)/last_price < PRICE_MOVE_OVERRIDE:
                        continue
                    # If direction flipped, also allow - handled by score returning new direction
                    if seen[symbol].get("direction") == "SAME":
                        pass
                except:
                    continue

        result = score_coin(symbol, cat, btc_status, alt_season)
        if result:
            # Check cooldown again with direction
            if symbol in seen:
                prev = seen[symbol]
                hours_since = (time.time() - prev.get("time",0))/3600
                if hours_since < COOLDOWN_HOURS:
                    # Only send if direction flipped OR price moved >2%
                    if prev.get("direction") == result['direction'] and abs(result['price']-prev.get("price",0))/prev.get("price",1) < PRICE_MOVE_OVERRIDE:
                        print(f"{symbol} cooldown skip")
                        continue
            send_telegram(format_signal(result))
            seen[symbol] = {"time": time.time(), "price": result['price'], "direction": result['direction']}
            sent += 1
            print(f"SENT {symbol} {result['direction']} {result['score']}")

    save_seen(seen)
    print(f"Checked:{checked} Sent:{sent} Seen:{len(seen)}")

    if should_send_alive():
        send_telegram(
            f"🤖 <b>Bot Alive</b>\n"
            f"Checked: {checked} | Sent: {sent}\n"
            f"BTC: {btc_status} ${btc_price:.0f} | AltSeason: {alt_season}\n"
            f"BTC Dynamic: ON | Shorts Allowed\n"
            f"Time: {lagos} Lagos"
        )
        mark_alive()

if __name__ == "__main__":
    main()
