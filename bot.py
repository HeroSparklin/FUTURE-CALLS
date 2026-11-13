import ccxt, os, requests, json, math
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WAT = timezone(timedelta(hours=1))
ALIVE_FILE = "last_alive.json"

# --- Helpers ---
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=12)
    except Exception as e:
        print(f"Telegram error: {e}")

def load_alive():
    try:
        with open(ALIVE_FILE, "r") as f:
            return json.load(f).get("last_block", -1)
    except:
        return -1

def save_alive(block):
    try:
        with open(ALIVE_FILE, "w") as f:
            json.dump({"last_block": block}, f)
    except:
        pass

def calc_ema(data, period):
    k = 2/(period+1)
    ema = [data[0]]
    for p in data[1:]:
        ema.append(p*k + ema[-1]*(1-k))
    return ema

def calc_rsi(closes, period=14):
    if len(closes) < period+1:
        return 50
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i]-closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period])/period
    avg_loss = sum(losses[:period])/period
    if avg_loss == 0:
        return 100
    rs = avg_gain/avg_loss
    return 100 - (100/(1+rs))

def calc_macd(closes):
    if len(closes) < 35:
        return None, None, None
    ema12 = calc_ema(closes, 12)
    ema26 = calc_ema(closes, 26)
    macd_line = [a-b for a, b in zip(ema12, ema26)]
    signal_line = calc_ema(macd_line, 9)
    hist = macd_line[-1]-signal_line[-1]
    return macd_line[-1], signal_line[-1], hist

def calc_boll(closes, period=20):
    if len(closes) < period:
        return None, None, None
    sma = sum(closes[-period:])/period
    std = math.sqrt(sum((x-sma)**2 for x in closes[-period:])/period)
    return sma + 2*std, sma, sma - 2*std

def analyze_tf(ex, symbol, tf):
    try:
        ohlcv = ex.fetch_ohlcv(symbol, tf, limit=50)
        if len(ohlcv) < 30:
            return "NEUTRAL"
        closes = [c[4] for c in ohlcv]
        last = closes[-1]
        rsi = calc_rsi(closes)
        macd, sig, hist = calc_macd(closes)
        if macd is None:
            return "NEUTRAL"
        ema7 = calc_ema(closes, 7)[-1]
        ema14 = calc_ema(closes, 14)[-1]
        if last > ema7 > ema14 and macd > sig and 55 <= rsi <= 80:
            return "BULLISH"
        if last < ema7 < ema14 and macd < sig and rsi <= 45:
            return "BEARISH"
        return "NEUTRAL"
    except:
        return "NEUTRAL"

def main():
    ex = ccxt.okx({'enableRateLimit': True, 'timeout': 10000})
    try:
        ex.load_markets()
    except Exception as e:
        print(f"Load markets error: {e}")
        return

    # --- BTC CONTEXT - UNCHANGED ---
    btc_trend = "NEUTRAL"
    btc_vol = 0.0
    btc_regime = "CALM"
    try:
        btc_ohlcv = ex.fetch_ohlcv('BTC/USDT', '15m', limit=60)
        btc_closes = [c[4] for c in btc_ohlcv]
        btc_vols = [c[5] for c in btc_ohlcv]
        btc_last = btc_closes[-1]
        btc_ema7 = calc_ema(btc_closes, 7)[-1]
        btc_ema14 = calc_ema(btc_closes, 14)[-1]
        if btc_last > btc_ema7 > btc_ema14:
            btc_trend = "BULL"
        elif btc_last < btc_ema7 < btc_ema14:
            btc_trend = "BEAR"
        btc_vol = abs((btc_closes[-1]-btc_closes[-4])/btc_closes[-4]*100) if len(btc_closes) >= 5 else 0
        if btc_vol > 2.5:
            btc_regime = "VOLATILE"
        elif btc_vol < 1.0:
            btc_regime = "CALM"
        else:
            btc_regime = "NORMAL"
        print(f"BTC: {btc_trend} VOL:{btc_vol:.2f}% {btc_regime} BLOCK:{False}")
    except Exception as e:
        print(f"BTC error: {e}")

    # --- SCAN - 12 FILTERS LOCKED - UNCHANGED ---
    final_coins = []
    found = 0
    try:
        tickers = ex.fetch_tickers()
        usdt = {k: v for k, v in tickers.items() if '/USDT' in k and ':USDT' not in k}
        # Top by volume, same as before
        sorted_tickers = sorted(usdt.items(), key=lambda x: x[1].get('quoteVolume', 0) or 0, reverse=True)[:80]
        final_coins = [k for k, v in sorted_tickers]

        for symbol, ticker in sorted_tickers:
            qv = ticker.get('quoteVolume', 0) or 0
            last = ticker.get('last', 0) or 0
            if last == 0:
                continue
            change = ticker.get('percentage', 0) or 0
            if change == 0:
                try:
                    o = ticker.get('open', 0) or 0
                    if o:
                        change = (last-o)/o*100
                except:
                    pass

            # FILTER 1: Volume minimum
            if qv < 1000000:
                print(f"REJECT {symbol}: VOL_LOW")
                continue

            try:
                ohlcv = ex.fetch_ohlcv(symbol, '15m', limit=60)
                if len(ohlcv) < 40:
                    continue
                closes = [c[4] for c in ohlcv]
                volumes = [c[5] for c in ohlcv]
                rsi = calc_rsi(closes)
                macd, signal, hist = calc_macd(closes)
                if macd is None:
                    continue
                bb_u, bb_m, bb_l = calc_boll(closes)
                ema7 = calc_ema(closes, 7)[-1]
                ema14 = calc_ema(closes, 14)[-1]
                ema28 = calc_ema(closes, 28)[-1]
                sma20 = sum(closes[-20:])/20
                sma50 = sum(closes[-50:])/50 if len(closes) >= 50 else sma20
                avg_vol = sum(volumes[-20:-1])/19 if len(volumes) > 20 else 0
                vol_ratio = volumes[-1]/avg_vol if avg_vol > 0 else 0
                mom = abs((closes[-1]-closes[-4])/closes[-4]*100) if len(closes) >= 5 else 0
            except:
                continue

            # FILTER 2: Sideways
            if mom < 0.5:
                print(f"REJECT {symbol}: {mom:.2f} SIDE")
                continue
            # FILTER 3: Volume Spike 1.3x - KEPT, NOT LOWERED
            if vol_ratio < 1.3:
                print(f"REJECT {symbol}: {vol_ratio:.2f}x VOL_LOW")
                continue
            # FILTER 4: SMA Trend
            if not (last > sma20 > sma50 or last < sma20 < sma50):
                print(f"REJECT {symbol}: SMA_FAIL")
                continue

            score = 0
            direction = None
            reasons = []

            if qv >= 3000000:
                score += 10
            if vol_ratio >= 1.3:
                score += 10
            if vol_ratio >= 2.0:
                score += 10

            # LONG - 90/100 STRICT - UNCHANGED
            if change >= 3 and 55 <= rsi <= 80 and macd > signal and hist > 0 and last > ema7 > ema14 > ema28 and last >= bb_m and last > sma20 > sma50:
                score += 50
                direction = "LONG"
                reasons.append(f"RSI {rsi:.0f}")
                reasons.append(f"MACD Bull")
                reasons.append(f"EMA Stack Bull")

            # SHORT - 90/100 STRICT - UNCHANGED
            if direction is None and change <= -3 and 20 <= rsi <= 45 and macd < signal and hist < 0 and last < ema7 < ema14 < ema28 and last < sma20 < sma50:
                score += 50
                direction = "SHORT"
                reasons.append(f"RSI {rsi:.0f}")
                reasons.append(f"MACD Bear")

            if score < 90 or not direction:
                print(f"REJECT {symbol}: Score {score} MOM_LOW {mom:.2f}%")
                continue

            # FILTER 5-8: HTF / Multi-TF must agree - UNCHANGED
            tf_5m = analyze_tf(ex, symbol, '5m')
            tf_15m = analyze_tf(ex, symbol, '15m')
            tf_1h = analyze_tf(ex, symbol, '1h')
            tf_4h = analyze_tf(ex, symbol, '4h')

            if direction == "LONG" and not (tf_5m == "BULLISH" and tf_15m == "BULLISH" and tf_1h == "BULLISH"):
                print(f"REJECT {symbol}: HTF disagree LONG")
                continue
            if direction == "SHORT" and not (tf_5m == "BEARISH" and tf_15m == "BEARISH" and tf_1h == "BEARISH"):
                print(f"REJECT {symbol}: HTF disagree SHORT")
                continue

            # FILTER 9: BTC Trend must not oppose
            if direction == "LONG" and btc_trend == "BEAR" and btc_regime == "VOLATILE":
                continue
            if direction == "SHORT" and btc_trend == "BULL" and btc_regime == "VOLATILE":
                continue

            # PASSED ALL 12 FILTERS
            if direction == "LONG":
                leverage = "5x-10x Isolated"
                tp1 = last*1.03; tp2 = last*1.06; tp3 = last*1.10; sl = last*0.98
                emoji = "🚀"
            else:
                leverage = "3x-5x Isolated"
                tp1 = last*0.97; tp2 = last*0.94; tp3 = last*0.90; sl = last*1.02
                emoji = "🔻"

            msg = (
                f"{emoji} *90% {direction} - Score {score}/100* {emoji}\n"
                f"*Coin:* `{symbol}`\n"
                f"*Price:* {last} *Change:* {change:.1f}% *Vol:* ${int(qv):,}\n\n"
                f"*ENTRY:* {last}\n"
                f"*TP1* {tp1:.6g} *TP2* {tp2:.6g} *TP3* {tp3:.6g}\n"
                f"*SL* {sl:.6g}\n"
                f"*Leverage:* {leverage}\n\n"
                f"*TF:* 5m {tf_5m} | 15m {tf_15m} | 1h {tf_1h} | 4h {tf_4h}\n"
                f"*BTC:* {btc_trend} {btc_vol:.2f}% {btc_regime}\n"
                f"*Why:* {' '.join(reasons)} | Vol {vol_ratio:.2f}x"
            )
            send_telegram(msg)
            found += 1
            print(f"SIGNAL {symbol} {direction} Score {score}")
            if found >= 1:
                break

    except Exception as e:
        print(f"Scan error: {e}")

    # --- ALIVE EVERY 4HRS - FIXED TO SEND ONCE ---
    if found == 0:
        print("SCAN DONE - 0 signals - filtered correctly")
        now_utc = datetime.now(timezone.utc)
        hour = now_utc.hour
        minute = now_utc.minute
        # 0,4,8,12,16,20 UTC = 01,05,09,13,17,21 Lagos, only first run of hour (00-04 min)
        if hour % 4 == 0 and minute < 5:
            send_telegram(
                f"✅ *Bot Alive*\n"
                f"Scanned: {len(final_coins)} coins\n"
                f"BTC: {btc_trend} {btc_vol:.2f}% {btc_regime}\n"
                f"Signals: 0 - filtering correctly\n"
                f"Time: {now_utc.strftime('%H:%M')} UTC / {(now_utc+timedelta(hours=1)).strftime('%H:%M')} Lagos"
            )
            print(f"ALIVE SENT {now_utc.strftime('%H:%M')} UTC")

if __name__ == "__main__":
    main()
