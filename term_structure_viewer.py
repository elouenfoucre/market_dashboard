# Futures Term Structure Viewer — Dollar, Gold & Oil (Yahoo Finance)
# Shows Front / Back / Back+1 to visualize Contango vs Backwardation
# Robust version: auto-computes contract codes and gracefully skips missing ones

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

# Contract month patterns per asset (what months actually list liquid contracts)
ASSET_SPECS = {
    # Dollar Index is quarterly (Mar, Jun, Sep, Dec) — Yahoo often exposes only the front continuous (DX=F)
    "US Dollar Index": {
        "root": "DX", "suffixes": [".NYB", ".NYBOT", ".ICE", ".CBT"],
        "months": [3, 6, 9, 12],
        "front_ticker": "DX=F",
    },
    # Gold (COMEX) uses Feb, Apr, Jun, Aug, Oct, Dec
    "Gold": {
        "root": "GC", "suffix": ".CMX", "months": [2, 4, 6, 8, 10, 12],
        "front_ticker": "GC=F",
    },
    # WTI Crude Oil (NYMEX) lists all 12 months
    "WTI Crude": {
        "root": "CL", "suffix": ".NYM", "months": [1,2,3,4,5,6,7,8,9,10,11,12],
        "front_ticker": "CL=F",
    },
}

@st.cache_data(ttl=1800)
def last_close(ticker: str):
    """Return last closing price for a single Yahoo ticker as float, or None if unavailable."""
    try:
        hist = yf.Ticker(ticker).history(period="10d", interval="1d", auto_adjust=False)
        if hist is None or hist.empty:
            return None
        if "Close" in hist and not hist["Close"].dropna().empty:
            return float(hist["Close"].dropna().iloc[-1])
        if "Adj Close" in hist and not hist["Adj Close"].dropna().empty:
            return float(hist["Adj Close"].dropna().iloc[-1])
        return None
    except Exception:
        return None


def months_ahead(max_months: int = 18):
    """Yield (year, month) pairs for the next `max_months` months from today."""
    today = datetime.today()
    y, m = today.year, today.month
    for i in range(max_months):
        mm = ((m - 1 + i) % 12) + 1
        yy = y + (m - 1 + i) // 12
        yield yy, mm


def find_back_months(spec: dict, need: int = 2):
    """Scan forward and return up to `need` available back-month contracts (ticker, price)."""
    found = []
    for yy, mm in months_ahead(18):
        if mm not in spec["months"]:
            continue
        if spec.get("root") == "DX":
            # DX is tricky on Yahoo — try multiple suffixes
            for sfx in spec.get("suffixes", []):
                tkr = compose_ticker(spec["root"], yy, mm, sfx)
                px = last_close(tkr)
                if px is not None:
                    found.append((tkr, px))
                    break
        else:
            tkr = compose_ticker(spec["root"], yy, mm, spec["suffix"])
            px = last_close(tkr)
            if px is not None:
                found.append((tkr, px))
        if len(found) >= need:
            break
    return found


def compose_ticker(root: str, year: int, month: int, suffix: str) -> str:
    yy = year % 100
    code = MONTH_CODE[month]
    return f"{root}{code}{yy:02d}{suffix}"


def resolve_contracts(asset: str):
    spec = ASSET_SPECS[asset]
    rows = []

    # Front continuous (if available on Yahoo)
    front_price = last_close(spec.get("front_ticker")) if spec.get("front_ticker") else None
    if front_price is not None:
        rows.append({"Asset": asset, "Contract": "Front", "Ticker": spec["front_ticker"], "Price": front_price})

    # Back and Back+1 by scanning future months for available tickers
    backs = find_back_months(spec, need=2)
    for i, (tkr, px) in enumerate(backs, start=1):
        label = "Back" if i == 1 else "Back+1"
        rows.append({"Asset": asset, "Contract": label, "Ticker": tkr, "Price": px})

    return rows

# ----------------------------
# Build dataset
# ----------------------------
selected_assets = ["US Dollar Index", "Gold", "WTI Crude"]
all_rows = []
for a in selected_assets:
    all_rows.extend(resolve_contracts(a))

df = pd.DataFrame(all_rows)

if df.empty:
    st.error("No futures data could be retrieved from Yahoo Finance for the requested assets.")
    st.stop()

# Sort contracts in logical order
order = pd.CategoricalDtype(categories=["Front", "Back", "Back+1"], ordered=True)
df["Contract"] = df["Contract"].astype(order)
df.sort_values(["Asset", "Contract"], inplace=True)

# ----------------------------
# Display per asset
# ----------------------------
for asset in df["Asset"].unique():
    sub = df[df["Asset"] == asset]
    st.subheader(f"{asset}")
    if set(["Back", "Back+1"]) - set(sub["Contract"].unique()):
        st.info("Back months may be limited on Yahoo Finance. The app scans upcoming expiries and shows any available.")
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
