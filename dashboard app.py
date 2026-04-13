import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- 1. TERMINAL CONFIG ---
st.set_page_config(page_title="ALPHA TERMINAL", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&display=swap');
    .main { background-color: #0d1117; color: #c9d1d9; }
    .stMetric { 
        border: 1px solid #30363d !important; 
        background-color: #0d1117 !important; 
        border-radius: 0px !important; 
        padding: 20px !important; 
    }
    .data-font { font-family: 'Roboto Mono', monospace !important; }
    h1, h2, h3, p, span { font-family: 'Roboto Mono', monospace !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA ENGINE (Optimized for Cloud Speeds) ---
class AlphaEngine:
    def get_bulk_px(self, tickers, days=350):
        """Downloads all tickers in ONE shot to prevent hanging."""
        try:
            df = yf.download(tickers, period=f"{days}d", interval="1d", progress=False, auto_adjust=True)
            if df.empty:
                return None
            return df['Close']
        except:
            return None

    def get_yc(self):
        try:
            df = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
            df.columns = ['date', 'value']
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna()
            curr = float(df.iloc[-1]['value'])
            was_inv = (df.tail(180)['value'] < 0).any()
            score = 1 if (curr > 0 and was_inv) else (5 if curr < 0 else 10)
            return score, curr, was_inv
        except: 
            return 5, 0.0, False

    def run_model(self):
        # We fetch EVERYTHING in one single request. This stops the app from hanging.
        all_tickers = ['SPY', '^VIX', 'XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
        bulk_data = self.get_bulk_px(all_tickers)
        
        if bulk_data is None or bulk_data.empty:
            # Fallback if Yahoo is down or blocking
            return 5, 5, 5, 5, 5, 5.0, 50, 0.0, 0.0, False, 0, 0

        # [A] Trend
        spy = bulk_data['SPY'].dropna()
        s_px = float(spy.iloc[-1])
        s_ma = float(spy.rolling(200).mean().iloc[-1])
        tr_s = 10 if s_px > s_ma else 1

        # [B] Breadth (11 Sectors)
        sectors = ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
        above = 0
        for s in sectors:
            s_data = bulk_data[s].dropna()
            if not s_data.empty:
                if float(s_data.iloc[-1]) > float(s_data.rolling(200).mean().iloc[-1]):
                    above += 1
        br_s = 10 if above <= 2 else (3 if above >= 9 else 7)

        # [C] Tactical (VIX)
        vix = bulk_data['^VIX'].dropna()
        vx_s = 5
        if len(vix) > 21:
            v_u = vix.rolling(20).mean() + (2 * vix.rolling(20).std())
            vx_s = 10 if (float(vix.iloc[-2]) > float(v_u.iloc[-2]) and float(vix.iloc[-1]) < float(v_u.iloc[-1])) else (2 if float(vix.iloc[-1]) < 13 else 6)
        
        # [D] DeMark
        dm = (spy > spy.shift(4)).astype(int)
        l_v = dm.iloc[-1]
        cnt = 0
        for val in reversed(dm.tolist()):
            if val == l_v: cnt += 1
            else: break
        dm_s = 10 if (cnt >= 8 and l_v == 0) else (1 if (cnt >= 8 and l_v == 1) else 5)

        # [E] Macro
        yc_s, yc_v, yc_w = self.get_yc()

        # [F] Final Calculation
        avg = (yc_s + tr_s + br_s + vx_s + dm_s) / 5
        alloc = 100 if avg >= 8.5 else (75 if avg >= 7 else (50 if avg >= 5.5 else (20 if avg >= 4 else 0)))
        
        return yc_s, tr_s, br_s, vx_s, dm_s, avg, alloc, s_px, yc_v, yc_w, above, cnt

# --- 3. UI DISPLAY ---
def main():
    st.write("### ALPHA TERMINAL v3.3 // RISK OVERSIGHT")
    
    e = AlphaEngine()
    
    # We run the calculations
    yc_s, tr_s, br_s, vx_s, dm_s, avg, alloc, spy, yc_v, yc_w, br_c, dm_c = e.run_model()

    if spy == 0.0:
        st.error("SYSTEM TIMEOUT: Yahoo Finance is not responding. Please refresh the page in 10 seconds.")
        return

    # --- TOP ROW ---
    c_a, c_b = st.columns([1, 1.5])
    with c_a:
        st.metric("CAPITAL ALLOCATION", f"{alloc}%")
        st.write(f"MODE: **{'AGGRESSIVE' if alloc >= 75 else 'DEFENSIVE' if alloc <= 25 else 'TACTICAL'}**")
    with c_b:
        fig = go.Figure(go.Indicator(
            mode = "gauge+number", value = avg,
            gauge = {'axis': {'range': [1, 10]}, 'bar': {'color': "#58a6ff"}, 'bgcolor': "#0d1117",
                     'steps': [{'range': [1, 4], 'color': "#3e1c1c"}, {'range': [7, 10], 'color': "#1c3e24"}]}))
        fig.update_layout(height=200, margin=dict(l=10,r=10,t=10,b=10), paper_bgcolor='rgba(0,0,0,0)', font={'color': "#8b949e"})
        st.plotly_chart(fig, use_container_width=True)

    # --- SECTION I: MACRO ---
    st.markdown("---")
    st.write("**SECTION I: MACRO REGIME**")
    m1, m2 = st.columns(2)
    m1.metric("YIELD CURVE SPREAD", f"{yc_v:.2f}%", delta="RECESSION WATCH" if yc_w and yc_v > 0 else None, delta_color="inverse")
    m2.metric("STRUCTURAL TREND", f"${spy:.2f}", help="SPY Price vs 200-Day Moving Average")

    # --- SECTION II: TACTICAL ---
    st.markdown("---")
    st.write("**SECTION II: TACTICAL EXECUTION**")
    t1, t2, t3 = st.columns(3)
    t1.metric("SECTOR BREADTH", f"{br_c}/11", help="Participation of 11 S&P sectors above 200MA")
    t2.metric("VOLATILITY SCORE", f"{vx_s}/10", help="VIX Bollinger Snapback Logic")
    t3.metric("EXHAUSTION COUNT", f"{dm_c} of 9", help="DeMark sequential trend count")

if __name__ == "__main__":
    main()
