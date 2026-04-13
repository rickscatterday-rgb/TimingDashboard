import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- 1. TERMINAL THEME SETUP ---
st.set_page_config(page_title="ALPHA TERMINAL v4.3", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&display=swap');
    .main { background-color: #0d1117; color: #c9d1d9; }
    .stMetric { border: 1px solid #30363d !important; background-color: #0d1117 !important; border-radius: 0px !important; }
    .data-font { font-family: 'Roboto Mono', monospace !important; }
    h1, h2, h3, p, span { font-family: 'Roboto Mono', monospace !important; font-weight: 700 !important; }
    .metric-row { border-bottom: 1px solid #30363d; padding: 15px 0; }
    .ledger-box { background-color: #161b22; border: 1px solid #30363d; padding: 25px; margin-top: 20px; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=1800)
def fetch_alpha_data():
    tks = ['SPY', '^VIX', 'HYG', 'IEF', 'XLY', 'XLP', 'XLE', 'XLF', 'XLV', 'XLI', 'XLB', 'XLK', 'XLU', 'XLC', 'XLRE']
    try:
        df = yf.download(tks, period="400d", interval="1d", progress=False, auto_adjust=True)
        return df['Close'] if not df.empty else None
    except: return None

def get_yc_analysis():
    try:
        df = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
        df.columns = ['date', 'value']; df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna(); curr = float(df['value'].iloc[-1]); was_inv = (df['value'].tail(180) < 0).any()
        # Linear: Trap = 0%, Inverted = 40%, Healthy (>0.50) = 100%
        if curr > 0 and was_inv: s = 10
        elif curr < 0: s = 40 + (curr + 1.0) * 20 # Slopes up from inversion
        else: s = min(100, 60 + (curr * 50))
        return s, curr, was_inv
    except: return 50, 0.0, False

# --- 3. LINEAR SCORING ENGINE ---
def run_model():
    prices = fetch_alpha_data()
    if prices is None: return None
    spy = prices['SPY'].dropna(); spy_px = float(spy.iloc[-1])
    
    # [1] TREND PROXIMITY (Distance from 200MA)
    ma200 = float(spy.rolling(200).mean().iloc[-1])
    dist = (spy_px - ma200) / ma200
    # 5% above = 100% Strength, at MA = 50%, 5% below = 0%
    tr_p = min(100, max(0, 50 + (dist * 1000)))
    
    # [2] CREDIT PROXIMITY (Ratio vs 50MA)
    ratio = (prices['HYG'].dropna() / prices['IEF'].dropna())
    r_ma = ratio.rolling(50).mean().iloc[-1]
    r_dist = (ratio.iloc[-1] - r_ma) / r_ma
    cr_p = min(100, max(0, 50 + (r_dist * 2000)))
    
    # [3] SECTOR BREADTH (11 Sectors)
    secs = ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
    above = 0
    for s in secs:
        p = prices[s].dropna()
        if not p.empty and p.iloc[-1] > p.rolling(200).mean().iloc[-1]: above += 1
    br_p = (above / 11) * 100
    
    # [4] VOLATILITY POSITION (VIX relative to 1.5SD Bands)
    vix = prices['^VIX'].dropna(); v_px = float(vix.iloc[-1])
    v_ma = vix.rolling(20).mean().iloc[-1]; v_std = vix.rolling(20).std().iloc[-1]
    v_u = v_ma + (1.5 * v_std); v_l = v_ma - (1.5 * v_std)
    # Strength = where price is between Lower(0%) and Upper(100%)
    vx_p = min(100, max(0, ((v_px - v_l) / (v_u - v_l)) * 100))

    # [5] EXHAUSTION COUNT
    dm = (spy > spy.shift(4)).astype(int); lv = int(dm.iloc[-1]); c = 0
    for val in reversed(dm.tolist()):
        if val == lv: c += 1
        else: break
    # Downside 9-count = 100% Buy Strength, Upside 9-count = 0% Strength
    dm_p = (c / 9 * 100) if lv == 0 else (100 - (c / 9 * 100))
    
    yc_p, yc_v, yc_w = get_yc_analysis()
    
    avg = (tr_p + cr_p + br_p + vx_p + dm_p + yc_p) / 6
    alloc = 100 if avg >= 80 else (75 if avg >= 60 else (50 if avg >= 40 else 20))
    
    return {
        "alloc": alloc, "avg": avg, "yc_v": yc_v, "yc_w": yc_w,
        "tr_p": tr_p, "cr_p": cr_p, "br_p": br_p, "vx_p": vx_p, "dm_p": dm_p, "yc_p": yc_p,
        "vix": v_px, "vix_u": v_u, "vix_l": v_l, "dm_c": c, "br_c": above
    }

# --- 4. DISPLAY ---
def main():
    st.write("### ALPHA TERMINAL v4.3 // LINEAR STRENGTH LEDGER")
    d = run_model()
    if d is None:
        st.error("SYNC FAILED. Refreshing data..."); st.rerun()

    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.metric("CAPITAL ALLOCATION", f"{d['alloc']}%")
        st.write(f"Aggregate Strength: **{d['avg']:.1f}%**")
        st.caption("100% = Maximum Bullish | 0% = Maximum Bearish")
    with c2:
        fig = go.Figure(go.Indicator(mode="gauge+number", value=d['avg'], gauge={'axis':{'range':[0,100]}, 'bar':{'color':"#58a6ff"}, 'bgcolor':"#0d1117"}))
        fig.update_layout(height=180, margin=dict(l=10,r=10,t=10,b=10), paper_bgcolor='rgba(0,0,0,0)', font={'color': "#8b949e", 'family':"Roboto Mono"})
        st.plotly_chart(fig, use_container_width=True)

    st.write("---")
    st.write("**STRENGTH LEDGER (LINEAR RANKINGS)**")
    
    rows = [
        ("Macro: Yield Curve", f"10Y-2Y Spread: {d['yc_v']:.2f}%", d['yc_p'], "Measures the 6-month recession lag. 0% = Trap (Re-steepening)."),
        ("Macro: Global Trend", f"SPY vs 200MA Proximity", d['tr_p'], "Strength increases as price separates above the 200-day average."),
        ("Macro: Credit Canary", f"HYG/IEF Ratio Strength", d['cr_p'], "Measures risk appetite. 100% means Junk Bonds are surging vs Treasuries."),
        ("Int: Sector Breadth", f"{d['br_c']}/11 Sectors Positive", d['br_p'], "Calculates total market participation. 100% means all sectors are in uptrends."),
        ("Tactical: Volatility", f"VIX Pos: {d['vix']:.1f} (Bands: {d['vix_l']:.1f}-{d['vix_u']:.1f})", d['vx_p'], "Scores VIX position between bands. 100% = Panic peak, 0% = Complacency."),
        ("Tactical: Exhaustion", f"DeMark 9-Count Progress", d['dm_p'], "Scores based on count progress. 100% = Complete Downside Exhaustion.")
    ]

    for label, read, pct, logic in rows:
        st.markdown("<div class='metric-row'>", unsafe_allow_html=True)
        cl, cr, cb = st.columns([1, 1, 2])
        cl.write(label); cr.write(read)
        clr = "#39d353" if pct >= 70 else "#f85149" if pct <= 30 else "#e3b341"
        cb.markdown(f'<div style="display:flex; align-items:center;"><div style="background-color:#30363d; width:100%; height:10px; border-radius:5px; margin-right:15px;"><div style="background-color:{clr}; width:{pct}%; height:10px; border-radius:5px;"></div></div><span class="data-font">{pct:.0f}%</span></div>', unsafe_allow_html=True)
        with st.expander(f"Explain {label} Logic"):
            st.write(logic)
        st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
