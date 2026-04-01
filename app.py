import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, date, timedelta
import time
from typing import Dict, List, Optional, Tuple, Any

# ========== IMPORT OPSIONAL DENGAN PENANGANAN ERROR ==========
try:
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    st.warning("Library 'ta' tidak terinstal. Install dengan: pip install ta")

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False

try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# ========== KONSTANTA ==========
TIMEFRAMES = {"1d": "1d", "1wk": "1wk", "1mo": "1mo"}
DEFAULT_TICKER = "^JKSE"
CACHE_TTL = 600
SCANNER_CACHE_TTL = 1800
IHSG_BLUE_CHIPS = [
    "BBRI.JK", "BBCA.JK", "BMRI.JK", "TLKM.JK", "ASII.JK",
    "ADRO.JK", "ANTM.JK", "MDKA.JK", "UNTR.JK", "ICBP.JK",
    "INDF.JK", "UNVR.JK", "SMGR.JK", "CPIN.JK", "JPFA.JK"
]
VOLUME_SPIKE_THRESHOLD = 1.8
BREAKOUT_COOLDOWN_HOURS = 24
VOLUME_SPIKE_COOLDOWN_HOURS = 6

st.set_page_config(layout="wide", page_title="Smart Market Dashboard", page_icon="📊")

# ========== SESSION STATE ==========
if 'last_resistance' not in st.session_state:
    st.session_state.last_resistance = None
if 'last_breakout_notify_time' not in st.session_state:
    st.session_state.last_breakout_notify_time = None
if 'last_volume_ratio' not in st.session_state:
    st.session_state.last_volume_ratio = 0
if 'last_volume_notify_time' not in st.session_state:
    st.session_state.last_volume_notify_time = None
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

# ========== FUNGSI BANTU ==========
def safe_sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=1).mean()

def fix_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()
    if ticker.startswith('^') or ticker.endswith('.JK'):
        return ticker
    return ticker + '.JK'

def should_notify_breakout(current_price: float, resistance: float) -> bool:
    if current_price <= resistance:
        return False
    if st.session_state.last_resistance is None:
        return True
    if resistance > st.session_state.last_resistance:
        return True
    if st.session_state.last_breakout_notify_time is None:
        return True
    cooldown = timedelta(hours=BREAKOUT_COOLDOWN_HOURS)
    if datetime.now() - st.session_state.last_breakout_notify_time > cooldown:
        return True
    return False

def should_notify_volume_spike(volume_ratio: float) -> bool:
    if volume_ratio <= VOLUME_SPIKE_THRESHOLD:
        return False
    if st.session_state.last_volume_notify_time is None:
        return True
    cooldown = timedelta(hours=VOLUME_SPIKE_COOLDOWN_HOURS)
    if datetime.now() - st.session_state.last_volume_notify_time > cooldown:
        return True
    return False

def get_fundamental_details(ticker: str) -> Dict[str, Any]:
    try:
        obj = yf.Ticker(ticker)
        info = obj.info
        return {
            'pe': info.get('trailingPE'),
            'pb': info.get('priceToBook'),
            'div_yield': info.get('dividendYield'),
            'market_cap': info.get('marketCap'),
            'sector': info.get('sector'),
            'roa': info.get('returnOnAssets'),
            'roe': info.get('returnOnEquity'),
            'debt_to_equity': info.get('debtToEquity'),
            'profit_margin': info.get('profitMargins'),
            'revenue_growth': info.get('revenueGrowth'),
            'earnings_growth': info.get('earningsGrowth'),
        }
    except Exception:
        return {}

@st.cache_data(ttl=CACHE_TTL)
def load_data(ticker: str, timeframe: str) -> pd.DataFrame:
    try:
        df = yf.download(ticker, period="2y", interval=timeframe, progress=False, auto_adjust=False)
        if df.empty:
            df = yf.download(ticker, period="1y", interval=timeframe, progress=False, auto_adjust=False)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna(how='all')
        # Pastikan kolom Volume ada, jika tidak buat dengan nilai 0
        if 'Volume' not in df.columns:
            df['Volume'] = 0
        else:
            df['Volume'] = df['Volume'].fillna(0)
        return df
    except Exception as e:
        st.error(f"Error loading data for {ticker}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=SCANNER_CACHE_TTL)
def scan_market_fast(tickers: List[str]) -> pd.DataFrame:
    try:
        all_data = yf.download(tickers, period="3mo", interval="1d", group_by="ticker", progress=False, threads=True, auto_adjust=False)
        rows = []
        for ticker in tickers:
            try:
                if isinstance(all_data.columns, pd.MultiIndex):
                    if ticker not in all_data.columns.levels[0]:
                        continue
                    df = all_data[ticker].dropna()
                else:
                    # Hanya satu ticker
                    if ticker != tickers[0]:
                        continue
                    df = all_data.dropna()
                if len(df) < 20:
                    continue
                close = df['Close']
                # Hitung RSI dengan penanganan data kurang
                if len(close) >= 14:
                    rsi = ta.momentum.rsi(close, window=14).iloc[-1]
                else:
                    rsi = 50.0
                sma20 = close.rolling(20).mean().iloc[-1]
                if pd.isna(sma20):
                    sma20 = close.iloc[-1]
                score_val = (1 if rsi < 35 else 0) + (1 if close.iloc[-1] > sma20 else 0)
                rows.append([ticker, round(rsi, 2), score_val])
            except Exception:
                continue
        return pd.DataFrame(rows, columns=["Ticker", "RSI", "Score"])
    except Exception as e:
        st.error(f"Scanner error: {e}")
        return pd.DataFrame()

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    close = df['Close']
    volume = df['Volume'] if 'Volume' in df.columns else pd.Series(0, index=df.index)

    df['SMA20'] = safe_sma(close, 20)
    df['SMA50'] = safe_sma(close, 50)

    if TA_AVAILABLE and len(df) >= 14:
        df['RSI'] = ta.momentum.rsi(close, window=14)
    else:
        df['RSI'] = 50.0

    if TA_AVAILABLE and len(df) >= 26:
        macd = ta.trend.MACD(close)
        df['MACD'] = macd.macd()
        df['MACD_signal'] = macd.macd_signal()
    else:
        df['MACD'] = 0.0
        df['MACD_signal'] = 0.0

    if volume.sum() > 0:
        df['Volume_MA'] = volume.rolling(20, min_periods=1).mean()
    else:
        df['Volume_MA'] = 0.0

    df['support'] = df['Low'].rolling(20, min_periods=1).min()
    df['resistance'] = df['High'].rolling(20, min_periods=1).max()

    if TA_AVAILABLE:
        try:
            df['AD'] = ta.volume.acc_dist_index(df['High'], df['Low'], df['Close'], df['Volume'], fillna=True)
        except Exception:
            df['AD'] = 0.0
        try:
            df['CMF'] = ta.volume.chaikin_money_flow(df['High'], df['Low'], df['Close'], df['Volume'], window=20, fillna=True)
        except Exception:
            df['CMF'] = 0.0
    else:
        df['AD'] = 0.0
        df['CMF'] = 0.0

    if TA_AVAILABLE and len(df) >= 20:
        bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        df['BB_upper'] = bb.bollinger_hband()
        df['BB_middle'] = bb.bollinger_mavg()
        df['BB_lower'] = bb.bollinger_lband()
    else:
        df['BB_upper'] = np.nan
        df['BB_middle'] = np.nan
        df['BB_lower'] = np.nan

    df = df.ffill().fillna(0)
    return df

def calculate_ai_score(df: pd.DataFrame, volume: pd.Series) -> int:
    if df.empty:
        return 0
    conditions = [
        df['RSI'].iloc[-1] < 35,
        df['Close'].iloc[-1] > df['SMA20'].iloc[-1],
        df['SMA20'].iloc[-1] > df['SMA50'].iloc[-1],
        df['MACD'].iloc[-1] > df['MACD_signal'].iloc[-1],
        volume.iloc[-1] > df['Volume_MA'].iloc[-1] if volume.sum() > 0 else False
    ]
    return sum(conditions)

def get_portfolio_current_prices(tickers: List[str]) -> Dict[str, Optional[float]]:
    if not tickers:
        return {}
    try:
        # Jika hanya satu ticker, download sebagai Series biasa
        if len(tickers) == 1:
            data = yf.download(tickers[0], period="1d", progress=False, auto_adjust=False)
            if not data.empty:
                return {tickers[0]: data['Close'].iloc[-1]}
            else:
                return {tickers[0]: None}
        # Multiple tickers
        data = yf.download(tickers, period="1d", group_by='ticker', progress=False, auto_adjust=False)
        prices = {}
        for tick in tickers:
            try:
                if tick in data.columns.levels[0]:
                    prices[tick] = data[tick]['Close'].iloc[-1]
                else:
                    prices[tick] = None
            except Exception:
                prices[tick] = None
        return prices
    except Exception as e:
        st.error(f"Error fetching portfolio prices: {e}")
        return {t: None for t in tickers}

# ========== FUNGSI BACKTEST, ML, SENTIMEN ==========
def backtest_strategy(df, initial_capital=1000000):
    """Backtest strategi RSI < 35 dan Close > SMA20"""
    if df.empty or len(df) < 50:
        return None
    df = df.copy()
    # Hitung indikator
    df['sma20'] = df['Close'].rolling(20).mean()
    if TA_AVAILABLE:
        df['rsi'] = ta.momentum.rsi(df['Close'], window=14)
    else:
        df['rsi'] = 50.0
    # Drop baris dengan NaN (terutama awal data)
    df = df.dropna(subset=['sma20', 'rsi'])
    if len(df) < 10:
        return None
    # Sinyal beli: RSI < 35 dan Close > SMA20
    df['buy_signal'] = (df['rsi'] < 35) & (df['Close'] > df['sma20'])
    df['sell_signal'] = (df['rsi'] > 70) | (df['Close'] < df['sma20'])
    # Simulasi
    position = 0
    cash = initial_capital
    trades = []
    for i in range(1, len(df)):
        if df['buy_signal'].iloc[i] and position == 0:
            position = cash / df['Close'].iloc[i]
            cash = 0
            trades.append(('BUY', df.index[i], df['Close'].iloc[i]))
        elif df['sell_signal'].iloc[i] and position > 0:
            cash = position * df['Close'].iloc[i]
            position = 0
            trades.append(('SELL', df.index[i], df['Close'].iloc[i]))
    if position > 0:
        cash = position * df['Close'].iloc[-1]
    total_return = (cash - initial_capital) / initial_capital * 100
    return {
        'final_capital': cash,
        'total_return': total_return,
        'num_trades': len(trades),
        'trades': trades
    }

def prepare_ml_features(df):
    """Siapkan fitur dan target untuk ML (hanya jika sklearn tersedia)"""
    if not SKLEARN_AVAILABLE:
        return None, None
    if df.empty or len(df) < 100:
        return None, None
    df = df.copy()
    # Pastikan kolom Volume ada
    if 'Volume' not in df.columns:
        df['Volume'] = 0
    if TA_AVAILABLE:
        df['rsi'] = ta.momentum.rsi(df['Close'], window=14)
        df['ad'] = ta.volume.acc_dist_index(df['High'], df['Low'], df['Close'], df['Volume'], fillna=True)
        df['cmf'] = ta.volume.chaikin_money_flow(df['High'], df['Low'], df['Close'], df['Volume'], window=20, fillna=True)
    else:
        df['rsi'] = 50.0
        df['ad'] = 0.0
        df['cmf'] = 0.0
    df['sma20'] = df['Close'].rolling(20).mean()
    df['sma50'] = df['Close'].rolling(50).mean()
    df['volume_ma'] = df['Volume'].rolling(20).mean()
    # Target: kenaikan >1% dalam 5 hari
    df['future_return'] = df['Close'].shift(-5) / df['Close'] - 1
    df['target'] = (df['future_return'] > 0.01).astype(int)
    df = df.dropna()
    if len(df) < 50:
        return None, None
    features = ['rsi', 'sma20', 'sma50', 'volume_ma', 'ad', 'cmf']
    X = df[features]
    y = df['target']
    return X, y

def get_news_sentiment():
    """Ambil sentimen dari RSS (CNBC Indonesia) jika library tersedia"""
    if not (FEEDPARSER_AVAILABLE and TEXTBLOB_AVAILABLE):
        return None
    try:
        feed = feedparser.parse('https://www.cnbcindonesia.com/news/rss')
        sentiments = []
        for entry in feed.entries[:10]:
            blob = TextBlob(entry.title)
            sentiments.append(blob.sentiment.polarity)
        if sentiments:
            return sum(sentiments) / len(sentiments)
        else:
            return 0.0
    except Exception:
        return None

# ========== SIDEBAR ==========
with st.sidebar:
    st.markdown("# 📊 Smart Market Dashboard")
    ticker_input = st.text_input("Ticker", DEFAULT_TICKER, help="Contoh: BBCA, BBRI, ASII, atau ^JKSE untuk IHSG.")
    ticker = fix_ticker(ticker_input)
    if ticker != ticker_input:
        st.info(f"Format: {ticker}")
    timeframe = st.selectbox("Timeframe", list(TIMEFRAMES.keys()))
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown("---")
    st.caption("Data dari Yahoo Finance | Update 10 menit")

# ========== LOAD DATA ==========
with st.spinner("Memuat data..."):
    data = load_data(ticker, TIMEFRAMES[timeframe])

if data.empty or len(data) < 5:
    st.warning(f"Data tidak cukup untuk {ticker} (minimal 5 periode).")
    st.stop()

data = add_indicators(data)

# Notifikasi breakout & volume
if not data.empty:
    current_resistance = data['resistance'].iloc[-1]
    current_price = data['Close'].iloc[-1]
    if should_notify_breakout(current_price, current_resistance):
        st.toast(f"🚀 BREAKOUT! Harga menembus resistance {current_resistance:.2f}", icon="🚀")
        st.session_state.last_resistance = current_resistance
        st.session_state.last_breakout_notify_time = datetime.now()
    
    volume = data['Volume'] if 'Volume' in data.columns else pd.Series(0, index=data.index)
    if volume.sum() > 0:
        vol_last = volume.iloc[-1]
        vol_ma = data['Volume_MA'].iloc[-1]
        if vol_ma > 0:
            volume_ratio = vol_last / vol_ma
            if should_notify_volume_spike(volume_ratio):
                st.toast(f"🔥 Volume Spike! {volume_ratio:.1f}x", icon="⚠️")
                st.session_state.last_volume_ratio = volume_ratio
                st.session_state.last_volume_notify_time = datetime.now()

# ========== HEADER HARGA ==========
st.title(f"📈 {ticker}")
last_close = data['Close'].iloc[-1]
last_high = data['High'].iloc[-1]
last_low = data['Low'].iloc[-1]
prev_close = data['Close'].iloc[-2] if len(data) > 1 else last_close
change = last_close - prev_close
change_pct = (change / prev_close) * 100 if prev_close != 0 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Harga Terakhir", f"{last_close:.2f}", f"{change_pct:.2f}%", delta_color="normal")
col2.metric("Hari Ini - Tertinggi", f"{last_high:.2f}")
col3.metric("Hari Ini - Terendah", f"{last_low:.2f}")
col4.metric("Volume Terakhir", f"{volume.iloc[-1]:,.0f}" if volume.sum() > 0 else "N/A")

ad_val = data['AD'].iloc[-1]
cmf_val = data['CMF'].iloc[-1]
ad_status = "Akumulasi" if ad_val > 0 else "Distribusi" if ad_val < 0 else "Netral"
cmf_status = "Akumulasi" if cmf_val > 0 else "Distribusi" if cmf_val < 0 else "Netral"
st.markdown(f"""
<div style="background-color: #f0f2f6; padding: 10px; border-radius: 10px; margin-bottom: 10px;">
    <b>📊 Akumulasi/Distribusi (AD):</b> {ad_status} ({ad_val:.2f}) &nbsp;&nbsp;|&nbsp;&nbsp;
    <b>💰 Chaikin Money Flow (CMF20):</b> {cmf_status} ({cmf_val:.3f})
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ========== TABS ==========
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📈 Grafik", "🤖 AI Signal", "🔍 Scanner", "📁 Portfolio", "🧪 Backtest & ML", "📖 Info"])

# ========== TAB 1: GRAFIK ==========
with tab1:
    st.subheader("Candlestick Chart")
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=data.index, open=data['Open'], high=data['High'],
                                 low=data['Low'], close=data['Close'], name="Price"))
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA20'], name="SMA20"))
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA50'], name="SMA50"))
    fig.add_trace(go.Scatter(x=data.index, y=data['support'], name="Support", line=dict(dash='dash')))
    fig.add_trace(go.Scatter(x=data.index, y=data['resistance'], name="Resistance", line=dict(dash='dash')))
    if 'BB_upper' in data.columns and not data['BB_upper'].isnull().all():
        fig.add_trace(go.Scatter(x=data.index, y=data['BB_upper'], name="BB Upper", line=dict(dash='dot')))
        fig.add_trace(go.Scatter(x=data.index, y=data['BB_lower'], name="BB Lower", line=dict(dash='dot')))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Volume")
    if volume.sum() > 0:
        st.bar_chart(volume)
    else:
        st.info("Volume tidak tersedia untuk indeks")

    col_r, col_m = st.columns(2)
    with col_r:
        st.subheader("RSI (14)")
        st.line_chart(data['RSI'])
        st.caption("RSI < 35: Oversold | >70: Overbought")
    with col_m:
        st.subheader("MACD")
        st.line_chart(data[['MACD', 'MACD_signal']])
        st.caption("MACD > Signal: Bullish")

    st.subheader("AD & CMF")
    col_ad, col_cmf = st.columns(2)
    with col_ad:
        st.line_chart(data['AD'])
    with col_cmf:
        st.line_chart(data['CMF'])

# ========== TAB 2: AI SIGNAL ==========
with tab2:
    score = calculate_ai_score(data, volume)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🤖 AI Score")
        st.metric("Score", f"{score}/5")
        if score >= 4:
            st.success("🚀 STRONG BUY")
        elif score == 3:
            st.info("🟡 HOLD")
        else:
            st.error("🔻 SELL")
    with col_b:
        st.subheader("🎯 Risk Meter")
        returns = data['Close'].pct_change().dropna()
        if len(returns) > 0:
            if timeframe == "1d":
                periods_per_year = 252
            elif timeframe == "1wk":
                periods_per_year = 52
            else:
                periods_per_year = 12
            daily_vol = returns.std()
            annual_vol = daily_vol * np.sqrt(periods_per_year) * 100
        else:
            annual_vol = 0.0
        if annual_vol < 15:
            risk = "LOW"
            st.success(f"Risk Level: {risk} ({annual_vol:.1f}% annual)")
        elif annual_vol < 30:
            risk = "MEDIUM"
            st.warning(f"Risk Level: {risk} ({annual_vol:.1f}% annual)")
        else:
            risk = "HIGH"
            st.error(f"Risk Level: {risk} ({annual_vol:.1f}% annual)")

    st.subheader("📊 Probability Engine")
    bull = bear = 0
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
    if total > 0:
        bull_prob = (bull/total)*100
        bear_prob = (bear/total)*100
    else:
        bull_prob = bear_prob = 50
    st.write(f"📈 Bullish: {bull_prob:.1f}% | 📉 Bearish: {bear_prob:.1f}%")

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

    col_brk, col_vol = st.columns(2)
    with col_brk:
        st.subheader("🚀 Breakout Detector")
        if len(data) > 1 and data['Close'].iloc[-1] > data['resistance'].iloc[-2]:
            st.success("🔥 BREAKOUT DETECTED")
        else:
            st.info("Tidak ada breakout")
    with col_vol:
        st.subheader("🚨 Volume Alert")
        if volume.sum() > 0:
            if volume.iloc[-1] > data['Volume_MA'].iloc[-1] * VOLUME_SPIKE_THRESHOLD:
                st.success("Volume Spike Detected")
            else:
                st.write("Normal Volume")
        else:
            st.info("Volume tidak tersedia")

    st.header("🧠 AI FINAL PRO")
    final_score = 0
    if bull_prob > 60:
        final_score += 1
    if risk == "LOW":
        final_score += 1
    if momentum > 2:
        final_score += 1
    if volume.sum() > 0 and volume.iloc[-1] > data['Volume_MA'].iloc[-1]:
        final_score += 1
    if final_score >= 2:
        st.success("🚀 STRONG ACCUMULATE")
    elif final_score == 1:
        st.warning("🟡 SPEC BUY")
    else:
        st.error("🔻 WAIT / AVOID")

    st.header("🚀 GOD MODE TRADING ENGINE")
    price = data['Close'].iloc[-1]
    support = data['support'].iloc[-1] if pd.notna(data['support'].iloc[-1]) else price * 0.95
    resistance = data['resistance'].iloc[-1] if pd.notna(data['resistance'].iloc[-1]) else price * 1.05

    entry = (support + price) / 2
    stoploss = support * 0.97
    target1 = resistance
    risk_amount = entry - stoploss
    reward = target1 - entry
    rr = reward / risk_amount if risk_amount > 0 else 0

    col_e, col_s, col_t = st.columns(3)
    col_e.metric("🎯 Smart Entry", f"{entry:.2f}")
    col_s.metric("🛑 Stoploss", f"{stoploss:.2f}")
    col_t.metric("💰 Target 1", f"{target1:.2f}")
    st.write(f"**Risk Reward Ratio:** 1 : {rr:.2f}")
    if rr > 2:
        st.success("Good Trade Setup")
    elif rr > 1:
        st.warning("Moderate Setup")
    else:
        st.error("Bad Setup")

    col_ts, col_bs = st.columns(2)
    with col_ts:
        st.subheader("📈 Trend Score")
        trend_score = 0
        if price > data['SMA20'].iloc[-1]:
            trend_score += 1
        if data['SMA20'].iloc[-1] > data['SMA50'].iloc[-1]:
            trend_score += 1
        if data['RSI'].iloc[-1] > 50:
            trend_score += 1
        st.write(f"Trend Score: {trend_score}/3")
    with col_bs:
        st.subheader("🔥 Breakout Strength")
        if price > resistance:
            strength = (price - resistance) / resistance * 100
            st.success(f"Breakout Strength: {strength:.2f}%")
        else:
            st.write("No Breakout")

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

    st.header("FINAL DECISION")
    if score >= 3:
        st.success("🟢 ACCUMULATE")
    elif score == 2:
        st.warning("🟡 WAIT")
    else:
        st.error("🔴 AVOID")

# ========== TAB 3: SCANNER ==========
with tab3:
    st.subheader("🔥 SUPER FAST IHSG SCANNER (15 Blue Chip)")
    with st.spinner("Memindai 15 saham..."):
        scan_df = scan_market_fast(IHSG_BLUE_CHIPS)
    if not scan_df.empty:
        st.dataframe(scan_df.sort_values("Score", ascending=False), use_container_width=True)
        st.subheader("🚀 TOP 5 BUY")
        top5 = scan_df.sort_values("Score", ascending=False).head(5)
        if not top5.empty:
            st.table(top5)
        else:
            st.info("Tidak ada saham dengan score > 0")
    else:
        st.warning("Scanner gagal, coba lagi nanti.")

# ========== TAB 4: PORTFOLIO ==========
with tab4:
    st.subheader("📁 Portfolio Tracker")
    with st.expander("➕ Tambah Posisi Baru"):
        col_t1, col_t2, col_t3, col_t4 = st.columns(4)
        with col_t1:
            ticker_entry = st.text_input("Ticker", key="entry_ticker", help="Contoh: BBCA.JK")
        with col_t2:
            entry_date = st.date_input("Tanggal Entry", value=date.today())
        with col_t3:
            entry_price = st.number_input("Harga Entry", min_value=0.0, step=10.0)
        with col_t4:
            shares = st.number_input("Jumlah Saham", min_value=1, step=100)
        if st.button("Simpan Posisi"):
            if ticker_entry and entry_price > 0 and shares > 0:
                st.session_state.portfolio.append({
                    'ticker': fix_ticker(ticker_entry),
                    'entry_date': entry_date.strftime('%Y-%m-%d'),
                    'entry_price': entry_price,
                    'shares': shares
                })
                st.success("Posisi ditambahkan!")
                st.rerun()
            else:
                st.error("Isi semua field dengan benar.")
    if st.session_state.portfolio:
        portfolio_df = pd.DataFrame(st.session_state.portfolio)
        unique_tickers = portfolio_df['ticker'].unique().tolist()
        current_prices = get_portfolio_current_prices(unique_tickers)
        portfolio_df['current_price'] = portfolio_df['ticker'].map(current_prices)
        portfolio_df['unrealized_pnl'] = (portfolio_df['current_price'] - portfolio_df['entry_price']) * portfolio_df['shares']
        portfolio_df['pnl_pct'] = ((portfolio_df['current_price'] - portfolio_df['entry_price']) / portfolio_df['entry_price']) * 100
        st.dataframe(portfolio_df, use_container_width=True)
        total_pnl = portfolio_df['unrealized_pnl'].sum()
        st.metric("Total Unrealized P&L", f"{total_pnl:,.2f}", delta=f"{total_pnl:+,.2f}")
        if st.button("Hapus Semua Posisi"):
            st.session_state.portfolio = []
            st.rerun()
    else:
        st.info("Belum ada posisi. Gunakan form di atas untuk menambahkan.")
    st.divider()
    st.subheader("📐 Position Sizing Calculator")
    col_cap, col_risk, col_sl = st.columns(3)
    with col_cap:
        capital = st.number_input("Modal (Rp)", min_value=0.0, value=100_000_000.0, step=10_000_000.0)
    with col_risk:
        risk_percent = st.number_input("Risiko per Trade (%)", min_value=0.0, max_value=100.0, value=2.0, step=0.5)
    with col_sl:
        stoploss_price = st.number_input("Stop Loss (Rp)", min_value=0.0, value=last_close * 0.97 if last_close else 0.0)
    if capital > 0 and risk_percent > 0 and stoploss_price > 0 and last_close > 0:
        risk_amount = capital * (risk_percent / 100)
        price_risk = last_close - stoploss_price
        if price_risk > 0:
            suggested_shares = int(risk_amount / price_risk)
            position_value = suggested_shares * last_close
            st.write(f"**Jumlah saham yang direkomendasikan:** {suggested_shares:,} lembar")
            st.write(f"Nilai posisi: Rp {position_value:,.2f} ({position_value/capital*100:.1f}% dari modal)")
            if position_value > capital:
                st.warning("Nilai posisi melebihi modal! Turunkan jumlah saham atau perbesar stop loss.")
        else:
            st.warning("Stop loss harus di bawah harga saat ini.")
    else:
        st.info("Masukkan modal, risiko, dan stop loss untuk menghitung.")

# ========== TAB 5: BACKTEST & ML ==========
with tab5:
    st.header("🧪 Backtesting & Machine Learning")
    
    # Backtesting
    st.subheader("📈 Backtest Strategi (RSI < 35 & Harga > SMA20)")
    with st.spinner("Menjalankan backtest..."):
        bt_result = backtest_strategy(data)
    if bt_result:
        st.metric("Total Return", f"{bt_result['total_return']:.2f}%", delta=f"{bt_result['total_return']:.2f}%")
        st.metric("Jumlah Transaksi", bt_result['num_trades'])
        st.write(f"**Modal Akhir:** Rp {bt_result['final_capital']:,.2f}")
        with st.expander("Lihat Detail Transaksi"):
            st.dataframe(pd.DataFrame(bt_result['trades'], columns=['Tipe', 'Tanggal', 'Harga']))
    else:
        if len(data) < 50:
            st.warning(f"Data tidak cukup untuk backtest. Minimal 50 baris, saat ini hanya {len(data)} baris.")
        else:
            st.warning("Backtest gagal. Pastikan data memiliki kolom Close, Volume, dan indikator yang diperlukan.")
    
    st.divider()
    
    # Machine Learning
    st.subheader("🤖 Machine Learning Prediction (Random Forest)")
    if SKLEARN_AVAILABLE:
        X, y = prepare_ml_features(data)
        if X is not None and len(X) > 50:
            # Split data (waktu berurutan)
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)
            model = RandomForestClassifier(n_estimators=100, random_state=42)
            model.fit(X_train, y_train)
            acc = accuracy_score(y_test, model.predict(X_test))
            st.metric("Akurasi Model (Test)", f"{acc:.2%}")
            # Prediksi untuk hari ini
            latest = X.iloc[-1:].values
            prob = model.predict_proba(latest)[0][1]
            st.write(f"**Probabilitas harga naik >1% dalam 5 hari:** {prob:.2%}")
            # Feature importance
            if st.checkbox("Tampilkan Feature Importance"):
                importance = pd.DataFrame({'Feature': X.columns, 'Importance': model.feature_importances_})
                st.bar_chart(importance.set_index('Feature'))
        else:
            if len(data) < 100:
                st.warning(f"Data tidak cukup untuk melatih model. Minimal 100 baris, saat ini {len(data)} baris.")
            else:
                st.warning("Data tidak cukup setelah preprocessing (mungkin karena missing values).")
    else:
        st.error("❌ Machine learning tidak tersedia karena library 'scikit-learn' tidak terinstal. Install dengan: pip install scikit-learn")
    
    st.divider()
    
    # Sentimen Berita (Diversifikasi)
    st.subheader("📰 Sentimen Berita (Diversifikasi)")
    if FEEDPARSER_AVAILABLE and TEXTBLOB_AVAILABLE:
        with st.spinner("Mengambil sentimen berita..."):
            sentiment = get_news_sentiment()
        if sentiment is not None:
            sentiment_text = "Positif" if sentiment > 0 else "Negatif" if sentiment < 0 else "Netral"
            st.metric("Sentimen 24 Jam", f"{sentiment_text} ({sentiment:.2f})")
            st.caption("Sumber: CNBC Indonesia RSS (judul berita terbaru)")
        else:
            st.info("Tidak dapat mengambil sentimen berita saat ini. Cek koneksi internet atau RSS feed.")
    else:
        missing = []
        if not FEEDPARSER_AVAILABLE:
            missing.append("feedparser")
        if not TEXTBLOB_AVAILABLE:
            missing.append("textblob")
        st.error(f"❌ Fitur sentimen tidak tersedia karena library {', '.join(missing)} tidak terinstal. Install dengan: pip install {' '.join(missing)}")

# ========== TAB 6: INFO ==========
with tab6:
    if not ticker.startswith('^'):
        st.subheader("📊 Fundamental Details")
        fund = get_fundamental_details(ticker)
        if fund:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("PER (TTM)", f"{fund['pe']:.2f}" if fund['pe'] else "N/A")
                st.metric("PBV", f"{fund['pb']:.2f}" if fund['pb'] else "N/A")
                st.metric("Dividend Yield", f"{fund['div_yield']*100:.2f}%" if fund['div_yield'] else "N/A")
                st.metric("Market Cap", f"{fund['market_cap']/1e12:.2f}T" if fund['market_cap'] else "N/A")
                st.metric("Sektor", fund['sector'] if fund['sector'] else "N/A")
            with col2:
                st.metric("ROA", f"{fund['roa']*100:.2f}%" if fund['roa'] else "N/A")
                st.metric("ROE", f"{fund['roe']*100:.2f}%" if fund['roe'] else "N/A")
                st.metric("Debt to Equity", f"{fund['debt_to_equity']:.2f}" if fund['debt_to_equity'] else "N/A")
                st.metric("Profit Margin", f"{fund['profit_margin']*100:.2f}%" if fund['profit_margin'] else "N/A")
                st.metric("Revenue Growth (YoY)", f"{fund['revenue_growth']*100:.2f}%" if fund['revenue_growth'] else "N/A")
        else:
            st.info("Data fundamental tidak tersedia untuk ticker ini.")
    else:
        st.info("Data fundamental tidak tersedia untuk indeks.")
    
    st.divider()
    
    # Opsional: tampilkan sentimen juga di tab info jika tersedia
    if FEEDPARSER_AVAILABLE and TEXTBLOB_AVAILABLE:
        st.subheader("📰 Diversifikasi Sinyal: Sentimen Berita Terkini")
        sentiment = get_news_sentiment()
        if sentiment is not None:
            sentiment_text = "Positif" if sentiment > 0 else "Negatif" if sentiment < 0 else "Netral"
            st.metric("Sentimen 24 Jam", f"{sentiment_text} ({sentiment:.2f})")
            st.caption("Sumber: CNBC Indonesia RSS (judul berita terbaru)")
        else:
            st.info("Tidak dapat mengambil sentimen saat ini.")
    
    with st.expander("📖 Glossary (Klik untuk lihat)"):
        st.markdown("""
        **RSI** < 35: Oversold | >70: Overbought  
        **SMA20/50**: Harga > SMA = uptrend  
        **MACD > Signal**: Bullish  
        **Volume > Volume MA**: Volume di atas rata-rata  
        **AD > 0**: Akumulasi (tekanan beli)  
        **CMF > 0**: Tekanan beli  
        **Risk Reward Ratio**: Target/risk > 2 = good setup  
        **AI Score** 4-5: Strong Buy, 3: Hold, 0-2: Sell  
        **FINAL DECISION** score ≥3: Accumulate, =2: Wait, ≤1: Avoid
        **Backtest**: Menguji strategi RSI + SMA pada data historis  
        **Machine Learning**: Prediksi probabilitas kenaikan harga >1% dalam 5 hari
        """)

st.markdown("---")
st.caption("⚠️ **DISCLAIMER:** Dashboard ini hanya untuk edukasi dan analisis otomatis. Bukan rekomendasi beli/jual. Keputusan investasi sepenuhnya risiko Anda.")
