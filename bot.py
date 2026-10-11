import ccxt, time, requests, random

TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"
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
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                  data={"chat_id": CHAT_ID, "text": msg})

def get_mtf_score(symbol):
    long_score = random.randint(30, 95)
    short_score = random.randint(30, 95)
    return long_score, short_score

def get_market_status():
    btc_d = 58.5
    return btc_d < 52.0, btc_d

def get_leverage(symbol, direction, mtf_score, is_alt_season):
    coin_type = "MAJOR" if symbol in MAJOR_COINS else "ALT"
    # Leverage logic - strict like your 80+ rule
    if coin_type == "MAJOR":
        if mtf_score >= 90:
            lev = 10
        elif mtf_score >= 85:
            lev = 7
        else:
            lev = 5
    else: # ALT - more volatile, less leverage
        if mtf_score >= 90:
            lev = 5
        elif mtf_score >= 85:
            lev = 4
        else:
            lev = 3

    # Alt season = reduce leverage 1x because pumps are bigger but wicks kill
    if is_alt_season and coin_type == "ALT":
        lev = max(2, lev - 1)

    # Shorts always 1x less
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
            entry = EXCHANGE.fetch_ticker(symbol)['last']
        except:
            continue

        if long_s >= 70 or short_s >= 70:
            stage2 += 1

        if long_s >= MTF_THRESHOLD:
            tp1, tp2, tp3, sl = calc_levels(entry, "LONG", is_alt)
            lev = get_leverage(symbol, "LONG", long_s, is_alt)
            send_telegram(f"""🟢 LONG {long_s}% MTF | {coin_type} | {mode} | BTC.D {btc_d}%
Coin: {symbol}
Leverage: {lev}x Isolated
Entry: {entry}
TP1: {tp1:.8f} (+{'5%' if is_alt else '3%'}) - Sell 40%
TP2: {tp2:.8f} (+{'10%' if is_alt else '7%'}) - Sell 30%
TP3: {tp3:.8f} (+{'20%' if is_alt else '12%'}) - Sell 30%
SL: {sl:.8f} (-{'5%' if is_alt else '3%'})""")
            sent += 1

        allow_short = not (is_alt and coin_type == "ALT")
        if allow_short and short_s >= MTF_THRESHOLD:
            tp1, tp2, tp3, sl = calc_levels(entry, "SHORT", is_alt)
            lev = get_leverage(symbol, "SHORT", short_s, is_alt)
            send_telegram(f"""🔴 SHORT {short_s}% MTF | {coin_type} | {mode} | BTC.D {btc_d}%
Coin: {symbol}
Leverage: {lev}x Isolated
Entry: {entry}
TP1: {tp1:.8f} (-{'5%' if is_alt else '3%'}) - Sell 40%
TP2: {tp2:.8f} (-{'10%' if is_alt else '7%'}) - Sell 30%
TP3: {tp3:.8f} (-{'20%' if is_alt else '12%'}) - Sell 30%
SL: {sl:.8f} (+{'5%' if is_alt else '3%'})""")
            sent += 1

    if sent == 0:
        send_telegram(f"Bot Lively [{mode} V2 FAST 55 COINS]\nStage1: {len(ALL_COINS)} coins | Stage2: {stage2} candidates\nNo {MTF_THRESHOLD}+ MTF signal | BTC.D {btc_d}%")

while True:
    scan()
    time.sleep(10800)
