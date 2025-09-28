# Futures Term Structure Viewer — Optimized with batch Yahoo requests
import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="Futures Term Structure", layout="wide")
st.title("Futures Term Structure with Yahoo Finance")

# ----------------------------
# Helpers
# ----------------------------
MONTH_CODE = {1:"F",2:"G",3:"H",4:"J",5:"K",6:"M",7:"N",8:"Q",9:"U",10:"V",11:"X",12:"Z"}
CODE_MONTH = {v:k for k,v in MONTH_CODE.items()}

ASSET_SPECS = {
    "US Dollar Index": {
        "root": "DX", "suffixes": [".NYB", ".NYBOT", ".ICE", ".CBT"],
        "months": [3, 6, 9, 12],
        "front_ticker": "DX=F",
    },
    "Gold": {
        "root": "GC", "suffix": ".CMX",
        "months": [2, 4, 6, 8, 10, 12],
        "front_ticker": "GC=F",
    },
    "WTI Crude": {
        "root": "CL", "suffix": ".NYM",
        "months": list(range(1,13)),
        "front_ticker": "CL=F",
    },
}

def months_ahead(max_months: int = 18):
    today = datetime.today()
    y, m = today.year, today.month
    for i in range(max_months):
        mm = ((m - 1 + i) % 12) + 1
        yy = y + (m - 1 + i) // 12
        yield yy, mm

def compose_ticker(root: str, year: int, month: int, suffix: str) -> str:
    yy = year % 100
    code = MONTH_CODE[month]
    return f"{root}{code}{yy:02d}{suffix}"

def candidate_tickers(spec: dict, max_months=18):
    tickers = []
    for yy, mm in months_ahead(max_months):
        if mm not in spec["months"]:
            continue
        if spec.get("root") == "DX":
            for sfx in spec.get("suffixes", []):
                tickers.append(compose_ticker(spec["root"], yy, mm, sfx))
        else:
            tickers.append(compose_ticker(spec["root"], yy, mm, spec["suffix"]))
    return tickers

@st.cache_data(ttl=1800)
def fetch_last_prices(tickers):
    """Batch fetch last close for all tickers."""
    df = yf.download(tickers, period="10d", interval="1d", progress=False)["Close"]
    if isinstance(df, pd.Series):
        df = df.to_frame()
    df = df.ffill().iloc[-1]
    return df.to_dict()

def resolve_contracts(asset: str, prices_dict: dict):
    spec = ASSET_SPECS[asset]
    rows = []

    # Front continuous
    if spec.get("front_ticker") and spec["front_ticker"] in prices_dict:
        rows.append({
            "Asset": asset,
            "Contract": "Front",
            "Ticker": spec["front_ticker"],
            "Price": prices_dict[spec["front_ticker"]],
        })

    # Back / Back+1
    backs = []
    for tkr in candidate_tickers(spec):
        if tkr in prices_dict and not pd.isna(prices_dict[tkr]):
            backs.append((tkr, prices_dict[tkr]))
        if len(backs) >= 2:
            break

    for i, (tkr, px) in enumerate(backs, start=1):
        label = "Back" if i == 1 else "Back+1"
        rows.append({"Asset": asset, "Contract": label, "Ticker": tkr, "Price": px})

    return rows

# ----------------------------
# Build dataset
# ----------------------------
selected_assets = ["US Dollar Index", "Gold", "WTI Crude"]

# Collect all candidate tickers (front + back months)
all_candidates = []
for a in selected_assets:
    spec = ASSET_SPECS[a]
    if spec.get("front_ticker"):
        all_candidates.append(spec["front_ticker"])
    all_candidates.extend(candidate_tickers(spec))

# Batch fetch once
prices_dict = fetch_last_prices(list(set(all_candidates)))

# Build final rows
all_rows = []
for a in selected_assets:
    all_rows.extend(resolve_contracts(a, prices_dict))

df = pd.DataFrame(all_rows)
if df.empty:
    st.error("No futures data could be retrieved.")
    st.stop()

# Sort
order = pd.CategoricalDtype(categories=["Front", "Back", "Back+1"], ordered=True)
df["Contract"] = df["Contract"].astype(order)
df.sort_values(["Asset", "Contract"], inplace=True)

# ----------------------------
# Display
# ----------------------------
for asset in df["Asset"].unique():
    sub = df[df["Asset"] == asset]
    st.subheader(f"{asset}")
    if set(["Back", "Back+1"]) - set(sub["Contract"].unique()):
        st.info("Back months may be limited on Yahoo Finance.")
    if sub.shape[0] == 1:
        fig = px.scatter(sub, x="Contract", y="Price", text="Price", title=f"{asset} — Available Contract(s)")
        fig.update_traces(textposition="top center")
    else:
        fig = px.line(sub, x="Contract", y="Price", markers=True, title=f"{asset} — Term Structure")
    fig.update_layout(xaxis_title="Contract", yaxis_title="Price")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(sub.reset_index(drop=True), use_container_width=True)

# ----------------------------
# Download CSV
# ----------------------------
csv = df.to_csv(index=False)
st.download_button("📄 Download All Data (CSV)", data=csv, file_name="futures_term_structure_yahoo.csv")
