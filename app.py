# =========================
# FUNDAMENTAL (SAFE)
# =========================
st.subheader("Fundamental")

ticker_obj = yf.Ticker(ticker)

try:
    hist = ticker_obj.history(period="1y")
    last_price = hist['Close'].iloc[-1]
    avg_volume = hist['Volume'].mean()
    high_52 = hist['High'].max()
    low_52 = hist['Low'].min()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Last Price", round(last_price,2))
    col2.metric("Avg Volume", int(avg_volume))
    col3.metric("52W High", round(high_52,2))
    col4.metric("52W Low", round(low_52,2))

except:
    st.write("Fundamental data unavailable")
