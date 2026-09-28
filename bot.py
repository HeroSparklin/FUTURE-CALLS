import os, requests
TOKEN=os.getenv("BOT_TOKEN")
CHAT_ID=os.getenv("CHAT_ID")
requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": "✅ TEST: Bot is connected to @Herocallss and active!\nIf you see this, it works."})
print("Test sent")
