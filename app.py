import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import numpy as np

st.set_page_config(layout="wide")
st.title("🚀 SMART MARKET DASHBOARD — ALL IN ONE FINAL")

# =========================
# INPUT
# =========================
col1, col2 = st.columns(2)
ticker = col1.text_input("Ticker", "BBRI.JK")
timeframe = col2.selectbox("Timeframe", ["1d","1wk","1mo"])

# =========================
# LOAD DATA
# =========================
@st.cache_data
def load_data(ticker, timeframe):
    df = yf.download(ticker, period="1y", interval=timeframe, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

data = load_data(ticker, timeframe)

if data.empty:
    st.warning("No data")
    st.stop()

close = data['Close']

# =========================
# INDICATORS
# =========================
data['SMA20'] = ta.trend.sma_indicator(close, window=20)
data['SMA50'] = ta.trend.sma_indicator(close, window=50)
data['RSI'] = ta.momentum.rsi(close)

macd = ta.trend.MACD(close)
data['MACD'] = macd.macd()
data['MACD_signal'] = macd.macd_signal()

data['Volume_MA'] = data['Volume'].rolling(20).mean()

# =========================
# SUPPORT RESISTANCE
# =========================
data['support'] = data['Low'].rolling(20).min()
data['resistance'] = data['High'].rolling(20).max()

# =========================
# CHART
# =========================
fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=data.index,
    open=data['Open'],
    high=data['High'],
    low=data['Low'],
    close=data['Close'],
    name="Price"
))

fig.add_trace(go.Scatter(x=data.index,y=data['SMA20'],name="SMA20"))
fig.add_trace(go.Scatter(x=data.index,y=data['SMA50'],name="SMA50"))
fig.add_trace(go.Scatter(x=data.index,y=data['support'],name="Support"))
fig.add_trace(go.Scatter(x=data.index,y=data['resistance'],name="Resistance"))

st.plotly_chart(fig, use_container_width=True)

# =========================
# VOLUME
# =========================
st.subheader("Volume")
st.bar_chart(data['Volume'])

# =========================
# RSI + MACD
# =========================
col1, col2 = st.columns(2)

with col1:
    st.subheader("RSI")
    st.line_chart(data['RSI'])

with col2:
    st.subheader("MACD")
    st.line_chart(data[['MACD','MACD_signal']])

# =========================
# AI SCORE ENGINE
# =========================
score = 0

if data['RSI'].iloc[-1] < 35:
    score += 1
if data['Close'].iloc[-1] > data['SMA20'].iloc[-1]:
    score += 1
if data['SMA20'].iloc[-1] > data['SMA50'].iloc[-1]:
    score += 1
if data['MACD'].iloc[-1] > data['MACD_signal'].iloc[-1]:
    score += 1
if data['Volume'].iloc[-1] > data['Volume_MA'].iloc[-1]:
    score += 1

st.subheader("🤖 AI Score")
st.metric("Score", f"{score}/5")

# =========================
# SIGNAL
# =========================
if score >= 4:
    st.success("🚀 STRONG BUY")
elif score == 3:
    st.info("🟡 HOLD")
else:
    st.error("🔻 SELL")

# =========================
# BREAKOUT DETECTOR
# =========================
if data['Close'].iloc[-1] > data['resistance'].iloc[-2]:
    st.success("🔥 BREAKOUT DETECTED")

# =========================
# SCANNER IHSG
# =========================
st.subheader("🔥 TOP MARKET SCANNER")

ihsg_list = [
"BBRI.JK","BBCA.JK","BMRI.JK","TLKM.JK","ASII.JK",
"ADRO.JK","ANTM.JK","MDKA.JK","UNTR.JK","ICBP.JK",
"INDF.JK","UNVR.JK","SMGR.JK","CPIN.JK","JPFA.JK"
]

@st.cache_data
def scan_market():
    data = yf.download(
        ihsg_list,
        period="3mo",
        interval="1d",
        group_by="ticker",
        progress=False
    )

    rows = []

    for t in ihsg_list:
        try:
            d = data[t]
            rsi = ta.momentum.rsi(d['Close']).iloc[-1]
            sma20 = d['Close'].rolling(20).mean().iloc[-1]

            score = 0
            if rsi < 35: score += 1
            if d['Close'].iloc[-1] > sma20: score += 1

            rows.append([t, round(rsi,2), score])
        except:
            pass

    return pd.DataFrame(rows, columns=["Ticker","RSI","Score"])

scan_df = scan_market()

if not scan_df.empty:
    st.dataframe(scan_df.sort_values("Score", ascending=False))
else:
    st.warning("Scanner loading...")

# =========================
# TOP BUY
# =========================
st.subheader("🚀 TOP BUY")

top_buy = scan_df.sort_values("Score", ascending=False).head(5)
st.table(top_buy)

# =========================
# MARKET MOMENTUM
# =========================
st.subheader("📈 Market Momentum")

gain = (data['Close'].pct_change().tail(20) > 0).sum()
loss = (data['Close'].pct_change().tail(20) < 0).sum()

st.write("Up Days:", gain)
st.write("Down Days:", loss)

# =========================
# FINAL LABEL
# =========================
st.header("FINAL DECISION")

if score >= 4:
    st.success("🟢 ACCUMULATE")
elif score == 3:
    st.warning("🟡 WAIT")
else:
    st.error("🔴 AVOID")
