import os, requests, time, random

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")

def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT, "text": msg, "parse_mode":"Markdown"})
    print(r.text)

def main():
    # Use SPOT API - never blocked on GitHub
    url = "https://api.binance.com/api/v3/ticker/24hr"
    data = requests.get(url, timeout=15).json()
    
    # Filter USDT pairs
    usdt = [c for c in data if c['symbol'].endswith('USDT')]
    top = sorted(usdt, key=lambda x: float(x['priceChangePercent']), reverse=True)[:30]
    coin = random.choice(top)
    
    symbol = coin['symbol']
    change = float(coin['priceChangePercent'])
    price = float(coin['lastPrice'])
    side = "LONG 🟢" if change > 0 else "SHORT 🔴"
    
    msg = f"""🚀 *FUTURE CALLS - Auto Signal*

Coin: `{symbol}`
Signal: *{side}*
Price: `${price}`
24h: `{change:.2f}%`

Entry: `{price}`
TP1: `{price*1.02:.4f}` (+2%)
TP2: `{price*1.05:.4f}` (+5%)
SL: `{price*0.97:.4f}` (-3%)

⏰ {time.strftime('%Y-%m-%d %H:%M UTC')}
#Crypto #Futures
"""
    send(msg)
    print(f"Sent {symbol}")

if __name__ == "__main__":
    main()
