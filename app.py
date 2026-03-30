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
# ✅ SUDAH DIUBAH: Default ticker sekarang adalah ^JKSE (IHSG/IDX Composite)
ticker = col1.text_input("Ticker", "^JKSE")
timeframe = col2.selectbox("Timeframe", ["1d","1wk","1mo"])

# =========================
# LOAD DATA
# =========================
@st.cache_data
def load_data(ticker, timeframe):
    # Download data
    df = yf.download(ticker, period="1y", interval=timeframe, progress=False)
    
    # Perbaikan khusus untuk Index (^JKSE, ^HSI, dll)
    if df.empty:
        df = yf.download(ticker, period="1y", interval=timeframe, progress=False, auto_adjust=False)
    
    # Rapikan columns (untuk multi-level columns)
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
            if len(d) > 20:
                rsi = ta.momentum.rsi(d['Close']).iloc[-1]
                sma20 = d['Close'].rolling(20).mean().iloc[-1]

                score = 0
                if rsi < 35: score += 1
                if d['Close'].iloc[-1] > sma20: score += 1

                rows.append([t, round(rsi,2), score])
        except Exception as e:
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
# GOD MODE ENGINE
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
# GLOSSARY LENGKAP
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
        - Garis histogram menunjukkan kekuatan trend
        """)
    
    with col2:
        st.markdown("""
        **4. Volume & Volume MA**
        - Volume: Jumlah saham yang diperdagangkan
        - Volume MA: Rata-rata volume 20 hari
        - Volume > MA(20)×1.8 = Volume Spike
        - Volume tinggi = Minat besar
            
        **5. Support & Resistance**
        - Support: Level harga terendah (area beli)
        - Resistance: Level harga tertinggi (area jual)
        - Support (20 periode): Low terendah 20 hari
        - Resistance (20 periode): High tertinggi 20 hari
        """)
    
    st.markdown("---")
    st.markdown("### 🎯 SIGNAL & SCORING SYSTEMS")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **AI Score (0-5)**
        - +1: RSI < 35 (Oversold)
        - +1: Harga > SMA20
        - +1: SMA20 > SMA50 (Golden Cross)
        - +1: MACD > Signal
        - +1: Volume > Rata-rata
        - 4-5: STRONG BUY 🚀
        - 3: HOLD 🟡
        - 0-2: SELL 🔻
            
        **Probability Engine**
        - Menghitung peluang Bullish/Bearish
        - Bull > 60% = Potensi naik
        - Bear > 60% = Potensi turun
        """)
    
    with col2:
        st.markdown("""
        **Trend Score (0-3)**
        - +1: Harga > SMA20
        - +1: SMA20 > SMA50 (Uptrend)
        - +1: RSI > 50 (Momentum positif)
        - 3: Strong Uptrend
        - 2: Moderate Uptrend
        - 1: Weak Trend
            
        **Risk Meter**
        - Volatilitas dari return harian
        - < 1.5% = LOW RISK ✅
        - 1.5-3% = MEDIUM RISK ⚠️
        - > 3% = HIGH RISK 🔴
        """)
    
    st.markdown("---")
    st.markdown("### 🚀 TRADING SIGNALS")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Breakout Signals**
        - Breakout: Harga > Resistance
        - Breakdown: Harga < Support
        - Breakout Strength: (Harga - Resistance)/Resistance × 100%
        - Strong breakout > 3%
            
        **Momentum Detector**
        - Change 5 hari terakhir × 100%
        - > 5%: Strong Up Momentum 🔥
        - 2-5%: Moderate Up Momentum 📈
        - -2 s/d 2%: Sideways ➡️
        - < -5%: Strong Down Momentum 📉
        """)
    
    with col2:
        st.markdown("""
        **Risk Reward Ratio**
        - RR = (Target1 - Entry) / (Entry - Stop Loss)
        - RR > 2: Good Setup ✅
        - RR 1-2: Moderate Setup ⚠️
        - RR < 1: Bad Setup 🔴
            
        **Volume Spike Alert**
        - Volume > MA(20) × 1.8
        - Menandakan minat institusi
        - Konfirmasi breakout lebih valid
        """)
    
    st.markdown("---")
    st.markdown("### 🧠 GOD MODE COMPONENTS")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Smart Entry**
        - Formula: (Support + Current Price) / 2
        - Entry di area support untuk safety
        - Menghindari FOMO (Fear Of Missing Out)
            
        **Stop Loss**
        - Formula: Support × 0.97
        - Stop loss 3% di bawah support
        - Proteksi modal maksimal -5-7%
        """)
    
    with col2:
        st.markdown("""
        **Target Profit**
        - Target 1: Resistance level
        - Target 2: Resistance × 1.05 (+5%)
        - Ambil profit bertahap
            
        **God Score (0-4)**
        - +1: RR > 2
        - +1: Trend Score ≥ 2
        - +1: RSI < 70 (Tidak overbought)
        - +1: Harga > SMA20
        - 3-4: GOD MODE BUY 🚀
        - 2: SPEC BUY ⚡
        - 0-1: NO TRADE ❌
        """)
    
    st.markdown("---")
    st.markdown("### 📈 MARKET SCANNER")
    
    st.markdown("""
    **IHSG Scanner Logic**
    - Memindai 15 saham blue chip IHSG
    - Filter: RSI oversold & Harga > SMA20
    - Score 0-2 untuk setiap saham
    - Top 5 saham dengan score tertinggi
            
    **Market Momentum**
    - Menghitung up/down days dalam 20 hari
    - Up days > Down days = Bullish market
    - Down days > Up days = Bearish market
    """)
    
    st.markdown("---")
    st.markdown("### ⚠️ INTERPRETASI SCORE")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("**🔥 STRONG BUY (4-5)**")
        st.write("""
        - Semua indikator bullish
        - Momentum kuat
        - Risiko rendah-medium
        - Cocok untuk entry
        """)
    
    with col2:
        st.warning("**🟡 HOLD/WAIT (3)**")
        st.write("""
        - Indikator mixed
        - Tunggu konfirmasi
        - Perketat stop loss
        - Observasi dulu
        """)
    
    with col3:
        st.error("**🔴 SELL/AVOID (0-2)**")
        st.write("""
        - Indikator bearish
        - Momentum turun
        - Risiko tinggi
        - Hindari entry baru
        """)
    
    st.markdown("---")
    st.markdown("### 💡 TIPS PENGGUNAAN")
    
    st.success("""
    1. **Multi-Timeframe**: Cek timeframe 1d, 1wk, 1mo untuk konfirmasi trend
    2. **Konfirmasi**: Jangan hanya andalkan 1 indikator
    3. **Risk Management**: Selalu gunakan stop loss (max 5-7%)
    4. **Volume Penting**: Breakout tanpa volume = false breakout
    5. **Market Scanner**: Cek saham lain jika saham utama sedang bearish
    6. **God Mode**: Gunakan untuk entry yang lebih akurat
    7. **Probabilitas**: Bukan kepastian, selalu siap dengan skenario alternatif
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
