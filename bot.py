import requests, os
TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
print(f"CHAT={CHAT} TOKEN starts with {TOKEN[:10]}")
url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
r = requests.post(url, json={"chat_id": CHAT, "text": "TEST HELLO"})
print("TELEGRAM REPLY:")
print(r.text)
