import os, requests
from datetime import datetime
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
text = f"✅ @Herocallss ACTIVE & CONNECTED\n\nTime: {datetime.now().strftime('%H:%M')} Lagos\nBot is online - 70/100 ready"
requests.post(url, data={"chat_id": CHAT_ID, "text": text})
print("sent")
