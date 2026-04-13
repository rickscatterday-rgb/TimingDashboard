import os
import yfinance as yf
import pandas as pd
import streamlit as st
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# =============================================================================
# 1. SETUP
# =============================================================================
RECIPIENTS = ["your_email@gmail.com"] 

# =============================================================================
# 2. THE ENGINE
# =============================================================================
class RegimeEngine:
    def get_price(self, ticker, days=300):
        try:
            # Download data
            df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False, auto_adjust=True)
            if df.empty:
                return pd.Series()
            
            # This line handles the "MultiIndex" error that causes most crashes
            if isinstance(df.columns, pd.MultiIndex):
                close_data = df['Close'].iloc[:, 0]
            else:
                close_data = df['Close']
            
            return close_data.dropna()
        except:
            return pd.Series()

    def get_yc(self):
        try:
            url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y"
            df = pd.read_csv(url)
            df.columns = ['date', 'value']
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            return df.dropna()
        except:
            return pd.DataFrame()

    def run_analysis(self):
        # 1. Yield Curve Logic
        yc_df = self.get_yc()
        if yc_df.empty:
            return None
        
        curr_yc = float(yc_df.iloc[-1]['value'])
        was_neg = (yc_df.tail(252)['value'] < 0).any()
        yc_safe = not (curr_yc > 0 and was_neg)

        # 2. Credit Logic (HYG vs IEF)
        hyg = self.get_price('HYG', 150)
        ief = self.get_price('IEF', 150)
        
        if hyg.empty or ief.empty:
            return None

        ratio = hyg / ief
        ma50 = ratio.rolling(50).mean()
        credit_safe = float(ratio.iloc[-1]) > float(ma50.iloc[-1])

        # 3. Timing Triggers (VIX)
        vix = self.get_price('^VIX', 50)
        vix_buy = False
        if not vix.empty and len(vix) > 21:
            v_ma = vix.rolling(20).mean()
            v_std = vix.rolling(20).std()
            upper = v_ma + (2 * v_std)
            vix_buy = (float(vix.iloc[-2]) > float(upper.iloc[-2])) and (float(vix.iloc[-1]) < float(upper.iloc[-1]))

        # 4. Trend Logic
        spy = self.get_price('SPY', 300)
        spy_price = float(spy.iloc[-1]) if not spy.empty else 0
        spy_ma = spy.rolling(200).mean()
        trend_up = spy_price > float(spy_ma.iloc[-1]) if not spy.empty else False

        regime = "OFFENSIVE" if (yc_safe and credit_safe) else "DEFENSIVE"
        
        return {
            "regime": regime,
            "yc_val": curr_yc,
            "yc_safe": yc_safe,
            "credit_safe": credit_safe,
            "vix_buy": vix_buy,
            "trend_up": trend_up,
            "spy_price": spy_price
        }

# =============================================================================
# 3. DASHBOARD & ALERTS
# =============================================================================
def send_email(text):
    sender = os.environ.get("EMAIL_ADDRESS")
    pwd = os.environ.get("EMAIL_PASSWORD")
    if not sender or not pwd: return
    try:
        msg = MIMEText(text)
        msg['Subject'] = "Market Timing Alert"
        msg['From'] = sender
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, pwd)
            server.sendmail(sender, RECIPIENTS, msg.as_string())
    except: pass

def main():
    # If running in a browser (Streamlit)
    if st.runtime.exists():
        st.set_page_config(page_title="Market Timer")
        st.title("🛡️ Market Timing Dashboard")
        
        engine = RegimeEngine()
        data = engine.run_analysis()
        
        if data:
            c1, c2 = st.columns(2)
            if data['regime'] == "OFFENSIVE":
                c1.success(f"### REGIME: {data['regime']} 🟢")
            else:
                c1.error(f"### REGIME: {data['regime']} 🔴")
            
            c2.metric("Yield Curve", f"{data['yc_val']:.2f}%")
            
            st.divider()
            st.write(f"**VIX Signal:** {'✅ BUY' if data['vix_buy'] else '⚪ None'}")
            st.write(f"**Long-Term Trend:** {'📈 Bullish' if data['trend_up'] else '📉 Bearish'}")
            st.info(f"Price: SPY ${data['spy_price']:.2f}")
        else:
            st.error("Data currently unavailable. Please refresh in a moment.")

    # If running as an automated background alert
    else:
        engine = RegimeEngine()
        data = engine.run_analysis()
        if data and data['regime'] == "OFFENSIVE" and data['vix_buy']:
            send_email(f"BUY SIGNAL: Regime Offensive / VIX Snapback. SPY: ${data['spy_price']:.2f}")

if __name__ == "__main__":
    main()
