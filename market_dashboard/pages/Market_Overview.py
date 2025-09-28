import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from pandas_datareader import data as pdr
import datetime

st.title("Market Overview Dashboard with Yahoo Finance ")

# Set macro data time range: last 5 years
start_macro = datetime.datetime(datetime.datetime.now().year - 5, 1, 1)
end_macro = datetime.datetime.now()

# Define macroeconomic series from FRED
series = {
    "US_GDP_YoY": "A191RL1Q225SBEA",  # Real GDP (YoY % change)
    "US_CPI": "CPILFESL",              # Core CPI index
    "US_10Y_Yield": "DGS10"            # 10-Year Treasury Yield
}

# Fetch macroeconomic data from FRED
df_macro = pdr.DataReader(list(series.values()), "fred", start_macro, end_macro)
df_macro.columns = list(series.keys())

# Calculate YoY change in CPI (Core CPI inflation rate)
df_macro["US_CPI_YoY"] = df_macro["US_CPI"].pct_change(12) * 100
df_macro = df_macro.dropna()

# Extract latest macro values
latest = df_macro.iloc[-1]
rate_6m_avg = df_macro["US_10Y_Yield"].rolling(window=180).mean().iloc[-1]

# Detect current macro regime
regime = {
    "Growth Regime": "Expansion" if latest["US_GDP_YoY"] > 1 else "Recession",
    "Inflation Regime": "High Inflation" if latest["US_CPI_YoY"] > 4 else "Low Inflation",
    "Rate Regime": "Rising Rates" if latest["US_10Y_Yield"] > rate_6m_avg else "Falling Rates"
}

# Sidebar filters for regime selection
st.sidebar.markdown("### Market Regime Filter")
growth_filter = st.sidebar.selectbox("Growth Regime", ["All", "Expansion", "Recession"])
inflation_filter = st.sidebar.selectbox("Inflation Regime", ["All", "High Inflation", "Low Inflation"])
rate_filter = st.sidebar.selectbox("Rate Regime", ["All", "Rising Rates", "Falling Rates"])

# Check if current macro regime matches filters
match = True
if growth_filter != "All" and regime["Growth Regime"] != growth_filter:
    match = False
if inflation_filter != "All" and regime["Inflation Regime"] != inflation_filter:
    match = False
if rate_filter != "All" and regime["Rate Regime"] != rate_filter:
    match = False

# Display current macro regime
st.markdown("### Current US Market Regime")
for label, value in regime.items():
    st.write(f"**{label}**: {value}")

# Asset universe (by class) with Yahoo Finance tickers
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

# Sidebar asset selection
asset_class = st.sidebar.selectbox("Choose asset class", list(assets.keys()))
selected_assets = st.sidebar.multiselect(
    f"Select assets ({asset_class})", list(assets[asset_class].keys())
)

# Time period selection
date_option = st.sidebar.selectbox(
    "Select time period",
    ["1Y", "3Y", "5Y", "10Y", "20Y", "Year-to-Date", "Last Month", "Custom"],
    index=0  # Default = "1Y"
)

today = pd.Timestamp.today().normalize()

if date_option == "1Y":
    start_date = today - pd.DateOffset(years=1)
    end_date = today
elif date_option == "3Y":
    start_date = today - pd.DateOffset(years=3)
    end_date = today
elif date_option == "5Y":
    start_date = today - pd.DateOffset(years=5)
    end_date = today
elif date_option == "10Y":
    start_date = today - pd.DateOffset(years=10)
    end_date = today
elif date_option == "20Y":
    start_date = today - pd.DateOffset(years=20)
    end_date = today
elif date_option == "Year-to-Date":
    start_date = pd.to_datetime(datetime.date(today.year, 1, 1))
    end_date = today
elif date_option == "Last Month":
    start_date = today - pd.DateOffset(months=1)
    end_date = today
else:  # Custom
    start_date = st.sidebar.date_input("Start date", pd.to_datetime("2022-01-01"))
    end_date = st.sidebar.date_input("End date", today)

today = pd.Timestamp.today().normalize()

if date_option == "Year-to-Date":
    start_date = pd.to_datetime(datetime.date(today.year, 1, 1))
    end_date = today
elif date_option == "Year-over-Year":
    start_date = today - pd.DateOffset(years=1)
    end_date = today
elif date_option == "Last Month":
    start_date = today - pd.DateOffset(months=1)
    end_date = today
else:
    start_date = st.sidebar.date_input("Start date", pd.to_datetime("2022-01-01"))
    end_date = st.sidebar.date_input("End date", today)

# Normalize option for chart
normalize = st.sidebar.checkbox("Normalize to 100", value=True)

# Conditional display based on regime match
if not match:
    st.warning("Selected regime filter does not match current macro regime.")
else:
    # If assets are selected, fetch their data
    if selected_assets:
        df_all = pd.DataFrame()
        skipped = []

        for name in selected_assets:
            ticker = assets[asset_class][name]
            try:
                data = yf.download(ticker, start=start_date, end=end_date)["Close"].dropna()
                if not data.empty:
                    df_all[name] = data
                else:
                    skipped.append(name)
            except:
                skipped.append(name)

        # Remove assets with no data, forward fill any missing prices
        df_all = df_all.dropna(axis=1, how="all").ffill()

        if df_all.empty:
            st.warning("No data available for selected assets.")
        else:
            # Chart: normalized or raw prices
            if normalize:
                df_plot = df_all / df_all.iloc[0] * 100
                st.line_chart(df_plot)
                st.write("Assets normalized to 100 at start date.")
            else:
                st.line_chart(df_all)
                st.write("Raw closing prices.")

            # Volatility calculation
            returns = df_all.pct_change().dropna()
            vol_series = (returns.std() * np.sqrt(252) * 100).round(2)  # Annualized %

            # Build volatility DataFrame
            vol_df = pd.DataFrame({
                "Asset": vol_series.index,
                "Volatility (%)": vol_series.values
            })

            # Map assets to their class for grouping
            asset_to_class = {name: class_name for class_name, d in assets.items() for name in d}
            vol_df["Asset Class"] = vol_df["Asset"].map(asset_to_class)

            # Display per-asset volatility
            st.subheader("Annualized Volatility by Asset")
            st.dataframe(vol_df.sort_values("Volatility (%)", ascending=False), use_container_width=True)

            # Display average volatility by asset class
            class_vol_df = vol_df.groupby("Asset Class")["Volatility (%)"].mean().round(2).reset_index()
            st.subheader("Average Volatility by Asset Class")
            st.dataframe(class_vol_df.sort_values("Volatility (%)", ascending=False), use_container_width=True)

        # Warn if any assets failed to load
        if skipped:
            st.warning("Some assets could not be loaded: " + ", ".join(skipped))
    else:
        st.info("Please select at least one asset.")
