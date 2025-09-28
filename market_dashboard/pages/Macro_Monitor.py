# pages/Macro_Monitor.py
import pandas as pd
import numpy as np
from pandas_datareader import data as pdr
import streamlit as st
import plotly.graph_objects as go
import yfinance as yf

st.set_page_config(page_title="US Macro Dashboard", page_icon="🇺🇸", layout="wide")
st.title("US Macro Dashboard with Fred")

START = pd.Timestamp("2000-01-01")
END = min(pd.Timestamp("2025-12-31"), pd.Timestamp.today().normalize())

# --- FRED series codes ---
CPI_SERIES = "CPIAUCSL"       # CPI (SA, monthly)
GDP_REAL_LVL = "GDPC1"        # Real GDP, chained 2017$, quarterly level
YIELD_SERIES = {
    "1M":  "DGS1MO",
    "3M":  "DGS3MO",
    "2Y":  "DGS2",
    "5Y":  "DGS5",
    "10Y": "DGS10",
    "30Y": "DGS30",
}

# ===================== Helpers =====================
def maybe_resample(df, freq="M", threshold=5000):
    """Resample to monthly if dataset is very large (for faster charts)."""
    return df.resample(freq).last() if len(df) > threshold else df

@st.cache_data(show_spinner=False, ttl=6*60*60)
def load_cpi(start=START, end=END):
    df = pdr.DataReader(CPI_SERIES, "fred", start, end).asfreq("MS")
    df["YoY_%"] = df[CPI_SERIES].pct_change(12) * 100
    df["MoM_%"] = df[CPI_SERIES].pct_change(1) * 100
    return df

@st.cache_data(show_spinner=False, ttl=6*60*60)
def load_yields(start=START, end=END):
    df = pdr.DataReader(list(YIELD_SERIES.values()), "fred", start, end)
    df.rename(columns={v: k for k, v in YIELD_SERIES.items()}, inplace=True)
    return df.dropna(how="all")

@st.cache_data(show_spinner=False, ttl=6*60*60)
def load_gdp_yoy(start=START, end=END):
    gdp_level = pdr.DataReader(GDP_REAL_LVL, "fred", start, end)  # quarterly level
    gdp_level = gdp_level.asfreq("QS")
    gdp_yoy = gdp_level.pct_change(4) * 100
    gdp_yoy.rename(columns={GDP_REAL_LVL: "YoY_%"}, inplace=True)
    return gdp_yoy

@st.cache_data(show_spinner=False, ttl=6*60*60)
def load_prices_batch(tickers, start=START, end=END):
    """Batch download adjusted closes from Yahoo Finance."""
    df = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)["Close"]
    if isinstance(df, pd.Series):
        df = df.to_frame()
    return df.dropna(how="all")

def realized_vol(returns: pd.Series, window: int = 20) -> pd.Series:
    """Annualized realized volatility in % from daily returns."""
    return returns.rolling(window).std() * np.sqrt(252) * 100

# ===================== Load core data =====================
cpi = load_cpi()
yields = load_yields()
gdp = load_gdp_yoy()

# ================= INFLATION SECTION =================
st.header("US Inflation (CPI YoY)")
latest_cpi = cpi.dropna().iloc[-1]
latest_date = latest_cpi.name.strftime("%b %Y")
top1, top2, top3 = st.columns([1.5, 1, 2])
with top1:
    st.metric(f"CPI YoY ({latest_date})", f"{latest_cpi['YoY_%']:.2f}%")
with top2:
    st.metric("CPI MoM", f"{latest_cpi['MoM_%']:.2f}%")
with top3:
    st.caption("Source: FRED (CPIAUCSL, SA). YoY = 12-month % change; MoM = 1-month % change.")

fig_cpi = go.Figure()
fig_cpi.add_trace(go.Scatter(x=cpi.index, y=cpi["YoY_%"], mode="lines", name="CPI YoY (%)"))
fig_cpi.update_layout(
    xaxis_title="Date", yaxis_title="Inflation (YoY %)",
    height=360, hovermode="x unified",
    margin=dict(l=40, r=20, t=30, b=40),
)
st.plotly_chart(fig_cpi, use_container_width=True)

with st.expander("Show CPI data (last 24 months)"):
    st.dataframe(cpi[["CPIAUCSL", "MoM_%", "YoY_%"]].tail(24).round(2))

# ================= GDP GROWTH SECTION =================
st.header("US GDP Growth (YoY)")
latest_gdp_val = float(gdp["YoY_%"].dropna().iloc[-1])
q = gdp.dropna().index[-1]
latest_gdp_date = f"Q{((q.month-1)//3)+1} {q.year}"
st.metric(f"GDP YoY ({latest_gdp_date})", f"{latest_gdp_val:.2f}%")

fig_gdp = go.Figure()
fig_gdp.add_trace(go.Scatter(x=gdp.index, y=gdp["YoY_%"], mode="lines", name="GDP YoY (%)"))
fig_gdp.update_layout(
    xaxis_title="Quarter", yaxis_title="Growth (YoY %)",
    height=360, hovermode="x unified",
    margin=dict(l=40, r=20, t=30, b=40),
)
st.plotly_chart(fig_gdp, use_container_width=True)

with st.expander("Show GDP data (last 16 quarters)"):
    st.dataframe(gdp.tail(16).round(2))

# ================= YIELDS SECTION =================
st.header("US Treasury Yields (2000–2025)")
yields = maybe_resample(yields)  # compress long history if needed
latest_yields = yields.dropna().iloc[-1]
cols = st.columns(len(latest_yields))
for col, (tenor, value) in zip(cols, latest_yields.items()):
    col.metric(tenor, f"{float(value):.2f}%")

fig_yields = go.Figure()
for tenor in yields.columns:
    fig_yields.add_trace(go.Scatter(x=yields.index, y=yields[tenor], mode="lines", name=tenor))
fig_yields.update_layout(
    xaxis_title="Date", yaxis_title="Yield (%)",
    legend_title="Maturity", height=460,
    hovermode="x unified", margin=dict(l=40, r=20, t=30, b=40),
)
st.plotly_chart(fig_yields, use_container_width=True)

with st.expander("Show yield data (last 12 rows)"):
    st.dataframe(yields.tail(12).round(2))

# ================= VOLATILITY SECTION =================
st.header("US Market Volatility — Realized vs Implied")

left, right = st.columns([2, 1])
with right:
    ticker = st.selectbox("Underlying (realized vol):", ["SPY", "QQQ", "IWM"], index=0)
    window = st.selectbox("Realized vol window (days):", [20, 60, 120], index=1)
with left:
    st.caption("Realized vol = rolling stdev of daily returns × √252 (annualized, %). "
               "VIX = implied vol from S&P 500 options (30-day horizon).")

# --- Load RV + VIX in one go
prices_df = load_prices_batch([ticker, "^VIX"], START, END)
if ticker not in prices_df.columns or "^VIX" not in prices_df.columns:
    st.w
