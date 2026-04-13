import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- 1. TERMINAL THEME SETUP ---
st.set_page_config(page_title="ALPHA TERMINAL v4.7", layout="wide")

st.markdown("""
<style>
    html, body, [class*="st-"] { font-family: 'Courier New', Courier, monospace !important; }
    .main { background-color: #0d1117; color: #c9d1d9; }
    .metric-container {
        border: 1px solid #30363d;
        padding: 20px;
        background-color: #161b22;
        margin-bottom: 20px;
    }
    .logic-box {
        background-color: #0d1117;
        border-left: 3px solid #58a6ff;
        padding: 15px;
        margin: 10px 0;
    }
    .signal-buy { color: #39d353; font-weight: bold; }
    .signal-sell { color: #f85149; font-weight: bold; }
    .progress-bg { background-color: #30363d; width: 100%; height: 12px; border-radius: 2px; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=3600)
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
        if curr > 0 and was_inv: s = 10 # Trap
        elif curr < 0: s = 40 + (curr + 1.0) * 20 # Deep inversion vs shallow
        else: s = min(100, 60 + (curr * 50))
        return s, curr
    except: return 50, 0.0

# --- 3. ANALYTICS ENGINE ---
def run_model():
    prices = fetch_alpha_data()
    if prices is None: return None
    spy = prices['SPY'].dropna(); spy_px = float(spy.iloc[-1])
    
    # 1. Trend (200MA)
    ma200 = float(spy.rolling(200).mean().iloc[-1])
    dist = (spy_px - ma200) / ma200
    tr_p = min(100, max(0, 50 + (dist * 1000)))
    
    # 2. Credit (HYG/IEF)
    ratio = (prices['HYG'].dropna() / prices['IEF'].dropna())
    r_ma = ratio.rolling(50).mean().iloc[-1]
    r_dist = (ratio.iloc[-1] - r_ma) / r_ma
    cr_p = min(100, max(0, 50 + (r_dist * 2000)))
    
    # 3. Breadth
    secs = ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
    above = 0
    for s in secs:
        p = prices[s].dropna()
        if not p.empty and p.iloc[-1] > p.rolling(200).mean().iloc[-1]: above += 1
    br_p = (above / 11) * 100
    
    # 4. VIX Position
    vix = prices['^VIX'].dropna(); v_px = float(vix.iloc[-1])
    v_ma = vix.rolling(20).mean().iloc[-1]; v_std = vix.rolling(20).std().iloc[-1]
    v_u = v_ma + (1.5 * v_std); v_l = v_ma - (1.5 * v_std)
    vx_p = min(100, max(0, ((v_px - v_l) / (v_u - v_l)) * 100))

    # 5. Exhaustion
    dm = (spy > spy.shift(4)).astype(int); lv = int(dm.iloc[-1]); c = 0
    for val in reversed(dm.tolist()):
        if val == lv: c += 1
        else: break
    dm_p = (c / 9 * 100) if lv == 0 else (100 - (c / 9 * 100))
    
    yc_p, yc_v = get_yc_analysis()
    avg = (tr_p + cr_p + br_p + vx_p + dm_p + yc_p) / 6
    alloc = 100 if avg >= 80 else (75 if avg >= 60 else (50 if avg >= 40 else 20))
    
    return {
        "alloc": alloc, "avg": avg, "yc_v": yc_v, "c": c, "lv": lv,
        "metrics": [
            ("Macro: Yield Curve", f"{yc_v:.2f}% Spread", yc_p),
            ("Trend: 200MA Prox", f"{dist:+.2%}", tr_p),
            ("Credit: Risk Ratio", "HYG/IEF", cr_p),
            ("Breadth: Sectors", f"{above}/11 Bullish", br_p),
            ("Tactical: VIX Band", f"Spot: {v_px:.1f}", vx_p),
            ("Tactical: Exhaust", f"Count: {c}/9", dm_p)
        ]
    }

# --- 4. DISPLAY ---
def main():
    st.write(f"## ALPHA TERMINAL v4.7 // {datetime.now().strftime('%H:%M:%S')}")
    d = run_model()
    if d is None: st.error("SYNC FAILED"); return

    # TOP DASHBOARD
    c_left, c_right = st.columns([1, 1])
    with c_left:
        st.markdown(f"""
        <div class="metric-container">
            <p style="color:#8b949e;">AGGREGATE SIGNAL STRENGTH</p>
            <h1 style="color:#58a6ff; font-size:48px; margin:0;">{d['avg']:.1f}%</h1>
            <p style="margin-top:15px;">RECOMMENDED ALLOCATION: <span style="color:#39d353;">{d['alloc']}% EQUITY</span></p>
        </div>
        """, unsafe_allow_html=True)
    with c_right:
        fig = go.Figure(go.Indicator(mode="gauge+number", value=d['avg'], gauge={'axis':{'range':[0,100]}, 'bar':{'color':"#58a6ff"}, 'bgcolor':"#161b22"}))
        fig.update_layout(height=220, margin=dict(l=20,r=20,t=30,b=20), paper_bgcolor='rgba(0,0,0,0)', font={'color': "#8b949e"})
        st.plotly_chart(fig, use_container_width=True)

    # LEDGER SECTION
    st.write("### STRENGTH LEDGER")
    for label, reading, pct in d['metrics']:
        col1, col2, col3 = st.columns([1, 1, 2])
        col1.write(f"**{label}**")
        col2.write(reading)
        color = "#39d353" if pct >= 70 else "#f85149" if pct <= 30 else "#e3b341"
        bar_html = f'<div class="progress-bg"><div style="background-color:{color}; width:{pct}%; height:12px; border-radius:2px;"></div></div>'
        col3.markdown(bar_html, unsafe_allow_html=True)

    # --- 5. SIGNAL INTELLIGENCE DICTIONARY (THE EXPLANATIONS) ---
    st.write("---")
    st.write("### 🧠 SIGNAL INTELLIGENCE DICTIONARY")
    
    dict_cols = st.columns(2)
    
    with dict_cols[0]:
        st.markdown("""
        <div class="logic-box">
            <p><b>1. Yield Curve (Macro)</b></p>
            <span class="signal-buy">BUY:</span> Curve is "Normal" (Positive > 0.5) OR deeply inverted (-1.0).<br>
            <span class="signal-sell">SELL:</span> "The Trap." When the curve crosses from Negative back to Positive (0.0). This precedes 90% of recessions.
        </div>
        <div class="logic-box">
            <p><b>2. Trend Proximity (Momentum)</b></p>
            <span class="signal-buy">BUY:</span> Price is > 5% above the 200-Day Moving Average (Structural Uptrend).<br>
            <span class="signal-sell">SELL:</span> Price drops below the 200MA. Historically, the worst market crashes occur only while below the 200MA.
        </div>
        <div class="logic-box">
            <p><b>3. Credit Canary (Risk-On/Off)</b></p>
            <span class="signal-buy">BUY:</span> HYG (Junk Bonds) outperforming IEF (Treasuries). Indicates big institutions are taking risks.<br>
            <span class="signal-sell">SELL:</span> Treasuries outperforming Junk bonds. Indicates "Flight to Safety" liquidity flows.
        </div>
        """, unsafe_allow_html=True)

    with dict_cols[1]:
        st.markdown("""
        <div class="logic-box">
            <p><b>4. Sector Breadth (Internal Health)</b></p>
            <span class="signal-buy">BUY:</span> > 8/11 sectors are above their 200MA. High participation confirms a healthy rally.<br>
            <span class="signal-sell">SELL:</span> < 4/11 sectors are positive. Indicates "Narrow Leadership" where only a few stocks prop up the index.
        </div>
        <div class="logic-box">
            <p><b>5. Volatility Position (Sentiment)</b></p>
            <span class="signal-buy">BUY:</span> VIX hits the Upper Bollinger Band (Extreme Fear). Markets usually bottom when fear peaks.<br>
            <span class="signal-sell">SELL:</span> VIX hits the Lower Bollinger Band (Complacency). Risk is highest when everything feels safe.
        </div>
        <div class="logic-box">
            <p><b>6. Exhaustion Count (Timing)</b></p>
            <span class="signal-buy">BUY:</span> Downside 9-Count. Indicates sellers are exhausted; a relief rally or reversal is statistically probable.<br>
            <span class="signal-sell">SELL:</span> Upside 9-Count. Indicates "FOMO" buying is exhausted; market is likely "overbought" and needs to cool.
        </div>
        """, unsafe_allow_html=True)

    st.caption(f"ALPHA TERMINAL v4.7 // AGGREGATE MODEL WEIGHTING: EQUAL-WEIGHT LINEAR RANK // REFRESH TO SYNC")

if __name__ == "__main__":
    main()
