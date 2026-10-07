import ccxt, requests, os
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

POSITION_USDT = 20
LEVERAGE = 20
TP1_PCT = 4.0
TP2_PCT = 8.0
SL_PCT = 2.5

TIMEFRAMES = ['5m', '30m', '2h', '6h', '1d']
COINS = ['BTC/USDT','ETH/USDT','SOL/USDT','XRP/USDT','DOGE/USDT','PEPE/USDT','SHIB/USDT','WIF/USDT','BONK/USDT','FLOKI/USDT','AVAX/USDT','LINK/USDT','ADA/USDT','LTC/USDT','BCH/USDT','TAO/USDT','FET/USDT','ENA/USDT','ONDO/USDT','SUI/USDT']

def send(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except Exception as e:
        print(e)

def ema(data, period):
    if len(data) < period: return None
    k = 2 / (period + 1)
    ema_val = sum(data[:period]) / period
    for price in data[period:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val

def rsi(closes, period=14):
    if len(closes) < period + 1: return 50
    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = closes[-i] - closes[-i-1]
        if diff > 0: gains.append(diff)
        else: losses.append(abs(diff))
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0.0001
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def macd(closes):
    if len(closes) < 26: return 0, 0
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    if not ema12 or not ema26: return 0, 0
    macd_line = ema12 - ema26
    # signal is EMA9 of macd - simplified
    return macd_line, macd_line # for speed, we use macd line cross 0 as signal

def get_tf_data(ex, symbol, tf):
    try:
        ohlcv = ex.fetch_ohlcv(symbol, tf, limit=100)
        if len(ohlcv) < 50: return None
        closes = [c[4] for c in ohlcv]
        close = closes[-1]
        prev = closes[-2]
        change = ((close - prev) / prev) * 100

        ema7 = ema(closes, 7)
        ema20 = ema(closes, 20)
        ema50 = ema(closes, 50)
        rsi_val = rsi(closes)
        macd_line, _ = macd(closes)

        # Trend logic with EMA7/20/50
        trend = 0
        if close > ema7 and ema7 > ema20 and ema20 > ema50:
            trend = 1 # Strong bullish
        elif close < ema7 and ema7 < ema20 and ema20 < ema50:
            trend = -1 # Strong bearish
        elif close > ema20:
            trend = 1
        elif close < ema20:
            trend = -1

        vol_mult = 1
        if tf == '5m':
            vol = ohlcv[-1][5]
            avg = sum(c[5] for c in ohlcv[-6:-1]) / 5
            vol_mult = vol / avg if avg else 0

        return {
            "close": close, "change": change, "trend": trend,
            "ema7": ema7, "ema20": ema20, "ema50": ema50,
            "rsi": rsi_val, "macd": macd_line, "vol_mult": vol_mult
        }
    except:
        return None

def analyze():
    ex = ccxt.mexc()
    try:
        btc = get_tf_data(ex, 'BTC/USDT', '5m')
        btc_chg = btc['change'] if btc else 0
    except:
        btc_chg = 0

    for symbol in COINS:
        try:
            tf_results = {}
            for tf in TIMEFRAMES:
                d = get_tf_data(ex, symbol, tf)
                if d: tf_results[tf] = d

            if '5m' not in tf_results: continue
            m5 = tf_results['5m']

            # === STRICT FILTERS ===
            if abs(m5['change']) < 2.5: continue
            if m5['vol_mult'] < 1.8: continue
            if m5['rsi'] > 80 or m5['rsi'] < 20: continue # Overbought/oversold skip

            # EMA7 filter - price must respect EMA7
            if m5['change'] > 0 and m5['close'] < m5['ema7']: continue
            if m5['change'] < 0 and m5['close'] > m5['ema7']: continue

            # MACD filter - must be in momentum direction
            if m5['change'] > 0 and m5['macd'] < 0: continue
            if m5['change'] < 0 and m5['macd'] > 0: continue

            # MTF alignment
            bullish = sum(1 for v in tf_results.values() if v['trend'] == 1)
            bearish = sum(1 for v in tf_results.values() if v['trend'] == -1)

            side = None
            if m5['change'] > 0 and bullish >= 4 and m5['trend'] == 1:
                side = "LONG"
                align = bullish
            elif m5['change'] < 0 and bearish >= 4 and m5['trend'] == -1:
                side = "SHORT"
                align = bearish
            else:
                continue

            if side == "LONG" and btc_chg < -1: continue
            if side == "SHORT" and btc_chg > 1: continue

            score = 60
            if abs(m5['change']) >= 3.5: score += 10
            if abs(m5['change']) >= 5: score += 10
            if m5['vol_mult'] >= 2.5: score += 10
            score += align * 2
            if m5['rsi'] >= 60 and m5['rsi'] <= 75 and side=="LONG": score += 5
            if m5['rsi'] <= 40 and m5['rsi'] >= 25 and side=="SHORT": score += 5
            score = min(score, 99)

            if score < 80: continue

            entry = m5['close']
            tp1 = entry * (1 + TP1_PCT/100) if side=="LONG" else entry * (1 - TP1_PCT/100)
            tp2 = entry * (1 + TP2_PCT/100) if side=="LONG" else entry * (1 - TP2_PCT/100)
            sl = entry * (1 - SL_PCT/100) if side=="LONG" else entry * (1 + SL_PCT/100)

            mtf_line = " | ".join([f"{tf}:{tf_results[tf]['change']:+.1f}%" for tf in TIMEFRAMES if tf in tf_results])

            msg = (
                f"🚀 FUTURE CALLS {symbol} {side} | Score {score}/100\n"
                f"MTF {align}/5 Aligned | {mtf_line}\n"
                f"5m {m5['change']:+.2f}% x{m5['vol_mult']:.1f}Vol | RSI {m5['rsi']:.0f} | MACD {'🟢' if m5['macd']>0 else '🔴'}\n"
                f"EMA7:{m5['ema7']:.4g} EMA20:{m5['ema20']:.4g} EMA50:{m5['ema50']:.4g}\n"
                f"BTC 5m {btc_chg:+.1f}%\n\n"
                f"ENTRY: {entry:.8g}\n"
                f"LEV: {LEVERAGE}x | ${POSITION_USDT}\n"
                f"TP1: {tp1:.8g} (+4%) | TP2: {tp2:.8g} (+8%)\n"
                f"SL: {sl:.8g} (-2.5%)\n\n"
                f"✅ All filters: EMA7/20/50 + MACD + RSI + Vol + MTF"
            )
            send(msg)
            return

        except Exception as e:
            print(f"{symbol} {e}")
            continue

    now = datetime.utcnow().strftime("%H:%M UTC")
    send(f"💓 Bot Lively - MTF PRO Scan\nScanned {len(COINS)} coins x 5 TFs\nFilters: EMA7/20/50 + MACD + RSI + Vol + MTF 4/5\nNo signal - all below 80 | {now}")

if __name__ == "__main__":
    analyze()
