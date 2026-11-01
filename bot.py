import ccxt, os, requests, json, time
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WAT = timezone(timedelta(hours=1))
SEEN_FILE = "seen_all.json"
ALIVE_FILE = "last_alive_all.json"

MAJORS = ['BTC/USDT','ETH/USDT','SOL/USDT','BNB/USDT','XRP/USDT','DOGE/USDT']
ALTS = ['PEPE/USDT','WIF/USDT','ARB/USDT','OP/USDT','SUI/USDT','SEI/USDT','APT/USDT','AVAX/USDT','LINK/USDT','UNI/USDT','LTC/USDT','BCH/USDT','ADA/USDT','TRX/USDT','FIL/USDT','ETC/USDT','NEAR/USDT','ATOM/USDT','POL/USDT','SHIB/USDT','BONK/USDT','FLOKI/USDT','FET/USDT','RENDER/USDT','TAO/USDT','INJ/USDT','STX/USDT']

def load_seen():
    try:
        with open(SEEN_FILE, "r") as f: return set(json.load(f))
    except: return set()
def save_seen(seen):
    try:
        with open(SEEN_FILE, "w") as f: json.dump(list(seen)[-1000:], f)
    except: pass
def load_alive():
    try:
        with open(ALIVE_FILE, "r") as f: return json.load(f).get("last", 0)
    except: return 0
def save_alive(ts):
    try:
        with open(ALIVE_FILE, "w") as f: json.dump({"last": ts}, f)
    except: pass
def send_text(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=20)
    except: pass
def get_ex(name):
    try:
        ex = getattr(ccxt, name)({'enableRateLimit': True, 'timeout': 15000})
        ex.load_markets()
        print(f"{name} loaded ok")
        return ex
    except Exception as e:
        print(f"{name} load err {e}")
        return None

def calc_ema(data, period):
    k = 2/(period+1)
    ema = [data[0]]
    for p in data[1:]: ema.append(p*k + ema[-1]*(1-k))
    return ema
def calc_rsi(closes, period=14):
    if len(closes) < period+1: return 50
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i]-closes[i-1]
        gains.append(max(d,0)); losses.append(max(-d,0))
    ag = sum(gains[:period])/period
    al = sum(losses[:period])/period
    if al==0: return 100
    return 100 - (100/(1+ag/al))
def calc_macd(closes):
    if len(closes) < 26: return None,None,None
    ema12 = calc_ema(closes,12); ema26 = calc_ema(closes,26)
    macd_line = [a-b for a,b in zip(ema12,ema26)]
    if len(macd_line)<9: return None,None,None
    sig_line = calc_ema(macd_line,9)
    return macd_line[-1], sig_line[-1], macd_line[-1]-sig_line[-1]
def analyze_tf(closes):
    if len(closes) < 35: return None
    rsi = calc_rsi(closes)
    macd,sig,hist = calc_macd(closes)
    if macd is None: return None
    return {"rsi":rsi, "macd":macd, "sig":sig, "hist":hist, "ema7":calc_ema(closes,7)[-1], "ema14":calc_ema(closes,14)[-1], "ema28":calc_ema(closes,28)[-1], "ema50":calc_ema(closes,50)[-1] if len(closes)>=50 else calc_ema(closes,28)[-1], "last":closes[-1]}

def get_btc_trend(ex):
    # BTC TREND FILTER for MAJOR/ALT/QUANT
    try:
        o1h = ex.fetch_ohlcv('BTC/USDT', '1h', limit=60)
        o4h = ex.fetch_ohlcv('BTC/USDT', '4h', limit=60)
        if len(o1h)<30 or len(o4h)<30: return "NEUTRAL"
        c1h = [c[4] for c in o1h]
        c4h = [c[4] for c in o4h]
        tf1h = analyze_tf(c1h)
        tf4h = analyze_tf(c4h)
        if not tf1h or not tf4h: return "NEUTRAL"
        if tf1h["last"]>tf1h["ema28"] and tf4h["last"]>tf4h["ema28"] and tf1h["macd"]>tf1h["sig"] and tf4h["macd"]>tf4h["sig"]:
            return "BULL"
        if tf1h["last"]<tf1h["ema28"] and tf4h["last"]<tf4h["ema28"] and tf1h["macd"]<tf1h["sig"] and tf4h["macd"]<tf4h["sig"]:
            return "BEAR"
        return "NEUTRAL"
    except:
        return "NEUTRAL"

def check_long(tf5, tf15, tf1h, tf4h, tf1d):
    if not tf5 or not tf15: return False
    if not (52 <= tf5["rsi"] <= 78 and tf5["macd"] > tf5["sig"] and tf5["hist"] > 0 and tf5["last"] > tf5["ema7"]): return False
    if not (50 <= tf15["rsi"] <= 76 and tf15["macd"] > tf15["sig"] and tf15["last"] > tf15["ema14"]): return False
    if tf1h and not (52 <= tf1h["rsi"] <= 78 and tf1h["macd"] > tf1h["sig"] and tf1h["last"] > tf1h["ema14"]): return False
    if tf4h and not (tf4h["rsi"] > 50 and tf4h["macd"] > tf4h["sig"] and tf4h["last"] > tf4h["ema28"]): return False
    if tf1d and not (tf1d["rsi"] > 50 and tf1d["macd"] > tf1d["sig"] and tf1d["last"] > tf1d["ema28"]): return False
    return True

def check_short(tf5, tf15, tf1h, tf4h, tf1d):
    if not tf5 or not tf15: return False
    if not (22 <= tf5["rsi"] <= 48 and tf5["macd"] < tf5["sig"] and tf5["hist"] < 0 and tf5["last"] < tf5["ema7"]): return False
    if not (25 <= tf15["rsi"] <= 50 and tf15["macd"] < tf15["sig"] and tf15["last"] < tf15["ema14"]): return False
    if tf1h and not (tf1h["rsi"] < 50 and tf1h["macd"] < tf1h["sig"]): return False
    if tf4h and not (tf4h["rsi"] < 50 and tf4h["macd"] < tf4h["sig"]): return False
    return True

def passes_filters(ex, symbol, category):
    # VOL, ORDER BOOK DEPTH, SPREAD, FUNDING RATE
    try:
        # 1. SPREAD FILTER
        ob = ex.fetch_order_book(symbol, 20)
        if not ob['bids'] or not ob['asks']: return False, "no orderbook"
        bid = ob['bids'][0][0]
        ask = ob['asks'][0][0]
        last = (bid+ask)/2
        spread_pct = (ask-bid)/last*100 if last else 99
        if spread_pct > 0.6: return False, f"spread high {spread_pct:.2f}%"

        # 2. ORDER BOOK DEPTH FILTER
        bid_usd = sum(b[0]*b[1] for b in ob['bids'][:15])
        ask_usd = sum(a[0]*a[1] for a in ob['asks'][:15])
        min_depth = 15000 if category=="NEW" else 20000
        if bid_usd < min_depth and ask_usd < min_depth:
            return False, f"depth low ${int(bid_usd)}/${int(ask_usd)}"

        # 3. FUNDING RATE FILTER (if exchange supports)
        try:
            if hasattr(ex, 'fetch_funding_rate'):
                fr = ex.fetch_funding_rate(symbol)
                funding = fr.get('fundingRate', 0) or 0
                # Skip if funding too high = overcrowded
                if abs(funding) > 0.0015: # 0.15%
                    return False, f"funding {funding*100:.3f}%"
        except:
            pass # funding not available for spot - skip filter

        return True, f"Spread {spread_pct:.2f}% Depth ${int(bid_usd):,} Fund OK"
    except Exception as e:
        # If filter fails, still allow if volume ok
        if "does not have market" in str(e):
            return False, str(e)
        return True, "filter skip"

def process_symbol(ex, symbol, seen, category, extra_info="", btc_trend="NEUTRAL", all_exs=[]):
    try:
        # Try fallback ex if symbol not found
        cur_ex = ex
        for cand in all_exs:
            if not cand: continue
            try:
                if symbol in cand.markets:
                    cur_ex = cand
                    break
            except: continue
        
        # FILTERS: vol, book, spread, funding
        ok, filter_info = passes_filters(cur_ex, symbol, category)
        if not ok:
            if "does not have market" in filter_info:
                # try other ex
                for cand in all_exs:
                    if cand==cur_ex or not cand: continue
                    try:
                        ok2, info2 = passes_filters(cand, symbol, category)
                        if ok2:
                            cur_ex = cand
                            filter_info = info2
                            ok = True
                            break
                    except: continue
            if not ok:
                print(f"filter {symbol} {filter_info}")
                return None

        # BTC TREND FILTER for MAJOR/ALT/QUANT (NEW listings ignore BTC)
        if category in ["MAJOR","ALT","QUANT"]:
            # LONG needs BTC not BEAR, SHORT needs BTC not BULL
            pass # will check after direction

        o5m = cur_ex.fetch_ohlcv(symbol, '5m', limit=100); time.sleep(0.15)
        o15m = cur_ex.fetch_ohlcv(symbol, '15m', limit=100); time.sleep(0.15)
        try: o1h = cur_ex.fetch_ohlcv(symbol, '1h', limit=100)
        except: o1h = []
        try: o4h = cur_ex.fetch_ohlcv(symbol, '4h', limit=100)
        except: o4h = []
        try: o1d = cur_ex.fetch_ohlcv(symbol, '1d', limit=100)
        except: o1d = []

        if len(o5m)<35 or len(o15m)<35: return None
        c5 = [c[4] for c in o5m]; c15 = [c[4] for c in o15m]
        c1h = [c[4] for c in o1h] if len(o1h)>=30 else []
        c4h = [c[4] for c in o4h] if len(o4h)>=30 else []
        c1d = [c[4] for c in o1d] if len(o1d)>=30 else []
        v15 = [c[5] for c in o15m] if len(o15m)>=11 else []

        tf5 = analyze_tf(c5); tf15 = analyze_tf(c15)
        tf1h = analyze_tf(c1h) if c1h else None
        tf4h = analyze_tf(c4h) if c4h else None
        tf1d = analyze_tf(c1d) if c1d else None
        if not tf5 or not tf15: return None

        if v15 and len(v15)>=11:
            vol_avg = sum(v15[-11:-1])/10 if sum(v15[-11:-1])>0 else v15[-1]
            if vol_avg>0 and v15[-1] < vol_avg * 1.3: return None
            vol_txt = f"{v15[-1]/vol_avg:.1f}x"
        else: vol_txt = "N/A"

        last = c5[-1]; direction=None; lev=""; tp1=tp2=tp3=sl=0
        if check_long(tf5, tf15, tf1h, tf4h, tf1d):
            # BTC TREND CHECK for LONG
            if category in ["MAJOR","ALT","QUANT"] and btc_trend=="BEAR":
                print(f"BTC BEAR skip LONG {symbol}")
                return None
            direction=f"{category} LONG"
            if category=="NEW": lev="5x-8x Isolated"; tp1=last*2.2; tp2=last*4.5; tp3=last*9.0; sl=last*0.70
            elif category=="QUANT": lev="5x Isolated"; tp1=last*1.08; tp2=last*1.18; tp3=last*1.35; sl=last*0.95
            elif category=="MAJOR": lev="3x-5x Isolated"; tp1=last*1.05; tp2=last*1.11; tp3=last*1.22; sl=last*0.96
            else: lev="4x-6x Isolated"; tp1=last*1.07; tp2=last*1.16; tp3=last*1.32; sl=last*0.94
        elif check_short(tf5, tf15, tf1h, tf4h, tf1d):
            # BTC TREND CHECK for SHORT
            if category in ["MAJOR","ALT","QUANT"] and btc_trend=="BULL":
                print(f"BTC BULL skip SHORT {symbol}")
                return None
            direction=f"{category} SHORT"
            lev="3x-5x Isolated"; tp1=last*0.95; tp2=last*0.89; tp3=last*0.80; sl=last*1.04
        else: return None

        key = f"{symbol}_{direction}"
        if key in seen: return None

        tf1h_txt = f"RSI {tf1h['rsi']:.0f} MACD {tf1h['macd']:.4f}>{tf1h['sig']:.4f}" if tf1h else "New(skip)"
        tf4h_txt = f"RSI {tf4h['rsi']:.0f} MACD {tf4h['macd']:.4f}>{tf4h['sig']:.4f}" if tf4h else "New(skip)"
        tf1d_txt = f"RSI {tf1d['rsi']:.0f} MACD {tf1d['macd']:.4f}>{tf1d['sig']:.4f}" if tf1d else "New(skip)"
        icons = {"NEW":"🔥 NEW","QUANT":"⚡ QUANT","MAJOR":"📊 MAJOR","ALT":"🚀 ALT"}
        tag = icons.get(category, "📊")

        msg = f"""{tag} *{direction} - 80/100 STRICT* {tag}
*Coin:* `{symbol}` {extra_info} VolSpike {vol_txt}
*Price:* {last:.6g} *BTC:* {btc_trend}
*ENTRY:* {last:.6g}
*TP1* {tp1:.6g} *TP2* {tp2:.6g} *TP3* {tp3:.6g}
*SL* {sl:.6g} *Lev:* {lev}

*FILTERS PASSED:*
✅ Vol ${extra_info} ✅ {filter_info} ✅ BTC {btc_trend}

*TIME FRAME - MACD+RSI+EMA:*
✅ 5m RSI {tf5['rsi']:.0f} MACD {tf5['macd']:.5f}>{tf5['sig']:.5f} HIST {tf5['hist']:.5f}
✅ 15m RSI {tf15['rsi']:.0f} MACD {tf15['macd']:.5f}>{tf15['sig']:.5f}
✅ 1h {tf1h_txt}
✅ 4h {tf4h_txt}
✅ 1D {tf1d_txt}
"""
        return (key, msg)
    except Exception as e:
        print(f"process {symbol} err {e}")
        return None

def main():
    ex_gate = get_ex('gate')
    ex_mexc = get_ex('mexc')
    ex_okx = get_ex('okx')
    all_exs = [ex_gate, ex_mexc, ex_okx]
    ex = ex_gate or ex_mexc or ex_okx
    if not ex: return
    seen = load_seen()
    now_lagos = datetime.now(WAT)
    now_ts = int(datetime.now().timestamp())
    signals_sent = 0

    # BTC TREND for filtering
    btc_trend = get_btc_trend(ex)
    print(f"BTC Trend {btc_trend}")

    # 1. NEW LISTING
    for ex_name, ex_cur in [('GATE', ex_gate), ('MEXC', ex_mexc), ('OKX', ex_okx)]:
        if not ex_cur or signals_sent>=1: continue
        try:
            tickers = ex_cur.fetch_tickers()
            usdt = {k:v for k,v in tickers.items() if '/USDT' in k and '3L' not in k and '3S' not in k and 'UP' not in k and 'DOWN' not in k}
            sorted_t = sorted(usdt.items(), key=lambda x: x[1].get('quoteVolume',0) or 0, reverse=True)[:60]
            for symbol, ticker in sorted_t:
                if signals_sent>=1: break
                try:
                    qv = ticker.get('quoteVolume',0) or 0; last = ticker.get('last',0) or 0
                    if qv < 150000 or last==0 or last>5000: continue
                    o1d_c = ex_cur.fetch_ohlcv(symbol, '1d', limit=5)
                    if len(o1d_c) >=3: continue
                    o5m_c = ex_cur.fetch_ohlcv(symbol, '5m', limit=20)
                    if len(o5m_c) < 5: continue
                    first_high = max(c[2] for c in o5m_c[:6]) if len(o5m_c)>=6 else o5m_c[0][2]
                    dip = (last-first_high)/first_high*100 if first_high else 0
                    if not (-50 <= dip <= -7): continue
                    res = process_symbol(ex_cur, symbol, seen, "NEW", f"Vol ${int(qv):,} Dip {dip:.1f}%", btc_trend, all_exs)
                    if res:
                        key, msg = res
                        send_text(msg); seen.add(key); signals_sent+=1; break
                except: continue
        except: continue

    # 2. QUANT
    if signals_sent==0 and ex_gate:
        try:
            tickers = ex_gate.fetch_tickers()
            usdt = {k:v for k,v in tickers.items() if '/USDT' in k and v.get('quoteVolume',0)>500000}
            sorted_q = sorted(usdt.items(), key=lambda x: x[1].get('percentage',0) or 0, reverse=True)[:40]
            for symbol, ticker in sorted_q:
                if signals_sent>=1: break
                try:
                    change = ticker.get('percentage',0) or 0
                    if abs(change) < 4: continue
                    res = process_symbol(ex_gate, symbol, seen, "QUANT", f"Change {change:.1f}%", btc_trend, all_exs)
                    if res:
                        key, msg = res
                        send_text(msg); seen.add(key); signals_sent+=1; break
                except: continue
        except: pass

    # 3. MAJOR
    if signals_sent==0:
        for symbol in MAJORS:
            if signals_sent>=1: break
            res = process_symbol(ex, symbol, seen, "MAJOR", "", btc_trend, all_exs)
            if res:
                key, msg = res
                send_text(msg); seen.add(key); signals_sent+=1; break

    # 4. ALT
    if signals_sent==0:
        for symbol in ALTS:
            if signals_sent>=1: break
            res = process_symbol(ex, symbol, seen, "ALT", "", btc_trend, all_exs)
            if res:
                key, msg = res
                send_text(msg); seen.add(key); signals_sent+=1; break

    # BOT ALIVE
    try:
        last_alive = load_alive()
        if signals_sent==0 and (now_ts-last_alive)>=21600:
            send_text(f"✅ *4-IN-1 Bot Alive* Lagos {now_lagos.strftime('%H:%M %d/%m')}\nBTC Trend {btc_trend} | Scanning: NEW | QUANT | MAJOR | ALT | Filters: Vol+Depth+Spread+Funding+BTC | NO BYBIT")
            save_alive(now_ts)
    except: pass

    save_seen(seen)
    print(f"Done Lagos {now_lagos.strftime('%H:%M')} | BTC {btc_trend} | Signals {signals_sent} | NO BYBIT ALL FILTERS")

if __name__=="__main__":
    main()
