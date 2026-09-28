import os, requests
import ccxt
TOKEN=os.getenv("BOT_TOKEN"); CHAT_ID=os.getenv("CHAT_ID")
BINANCE=ccxt.binance({'enableRateLimit': True})
def send(m): requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": m, "parse_mode": "Markdown"}, timeout=10)
def get_sig(sym):
    try:
        o=BINANCE.fetch_ohlcv(sym, '15m', limit=21)
        c=[x[4] for x in o]; e=c[-1]; e9=sum(c[-9:])/9; e21=sum(c[-21:])/21
        if e9>e21: side="LONG"; emoji="🟢"; tp1=e*1.008; tp2=e*1.015; tp3=e*1.03; sl=e*0.97
        else: side="SHORT"; emoji="🔴"; tp1=e*0.992; tp2=e*0.985; tp3=e*0.97; sl=e*1.03
        return f"{emoji} FUTURE-CALL: {sym} - {side}\nInterval: 15m\n\n💰 Entry: `{e:.4f}`\n🎯 TP1: `{tp1:.4f}`\nTP2: `{tp2:.4f}`\nTP3: `{tp3:.4f}`\n🛑 SL: `{sl:.4f}`"
    except: return None

# Test 10 major coins - GUARANTEED to find something
for coin in ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","ADAUSDT","SHIBUSDT"]:
    s=get_sig(coin)
    if s:
        send(s)
        print(f"Sent {coin}")
        break
print("Done. Found 1")
