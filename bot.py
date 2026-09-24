
    

import os, requests, time, random

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")

BASES = [
    "https://fapi.binance.com",
    "https://fapi1.binance.com",
    "https://fapi2.binance.com",
    "https://fapi3.binance.com",
    "https://api.binance.com"
]

def api_get(path):
    for base in BASES:
        try:
            r = requests.get(base+path, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code == 451:
                continue
            r.raise_for_status()
            return r.json()
        except:
            continue
    # fallback - use spot data if futures blocked
    try:
        r = requests.get(f"https://api.binance.com{path.replace('/fapi/','/api/')}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise e

def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT, "text": msg, "parse_mode":"Markdown"})

def main():
    try:
        data = api_get("/fapi/v1/ticker/24hr")
        # pick random top mover
        movers = sorted(data, key=lambda x: float(x.get('priceChangePercent',0)), reverse=True)[:20]
        if not movers:
            raise Exception("No data")
        coin = random.choice(movers)
        symbol = coin['symbol']
        change = float(coin['priceChangePercent'])
        price = float(coin['lastPrice'])
        
        side = "LONG 🟢" if change > 0 else "SHORT 🔴"
        
        msg = f"""🚀 *FUTURE CALLS - Auto Signal*

Coin: `{symbol}`
Side: *{side}*
Price: `${price}`
24h Change: `{change:.2f}%`

Entry: `{price}`
Target 1: `{price*1.02:.4f}` (+2%)
Target 2: `{price*1.05:.4f}` (+5%)
Stop Loss: `{price*0.97:.4f}` (-3%)

⏰ {time.strftime('%Y-%m-%d %H:%M UTC')}

#Binance #Futures
"""
        send(msg)
        print(f"Sent {symbol}")
    except Exception as e:
        print(f"Error: {e}")
        # send error to telegram for debugging
        try:
            send(f"Bot error: {e}")
        except:
            pass
        raise

if __name__ == "__main__":
    main()
