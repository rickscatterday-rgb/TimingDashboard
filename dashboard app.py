import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- 1. THEME SETUP ---
st.set_page_config(page_title="ALPHA TERMINAL v3.7", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&display=swap');
    .main { background-color: #0d1117; color: #c9d1d9; }
    .data-font { font-family: 'Roboto Mono', monospace !important; }
    .metric-row { border-bottom: 1px solid #30363d; padding: 15px 0; }
    .label { color: #8b949e; font-size: 0.75rem; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; }
    .strength-text { font-family: 'Roboto Mono', monospace; font-weight: 700; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# --- 2. RESILIENT DATA ENGINE ---
@st.cache_data(ttl=1800)
def fetch_alpha_data():
    # Batch download all tickers at once
    tks = ['SPY', '^VIX', 'HYG', 'IEF', 'XLY', 'XLP', 'XLE', 'XLF', 'XLV', 'XLI', 'XLB', 'XLK', 'XLU', 'XLC', 'XLRE']
    try:
        data = yf.download(tks, period="400d", interval="1d", progress=False, auto_adjust=True)
        return data['Close'] if not data.empty else None
    except: return None

def get_yc_data():
    try:
        df = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
        df.columns = ['date', 'value']; df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna(); curr = float(df.iloc[-1]['value']); was_inv = (df.tail(180)['value'] < 0).any()
        # Trap = 0%, Inverted = 50%, Normal = 100%
        strength = 0 if (curr > 0 and was_inv) else (50 if curr < 0 else 100)
        return strength, curr, was_inv
    except: return 50, 0.0, False

def get_allocation_value(avg):
    # Simple, safe allocation logic
    if avg >= 85: return 100
    if avg >= 65: return 75
    if avg >= 45: return 50
    if avg >= 30: return 20
    return 0

# --- 3. LOGIC ENGINE ---
def run_model():
    prices = fetch_alpha_data()
    if prices is None: return None
    
    # [1] TREND (SPY vs 200MA)
    spy = prices['SPY'].dropna(); spy_px = float(spy.iloc[-1])
    spy_ma = float(spy.rolling(200).mean().iloc[-1])
    tr_pct = 100 if spy_px > spy_ma else 0
    
    # [2] CREDIT (HYG/IEF vs 50MA)
    hyg = prices['HYG'].dropna(); ief = prices['IEF'].dropna()
    ratio = hyg / ief; ma50 = ratio.rolling(50).mean()
    cr_pct = 100 if float(ratio.iloc[-1]) > float(ma50.iloc[-1]) else 0
    
    # [3] BREADTH (11 Sectors vs 200MA)
    sectors = ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
    above = 0
    for s in sectors:
        p = prices[s].dropna()
        if not p.empty and p.iloc[-1] > p.rolling(200).mean().iloc[-1]: above += 1
    br_pct = 100 if above <= 2 else (0 if above >= 9 else 65)
    
    # [4] VIX SNAPBACK
    vix = prices['^VIX'].dropna(); vx_pct = 50
    if len(vix) > 21:
        v_ma = vix.rolling(20).mean(); v_std = vix.rolling(20).std()
        v_u = v_ma + (2 * v_std); v_n = float(vix.iloc[-1]); v_p = float(vix.iloc[-2])
        if v_p > float(v_u.iloc[-2]) and v_n < float(v_u.iloc[-1]): vx_pct = 100
        elif v_n < 13: vx_pct = 0
    
    # [5] EXHAUSTION (DeMark)
    dm = (spy > spy.shift(4)).astype(int); last = int(dm.iloc[-1]); c = 0
    for val in reversed(dm.tolist()):
        if val == last: c += 1
        else: break
    dm_pct = 100 if (c >= 8 and last == 0) else (0 if (c >= 8 and last == 1) else 50)
    
    # [6] YIELD CURVE
    yc_pct, yc_v, yc_w = get_yc_data()
    
    avg = (tr_pct + cr_pct + br_pct + vx_pct + dm_pct + yc_pct) / 6
    alloc = get_allocation_value(avg)
    
    return {
        "alloc": alloc, "avg": avg, "spy": spy_px, "yc_v": yc_v, "yc_w": yc_w,
        "tr_p": tr_pct, "cr_p": cr_pct, "br_p": br_pct, "vx_p": vx_pct, "dm_p": dm_pct, "yc_p": yc_pct,
        "br_c": above, "dm_c": c, "dm_t": "Upside" if last == 1 else "Downside"
    }

# --- 4. UI ---
def main():
    st.write("### ALPHA TERMINAL v3.7 // ALLOCATION LEDGER")
    d = run_model()
    
    if d is None:
        st.error("SYNC FAILED: Yahoo Finance is throttled. Refresh in 30s.")
        return

    # TOP SECTION
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.markdown(f"**RECOMMENDED CAPITAL EXPOSURE**")
        st.markdown(f"<h1 style='font-size:4rem; color:#58a6ff;'>{d['alloc']}%</h1>", unsafe_allow_html=True)
        st.write(f"Aggregate Strength: **{d['avg']:.1f}%**")
    with c2:
        fig = go.Figure(go.Indicator(mode="gauge+number", value=d['avg'], gauge={'axis':{'range':[0,100]}, 'bar':{'color':"#58a6ff"}, 'bgcolor':"#0d1117"}))
        fig.update_layout(height=180, margin=dict(l=10,r=10,t=10,b=10), paper_bgcolor='rgba(0,0,0,0)', font={'color':"#8b949e"})
        st.plotly_chart(fig, use_container_width=True)

    # THE LEDGER
    st.write("---")
    st.write("**STRATEGIC STRENGTH LEDGER (0% = SELL | 100% = BUY)**")
    
    # Table Header
    h1, h2, h3 = st.columns([1, 1, 2])
    h1.markdown("<p class='label'>Indicator</p>", unsafe_allow_html=True)
    h2.markdown("<p class='label'>Market Reading</p>", unsafe_allow_html=True)
    h3.markdown("<p class='label'>Strength Percentage</p>", unsafe_allow_html=True)

    # Indicator Data
    rows = [
        ("Macro: Yield Curve", f"10Y-2Y: {d['yc_v']:.2f}% (Trap: {d['yc_w']})", d['yc_p']),
        ("Macro: Global Trend", f"SPY Price vs 200-MA", d['tr_p']),
        ("Macro: Credit Canary", f"HYG/IEF vs 50-MA", d['cr_p']),
        ("Int: Sector Breadth", f"{d['br_c']}/11 Sectors > 200MA", d['br_p']),
        ("Tactical: Volatility", f"VIX Snapback Check", d['vx_p']),
        ("Tactical: Exhaustion", f"DeMark {d['dm_t']} {d['dm_c']}/9", d['dm_p'])
    ]

    for label, reading, pct in rows:
        st.markdown("<div class='metric-row'>", unsafe_allow_html=True)
        col_l, col_r, col_b = st.columns([1, 1, 2])
        col_l.write(label)
        col_r.write(reading)
        
        clr = "#39d353" if pct >= 70 else "#f85149" if pct <= 30 else "#e3b341"
        col_b.markdown(f"""
            <div style="display:flex; align-items:center;">
                <div style="background-color:#30363d; width:100%; height:10px; border-radius:5px; margin-right:15px;">
                    <div style="background-color:{clr}; width:{pct}%; height:10px; border-radius:5px;"></div>
                </div>
                <span class="strength-text">{pct}%</span>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
