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

# ===================== Helpers / Loaders =====================
@st.cache_data(show_spinner=False, ttl=6*60*60)
def load_cpi(start=START, end=END):
    df = pdr.DataReader(CPI_SERIES, "fred", start, end).asfreq("MS")
    df["YoY_%"] = df[CPI_SERIES].pct_change(12) * 100
    df["MoM_%"] = df[CPI_SERIES].pct_change(1) * 100
    return df

@st.cache_data(show_spinner=False, ttl=6*60*60)
def load_yields(start=START, end=END):
    frames = []
    for label, code in YIELD_SERIES.items():
        s = pdr.DataReader(code, "fred", start, end)
        s.rename(columns={code: label}, inplace=True)
        frames.append(s)
    df = pd.concat(frames, axis=1).loc[start:end].dropna(how="all")
    return df

@st.cache_data(show_spinner=False, ttl=6*60*60)
def load_gdp_yoy(start=START, end=END):
    gdp_level = pdr.DataReader(GDP_REAL_LVL, "fred", start, end)  # quarterly level
    gdp_level = gdp_level.asfreq("QS")
    gdp_yoy = gdp_level.pct_change(4) * 100
    gdp_yoy.rename(columns={GDP_REAL_LVL: "YoY_%"}, inplace=True)
    return gdp_yoy

@st.cache_data(show_spinner=False, ttl=6*60*60)
def load_prices(ticker: str, start=START, end=END) -> pd.Series:
    """Adjusted close from Yahoo Finance."""
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    return df["Close"].dropna()

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
    window = st.selectbox("Realized vol window (days):", [20, 60, 120], index=1)  # default 60d
with left:
    st.caption("Realized vol = rolling stdev of daily returns × √252 (annualized, %). "
               "VIX = implied vol from S&P 500 options (30-day horizon).")

  # --- Compute RV series
prices = load_prices(ticker, START, END)   # should be a Series, but we defend anyway
if isinstance(prices, pd.DataFrame):       # if somehow multi-col, take the first numeric col
    prices = prices.select_dtypes(include=[np.number])
if prices.shape[1] >= 1:
    prices = prices.iloc[:, 0]
if prices is None or len(prices) == 0:
    st.warning(f"No price data for {ticker}.")
else:
    rets = prices.pct_change()
    rv = realized_vol(rets, window).dropna()   # could be Series or DataFrame

    # --- Load VIX series
vix_series = yf.download("^VIX", start=START, end=END, auto_adjust=True, progress=False)
if isinstance(vix_series, pd.DataFrame) and "Close" in vix_series.columns:
    vix_series = vix_series["Close"].dropna()

if rv is None or len(rv) == 0 or vix_series is None or len(vix_series) == 0:
    st.warning("Not enough data to compute realized vol or load VIX.")
else:
    # ✅ Force BOTH into 1-column DataFrames with explicit names
    rv_col  = f"RV_{ticker}_{window}d"
    vix_col = "VIX"

if isinstance(rv, pd.DataFrame):
    # if multi-col (shouldn't be), take the first numeric col
    rv = rv.select_dtypes(include=[np.number])
    rv_df = rv.iloc[:, [0]].copy()
    rv_df.columns = [rv_col]
else:
    # Series -> DataFrame
    rv_df = rv.to_frame(name=rv_col)

if isinstance(vix_series, pd.DataFrame):
    vix_df = vix_series.iloc[:, [0]].copy()
    vix_df.columns = [vix_col]
else:
    vix_df = vix_series.to_frame(name=vix_col)

    # Align on common dates
df_vol = rv_df.join(vix_df, how="inner").dropna()

if df_vol.empty:
    st.warning("No overlapping dates between RV and VIX after alignment.")
else:
    # Latest metrics
    latest_rv  = float(df_vol[rv_col].iloc[-1])
    latest_vix = float(df_vol[vix_col].iloc[-1])
    m1, m2 = st.columns(2)
    m1.metric(f"{ticker} Realized Vol ({window}d)", f"{latest_rv:.2f}%")
    m2.metric("VIX (latest close)", f"{latest_vix:.2f}")

    # Plot
fig_vol = go.Figure()
fig_vol.add_trace(go.Scatter(x=df_vol.index, y=df_vol[rv_col],
                mode="lines", name=rv_col))
fig_vol.add_trace(go.Scatter(x=df_vol.index, y=df_vol[vix_col],
                mode="lines", name="VIX (Implied, %)"))
fig_vol.update_layout(
        title="Realized vs Implied Volatility",
        xaxis_title="Date",
        yaxis_title="Volatility (%)",
        hovermode="x unified",
        height=460,
        margin=dict(l=40, r=20, t=30, b=40),
    )
st.plotly_chart(fig_vol, use_container_width=True)

with st.expander("Show volatility data (last 12 rows)"):
                st.dataframe(df_vol.tail(12).round(2))
