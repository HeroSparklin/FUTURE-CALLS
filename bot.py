import ccxt
import requests
import random
import os
import yaml

# Load secrets from GitHub Secrets
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Config
EXCHANGE = ccxt.binance()
MTF_THRESHOLD = 80

MAJOR_COINS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "ADA/USDT", "AVAX/USDT", "DOGE/USDT", "TRX/USDT", "DOT/USDT",
    "LINK/USDT", "BCH/USDT", "NEAR/USDT", "LTC/USDT", "UNI/USDT"
]

ALT_COINS = [
    "SHIB/USDT", "PEPE/USDT", "WIF/USDT", "BONK/USDT", "FLOKI/USDT",
    "QNT/USDT", "STONK/USDT", "FET/USDT", "RENDER/USDT", "ARB/USDT",
    "OP/USDT", "MATIC/USDT", "APT/USDT", "SUI/USDT", "INJ/USDT",
    "SEI/USDT", "TIA/USDT", "ENA/USDT", "W/USDT", "JUP/USDT",
    "PYTH/USDT", "STRK/USDT", "WLD/USDT", "FIL/USDT", "ETC/USDT",
    "HBAR/USDT", "ICP/USDT", "ATOM/USDT", "MKR/USDT", "AAVE/USDT",
    "PENGU/USDT", "ASTER/USDT", "POPCAT/USDT", "MEW/USDT", "BRETT/USDT",
    "MOG/USDT", "TURBO/USDT", "NEIRO/USDT", "GOAT/USDT", "PNUT/USDT"
]

ALL_COINS = MAJOR_COINS + ALT_COINS

TP_NORMAL = [0.03, 0.07, 0.12]
SL_NORMAL = 0.03
TP_ALT = [0.05, 0.10, 0.20]
SL_ALT = 0.05

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(f"TELEGRAM MOCK: {msg}")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_mtf_score(symbol):
    # Replace with your real MTF logic
    long_score = random.randint(30, 95)
    short_score = random.randint(30, 95)
    return long_score, short_score

def get_market_status():
    # Replace with real BTC.D fetch
    btc_d = 58.5
    is_alt_season = btc_d < 52.0
    return is_alt_season, btc_d

def get_leverage(symbol, direction, mtf_score, is_alt_season):
    coin_type = "MAJOR" if symbol in MAJOR_COINS else "ALT"
    if coin_type == "MAJOR":
        lev = 10 if mtf_score >= 90 else 7 if mtf_score >= 85 else 5
    else:
        lev = 5 if mtf_score >= 90 else 4 if mtf_score >= 85 else 3

    if is_alt_season and coin_type == "ALT":
        lev = max(2, lev - 1)
    if direction == "SHORT":
        lev = max(2, lev - 1)
    return lev

def calc_levels(entry, direction, is_alt):
    tps = TP_ALT if is_alt else TP_NORMAL
    sl_pct = SL_ALT if is_alt else SL_NORMAL
    if direction == "LONG":
        return entry*(1+tps[0]), entry*(1+tps[1]), entry*(1+tps[2]), entry*(1-sl_pct)
    else:
        return entry*(1-tps[0]), entry*(1-tps[1]), entry*(1-tps[2]), entry*(1+sl_pct)

def scan():
    is_alt, btc_d = get_market_status()
    mode = "ALT SEASON 🟣" if is_alt else "NORMAL"
    sent = 0
    stage2 = 0

    for symbol in ALL_COINS:
        coin_type = "MAJOR" if symbol in MAJOR_COINS else "ALT"
        long_s, short_s = get_mtf_score(symbol)
        try:
            ticker = EXCHANGE.fetch_ticker(symbol)
            entry = ticker['last']
        except:
            continue

        if long_s >= 70 or short_s >= 70:
            stage2 += 1

        if long_s >= MTF_THRESHOLD:
            tp1, tp2, tp3, sl = calc_levels(entry, "LONG", is_alt)
            lev = get_leverage(symbol, "LONG", long_s, is_alt)
            send_telegram(f"🟢 LONG {long_s}% MTF | {coin_type} | {mode} | BTC.D {btc_d}%\nCoin: {symbol}\nLeverage: {lev}x Isolated\nEntry: {entry}\nTP1: {tp1:.8f} (+{'5%' if is_alt else '3%'}) - Sell 40%\nTP2: {tp2:.8f} (+{'10%' if is_alt else '7%'}) - Sell 30%\nTP3: {tp3:.8f} (+{'20%' if is_alt else '12%'}) - Sell 30%\nSL: {sl:.8f} (-{'5%' if is_alt else '3%'})")
            sent += 1

        allow_short = not (is_alt and coin_type == "ALT")
        if allow_short and short_s >= MTF_THRESHOLD:
            tp1, tp2, tp3, sl = calc_levels(entry, "SHORT", is_alt)
            lev = get_leverage(symbol, "SHORT", short_s, is_alt)
            send_telegram(f"🔴 SHORT {short_s}% MTF | {coin_type} | {mode} | BTC.D {btc_d}%\nCoin: {symbol}\nLeverage: {lev}x Isolated\nEntry: {entry}\nTP1: {tp1:.8f} (-{'5%' if is_alt else '3%'}) - Sell 40%\nTP2: {tp2:.8f} (-{'10%' if is_alt else '7%'}) - Sell 30%\nTP3: {tp3:.8f} (-{'20%' if is_alt else '12%'}) - Sell 30%\nSL: {sl:.8f} (+{'5%' if is_alt else '3%'})")
            sent += 1

    if sent == 0:
        send_telegram(f"Bot Lively [{mode} V2 FAST 55 COINS]\nStage1: {len(ALL_COINS)} coins (Major 15 + Alt 40) | Stage2: {stage2} candidates\nNo {MTF_THRESHOLD}+ MTF signal | BTC.D {btc_d}%")

# THIS IS THE FIX - runs once and exits for GitHub Actions
if __name__ == "__main__":
    scan()
    print("Scan complete - exiting")
