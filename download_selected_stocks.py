import yfinance as yf
import pandas as pd
import datetime
import json
import os

# Load tickers
with open("tickers.json", "r") as f:
    tickers = json.load(f)

today = datetime.date.today()
yesterday = today - datetime.timedelta(days=1)

all_rows = []

for symbol in tickers:
    data = yf.download(symbol, start=yesterday, end=today)

    if data.empty:
        print(f"⚠️ No data for {symbol}")
        continue

    open_price = data["Open"].iloc[0]
    close_price = data["Close"].iloc[0]

    all_rows.append({
        "Date": yesterday,
        "Ticker": symbol,
        "Open": float(open_price),
        "Close": float(close_price)
    })

# Convert to DataFrame
df = pd.DataFrame(all_rows)

# Save
df.to_excel("daily_open_close.xlsx", index=False)
print(df)
