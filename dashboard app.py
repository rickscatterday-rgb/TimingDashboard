import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- INSTITUTIONAL TERMINAL CONFIG ---
st.set_page_config(page_title="ALPHA TERMINAL v3.0", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Roboto+Mono:wght@400;700&display=swap');
    
    .main { background-color: #0d1117; color: #c9d1d9; }
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .data-font { font-family: 'Roboto Mono', monospace; }

    /* Structural Grid Styling */
    .grid-cell {
        border: 1px solid #30363d;
        padding: 20px;
        background-color: #0d1117;
        height: 100%;
    }
    
    .label { 
        color: #8b949e; 
        font-size: 0.65rem; 
        font-weight: 700; 
        letter-spacing: 1.5px; 
        text-transform: uppercase;
        margin-bottom: 10px;
    }

    .metric-value { 
        font-family: 'Roboto Mono', monospace; 
        font-size: 3rem; 
        font-weight: 700; 
        line-height: 1;
        color: #58a6ff;
    }

    .methodology-box {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 25px;
        margin-top: 30px;
    }

    .method-row {
        display: grid;
        grid-template-columns: 200px 1fr;
        border-bottom: 1px solid #30363d;
        padding: 15px 0;
    }

    .method-title { font-family: 'Roboto Mono', monospace; font-weight: 700; font-size: 0.8rem; color: #f0f6fc; }
    .method-desc { font-size: 0.85rem; line-height: 1.5; color: #8b949e; }
    </style>
    """, unsafe_allow_html=True)

class AlphaEngine:
    def get_px(self, ticker, days=400):
        try:
            df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False, auto_adjust=True)
            if df.empty: return pd.Series()
            return df['Close'].iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else df['Close']
        except: return pd.Series()

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
        except: return 5, 0, False

    def run(self):
        # 1. Yield Curve
        y_s, y_v, y_w = self.get_yc()
        # 2. Trend
        spy = self.get_px('SPY', 350); ma200 = spy.rolling(200).mean(); s_px = float(spy.iloc[-1])
        s_trend = 10 if s_px > float(ma200.iloc[-1]) else 1
        # 3. Breadth
        sectors = ['XLY','XLP','XLE','XLF','XLV','XLI','XLB','XLK','XLU','XLC','XLRE']
        above = 0
        for s in sectors:
            p = self.get_px(s, 250)
            if not p.empty and p.iloc[-1] > p.rolling(200).mean().iloc[-1]: above += 1
        s_breadth = 10 if above <= 2 else (3 if above >= 9 else 7)
        # 4. VIX
        v = self.get_px('^VIX', 50); v_ma = v.rolling(20).mean(); v_std = v.rolling(20).std()
        v_n = float(v.iloc[-1]); v_p = float(v.iloc[-2]); v_u = v_ma + (2 * v_std)
        s_vix = 10 if v_p > float(v_u.iloc[-2]) and v_n < float(v_u.iloc[-1]) else (2 if v_n < 13 else 6)
        # 5. DeMark
        dm = (spy > spy.shift(4)).astype(int); last = dm.iloc[-1]; c = 0
        for val in reversed(dm.tolist()):
            if val == last: c += 1
            else: break
        s_dm = 10 if (c >= 8 and last == 0) else (1 if (c >= 8 and last == 1) else 5)

        avg = (y_s + s_trend + s_breadth + s_vix + s_dm) / 5
        alloc = 100 if avg >= 8.5 else (75 if avg >= 7 else (50 if avg >= 5.5 else (20 if avg >= 4 else 0)))
        return {"yc_s": y_s, "tr_s": s_trend, "br_s": s_breadth, "vx_s": s_vix, "dm_s": s_dm, 
                "avg": avg, "alloc": alloc, "spy": s_px, "yc_v": y_v, "yc_w": y_w, "br_c": above}

def main():
    e = AlphaEngine()
    with st.spinner('SYSTEM INITIALIZING...'):
        d = e.run()

    st.markdown(f"<p class='data-font' style='color:#58a6ff; font-size:0.7rem;'>TERMINAL ACCESS // {datetime.now().strftime('%H:%M:%S')} UTC</p>", unsafe_allow_html=True)

    # --- TOP GRID: ALLOCATION ---
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.markdown(f"""<div class="grid-cell" style="border-left: 4px solid #58a6ff;"><p class="label">Capital Allocation</p><div class="metric-value">{d['alloc']}%</div><p class="data-font" style="font-size:0.8rem; margin-top:15px; color:#8b949e;">MODE: {'AGGRESSIVE' if d['alloc'] >= 75 else 'DEFENSIVE' if d['alloc'] <= 25 else 'NEUTRAL'}</p></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="grid-cell">', unsafe_allow_html=True)
        fig = go.Figure(go.Indicator(mode="gauge+number", value=d['avg'], gauge={'axis':{'range':[1,10]}, 'bar':{'color':"#58a6ff"}, 'bgcolor':"#0d1117"}))
        fig.update_layout(height=180, margin=dict(l=10,r=10,t=10,b=10), paper_bgcolor='rgba(0,0,0,0)', font={'color':"#8b949e", 'family':"Roboto Mono"})
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- MIDDLE GRID: METRICS ---
    st.markdown("<br>", unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f"""<div class="grid-cell"><p class="label">Recession Watch</p><h2 class="data-font">{d['yc_v']:.2f}%</h2><p style="font-size:0.7rem; color:{'#f85149' if d['yc_w'] else '#8b949e'}">{'[!] RE-STEEPENING TRAP' if d['yc_w'] and d['yc_v']>0 else 'SPREAD STABLE'}</p></div>""", unsafe_allow_html=True)
    with m2:
        st.markdown(f"""<div class="grid-cell"><p class="label">Global Trend</p><h2 class="data-font">${d['spy']:.2f}</h2><p style="font-size:0.7rem; color:#8b949e">{'BULLISH BIAS (Above 200MA)' if d['tr_s']==10 else 'BEARISH BIAS'}</p></div>""", unsafe_allow_html=True)
    with m3:
        st.markdown(f"""<div class="grid-cell"><p class="label">Sector Breadth</p><h2 class="data-font">{d['br_c']}/11</h2><p style="font-size:0.7rem; color:#8b949e">Sectors above 200MA</p></div>""", unsafe_allow_html=True)

    # --- BOTTOM GRID: TACTICAL ---
    st.markdown("<br>", unsafe_allow_html=True)
    t1, t2 = st.columns(2)
    with t1:
        st.markdown(f"""<div class="grid-cell"><p class="label">Volatility Score</p><h2 class="data-font">{d['vx_s']}/10</h2><p style="font-size:0.7rem; color:#8b949e">VIX Band-Snap Logic</p></div>""", unsafe_allow_html=True)
    with t2:
        st.markdown(f"""<div class="grid-cell"><p class="label">Sequential Exhaustion</p><h2 class="data-font">{d['dm_s']}/10</h2><p style="font-size:0.7rem; color:#8b949e">DeMark 9-Count Filter</p></div>""", unsafe_allow_html=True)

    # --- METHODOLOGY LEDGER ---
    st.markdown('<div class="methodology-box">', unsafe_allow_html=True)
    st.markdown('<p class="label" style="color:#58a6ff; font-size:0.9rem;">Intelligence Ledger & Methodology</p>', unsafe_allow_html=True)
    
    methods =
