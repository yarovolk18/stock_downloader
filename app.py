import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import requests
import io

st.set_page_config(page_title="Stock Dashboard", layout="wide")

st.title("📈 Stock Summary Dashboard")
st.markdown("Select one or more **S&P 500 stocks** to view their performance and summary.")

# --- Load S&P 500 tickers
@st.cache_data
def load_sp500_tickers():
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        tables = pd.read_html(response.text)
        if tables:
            df = tables[0]
            return df[['Symbol', 'Security']]
    except Exception as e:
        print("Wikipedia fetch failed:", e)

    print("Falling back to GitHub data source...")
    url_github = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
    df = pd.read_csv(url_github)
    if 'Name' in df.columns:
        df = df[['Symbol', 'Name']].rename(columns={'Name': 'Security'})
    elif 'Security' in df.columns:
        df = df[['Symbol', 'Security']]
    else:
        raise ValueError("GitHub CSV does not contain expected columns.")
    return df

sp500_df = load_sp500_tickers()

# --- Sidebar: Stock selection and date range
st.sidebar.header("Stock Selection")
default_tickers = ["AAPL", "MSFT", "NVDA"]
selected_symbols = st.sidebar.multiselect(
    "Choose S&P 500 Stocks:",
    options=sp500_df['Symbol'].tolist(),
    default=default_tickers,
    help="Start typing a company symbol or name to filter the list."
)

start_date = st.sidebar.date_input("Start Date", datetime.date(2024, 1, 1))
end_date = st.sidebar.date_input("End Date", datetime.date.today())

# --- Sidebar: Export Selected Stocks button
if selected_symbols:

    # Download full historical data for selected stocks
    all_selected_data = []
    for ticker in selected_symbols:
        df_ticker = yf.download(ticker, start=start_date, end=end_date, auto_adjust=True)
        df_ticker = df_ticker.reset_index()
        df_ticker['Ticker'] = ticker  # add ticker column
        all_selected_data.append(df_ticker)

    combined_selected_df = pd.concat(all_selected_data, ignore_index=True)

    # Convert to CSV for full export
    selected_buffer = io.BytesIO()
    combined_selected_df.to_csv(selected_buffer, index=False)
    selected_buffer.seek(0)

    # Download button for full historical data
    st.sidebar.download_button(
        label="📥 Export Full Selected Stocks Data",
        data=selected_buffer,
        file_name="selected_stocks_data.csv",
        mime="text/csv"
    )

    # ------------------------------
    # NEW: Export only Open/Close per ticker per day
    # ------------------------------
    daily_rows = []

    for ticker in selected_symbols:
        df_daily = yf.download(ticker, start=start_date, end=end_date)

        if df_daily.empty:
            continue

        df_daily = df_daily.reset_index()
        df_daily['Ticker'] = ticker
        df_daily = df_daily[['Date', 'Ticker', 'Open', 'Close']]

        daily_rows.append(df_daily)

    if daily_rows:
        df_open_close = pd.concat(daily_rows, ignore_index=True)

        open_close_buffer = io.BytesIO()
        df_open_close.to_csv(open_close_buffer, index=False)
        open_close_buffer.seek(0)

        st.sidebar.download_button(
            label="📥 Export Open/Close Only",
            data=open_close_buffer,
            file_name="open_close_selected_tickers.csv",
            mime="text/csv"
        )




if not selected_symbols:
    st.warning("Please select at least one stock to view data.")
    st.stop()

# --- Download historical data helper
def download_csv(df, ticker):
    buffer = io.BytesIO()
    df.to_csv(buffer, index=True)
    buffer.seek(0)
    return buffer

# --- Download market data
@st.cache_data
def load_data(tickers, start, end):
    return yf.download(tickers, start=start, end=end, group_by="ticker", auto_adjust=True, threads=True)

data = load_data(selected_symbols, start_date, end_date)

# --- Display overview metrics
st.subheader("📊 Stock Overview")
cols = st.columns(len(selected_symbols))
for i, ticker in enumerate(selected_symbols):
    info = yf.Ticker(ticker).info
    current_price = info.get("currentPrice", None)
    previous_close = info.get("previousClose", None)
    change = None
    if current_price and previous_close:
        change = ((current_price - previous_close) / previous_close) * 100

    with cols[i]:
        st.metric(
            label=f"{ticker}",
            value=f"${current_price:,.2f}" if current_price else "N/A",
            delta=f"{change:.2f}%" if change else "N/A"
        )
        if "marketCap" in info:
            st.caption(f"Market Cap: ${info['marketCap'] / 1e9:.2f}B")

# --- Price History Charts & Download per stock
st.subheader("📉 Price History")
for ticker in selected_symbols:
    ticker_data = data[ticker]['Close'] if len(selected_symbols) > 1 else data['Close']
    st.write(f"**{ticker} Price History**")
    st.line_chart(ticker_data.rename(ticker))
    # Download button for individual stock
    csv_buffer = download_csv(ticker_data.to_frame(), ticker)
    st.download_button(
        label=f"Download {ticker} Historical Data",
        data=csv_buffer,
        file_name=f"{ticker}_historical.csv",
        mime="text/csv"
    )

# --- Detailed chart section
st.subheader("📈 Detailed Charts")
selected_ticker = st.selectbox("Select a stock for detailed analysis:", selected_symbols)
df = data[selected_ticker] if len(selected_symbols) > 1 else data
df['MA20'] = df['Close'].rolling(20).mean()
df['MA50'] = df['Close'].rolling(50).mean()

st.write(f"### {selected_ticker} Price and Moving Averages")
st.line_chart(df[['Close', 'MA20', 'MA50']])

st.write(f"### {selected_ticker} Volume")
st.bar_chart(df['Volume'])

# --- Portfolio summary table
st.subheader("💼 Portfolio Summary")
portfolio = []
for ticker in selected_symbols:
    info = yf.Ticker(ticker).info
    portfolio.append({
        "Ticker": ticker,
        "Price": info.get("currentPrice", 0),
        "Previous Close": info.get("previousClose", 0),
        "Market Cap (B)": round(info.get("marketCap", 0) / 1e9, 2)
    })

df_portfolio = pd.DataFrame(portfolio)
df_portfolio["Change %"] = ((df_portfolio["Price"] - df_portfolio["Previous Close"]) / df_portfolio["Previous Close"]) * 100
df_portfolio.set_index("Ticker", inplace=True)

st.dataframe(df_portfolio.style.format({
    "Price": "${:,.2f}",
    "Previous Close": "${:,.2f}",
    "Market Cap (B)": "{:,.2f}"
}))
st.markdown(f"**Average Daily Change:** {df_portfolio['Change %'].mean():.2f}%")
