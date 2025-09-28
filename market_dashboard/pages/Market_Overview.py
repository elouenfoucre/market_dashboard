import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from pandas_datareader import data as pdr
import datetime

st.set_page_config(page_title="Market Overview Dashboard", layout="wide")
st.title("Market Overview Dashboard with Yahoo Finance")

# ---------------------------
# Macro data (FRED)
# ---------------------------
start_macro = datetime.datetime(datetime.datetime.now().year - 5, 1, 1)
end_macro = datetime.datetime.now()

series = {
    "US_GDP_YoY": "A191RL1Q225SBEA",  # Real GDP (YoY % change)
    "US_CPI": "CPILFESL",              # Core CPI index
    "US_10Y_Yield": "DGS10"            # 10-Year Treasury Yield
}

@st.cache_data(ttl=6*60*60, show_spinner=False)
def fetch_macro(series, start, end):
    df = pdr.DataReader(list(series.values()), "fred", start, end)
    df.columns = list(series.keys())
    df["US_CPI_YoY"] = df["US_CPI"].pct_change(12) * 100
    return df.dropna()

df_macro = fetch_macro(series, start_macro, end_macro)

# Detect macro regime
latest = df_macro.iloc[-1]
rate_6m_avg = df_macro["US_10Y_Yield"].rolling(window=180).mean().iloc[-1]
regime = {
    "Growth Regime": "Expansion" if latest["US_GDP_YoY"] > 1 else "Recession",
    "Inflation Regime": "High Inflation" if latest["US_CPI_YoY"] > 4 else "Low Inflation",
    "Rate Regime": "Rising Rates" if latest["US_10Y_Yield"] > rate_6m_avg else "Falling Rates"
}

# ---------------------------
# Sidebar
# ---------------------------
st.sidebar.markdown("### Market Regime Filter")
growth_filter = st.sidebar.selectbox("Growth Regime", ["All", "Expansion", "Recession"])
inflation_filter = st.sidebar.selectbox("Inflation Regime", ["All", "High Inflation", "Low Inflation"])
rate_filter = st.sidebar.selectbox("Rate Regime", ["All", "Rising Rates", "Falling Rates"])

# Check regime match
match = all([
    growth_filter == "All" or regime["Growth Regime"] == growth_filter,
    inflation_filter == "All" or regime["Inflation Regime"] == inflation_filter,
    rate_filter == "All" or regime["Rate Regime"] == rate_filter,
])

# Display current regime
st.markdown("### Current US Market Regime")
for label, value in regime.items():
    st.write(f"**{label}**: {value}")

# ---------------------------
# Assets
# ---------------------------
assets = {
    "Indexes": {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "Dow Jones": "^DJI",
        "Euro Stoxx 50": "^STOXX50E",
        "FTSE 100": "^FTSE",
        "Nikkei 225": "^N225"
    },
    "Stocks": {
        "Air Liquide": "AI.PA",
        "NVIDIA": "NVDA",
        "STMicroelectronics": "STM",
        "LVMH": "MC.PA",
        "Airbus": "AIR.PA",
        "TotalEnergies": "TTE.PA"
    },
    "Bonds (US only)": {
        "US 10Y": "^TNX"
    },
    "Commodities": {
        "Gold": "GC=F",
        "Crude Oil": "CL=F"
    },
    "FX": {
        "EUR/USD": "EURUSD=X",
        "EUR/CHF": "EURCHF=X",
        "EUR/GBP": "EURGBP=X",
        "EUR/JPY": "EURJPY=X",
        "EUR/TRY": "EURTRY=X"
    }
}

asset_class = st.sidebar.selectbox("Choose asset class", list(assets.keys()))
selected_assets = st.sidebar.multiselect(
    f"Select assets ({asset_class})", list(assets[asset_class].keys())
)

# ---------------------------
# Date selector
# ---------------------------
date_option = st.sidebar.selectbox(
    "Select time period",
    ["1Y", "3Y", "5Y", "10Y", "20Y", "Year-to-Date", "Last Month", "Custom"],
    index=0
)

today = pd.Timestamp.today().normalize()
if date_option == "1Y":
    start_date, end_date = today - pd.DateOffset(years=1), today
elif date_option == "3Y":
    start_date, end_date = today - pd.DateOffset(years=3), today
elif date_option == "5Y":
    start_date, end_date = today - pd.DateOffset(years=5), today
elif date_option == "10Y":
    start_date, end_date = today - pd.DateOffset(years=10), today
elif date_option == "20Y":
    start_date, end_date = today - pd.DateOffset(years=20), today
elif date_option == "Year-to-Date":
    start_date, end_date = pd.to_datetime(datetime.date(today.year, 1, 1)), today
elif date_option == "Last Month":
    start_date, end_date = today - pd.DateOffset(months=1), today
else:
    start_date = st.sidebar.date_input("Start date", pd.to_datetime("2022-01-01"))
    end_date = st.sidebar.date_input("End date", today)

if date_option in ["10Y", "20Y"]:
    st.warning("⚠️ Long horizons may take longer (data resampled to monthly).")

# ---------------------------
# Helpers
# ---------------------------
@st.cache_data(ttl=900, show_spinner=True)
def fetch_prices(tickers, start, end, resample_long=False):
    df = yf.download(tickers, start=start, end=end, progress=False)["Close"]
    if isinstance(df, pd.Series):
        df = df.to_frame()
    df = df.dropna(how="all")
    if resample_long and len(df) > 5000:  # long horizon
        df = df.resample("M").last()
    return df

normalize = st.sidebar.checkbox("Normalize to 100", value=True)

# ---------------------------
# Main display
# ---------------------------
if not match:
    st.warning("Selected regime filter does not match current macro regime.")
elif not selected_assets:
    st.info("Please select at least one asset.")
else:
    tickers = [assets[asset_class][a] for a in selected_assets]
    df_all = fetch_prices(
        tickers,
        start=start_date,
        end=end_date,
        resample_long=(date_option in ["10Y", "20Y"])
    )

    if df_all.empty:
        st.warning("No data available for selected assets.")
    else:
        # Chart
        if normalize:
            df_plot = df_all / df_all.iloc[0] * 100
            st.line_chart(df_plot)
            st.write("Assets normalized to 100 at start date.")
        else:
            st.line_chart(df_all)
            st.write("Raw closing prices.")

        # Volatility
        returns = df_all.pct_change().dropna()
        vol_series = (returns.std() * np.sqrt(252) * 100).round(2)

        vol_df = pd.DataFrame({
            "Asset": vol_series.index,
            "Volatility (%)": vol_series.values
        })
        asset_to_class = {name: class_name for class_name, d in assets.items() for name in d}
        vol_df["Asset Class"] = vol_df["Asset"].map(asset_to_class)

        st.subheader("Annualized Volatility by Asset")
        st.dataframe(vol_df.sort_values("Volatility (%)", ascending=False), use_container_width=True)

        class_vol_df = vol_df.groupby("Asset Class")["Volatility (%)"].mean().round(2).reset_index()
        st.subheader("Average Volatility by Asset Class")
        st.dataframe(class_vol_df.sort_values("Volatility (%)", ascending=False), use_container_width=True)

    # Warn if skipped
    missing = [a for a in selected_assets if assets[asset_class][a] not in df_all.columns]
    if missing:
        st.warning("Some assets could not be loaded: " + ", ".join(missing))
