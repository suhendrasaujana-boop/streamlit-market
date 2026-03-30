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
ticker = col1.text_input("Ticker", "^JKSE")
timeframe = col2.selectbox("Timeframe", ["1d","1wk","1mo"])

# =========================
# LOAD DATA dengan handling NaN
# =========================
@st.cache_data
def load_data(ticker, timeframe):
    # Download data dengan periode lebih panjang untuk indikator
    df = yf.download(ticker, period="2y", interval=timeframe, progress=False)
    
    if df.empty:
        df = yf.download(ticker, period="1y", interval=timeframe, progress=False, auto_adjust=False)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Hapus baris yang semua nilainya NaN
    df = df.dropna(how='all')
    
    # Untuk indeks (^JKSE), Volume sering 0 atau kosong - isi dengan 0
    if 'Volume' in df.columns:
        df['Volume'] = df['Volume'].fillna(0)
    
    return df

data = load_data(ticker, timeframe)

if data.empty or len(data) < 20:
    st.warning(f"Data tidak mencukupi untuk {ticker}. Minimal 20 periode data.")
    st.stop()

close = data['Close']

# =========================
# INDICATORS dengan handling NaN
# =========================
# Pastikan data cukup untuk rolling window
min_periods = min(20, len(data))

data['SMA20'] = ta.trend.sma_indicator(close, window=min(20, len(data)-1))
data['SMA50'] = ta.trend.sma_indicator(close, window=min(50, len(data)-1))

# RSI butuh minimal 14 data
if len(data) >= 15:
    data['RSI'] = ta.momentum.rsi(close, window=14)
else:
    data['RSI'] = 50  # nilai default netral

# MACD
if len(data) >= 26:
    macd = ta.trend.MACD(close)
    data['MACD'] = macd.macd()
    data['MACD_signal'] = macd.macd_signal()
else:
    data['MACD'] = 0
    data['MACD_signal'] = 0

# Volume MA - jika volume selalu 0 (indeks), maka MA juga 0
if data['Volume'].sum() > 0:
    data['Volume_MA'] = data['Volume'].rolling(20, min_periods=1).mean()
else:
    data['Volume_MA'] = 0

# Support/Resistance
data['support'] = data['Low'].rolling(20, min_periods=1).min()
data['resistance'] = data['High'].rolling(20, min_periods=1).max()

# Isi semua NaN dengan nilai sebelumnya atau 0
data = data.fillna(method='ffill').fillna(0)

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
# VOLUME (hanya tampil jika ada volume > 0)
# =========================
st.subheader("Volume")
if data['Volume'].sum() > 0:
    st.bar_chart(data['Volume'])
else:
    st.info("Volume data tidak tersedia untuk indeks (IHSG)")

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
# AI SCORE ENGINE (dengan pengecekan NaN)
# =========================
score = 0

try:
    if pd.notna(data['RSI'].iloc[-1]) and data['RSI'].iloc[-1] < 35:
        score += 1
    if pd.notna(data['Close'].iloc[-1]) and pd.notna(data['SMA20'].iloc[-1]) and data['Close'].iloc[-1] > data['SMA20'].iloc[-1]:
        score += 1
    if pd.notna(data['SMA20'].iloc[-1]) and pd.notna(data['SMA50'].iloc[-1]) and data['SMA20'].iloc[-1] > data['SMA50'].iloc[-1]:
        score += 1
    if pd.notna(data['MACD'].iloc[-1]) and pd.notna(data['MACD_signal'].iloc[-1]) and data['MACD'].iloc[-1] > data['MACD_signal'].iloc[-1]:
        score += 1
    if pd.notna(data['Volume'].iloc[-1]) and pd.notna(data['Volume_MA'].iloc[-1]) and data['Volume'].iloc[-1] > data['Volume_MA'].iloc[-1]:
        score += 1
except:
    pass

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
if len(data) > 1:
    if data['Close'].iloc[-1] > data['resistance'].iloc[-2]:
        st.success("🔥 BREAKOUT DETECTED")

# =========================
# RISK METER
# =========================
st.subheader("🎯 Risk Meter")

returns = data['Close'].pct_change().dropna()
if len(returns) > 0:
    volatility = returns.std() * 100
else:
    volatility = 0

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
# SCANNER IHSG (dengan error handling)
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
        period="6mo",  # tambah periode biar cukup data
        interval="1d",
        group_by="ticker",
        progress=False
    )

    rows = []

    for t in ihsg_list:
        try:
            d = data[t]
            if len(d) > 30:
                # Hitung RSI manual untuk menghindari error
                close_series = d['Close'].dropna()
                if len(close_series) >= 14:
                    rsi = ta.momentum.rsi(close_series, window=14).iloc[-1]
                else:
                    rsi = 50
                
                sma20 = close_series.rolling(20).mean().iloc[-1]
                if pd.isna(sma20):
                    sma20 = close_series.iloc[-1]
                
                score = 0
                if pd.notna(rsi) and rsi < 35:
                    score += 1
                if close_series.iloc[-1] > sma20:
                    score += 1
                
                rows.append([t, round(rsi,2) if pd.notna(rsi) else 50, score])
        except Exception as e:
            continue

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

if not scan_df.empty:
    top_buy = scan_df.sort_values("Score", ascending=False).head(5)
    st.table(top_buy)
else:
    st.write("Tidak ada data")

# =========================
# MARKET MOMENTUM
# =========================
st.subheader("📈 Market Momentum")

returns_tail = data['Close'].pct_change().tail(20).dropna()
gain = (returns_tail > 0).sum()
loss = (returns_tail < 0).sum()

st.write("Up Days:", gain)
st.write("Down Days:", loss)

# =========================
# PROBABILITY ENGINE
# =========================
st.subheader("📊 Probability Engine")

bull = 0
bear = 0

if pd.notna(data['RSI'].iloc[-1]) and data['RSI'].iloc[-1] < 35:
    bull += 1
else:
    bear += 1

if pd.notna(data['Close'].iloc[-1]) and pd.notna(data['SMA20'].iloc[-1]) and data['Close'].iloc[-1] > data['SMA20'].iloc[-1]:
    bull += 1
else:
    bear += 1

if pd.notna(data['MACD'].iloc[-1]) and pd.notna(data['MACD_signal'].iloc[-1]) and data['MACD'].iloc[-1] > data['MACD_signal'].iloc[-1]:
    bull += 1
else:
    bear += 1

total = bull + bear
if total > 0:
    bull_prob = (bull / total) * 100
    bear_prob = (bear / total) * 100
else:
    bull_prob = bear_prob = 50

st.write(f"📈 Bullish Probability : {bull_prob:.1f}%")
st.write(f"📉 Bearish Probability : {bear_prob:.1f}%")

# =========================
# MOMENTUM DETECTOR
# =========================
st.subheader("🔥 Momentum Detector")

if len(data) >= 6:
    momentum = data['Close'].pct_change(5).iloc[-1] * 100
    if pd.isna(momentum):
        momentum = 0
else:
    momentum = 0

if momentum > 5:
    st.success("Strong Up Momentum")
elif momentum > 2:
    st.info("Moderate Up Momentum")
elif momentum < -5:
    st.error("Strong Down Momentum")
else:
    st.warning("Sideways")

# =========================
# VOLUME SPIKE ALERT (skip jika volume 0)
# =========================
st.subheader("🚨 Volume Alert")

if data['Volume'].sum() > 0:
    if data['Volume'].iloc[-1] > data['Volume_MA'].iloc[-1] * 1.8:
        st.success("Volume Spike Detected")
    else:
        st.write("Normal Volume")
else:
    st.info("Volume tidak tersedia untuk indeks")

# =========================
# TREND STRENGTH
# =========================
st.subheader("📈 Trend Strength")

if pd.notna(data['SMA20'].iloc[-1]) and pd.notna(data['SMA50'].iloc[-1]):
    trend_strength = abs(data['SMA20'].iloc[-1] - data['SMA50'].iloc[-1])
    price_ref = data['Close'].iloc[-1]
    if price_ref > 0:
        if trend_strength > price_ref * 0.05:
            st.success("Strong Trend")
        elif trend_strength > price_ref * 0.02:
            st.info("Moderate Trend")
        else:
            st.warning("Weak Trend")
    else:
        st.warning("Weak Trend")
else:
    st.warning("Data tidak cukup")

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
if data['Volume'].sum() > 0 and data['Volume'].iloc[-1] > data['Volume_MA'].iloc[-1]:
    final_score += 1

if final_score >= 3:
    st.success("🚀 STRONG ACCUMULATE")
elif final_score == 2:
    st.warning("🟡 SPEC BUY")
else:
    st.error("🔻 WAIT / AVOID")

# =========================
# GOD MODE ENGINE (skip jika support/resistance NaN)
# =========================
st.header("🚀 GOD MODE TRADING ENGINE")

price = data['Close'].iloc[-1]
support = data['support'].iloc[-1]
resistance = data['resistance'].iloc[-1]

if pd.isna(support):
    support = price * 0.95
if pd.isna(resistance):
    resistance = price * 1.05

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

risk_amount = entry - stoploss
reward = target1 - entry

rr = 0
if risk_amount > 0:
    rr = reward / risk_amount
    st.write(f"Risk Reward Ratio : 1 : {rr:.2f}")

    if rr > 2:
        st.success("Good Trade Setup")
    elif rr > 1:
        st.warning("Moderate Setup")
    else:
        st.error("Bad Setup")
else:
    st.warning("Risk tidak valid (entry terlalu dekat dengan stoploss)")

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
# GLOSSARY LENGKAP (sama seperti sebelumnya)
# =========================
with st.expander("📖 GLOSSARY LENGKAP (Klik untuk lihat semua penjelasan)"):
    st.markdown("### 📊 TECHNICAL INDICATORS")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **1. RSI (Relative Strength Index)**
        - Mengukur kekuatan pergerakan harga
        - RSI < 30 → Oversold (potensi naik)
        - RSI > 70 → Overbought (potensi turun)
        - RSI 30-70 → Normal
            
        **2. SMA (Simple Moving Average)**
        - Rata-rata harga dalam periode tertentu
        - SMA20: Trend jangka pendek (1 bulan)
        - SMA50: Trend jangka menengah (2-3 bulan)
        - Harga > SMA = Trend naik
        - Harga < SMA = Trend turun
            
        **3. MACD (Moving Average Convergence Divergence)**
        - Indikator momentum dan trend
        - MACD > Signal = Bullish
        - MACD < Signal = Bearish
        """)
    with col2:
        st.markdown("""
        **4. Volume & Volume MA**
        - Volume: Jumlah saham yang diperdagangkan
        - Volume MA: Rata-rata volume 20 hari
        - Volume > MA(20)×1.8 = Volume Spike
            
        **5. Support & Resistance**
        - Support: Level harga terendah (area beli)
        - Resistance: Level harga tertinggi (area jual)
        """)
    st.markdown("---")
    st.markdown("### 🎯 SIGNAL & SCORING SYSTEMS")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **AI Score (0-5)**
        - +1: RSI < 35
        - +1: Harga > SMA20
        - +1: SMA20 > SMA50
        - +1: MACD > Signal
        - +1: Volume > Rata-rata
        """)
    with col2:
        st.markdown("""
        **Risk Meter**
        - < 1.5% = LOW RISK
        - 1.5-3% = MEDIUM RISK
        - > 3% = HIGH RISK
        """)
    st.markdown("---")
    st.markdown("### 💡 TIPS PENGGUNAAN")
    st.success("""
    1. **Multi-Timeframe**: Cek timeframe 1d, 1wk, 1mo
    2. **Konfirmasi**: Jangan hanya andalkan 1 indikator
    3. **Risk Management**: Selalu gunakan stop loss
    4. **Volume Penting**: Breakout tanpa volume = false breakout
    5. **IHSG**: Untuk indeks, data volume tidak tersedia
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
""")
