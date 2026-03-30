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
    # =========================
# GLOSSARY
# =========================
with st.expander("📖 Glossary (Klik untuk lihat penjelasan)"):
    st.write("""
    **RSI** : Indikator overbought / oversold  
    - RSI < 30 → Oversold (potensi naik)  
    - RSI > 70 → Overbought (potensi turun)

    **SMA20 / SMA50** : Moving average untuk melihat trend
    - Harga di atas SMA → Trend naik
    - Harga di bawah SMA → Trend turun

    **MACD** : Momentum trend
    - MACD cross up → bullish
    - MACD cross down → bearish

    **Volume Spike** : Lonjakan volume menandakan minat besar

    **Support** : Area harga bawah tempat harga sering memantul

    **Resistance** : Area harga atas tempat harga sering ditolak

    **Breakout** : Harga menembus resistance → sinyal bullish

    **AI Score** :
    - 0-2 → Bearish
    - 3 → Netral
    - 4-5 → Bullish
    """)

# =========================
# DISCLAIMER
# =========================
st.markdown("---")
st.caption("""
⚠️ DISCLAIMER:
Dashboard ini hanya untuk edukasi dan analisis teknikal otomatis.
Bukan merupakan rekomendasi beli atau jual saham.
Keputusan investasi sepenuhnya tanggung jawab masing-masing.
Gunakan risk management dan lakukan riset tambahan.
""")
# =========================
# RISK METER
# =========================
st.subheader("🎯 Risk Meter")

volatility = data['Close'].pct_change().std() * 100

if volatility < 1.5:
    risk = "LOW"
    st.success(f"Risk Level : {risk}")
elif volatility < 3:
    risk = "MEDIUM"
    st.warning(f"Risk Level : {risk}")
else:
    risk = "HIGH"
    st.error(f"Risk Level : {risk}")

# =========================
# PROBABILITY ENGINE
# =========================
st.subheader("📊 Probability Engine")

bull = 0
bear = 0

if data['RSI'].iloc[-1] < 35:
    bull += 1
else:
    bear += 1

if data['Close'].iloc[-1] > data['SMA20'].iloc[-1]:
    bull += 1
else:
    bear += 1

if data['MACD'].iloc[-1] > data['MACD_signal'].iloc[-1]:
    bull += 1
else:
    bear += 1

total = bull + bear
bull_prob = (bull / total) * 100
bear_prob = (bear / total) * 100

st.write(f"📈 Bullish Probability : {bull_prob:.1f}%")
st.write(f"📉 Bearish Probability : {bear_prob:.1f}%")

# =========================
# MOMENTUM DETECTOR
# =========================
st.subheader("🔥 Momentum Detector")

momentum = data['Close'].pct_change(5).iloc[-1] * 100

if momentum > 5:
    st.success("Strong Up Momentum")
elif momentum > 2:
    st.info("Moderate Up Momentum")
elif momentum < -5:
    st.error("Strong Down Momentum")
else:
    st.warning("Sideways")

# =========================
# VOLUME SPIKE ALERT
# =========================
st.subheader("🚨 Volume Alert")

if data['Volume'].iloc[-1] > data['Volume_MA'].iloc[-1] * 1.8:
    st.success("Volume Spike Detected")
else:
    st.write("Normal Volume")

# =========================
# TREND STRENGTH
# =========================
st.subheader("📈 Trend Strength")

trend_strength = abs(data['SMA20'].iloc[-1] - data['SMA50'].iloc[-1])

if trend_strength > data['Close'].iloc[-1] * 0.05:
    st.success("Strong Trend")
elif trend_strength > data['Close'].iloc[-1] * 0.02:
    st.info("Moderate Trend")
else:
    st.warning("Weak Trend")

# =========================
# AI FINAL DECISION PRO
# =========================
st.header("🧠 AI FINAL PRO")

final_score = 0

if bull_prob > 60:
    final_score += 1
if risk == "LOW":
    final_score += 1
if momentum > 2:
    final_score += 1
if data['Volume'].iloc[-1] > data['Volume_MA'].iloc[-1]:
    final_score += 1

if final_score >= 3:
    st.success("🚀 STRONG ACCUMULATE")
elif final_score == 2:
    st.warning("🟡 SPEC BUY")
else:
    st.error("🔻 WAIT / AVOID")
# =========================
# GOD MODE ENGINE (FIX)
# =========================
st.header("🚀 GOD MODE TRADING ENGINE")

price = data['Close'].iloc[-1]
support = data['support'].iloc[-1]
resistance = data['resistance'].iloc[-1]

# =========================
# SMART ENTRY
# =========================
st.subheader("🎯 Smart Entry")
entry = (support + price) / 2
st.write(f"Suggested Entry : {entry:.2f}")

# =========================
# STOPLOSS
# =========================
st.subheader("🛑 Stoploss")
stoploss = support * 0.97
st.write(f"Stoploss : {stoploss:.2f}")

# =========================
# TARGET PROFIT
# =========================
st.subheader("💰 Target Profit")
target1 = resistance
target2 = resistance * 1.05
st.write(f"Target 1 : {target1:.2f}")
st.write(f"Target 2 : {target2:.2f}")

# =========================
# RISK REWARD
# =========================
st.subheader("⚖️ Risk Reward")

risk = entry - stoploss
reward = target1 - entry

rr = 0  # <-- FIX penting

if risk > 0:
    rr = reward / risk
    st.write(f"Risk Reward Ratio : 1 : {rr:.2f}")

    if rr > 2:
        st.success("Good Trade Setup")
    elif rr > 1:
        st.warning("Moderate Setup")
    else:
        st.error("Bad Setup")
else:
    st.warning("Risk tidak valid")

# =========================
# TREND SCORE
# =========================
st.subheader("📈 Trend Score")

trend_score = 0
if price > data['SMA20'].iloc[-1]:
    trend_score += 1
if data['SMA20'].iloc[-1] > data['SMA50'].iloc[-1]:
    trend_score += 1
if data['RSI'].iloc[-1] > 50:
    trend_score += 1

st.write(f"Trend Score : {trend_score}/3")

# =========================
# BREAKOUT STRENGTH
# =========================
st.subheader("🔥 Breakout Strength")

if price > resistance:
    strength = (price - resistance) / resistance * 100
    st.success(f"Breakout Strength : {strength:.2f}%")
else:
    st.write("No Breakout")

# =========================
# FINAL GOD SIGNAL
# =========================
st.header("🧠 FINAL GOD SIGNAL")

god_score = 0

if rr > 2:
    god_score += 1
if trend_score >= 2:
    god_score += 1
if data['RSI'].iloc[-1] < 70:
    god_score += 1
if price > data['SMA20'].iloc[-1]:
    god_score += 1

if god_score >= 3:
    st.success("🚀 GOD MODE BUY")
elif god_score == 2:
    st.warning("⚡ SPEC BUY")
else:
    st.error("❌ NO TRADE")
