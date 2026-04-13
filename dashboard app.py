import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- 1. TERMINAL THEME SETUP ---
st.set_page_config(page_title="ALPHA TERMINAL v4.8", layout="wide")

st.markdown("""
<style>
    html, body, [class*="st-"] { font-family: 'Courier New', Courier, monospace !important; }
    .main { background-color: #05070a; color: #c9d1d9; }
    .metric-container {
        border: 1px solid #30363d;
        padding: 20px;
        background-color: #0d1117;
        margin-bottom: 20px;
    }
    .logic-box {
        background-color: #161b22;
        border-left: 3px solid #58a6ff;
        padding: 15px;
        margin: 10px 0;
        font-size: 0.9em;
    }
    .signal-buy { color: #39d353; font-weight: bold; }
    .signal-sell { color: #f85149; font-weight: bold; }
    .progress-bg { background-color: #30363d; width: 100%; height: 14px; border-radius: 2px; }
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
        if curr > 0 and was_inv: s = 10
        elif curr < 0: s = 40 + (curr + 1.0) * 20 
        else: s = min(100, 60 + (curr * 50))
        return s, curr
    except: return 50, 0.0

# --- 3. ANALYTICS ENGINE ---
def run_model():
    prices = fetch_alpha_data()
    if prices is None: return None
    spy = prices['SPY'].dropna(); spy_px = float(spy.iloc[-1])
    
    # [1] TREND (200MA)
    ma200 = float(spy.rolling(200).mean().iloc[-1])
    dist = (spy_px - ma200) / ma200
    tr_p = min(100, max(0, 50 + (dist * 1000)))
    
    # [2] CREDIT (HYG/IEF)
    ratio = (prices['HYG'].dropna() / prices['IEF'].dropna())
    r_ma = ratio.rolling(50).mean().iloc[-1]
    r_dist = (ratio.iloc[-1] - r_ma) / r_ma
    cr_p = min(100, max(0, 50 + (r_dist * 2000)))
    
    # [3] SECTOR BREADTH
    secs = ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
    above = 0
    for s in secs:
        p = prices[s].dropna()
        if not p.empty and p.iloc[-1] > p.rolling(200).mean().iloc[-1]: above += 1
    br_p = (above / 11) * 100
    
    # [4] VOLATILITY BAND (VIX Robust Logic)
    vix_series = prices['^VIX'].dropna()
    v_px = float(vix_series.iloc[-1])
    # Use 20-day High and Low as the bands
    v_high = vix_series.tail(20).max()
    v_low = vix_series.tail(20).min()
    
    # Formula: Current position between 20-day high and low
    # 100% = VIX is at 20-day high (Extreme Fear = Buy Opportunity)
    if v_high == v_low:
        vx_p = 50.0
    else:
        vx_p = ((v_px - v_low) / (v_high - v_low)) * 100
    
    # [5] EXHAUSTION
    dm = (spy > spy.shift(4)).astype(int); lv = int(dm.iloc[-1]); c = 0
    for val in reversed(dm.tolist()):
        if val == lv: c += 1
        else: break
    dm_p = (c / 9 * 100) if lv == 0 else (100 - (c / 9 * 100))
    
    yc_p, yc_v = get_yc_analysis()
    avg = (tr_p + cr_p + br_p + vx_p + dm_p + yc_p) / 6
    alloc = 100 if avg >= 80 else (75 if avg >= 60 else (50 if avg >= 40 else 20))
    
    return {
        "alloc": alloc, "avg": avg, "yc_v": yc_v, "v_px": v_px, "v_range": (v_low, v_high),
        "metrics": [
            ("Macro: Yield Curve", f"{yc_v:.2f}% Spread", yc_p),
            ("Trend: 200MA Prox", f"{dist:+.2%}", tr_p),
            ("Credit: Risk Ratio", "HYG/IEF", cr_p),
            ("Breadth: Sectors", f"{above}/11 Bullish", br_p),
            ("Tactical: VIX Band", f"Spot: {v_px:.1f}", vx_p),
            ("Tactical: Exhaust", f"Step {c}/9", dm_p)
        ]
    }

# --- 4. DISPLAY ---
def main():
    st.write(f"## ALPHA TERMINAL v4.8 // {datetime.now().strftime('%H:%M:%S')}")
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
        bar_html = f'<div class="progress-bg"><div style="background-color:{color}; width:{pct}%; height:14px; border-radius:2px;"></div></div>'
        col3.markdown(bar_html, unsafe_allow_html=True)

    # --- 5. SIGNAL INTELLIGENCE DICTIONARY ---
    st.write("---")
    st.write("### 🧠 SIGNAL INTELLIGENCE DICTIONARY")
    
    dict_cols = st.columns(2)
    
    with dict_cols[0]:
        st.markdown(f"""
        <div class="logic-box">
            <p><b>1. Yield Curve (Macro Correlation)</b></p>
            <span class="signal-buy">BUY CONDITION:</span> Curve is either healthy (>0.5) or "Deeply Inverted" (< -0.5) as the market has already priced in the pain.<br>
            <span class="signal-sell">SELL CONDITION:</span> "The Re-Steepening." When the spread crosses 0 from a negative value. This is the #1 signal of an imminent recession.
        </div>
        <div class="logic-box">
            <p><b>2. Trend Proximity (Moving Average)</b></p>
            <span class="signal-buy">BUY CONDITION:</span> Price is trending comfortably above the 200-day Moving Average. Momentum is in your favor.<br>
            <span class="signal-sell">SELL CONDITION:</span> Price breaks below the 200-day MA. This indicates a structural shift from a Bull to a Bear market.
        </div>
        <div class="logic-box">
            <p><b>3. Credit Canary (Risk Sentiment)</b></p>
            <span class="signal-buy">BUY CONDITION:</span> High Yield Junk Bonds (HYG) are outperforming safe-haven Treasuries (IEF). Capital is seeking risk.<br>
            <span class="signal-sell">SELL CONDITION:</span> Treasuries start outperforming Junk Bonds. This "Flight to Quality" usually happens before stock market crashes.
        </div>
        """, unsafe_allow_html=True)

    with dict_cols[1]:
        st.markdown(f"""
        <div class="logic-box">
            <p><b>4. Sector Breadth (Market Participation)</b></p>
            <span class="signal-buy">BUY CONDITION:</span> >8 of 11 S&P sectors are in uptrends. This confirms the rally is broad-based and sustainable.<br>
            <span class="signal-sell">SELL CONDITION:</span> <4 sectors are in uptrends. This is "Narrow Leadership" where only a few tech stocks are hiding a weak market.
        </div>
        <div class="logic-box">
            <p><b>5. Volatility Band (Contrarian Timing)</b></p>
            <span class="signal-buy">BUY CONDITION:</span> VIX is at a 20-day High (Strength = 100%). When the "crowd" is terrified, it is historically the best time to buy.<br>
            <span class="signal-sell">SELL CONDITION:</span> VIX is at a 20-day Low (Strength = 0%). Extreme complacency often leads to sharp, unexpected sell-offs.
        </div>
        <div class="logic-box">
            <p><b>6. Exhaustion Count (Sequential Logic)</b></p>
            <span class="signal-buy">BUY CONDITION:</span> Downside 9-Count. Current price has been lower than the price 4 days ago for 9 consecutive steps.<br>
            <span class="signal-sell">SELL CONDITION:</span> Upside 9-Count. The market is "vertically exhausted" and likely to mean-revert or consolidate.
        </div>
        """, unsafe_allow_html=True)

    st.caption(f"ALPHA TERMINAL // VIX 20D RANGE: {d['v_range'][0]:.1f} - {d['v_range'][1]:.1f}")

if __name__ == "__main__":
    main()
