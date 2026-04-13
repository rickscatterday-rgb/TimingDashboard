import os
import yfinance as yf
import pandas as pd
import streamlit as st
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# =============================================================================
# 1. SETUP & RECIPIENTS
# =============================================================================
# Edit these to your actual addresses
RECIPIENTS = ["your_email@gmail.com"] 

# =============================================================================
# 2. THE LOGIC (Bulletproofed for 2024/2025 Data Formats)
# =============================================================================
class RegimeBasedDashboard:
    def fetch_price_data(self, ticker, days=300):
        """Fetches data and ensures it returns a clean, single-column Series."""
        try:
            df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False, auto_adjust=True)
            if df.empty:
                return None
            # Handle the new yfinance MultiIndex (e.g., ('Close', 'SPY'))
            if isinstance(df.columns, pd.MultiIndex):
                # Just get the 'Close' column for the first ticker found
                data = df['Close'].iloc[:, 0]
            else:
                data = df['Close']
            return data.dropna()
        except Exception:
            return None

    def get_fred_yc(self):
        """Fetches Yield Curve data from FRED."""
        try:
            url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y"
            df = pd.read_csv(url)
            df.columns = ['date', 'value']
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            return df.dropna()
        except: return None

    def check_regime(self):
        # Dial 1: Yield Curve
        yc_df = self.get_fred_yc()
        if yc_df is None or yc_df.empty:
            return {"regime": "ERROR", "yc_val": 0, "yc_safe": False, "credit_safe": False}
        
        current_yc = float(yc_df.iloc[-1]['value'])
        was_negative = (yc_df.tail(252)['value'] < 0).any()
        yc_safe = not (current_yc > 0 and was_negative)

        # Dial 2: Credit (HYG/IEF)
        hyg = self.fetch_price_data('HYG', days=150)
        ief = self.fetch_price_data('IEF', days=150)
        
        if hyg is None or ief is None:
            return {"regime": "ERROR", "yc_val": current_yc, "yc_safe": yc_safe, "credit_safe": False}

        ratio = hyg / ief
        ma50 = ratio.rolling(50).mean()
        
        # We use float() on everything to prevent "Ambiguous Truth" errors
        current_ratio = float(ratio.iloc[-1])
        current_ma50 = float(ma50.iloc[-1])
        credit_safe = current_ratio > current_ma50

        regime = "OFFENSIVE" if (yc_safe and credit_safe) else "DEFENSIVE"
        return {
            "regime": regime, 
            "yc_val": current_yc, 
            "yc_safe": yc_safe, 
            "credit_safe": credit_safe
        }

    def get_signals(self):
        # VIX Snap-back logic
        vix = self.fetch_price_data('^VIX', days=50)
        if vix is None or len(vix) < 21:
            return {"vix_buy": False, "trend_up": False, "spy_price": 0}

        ma = vix.rolling(20).mean()
        std = vix.rolling(20).std()
        upper = ma + (2 * std)
        
        # Force comparison of pure numbers (scalars)
        vix_prev = float(vix.iloc[-2])
        vix_now = float(vix.iloc[-1])
        up_prev = float(upper.iloc[-2])
        up_now = float(upper.iloc[-1])
        
        vix_buy = (vix_prev > up_prev) and (vix_now < up_now)
        
        # Trend
        spy = self.fetch_price_data('SPY', days=300)
        if spy is None:
            return {"vix_buy": vix_buy, "trend_up": False, "spy_price": 0}

        ma200 = spy.rolling(200).mean()
        trend_up = float(spy.iloc[-1]) > float(ma200.iloc[-1])

        return {"vix_buy": vix_buy, "trend_up": trend_up, "spy_price": float(spy.iloc[-1])}

# =============================================================================
# 3. INTERFACE & ALERTING
# =============================================================================
def send_alerts(message_body):
    sender = os.environ.get("EMAIL_ADDRESS")
    password = os.environ.get("EMAIL_PASSWORD") 
    if not sender or not password: return

    msg = MIMEText(message_body)
    msg['Subject'] = "📊 Market Signal Alert"
    msg['From'] = sender
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.sendmail(sender, RECIPIENTS, msg.as_string())
    except: pass

def run_dashboard():
    st.set_page_config(page_title="Market Timing", page_icon="🛡️")
    st.title("🛡️ Market Timing Dashboard")
    
    engine = RegimeBasedDashboard()
    
    with st.spinner('Calculating Market Regime...'):
        reg = engine.check_regime()
        sig = engine.get_signals()

    if reg['regime'] == "ERROR":
        st.error("Error fetching market data. Please refresh.")
        return

    # Visual Display
    c1, c2 = st.columns(2)
    if reg['regime'] == "OFFENSIVE":
        c1.success(f"### REGIME: {reg['regime']} 🟢")
    else:
        c1.error(f"### REGIME: {reg['regime']} 🔴")

    c2.metric("Yiel
