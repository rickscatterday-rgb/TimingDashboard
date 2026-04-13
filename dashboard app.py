import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- SET PAGE CONFIG ---
st.set_page_config(page_title="Investment Allocation Console", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }
    .main { background-color: #f8f9fa; }
    .metric-card {
        background-color: white; padding: 20px; border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eef2f6;
        min-height: 180px;
    }
    .allocation-box {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        color: white; padding: 30px; border-radius: 15px; text-align: center;
        box-shadow: 0 10px 15px rgba(59, 130, 246, 0.2);
    }
    .status-tag { padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 0.75rem; }
    .logic-text { color: #64748b; font-size: 0.8rem; margin-top: 10px; line-height: 1.3; }
    </style>
    """, unsafe_allow_html=True)

class ProEngine:
    def get_px(self, ticker, days=365):
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
            return df.dropna()
        except: return pd.DataFrame()

    def calculate_all(self):
        scores = {}
        logic = {}

        # 1. Yield Curve
        yc = self.get_yc()
        curr_yc = float(yc.iloc[-1]['value'])
        was_neg = (yc.tail(252)['value'] < 0).any()
        if curr_yc > 0 and was_neg: 
            scores['Yield Curve'] = 1
            logic['Yield Curve'] = "The 'Trap': Curve re-steepened after inversion. Historical signal for recession onset."
        elif curr_yc < 0: 
            scores['Yield Curve'] = 5
            logic['Yield Curve'] = "Currently inverted. Market is pricing in future economic slowing."
        else: 
            scores['Yield Curve'] = 10
            logic['Yield Curve'] = "Normal positive curve. Healthy economic expansion environment."
        
        # 2. Credit (HYG/IEF)
        hyg = self.get_px('HYG', 150); ief = self.get_px('IEF', 150)
        ratio = hyg / ief; ma50 = ratio.rolling(50).mean()
        is_safe = float(ratio.iloc[-1]) > float(ma50.iloc[-1])
        scores['Credit Market'] = 10 if is_safe else 1
        logic['Credit Market'] = "Measures Junk Bonds vs Safe Treasuries. Risk is ON when HYG outperforms IEF."
        
        # 3. Trend (SPY 200MA)
        spy = self.get_px('SPY', 350); ma200 = spy.rolling(200).mean()
        is_bullish = float(spy.iloc[-1]) > float(ma200.iloc[-1])
        scores['Market Trend'] = 10 if is_bullish else 1
        logic['Market Trend'] = "The 'Ultimate Filter'. Bullish if price is above the 200-Day Moving Average."

        # 4. VIX Snapback
        vix = self.get_px('^VIX', 50); ma20 = vix.rolling(20).mean(); std20 = vix.rolling(20).std()
        upper = ma20 + (2 * std20); lower = ma20 - (2 * std20)
        v_now = float(vix.iloc[-1]); v_prev = float(vix.iloc[-2])
        if (v_prev > float(upper.iloc[-2])) and (v_now < float(upper.iloc[-1])):
            scores['Volatility'] = 10
            logic['Volatility'] = "Panic Peak Detected: VIX is falling back inside its bands after a spike. Historical Buy signal."
        elif v_now < float(lower.iloc[-1]):
            scores['Volatility'] = 2
            logic['Volatility'] = "Extreme Complacency: VIX is at floor levels. Risk of a sudden spike is high."
        else:
            scores['Volatility'] = 6
            logic['Volatility'] = "VIX is stable within normal ranges."

        # 5. Breadth
        leaders = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'JPM']
        above = 0
        for t in leaders:
            p = self.get_px(t, 60)
            if not p.empty and p.iloc[-1] > p.rolling(50).mean().iloc[-1]: above += 1
        b_pct = (above / len(leaders)) * 10
        logic['Breadth'] = f"Percentage of leaders above 50-MA. Extreme low ({b_pct:.0f}) = Washout Buy. Extreme high = Overbought."
        if b_pct <= 2: scores['Breadth'] = 10
        elif b_pct >= 8: scores['Breadth'] = 2
        else: scores['Breadth'] = 7

        # 6. Exhaustion (DeMark)
        counts = (spy > spy.shift(4)).astype(int); last_v = counts.iloc[-1]; c = 0
        for val in reversed(counts.tolist()):
            if val == last_v: c += 1
            else: break
        logic['Exhaustion'] = f"Sequential closing trends. Currently on a Day {c} { 'Upside' if last_v == 1 else 'Downside' } count."
        if c >= 8 and last_v == 0: scores['Exhaustion'] = 10
        elif c >= 8 and last_v == 1: scores['Exhaustion'] = 1
        else: scores['Exhaustion'] = 5

        total_score = sum(scores.values()) / len(scores)
        if total_score >= 8.5: alloc = 100
        elif total_score >= 7: alloc = 80
        elif total_score >= 5.5: alloc = 60
        elif total_score >= 4.5: alloc = 40
        else: alloc = 15

        return scores, logic, total_score, alloc, float(spy.iloc[-1])

def main():
    engine = ProEngine()
    scores, logic, avg_score, alloc, spy_px = engine.calculate_all()

    st.write(f"### 🛡️ Institutional Allocation Dashboard")
    st.caption(f"Last Scan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Data: Yahoo Finance & St. Louis FRED")
    
    st.divider()
    col_a, col_b = st.columns([1.2, 2])
    
    with col_a:
        st.markdown(f"""
            <div class="allocation-box">
                <p style="font-size: 0.9rem; opacity: 0.8; margin-bottom:0;">RECOMENDED CAPITAL EXPOSURE</p>
                <h1 style="font-size: 4rem; margin: 10px 0;">{alloc}%</h1>
                <p style="font-size: 1rem; font-weight: 600; letter-spacing: 1px;">{
                    'AGGRESSIVE OPPORTUNITY' if alloc >= 80 else 'CORE OFFENSIVE' if alloc >= 60 else 'NEUTRAL / CAUTION' if alloc >= 40 else 'PROTECTIVE / DEFENSIVE'
                }</p>
            </div>
        """, unsafe_allow_html=True)
        st.info("💡 Start scaling out as the score drops below 5.0. Scale in aggressively on 'Volatility' or 'Exhaustion' 10s.")

    with col_b:
        fig = go.Figure(go.Indicator(
            mode = "gauge+number", value = avg_score,
            gauge = {
                'axis': {'range': [1, 10], 'tickwidth': 1},
                'bar': {'color': "#1e3a8a"},
                'steps': [
                    {'range': [1, 4.5], 'color': "#fee2e2"},
                    {'range': [4.5, 7], 'color': "#fef3c7"},
                    {'range': [7, 10], 'color': "#dcfce7"}
                ],
            }
        ))
        fig.update_layout(height=300, margin=dict(l=30, r=30, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.write("### Internal Logic & Rankings")
    rows = [st.columns(3), st.columns(3)]
    items = list(scores.items())
    
    for i, (name, val) in enumerate(items):
        with rows[i // 3][i % 3]:
            tag_color = "#dcfce7" if val >= 7 else "#fef3c7" if val >= 4.5 else "#fee2e2"
            text_color = "#166534" if val >= 7 else "#92400e" if val >= 4.5 else "#991b1b"
            
            st.markdown(f"""
                <div class="metric-card">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <p style="color: #64748b; font-weight: 700; font-size: 0.8rem;">{name.upper()}</p>
                        <span class="status-tag" style="background-color: {tag_color}; color: {text_color};">SCORE: {val}/10</span>
                    </div>
                    <p class="logic-text">{logic[name]}</p>
                    <div style="height: 4px; width: 100%; background-color: #f1f5f9; border-radius: 10px; margin-top: 15px;">
                        <div style="height: 4px; width: {val*10}%; background-color: {text_color}; border-radius: 10px;"></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

    with st.expander("📚 View Complete Methodology"):
        st.write("""
        - **Yield Curve:** We track the 10-Year minus 2-Year Treasury spread. The 'Trap' occurs when the curve moves from negative back to positive, which historically precedes recessions by 0-6 months.
        - **Credit Canary:** Uses the ratio of HYG (High Yield) to IEF (7-10yr Treasuries). If the ratio is above its 50-day average, bond traders are 'Risk-On'.
        - **VIX Snapback:** We look for the VIX to close above its 2-standard deviation upper Bollinger Band and then close back inside. This marks a peak in panic.
        - **Breadth:** We check Apple, Microsoft, Nvidia, Google, Amazon, Meta, Tesla, and JPM. If only 0-2 are above their 50-day average, the market is 'washed out'.
        - **DeMark Exhaustion:** Compares today's close to the close 4 days ago. 9 consecutive days of the same trend usually indicates a reversal is imminent.
        """)

if __name__ == "__main__":
    main()
