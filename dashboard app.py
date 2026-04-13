import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- 1. THEME SETUP ---
st.set_page_config(page_title="ALPHA TERMINAL v4.1", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&display=swap');
    .main { background-color: #0d1117; color: #c9d1d9; }
    .stMetric { border: 1px solid #30363d !important; background-color: #0d1117 !important; border-radius: 0px !important; }
    .data-font { font-family: 'Roboto Mono', monospace !important; }
    h1, h2, h3, p, span { font-family: 'Roboto Mono', monospace !important; font-weight: 700 !important; }
    .metric-row { border-bottom: 1px solid #30363d; padding: 15px 0; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=1800)
def fetch_alpha_data():
    tks = ['SPY', '^VIX', 'HYG', 'IEF', 'XLY', 'XLP', 'XLE', 'XLF', 'XLV', 'XLI', 'XLB', 'XLK', 'XLU', 'XLC', 'XLRE']
    try:
        # Download all in one batch for speed and stability
        df = yf.download(tks, period="400d", interval="1d", progress=False, auto_adjust=True)
        if df.empty: return None
        return df['Close'] if 'Close' in df.columns else df
    except:
        return None

def get_yc_analysis():
    try:
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y"
        df = pd.read_csv(url)
        df.columns = ['date', 'value']
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna()
        curr = float(df['value'].iloc[-1])
        # Look back 180 days for the re-steepening trap
        was_inv = (df['value'].tail(180) < 0).any()
        # Strength: 0% = Trap, 50% = Inverted, 100% = Healthy
        s = 0 if (curr > 0 and was_inv) else (50 if curr < 0 else 100)
        return s, curr, was_inv
    except:
        return 50, 0.0, False

# --- 3. LOGIC ENGINE ---
def run_model():
    prices = fetch_alpha_data()
    if prices is None: return None
    
    # [1] Trend: SPY vs 200MA
    spy = prices['SPY'].dropna()
    spy_px = float(spy.iloc[-1])
    spy_ma = float(spy.rolling(200).mean().iloc[-1])
    tr_p = 100 if spy_px > spy_ma else 0
    
    # [2] Credit: HYG/IEF vs 50MA
    hyg = prices['HYG'].dropna()
    ief = prices['IEF'].dropna()
    ratio = hyg / ief
    ma50 = ratio.rolling(50).mean().iloc[-1]
    cr_p = 100 if float(ratio.iloc[-1]) > float(ma50) else 0
    
    # [3] Breadth: 11 Sectors vs 200MA
    secs = ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
    above = 0
    for s in secs:
        p = prices[s].dropna()
        if not p.empty and p.iloc[-1] > p.rolling(200).mean().iloc[-1]:
            above += 1
    # 9-11 sectors = 100% Strength (Trend confirmed)
    br_p = 100 if above >= 9 else (60 if above >= 5 else 20)
    
    # [4] VIX: 1.5 SD Bands
    vix = prices['^VIX'].dropna()
    vx_p, v_px, v_u = 50, 0.0, 0.0
    if not vix.empty and len(vix) > 21:
        v_px = float(vix.iloc[-1])
        v_u = float(vix.rolling(20).mean().iloc[-1] + (1.5 * vix.rolling(20).std().iloc[-1]))
        v_l = float(vix.rolling(20).mean().iloc[-1] - (1.5 * vix.rolling(20).std().iloc[-1]))
        if v_px > v_u: vx_p = 100 # Buy panic
        elif v_px < v_l: vx_p = 0 # Sell complacency
        else: vx_p = 65

    # [5] DeMark: 9-Count
    dm = (spy > spy.shift(4)).astype(int)
    lv = int(dm.iloc[-1])
    cnt = 0
    for val in reversed(dm.tolist()):
        if val == lv: cnt += 1
        else: break
    dm_p = 100 if (cnt >= 8 and lv == 0) else (0 if (cnt >= 8 and lv == 1) else 50)
    
    # [6] Yield Curve
    yc_p, yc_v, yc_w = get_yc_analysis()
    
    avg = (tr_p + cr_p + br_p + vx_p + dm_p + yc_p) / 6
    alloc = 100 if avg >= 80 else (75 if avg >= 60 else (50 if avg >= 40 else 20))
    
    return {
        "alloc": alloc, "avg": avg, "spy": spy_px, "yc_v": yc_v, "yc_w": yc_w,
        "tr_p": tr_p, "cr_p": cr_p, "br_p": br_p, "vx_p": vx_p, "dm_p": dm_p, "yc_p": yc_p,
        "br_c": above, "dm_c": cnt, "dm_t": "Upside" if lv == 1 else "Downside",
        "vix": v_px, "vix_u": v_u
    }

# --- 4. DISPLAY ---
def main():
    st.write("### ALPHA TERMINAL v4.1 // RISK LEDGER")
    d = run_model()
    
    if d is None:
        st.error("SYNC ERROR: Yahoo Finance throttled. Please refresh.")
        return

    # SUMMARY SECTION
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.metric("CAPITAL ALLOCATION", f"{d['alloc']}%")
        st.write(f"Strength Index: **{d['avg']:.1f}%**")
    with c2:
        fig = go.Figure(go.Indicator(mode="gauge+number", value=d['avg'], gauge={'axis':{'range':[0,100]}, 'bar':{'color':"#58a6ff"}, 'bgcolor':"#0d1117"}))
        fig.update_layout(height=180, margin=dict(l=10,r=10,t=10,b=10), paper_bgcolor='rgba(0,0,0,0)', font={'color':"#8b949e", 'family':"Roboto Mono"})
        st.plotly_chart(fig, use_container_width=True)

    # THE LEDGER
    st.write("---")
    rows = [
        ("Macro: Yield Curve", f"Value: {d['yc_v']:.2f}% (Watch: {d['yc_w']})", d['yc_p']),
        ("Macro: Global Trend", f"SPY Price vs 200-MA", d['tr_p']),
        ("Macro: Credit Canary", f"HYG/IEF Trend Strength", d['cr_p']),
        ("Int: Sector Breadth", f"{d['br_c']}/11 Sectors Above 200-MA", d['br_p']),
        ("Tactical: Volatility", f"VIX: {d['vix']:.1f} (1.5SD: {d['vix_u']:.1f})", d['vx_p']),
        ("Tactical: Exhaustion", f"DeMark {d['dm_t']} Count: {d['dm_c']}", d['dm_p'])
    ]

    for label, reading, pct in rows:
        st.markdown("<div class='metric-row'>", unsafe_allow_html=True)
        cl, cr, cb = st.columns([1, 1, 2])
        cl.write(label); cr.write(reading)
        color = "#39d353" if pct >= 70 else "#f85149" if pct <= 30 else "#e3b341"
        cb.markdown(f"""
            <div style="display:flex; align-items:center;">
                <div style="background-color:#30363d; width:100%; height:10px; border-radius:5px; margin-right:15px;">
                    <div style="background-color:{color}; width:{pct}%; height:10px; border-radius:5px;"></div>
                </div>
                <span style="font-family: 'Roboto Mono'; font-weight:700;">{pct}%</span>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
