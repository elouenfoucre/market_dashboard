import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="Inflation Monitor", layout="centered")
st.title("Macro Monitor")

# Your TradingEconomics API key
API_KEY = "e32848e1c8ec4d7:5oafpdg9rbhqg29"

# List of countries to fetch
countries = ["United States", "France", "Germany", "Japan", "United Kingdom"]

# Function to fetch latest inflation
@st.cache_data(ttl=3600)
def fetch_latest_inflation(country):
    url = f"https://api.tradingeconomics.com/historical/country/{country}?indicator=Inflation Rate YoY&c={API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None
        data = pd.DataFrame(response.json())
        if data.empty or "Value" not in data.columns or "Date" not in data.columns:
            return None
        data["Date"] = pd.to_datetime(data["Date"])
        data = data.dropna(subset=["Value", "Date"]).sort_values("Date")
        if not data.empty:
            return round(data.iloc[-1]["Value"], 2)
        return None
    except Exception as e:
        st.warning(f"{country}: error fetching data.")
        return None

# Build list of results
results = []
for country in countries:
    value = fetch_latest_inflation(country)
    if value is not None:
        results.append({"Country": country, "InflationRate": value})

# Create DataFrame
if results:
    df = pd.DataFrame(results).sort_values("InflationRate")

    # Plot
    fig, ax = plt.subplots()
    ax.barh(df["Country"], df["InflationRate"])
    ax.set_xlabel("Inflation Rate YoY (%)")
    ax.set_title("Latest Year-over-Year Inflation")
    ax.grid(True, axis="x")
    st.pyplot(fig)
else:
    st.warning("⚠️ No valid inflation data available for the selected countries.")
