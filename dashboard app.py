import os
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# --- SET PAGE CONFIG ---
st.set_page_config(page_title="Investment Allocation Console", layout="wide")

# --- CUSTOM CSS FOR PROFESSIONAL LOOK ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }
    .main { background-color: #f8f9fa; }
    .metric-card {
        background-color: white; padding: 20px; border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eef2f6;
    }
    .allocation-box {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        color: white; padding: 30px; border-radius: 15px; text-align: center;
        box-shadow: 0 10px 15px rgba(59, 130, 246, 0.2);
    }
    .status-tag {
        padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 0.8rem;
    }
    </style>
    """, unsafe_allow_html=True)

# --- DATA ENGINE ---
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
        # 1. Yield Curve
        yc = self.get_yc()
        curr_yc = float(yc.iloc[-1]['value'])
        was_neg = (yc.tail(252)['value'] < 0).any()
        scores['Yield Curve'] = 1 if (curr_yc > 0 and was_neg) else (5 if curr_yc < 0 else 10)
        
        # 2. Credit (HYG/IEF)
        hyg = self.get_px('HYG', 150); ief = self.get_px('IEF', 150)
        ratio = hyg / ief; ma50 = ratio.rolling(50).mean()
        scores['Credit Market'] = 10 if float(ratio.iloc[-1]) > float(ma50.iloc[-1]) else 1
        
        # 3. Trend (SPY 200MA)
        spy = self.get_px('SPY', 350); ma200 = spy.rolling(200).mean()
        scores['Market Trend'] = 10 if float(spy.iloc[-1]) > float(ma200.iloc[-1]) else 1

        # 4. VIX Snapback (Extreme Pullback Indicator)
        vix = self.get_px('^VIX', 50); ma20 = vix.rolling(20).mean(); std20 = vix.rolling(20).std()
        upper = ma20 + (2 * std20); lower = ma20 - (2 * std20)
        vix_val = float(vix.iloc[-1])
        if (float(vix.iloc[-2]) > float(upper.iloc[-2])) and (vix_val < float(upper.iloc[-2])): scores['Volatility'] = 10
        elif vix_val < float(lower.iloc[-1]): scores['Volatility'] = 2 # Overbought/Complacent
        else: scores['Volatility'] = 6

        # 5. Breadth (Sample of Leaders)
        leaders = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'JPM']
        above = 0
        for t in leaders:
            p = self.get_px(t, 60)
            if not p.empty and p.iloc[-1] > p.rolling(50).mean().iloc[-1]: above += 1
        b_score = (above / len(leaders)) * 10
        if b_score <= 2: scores['Breadth'] = 10 # Washout = Buy
        elif b_score >= 8: scores['Breadth'] = 2 # Overbought = Sell
        else: scores['Breadth'] = 7

        # 6. DeMark 9-Count
        counts = (spy > spy.shift(4)).astype(int); last_v = counts.iloc[-1]; c = 0
        for val in reversed(counts.tolist()):
            if val == last_v: c += 1
            else: break
        if c >= 8 and last_v == 0: scores['Exhaustion'] = 10 # Downside exhaustion
        elif c >= 8 and last_v == 1: scores['Exhaustion'] = 1 # Upside exhaustion
        else: scores['Exhaustion'] = 5

        total_score = sum(scores.values()) / len(scores)
        
        # ALLOCATION MATH
        if total_score >= 8.5: allocation = 100
        elif total_score >= 7: allocation = 80
        elif total_score >= 5.5: allocation = 60
        elif total_score >= 4.5: allocation = 40
        else: allocation = 15

        return scores, total_score, allocation, float(spy.iloc[-1])

# --- DASHBOARD UI ---
def main():
    engine = ProEngine()
    scores, avg_score, alloc, spy_px = engine.calculate_all()

    # --- HEADER ---
    st.write(f"### 🛡️ Institutional Allocation Dashboard")
    st.write(f"Snapshot: {datetime.now().strftime('%B %d, %Y')} | SPY: ${spy_px:.2f}")
    
    # --- TOP ROW: ALLOCATION BOX ---
    st.divider()
    col_a, col_b = st.columns([1.2, 2])
    
    with col_a:
        st.markdown(f"""
            <div class="allocation-box">
                <p style="font-size: 1rem; opacity: 0.9; margin-bottom:0;">Recommended Invested Capital</p>
                <h1 style="font-size: 4.5rem; margin: 0;">{alloc}%</h1>
                <p style="font-size: 1.2rem; font-weight: 600;">{
                    'AGGRESSIVE BUY' if alloc >= 80 else 'CORE HOLD' if alloc >= 60 else 'LIGHTEN EXPOSURE' if alloc >= 40 else 'CAPITAL PRESERVATION'
                }</p>
            </div>
        """, unsafe_allow_html=True)

    with col_b:
        # Create a Gauge Chart
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = avg_score,
            title = {'text': "Market Score (1-10)"},
            gauge = {
                'axis': {'range': [1, 10]},
                'bar': {'color': "#1e3a8a"},
                'steps': [
                    {'range': [1, 4.5], 'color': "#ffcfcf"},
                    {'range': [4.5, 7], 'color': "#fff4cf"},
                    {'range': [7, 10], 'color': "#cfffdf"}
                ],
            }
        ))
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # --- GRID OF INDICATORS ---
    st.write("### Internal Dial Health")
    rows = [st.columns(3), st.columns(3)]
    items = list(scores.items())
    
    for i, (name, val) in enumerate(items):
        with rows[i // 3][i % 3]:
            # Determine color tag
            tag_color = "#dcfce7" if val >= 7 else "#fef3c7" if val >= 4.5 else "#fee2e2"
            text_color = "#166534" if val >= 7 else "#92400e" if val >= 4.5 else "#991b1b"
            status_text = "BULLISH" if val >= 7 else "NEUTRAL" if val >= 4.5 else "BEARISH"
            
            st.markdown(f"""
                <div class="metric-card">
                    <p style="color: #64748b; font-weight: 600; font-size: 0.9rem; margin-bottom: 8px;">{name.upper()}</p>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 1.8rem; font-weight: 800;">{val}/10</span>
                        <span class="status-tag" style="background-color: {tag_color}; color: {text_color};">{status_text}</span>
                    </div>
                    <div style="height: 6px; width: 100%; background-color: #f1f5f9; border-radius: 10px; margin-top: 15px;">
                        <div style="height: 6px; width: {val*10}%; background-color: {text_color}; border-radius: 10px;"></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

    st.write("")
    st.caption("Logic: High Score = Safety/Opportunity (Buy). Low Score = Risk/Overbought (Sell).")

if __name__ == "__main__":
    main()
