import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- QUANTITATIVE TERMINAL CONFIG ---
st.set_page_config(page_title="ALPHA TERMINAL v3.0", layout="wide")

# CSS: GRID ARCHITECTURE & MONOSPACED DATA
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Roboto+Mono:wght@400;700&display=swap');
    
    .main { background-color: #0d1117; color: #c9d1d9; }
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    /* Terminal Data Font */
    .data-font { font-family: 'Roboto Mono', monospace; }

    /* Strict Grid System */
    .grid-cell {
        border: 1px solid #30363d;
        padding: 24px;
        background-color: #0d1117;
    }
    
    .terminal-label { 
        color: #8b949e; 
        font-size: 0.7rem; 
        font-weight: 700; 
        letter-spacing: 2px; 
        text-transform: uppercase;
        margin-bottom: 8px;
    }

    .big-metric { 
        font-family: 'Roboto Mono', monospace; 
        font-size: 3.5rem; 
        font-weight: 700; 
        line-height: 1;
        color: #58a6ff;
    }

    .doc-section {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 30px;
        margin-top: 40px;
    }

    .logic-grid {
        display: grid;
        grid-template-columns: 1fr 2fr;
        border-bottom: 1px solid #30363d;
        padding: 15px 0;
    }

    hr { border: 0; border-top: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

class AlphaEngine:
    def get_px(self, ticker, days=400):
        try:
            df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False, auto_adjust=True)
            if df.empty: return pd.Series()
            return df['Close'].iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else df['Close']
        except: return pd.Series()

    def get_yc_analysis(self):
        try:
            df = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
            df.columns = ['date', 'value']
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna()
            curr = float(df.iloc[-1]['value'])
            lookback = df.tail(180)
            was_inverted = (lookback['value'] < 0).any()
            # 1=Trap, 5=Inverted, 10=Normal
            score = 1 if (curr > 0 and was_inverted) else (5 if curr < 0 else 10)
            return score, curr, was_inverted
        except: return 5, 0, False

    def run_model(self):
        scores = {}
        # 1. Yield Curve
        yc_s, yc_v, yc_w = self.get_yc_analysis()
        scores['YC'] = yc_s
        # 2. Global Trend
        spy = self.get_px('SPY', 350); ma200 = spy.rolling(200).mean(); spy_c = float(spy.iloc[-1])
        scores['TREND'] = 10 if spy_c > float(ma200.iloc[-1]) else 1
        # 3. Sector Breadth
        sectors = ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
        above = 0
        for s in sectors:
            px = self.get_px(s, 250)
            if not px.empty and px.iloc[-1] > px.rolling(200).mean().iloc[-1]: above += 1
        scores['BREADTH'] = 10 if above <= 2 else (3 if above >= 9 else 7)
        # 4. Volatility
        vix = self.get_px('^VIX', 50); v_ma = vix.rolling(20).mean(); v_std = vix.rolling(20).std()
        v_u = v_ma + (2 * v_std); v_n = float(vix.iloc[-1]); v_p = float(vix.iloc[-2])
        scores['VOL'] = 10 if v_p > float(v_u.iloc[-2]) and v_n < float(v_u.iloc[-1]) else (2 if v_n < 13 else 6)
        # 5. Exhaustion
        dm = (spy > spy.shift(4)).astype(int); last_v = dm.iloc[-1]; c = 0
        for val in reversed(dm.tolist()):
            if val == last_v: c += 1
            else: break
        scores['COUNT'] = 10 if (c >= 8 and last_v == 0) else (1 if (c >= 8 and last_v == 1) else 5)

        avg = sum(scores.values()) / len(scores)
        alloc = 100 if avg >= 8.5 else (75 if avg >= 7 else (50 if avg >= 5.5 else (20 if avg >= 4 else 0)))
        return scores, avg, alloc, spy_c, yc_v, yc_w, above

def main():
    engine = AlphaEngine()
    with st.spinner('FETCHING MARKET DATA...'):
        scores, avg, alloc, spy_px, yc_val, yc_warn, bread_count = engine.run_model()

    # --- TOP LEVEL HEADER ---
    st.markdown("<p style='font-family:\"Roboto Mono\"; font-size: 0.7rem; color: #58a6ff; margin-bottom: 20px;'>[ TERMINAL_ID: 0xALPHA_v3.0 ] // DATA_REFRESH: " + datetime.now().strftime('%H:%M:%S') + " UTC</p>", unsafe_allow_html=True)
    
    col_1, col_2 = st.columns([1, 1.5])
    
    with col_1:
        st.markdown(f"""
            <div class="grid-cell" style="border-left: 4px solid #58a6ff;">
                <p class="terminal-label">Recommended Allocation</p>
                <div class="big-metric">{alloc}%</div>
                <p style="font-family:'Roboto Mono'; font-size: 0.8rem; color: #8b949e; margin-top: 15px;">STRATEGY: {'UNRESTRICTED' if alloc >= 75 else 'DEFENSIVE' if alloc <= 25 else 'TACTICAL'}</p>
            </div>
        """, unsafe_allow_html=True)

    with col_2:
        st.markdown("""<div class="grid-cell" style="height: 100%;">""", unsafe_allow_html=True)
        fig = go.Figure(go.Indicator(
            mode = "gauge+number", value = avg,
            gauge = {
                'axis': {'range': [1, 10], 'tickcolor': "#30363d", 'tickfont': {'family': "Roboto Mono"}},
                'bar': {'color': "#58a6ff"}, 'bgcolor': "#0d1117",
                'steps': [{'range': [1, 4], 'color': "#3e1c1c"}, {'range': [7, 10], 'color': "#1c3e24"}]
            }
        ))
        fig.update_layout(height=160, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor='rgba(0,0,0,0)', font={'color': "#8b949e", 'family': "Roboto Mono"})
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("""</div>""", unsafe_allow_html=True)

    # --- SECOND ROW: MACRO INDICATORS ---
    st.markdown("<br>", unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    
    with m1:
        st.markdown(f"""<div class="grid-cell"><p class="terminal-label">YC Recession Watch</p><h2 class="data-font">{yc_val:.2f}%</h2><p style="font-size: 0.7rem; color: {'#f85149' if yc_warn else '#8b949e'}">{'[!] RE-STEEPENING TRAP' if yc_warn and yc_val > 0 else 'STABLE'}</p></div>""", unsafe_allow_html=True)
    with m2:
        st.markdown(f"""<div class="grid-cell"><p class="terminal-label">Structural Trend</p><h2 class="data-font">${spy_px:.2f}</h2><p style="font-size: 0.7rem; color: #8b949e">{'ABOVE 200MA' if scores['TREND'] == 10 else 'BELOW 200MA'}</p></div>""", unsafe_allow_html=True)
    with m3:
        st.markdown(f"""<div class="grid-cell"><p class="terminal-label">Sector Breadth</p><h2 class="data-font">{bread_count}/11</h2><p style="font-size: 0.7rem; color: #8b949e">Sectors above 200MA</p></div>""", unsafe_allow_html=True)

    # --- THIRD ROW: TACTICAL ---
    st.markdown("<br>", unsafe_allow_html=True)
    t1, t2 = st.columns(2)
    with t1:
        val = scores['VOL']
        st.markdown(f"""<div class="grid-cell"><p class="terminal-label">Volatility Score</p><h2 class="data-font" style="color: {'#39d353' if val == 10 else '#f85149' if val == 2 else '#c9d1d9'};">{val}/10</h2><p style="font-size: 0.7rem; color: #8b949e">VIX Bollinger Snapback Check</p></div>""", unsafe_allow_html=True)
    with t2:
        val = scores['COUNT']
        st.markdown(f"""<div class="grid-cell"><p class="terminal-label">Sequential Exhaustion</p><h2 class="data-font" style="color: {'#39d353' if val == 10 else '#f85149' if val == 1 else '#c9d1d9'};">{val}/10</h2><p style="font-size: 0.7rem; color: #8b949e">DeMark 9-Count Logic</p></div>""", unsafe_allow_html=True)

    # --- DOCUMENTATION SECTION ---
    st.markdown("""
        <div class="doc-section">
            <p class="terminal-label" style="color: #58a6ff; font-size: 1rem;">Technical Methodology & Logic</p>
            <p style="color: #8b949e; font-siz
