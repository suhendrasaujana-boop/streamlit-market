import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("🚀 Smart Market Dashboard ULTIMATE PRO")

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
    data = yf.download(ticker, period="1y", interval=timeframe, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

data = load_data(ticker, timeframe)

if data.empty:
    st.stop()

close = data['Close']

# =========================
# INDICATORS
# =========================
data['SMA20'] = ta.trend.sma_indicator(close, window=20)
data['SMA50'] = ta.trend.sma_indicator(close, window=50)
data['RSI'] = ta.momentum.rsi(close, window=14)

macd = ta.trend.MACD(close)
data['MACD'] = macd.macd()
data['MACD_signal'] = macd.macd_signal()

# =========================
# CHART
# =========================
fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=data.index,
    open=data['Open'],
    high=data['High'],
    low=data['Low'],
    close=data['Close']
))

fig.add_trace(go.Scatter(x=data.index, y=data['SMA20'], name="SMA20"))
fig.add_trace(go.Scatter(x=data.index, y=data['SMA50'], name="SMA50"))

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
# AI SCORE
# =========================
st.subheader("AI Score")

score = 0

if data['RSI'].iloc[-1] < 30:
    score += 1
if data['Close'].iloc[-1] > data['SMA20'].iloc[-1]:
    score += 1
if data['SMA20'].iloc[-1] > data['SMA50'].iloc[-1]:
    score += 1
if data['MACD'].iloc[-1] > data['MACD_signal'].iloc[-1]:
    score += 1

st.metric("Score", f"{score}/4")

# =========================
# SIGNAL
# =========================
if score >= 3:
    st.success("STRONG BUY 🚀")
elif score == 2:
    st.info("HOLD")
else:
    st.error("SELL ⚠️")

# =========================
# SCANNER IHSG BATCH
# =========================
st.subheader("🔥 Top RSI Scanner")

ihsg_list = [
"BBRI.JK","BBCA.JK","BMRI.JK","TLKM.JK","ASII.JK",
"UNVR.JK","ICBP.JK","INDF.JK","ADRO.JK","ANTM.JK"
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

    results = []

    for t in ihsg_list:
        try:
            d = data[t]
            rsi = ta.momentum.rsi(d['Close']).iloc[-1]

            score = 0
            if rsi < 30: score += 1
            if d['Close'].iloc[-1] > d['Close'].rolling(20).mean().iloc[-1]: score += 1

            results.append([t, round(rsi,2), score])
        except:
            pass

    return pd.DataFrame(results, columns=["Ticker","RSI","Score"])

scan_df = scan_market()

if not scan_df.empty:
    st.dataframe(scan_df.sort_values("Score", ascending=False))
else:
    st.warning("Scanner loading...")
