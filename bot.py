import os, requests
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
print(f"BOT_TOKEN exists: {TOKEN is not None}")
print(f"CHAT_ID: {CHAT_ID}")
url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
r = requests.post(url, json={"chat_id": CHAT_ID, "text": "✅ SUCCESS! Herocallss bot is NOW CONNECTED!"})
print(r.text)
