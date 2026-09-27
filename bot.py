print(f"Scanning {len(COINS)} coins...")
found = 0
for coin in COINS:
    signal = check_signal(coin)
    if signal:
        send_telegram(f"{signal} {coin} - 80% strict - 10x")
        found += 1
    time.sleep(0.3)

if found == 0:
    print("No perfect setup found - protecting account")
    
print("Done")
