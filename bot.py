import requests, time, yaml
from datetime import datetime

with open("bot.yml") as f:
    cfg = yaml.safe_load(f)

LIVE_SYMBOLS = []

def update_bybit_list():
    global LIVE_SYMBOLS
    url = "https://api.bybit.com/v5/market/instruments-info?category=linear&limit=1000"
    data = requests.get(url).json()
    LIVE_SYMBOLS = [x['symbol'] for x in data['result']['list'] if x['symbol'].endswith("USDT")]
    blacklist = cfg['rules']['filters']['blacklist']
    LIVE_SYMBOLS = [s for s in LIVE_SYMBOLS if s not in blacklist]
    print(f"✅ {len(LIVE_SYMBOLS)} Bybit Futures coins loaded")
    return LIVE_SYMBOLS

def get_tickers():
    url = "https://api.bybit.com/v5/market/tickers?category=linear"
    return requests.get(url).json()['result']['list']

def calculate_score_and_trade(ticker):
    last = float(ticker['lastPrice'])
    change = float(ticker['price24hPcnt']) * 100
    volume = float(ticker['turnover24h'])
    high = float(ticker['highPrice24h'])
    low = float(ticker['lowPrice24h'])
    vol_24h = ((high - low) / low * 100) if low else 0

    # HARD 80/100 FILTERS
    if volume < cfg['rules']['filters']['min_volume_24h_usdt']: return None
    if vol_24h < cfg['rules']['filters']['min_volatility_24h']: return None
    if abs(change) < 1.5: return None

    score = 0
    if volume > 100_000_000: score += 30
    elif volume > 30_000_000: score += 25
    elif volume > 10_000_000: score += 20
    else: score += 15

    if vol_24h > 20: score += 40
    elif vol_24h > 12: score += 35
    elif vol_24h > 8: score += 30
    elif vol_24h > 5: score += 25
    else: score += 20

    if abs(change) > 15: score += 30
    elif abs(change) > 9: score += 27
    elif abs(change) > 5: score += 23
    else: score += 18

    score = min(score, 100)
    if score < 80: return None # 80/100 STRICT

    # --- ENTRY / LEVERAGE / TP / SL CALCULATION ---
    is_major = ticker['symbol'] in cfg['rules']['majors']
    direction = "LONG" if change > 0 else "SHORT"

    entry = last

    # Leverage Rule: Majors = Low Lev, Alts = Higher but controlled for 80/100
    if is_major:
        if vol_24h > 10: leverage = 5
        elif vol_24h > 5: leverage = 8
        else: leverage = 10
        # Majors are safer
        tp1_pct, tp2_pct, tp3_pct = 1.2, 2.5, 4.0
        sl_pct = 1.5
    else:
        # Alts - Big PnL but 80/100 strict
        if vol_24h > 15: leverage = 8
        elif vol_24h > 8: leverage = 10
        else: leverage = 12
        tp1_pct, tp2_pct, tp3_pct = 2.0, 4.5, 7.0
        sl_pct = 2.0

    if direction == "LONG":
        tp1 = entry * (1 + tp1_pct/100)
        tp2 = entry * (1 + tp2_pct/100)
        tp3 = entry * (1 + tp3_pct/100)
        sl = entry * (1 - sl_pct/100)
        liq_pct = 100 / leverage * 0.85 # Approx liquidation distance
    else:
        tp1 = entry * (1 - tp1_pct/100)
        tp2 = entry * (1 - tp2_pct/100)
        tp3 = entry * (1 - tp3_pct/100)
        sl = entry * (1 + sl_pct/100)
        liq_pct = 100 / leverage * 0.85

    return {
        "symbol": ticker['symbol'],
        "score": score,
        "group": "A-MAJOR" if is_major else "B-ALT",
        "direction": direction,
        "entry": entry,
        "leverage": leverage,
        "tp1": tp1, "tp2": tp2, "tp3": tp3,
        "tp1_pct": tp1_pct, "tp2_pct": tp2_pct, "tp3_pct": tp3_pct,
        "sl": sl, "sl_pct": sl_pct,
        "change": change, "vol_24h": vol_24h,
        "liq_dist": liq_pct
    }

def scan():
    tickers = get_tickers()
    signals = []
    for t in tickers:
        if t['symbol'] not in LIVE_SYMBOLS: continue
        trade = calculate_score_and_trade(t)
        if trade: signals.append(trade)

    signals.sort(key=lambda x: x['score'], reverse=True)
    majors = [s for s in signals if s['group'] == "A-MAJOR"][:4]
    alts = [s for s in signals if s['group'] == "B-ALT"][:6]
    final = sorted(majors + alts, key=lambda x: x['score'], reverse=True)

    for s in final:
        tag = "🔥 BIG PnL 80/100" if s['score'] >= 90 else "✅ 80/100 STRICT"
        msg = f"""
{tag} | {s['symbol']} | {s['group']} | {s['direction']}

ENTRY: {s['entry']:.6f}
LEVERAGE: {s['leverage']}x Isolated

TP1: {s['tp1']:.6f} (+{s['tp1_pct']}%)
TP2: {s['tp2']:.6f} (+{s['tp2_pct']}%)
TP3: {s['tp3']:.6f} (+{s['tp3_pct']}%) - Runner

SL: {s['sl']:.6f} (-{s['sl_pct']}%)
Liq Distance: ~{s['liq_dist']:.1f}%

Stats: Score {s['score']}/100 | 24h {s['change']:.2f}% | Vol {s['vol_24h']:.1f}%
Market: Bybit Futures Linear | {s['symbol']}
"""
        print(msg)

if __name__ == "__main__":
    update_bybit_list()
    last = time.time()
    while True:
        if time.time() - last > 21600:
            update_bybit_list()
            last = time.time()
        print(f"\n=== SCAN {datetime.utcnow()} UTC | 80/100 STRICT ===")
        try: scan()
        except Exception as e: print(e)
        time.sleep(180) # 3 mins
