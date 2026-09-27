import ccxt
import requests
import time

COINS = [
    "BTCUSDT", "ETHUSDT", ... # all your 105 coins
    "ASTUSDT", "MNTUSDT",
    "EURUSDT", "GBPUSDT", "AUDUSDT", "TRYUSDT", "BRLUSDT", "NGNUSDT", "EURGBP", "EURTRY", "GBPUSDC", "EURBUSD"
]

# NOW you can print
print(f"Scanning {len(COINS)} coins...")

def send_telegram(msg):
    ...

def check_signal(symbol):
    ...

# scan once - no while True for GitHub
found = 0
for coin in COINS:
    ...
print("Done")
