import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- 1. THEME & FONT SETUP ---
st.set_page_config(page_title="ALPHA TERMINAL", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&display=swap');
    .main { background-color: #0d1117; color: #c9d1d9; }
    .data-font { font-family: 'Roboto Mono', monospace; }
    .grid-cell { border: 1px solid #30363d; padding: 20px; background-color: #0d1117; height: 100%; }
    .label { color: #8b949e; font-size: 0.65rem; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
class AlphaEngine:
    def get_px(self, ticker, days=400):
        try:
            df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False, auto_adjust=True)
            if df.empty: return pd.Series()
            # Handle MultiIndex columns from newer yfinance versions
            if isinstance(df.columns, pd.MultiIndex):
                return df['Close'].iloc[:, 0]
            return df['Close']
        except: return pd.Series()

    def get_yc(self):
        try:
            df = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
            df.columns = ['date', 'value']
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna()
            curr = float(df.iloc[-1]['value'])
            was_inv = (df.tail(180)['value'] < 0).any()
            # 1=Trap, 5=Inverted, 10=Normal
            score = 1 if (curr > 0 and was_inv) else (5 if curr < 0 else 10)
            return score, curr, was_inv
        except: return 5, 0.0, False

    def run(self):
        # [A] Macro Logic
        yc_s, yc_v, yc_w = self.get_yc()
        spy = self.get_px('SPY', 350)
        s_px = float(spy.iloc[-1]) if not spy.empty else 0.0
        ma200 = float(spy.rolling(200).mean().iloc[-1]) if len(spy) > 200 else 0.0
        s_trend = 10 if s_px > ma200 else 1

        # [B] Breadth Logic (11 Sectors)
        sectors = ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
        above = 0
        for s in sectors:
            p = self.get_px(s, 250)
            if not p.empty and p.iloc[-1] > p.rolling(200).mean().iloc[-1]: above += 1
        s_breadth = 10 if above <= 2 else (3 if above >= 9 else 7)

        # [C] Tactical Logic (VIX & DeMark)
        vix = self.get_px('^VIX', 50)
        vx_s = 5
        if not vix.empty and len(vix) > 21:
            v_ma = vix.rolling(20).mean(); v_std = vix.rolling(20).std()
            v_u = v_ma + (2 * v_std); v_n = float(vix.iloc[-1]); v_p = float(vix.iloc[-2])
            vx_s = 10 if v_p > float(v_u.iloc[-2]) and v_n < float(v_u.iloc[-1]) else (2 if v_n < 13 else 6)
        
        dm = (spy > spy.shift(4)).astype(int)
        last_val = dm.iloc[-1] if not dm.empty else 0
        cnt = 0
        for val in reversed(dm.tolist()):
            if val == last_val: cnt += 1
            else: break
        s_dm = 10 if (cnt >= 8 and last_val == 0) else (1 if (cnt >= 8 and last_val == 1) else 5)

        # [D] Final Aggregation
        avg = (yc_s + s_trend + s_breadth + vx_s + s_dm) / 5
        alloc = 100 if avg >= 8.5 else (75 if avg >= 7 else (50 if avg >= 5.5 else (20 if avg >= 4 else 0)))
        return yc_s, s_trend, s_breadth, vx_s, s_dm, avg, alloc, s_px, yc_v, yc_w, above, cnt

# --- 3. UI DISPLAY ---
def main():
    e = AlphaEngine()
    with st.spinner('ACCESSING DATA TERMINAL...'):
        yc_s, tr_s, br_s, vx_s, dm_s, avg, alloc, spy, yc_v, yc_w, br_c, dm_c = e.run()

    st.markdown(f"<p class='data-font' style='color:#58a6ff; font-size:0.7rem;'>ALPHA TERMINAL v3.0 // {datetime.now().strftime('%H:%M:%S')} UTC</p>", unsafe_allow_html=True)

    # TOP ROW
    col1, col2 = st.columns([1, 1.5])
    with col1:
        st.markdown(f'<div class="grid-cell" style="border-left: 4px solid #58a6ff;"><p class="label">Target Allocation</p><h1 class="data-font" style="font-size:4rem; margin:0; color:#58a6ff;">{alloc}%</h1></div>', unsafe_allow_htm
