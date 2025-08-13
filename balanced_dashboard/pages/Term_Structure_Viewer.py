import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import date
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="US Treasuries & Dollar Futures", layout="centered")
st.title("U.S. Treasuries & Dollar Index Futures")

#  U.S. Treasury Yield Curve 
us_tickers = {
    "1M": "^IRX",   # 13-week T-bill (proxy for ~1M)
    "2Y": "^FVX",
    "10Y": "^TNX",
    "30Y": "^TYX"
}

def fetch_us_yields():
    results = {}
    for label, ticker in us_tickers.items():
        try:
            data = yf.download(ticker, period="5d", progress=False)["Close"].dropna()
            if not data.empty:
                # Yahoo's ^TNX,^FVX,^TYX are in "yield * 100"
                val = float(data.iloc[-1]) / 100.0
                results[label] = round(val, 2)
        except Exception:
            pass
    return results

yields = fetch_us_yields()

if yields:
    maturities = list(yields.keys())
    values = list(yields.values())

    fig, ax = plt.subplots()
    ax.plot(maturities, values, marker="o", linestyle="-")
    ax.set_title("U.S. Treasury Yield Curve")
    ax.set_xlabel("Maturity")
    ax.set_ylabel("Yield (%)")
    ax.grid(True)
    st.pyplot(fig)

    if st.checkbox("Show UST data table"):
        st.dataframe(pd.DataFrame({"Yield (%)": values}, index=maturities).style.format("{:.2f}"))
else:
    st.warning("No yield data could be retrieved for Treasuries.")

st.markdown("---")

#  Dollar Index Futures (front contract) 
st.subheader("Dollar Index Futures — Front Contract")

# Month codes for quarterly DX futures on ICE
MONTH_CODE = {3: "H", 6: "M", 9: "U", 12: "Z"}
QUARTERS = [3, 6, 9, 12]

def generate_quarterlies(n=8):
    """Return a list of DX quarterly Yahoo tickers from the nearest quarter onward (e.g., DXZ25.NYB)."""
    today = date.today()
    # find the first quarter month on/after today.month
    start_month = next((m for m in QUARTERS if m >= today.month), 3)
    y, m = today.year, start_month
    out = []
    while len(out) < n:
        code = MONTH_CODE[m]
        yy = str(y % 100).zfill(2)
        out.append(f"DX{code}{yy}.NYB")
        # advance by 3 months
        if m == 12:
            m = 3
            y += 1
        else:
            m += 3
    return out

def fetch_front_dollar_fut(period="3mo"):
    """
    Try continuous front-month (DX1!.NYB). If unavailable, fall back to
    the nearest active quarterly DX contract that returns data.
    Returns (series, used_ticker) where series is a pandas Series of Close.
    """
    # 1) Try continuous front-month with exchange suffix
    for sym in ["DX1!.NYB", "DX1!"]:
        try:
            s = yf.download(sym, period=period, interval="1d", progress=False)["Close"].dropna()
            if not s.empty:
                return s, sym
        except Exception:
            pass

    # 2) Fall back to nearest quarterlies
    for tkr in generate_quarterlies(n=10):
        try:
            s = yf.download(tkr, period=period, interval="1d", progress=False)["Close"].dropna()
            if not s.empty:
                return s, tkr
        except Exception:
            continue

    # 3) Nothing worked
    return pd.Series(dtype=float), None

# Controls for the futures chart only (no spot metric)
lookback = st.selectbox("Lookback", ["1M", "3M", "6M", "1Y"], index=1)
period_map = {"1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y"}
dx_series, dx_symbol = fetch_front_dollar_fut(period=period_map[lookback])

if dx_symbol is None or dx_series.empty:
    st.warning("Dollar Index futures data unavailable (DX1!/nearest contract).")
else:
    fig2, ax2 = plt.subplots()
    ax2.plot(dx_series.index, dx_series.values, marker="o", linestyle="-")
    ax2.set_title(f"{dx_symbol} — {lookback} History")
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Price")
    ax2.grid(True)
    st.pyplot(fig2)