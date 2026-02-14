import streamlit as st
import pandas as pd
import ccxt

# Lấy dữ liệu số lượng coin từ Secrets (Bảo mật)
# Nếu không có Secrets thì mặc định là 0
def get_holding(coin_tier):
    try:
        return st.secrets["holdings"][coin_tier]
    except:
        return 0.0

RWA_CONFIG = {
    'LINK': {'weight_target': 0.35, 'v1': (7.9, 8.3), 'v2': (6.5, 7.2), 'ath': 52.8}, 
    'ONDO': {'weight_target': 0.20, 'v1': (0.22, 0.24), 'v2': (0.15, 0.18), 'ath': 2.14},
    'QNT':  {'weight_target': 0.15, 'v1': (58.0, 62.0), 'v2': (45.0, 50.0), 'ath': 428.0},
    'PENDLE':{'weight_target': 0.10, 'v1': (1.05, 1.15), 'v2': (0.75, 0.90), 'ath': 7.52},
    'SYRUP': {'weight_target': 0.10, 'v1': (0.21, 0.25), 'v2': (0.14, 0.17), 'ath': 2.10},
    'CFG':   {'weight_target': 0.10, 'v1': (0.32, 0.36), 'v2': (0.22, 0.26), 'ath': 2.59}
}

st.set_page_config(page_title="RWA Command Center", layout="wide")
st.title("🛡️ RWA Iron Hand Dashboard - 2026")

exchange = ccxt.bybit()

data = []
total_value = 0

for coin, cfg in RWA_CONFIG.items():
    ticker = exchange.fetch_ticker(f"{coin}/USDT")
    price = ticker['last']
    holdings = get_holding(coin)
    value = price * holdings
    total_value += value
    
    data.append({
        "Coin": coin,
        "Giá Hiện Tại": price,
        "Số Lượng": holdings,
        "Giá Trị ($)": round(value, 2),
        "Vùng Gom 1": f"{cfg['v1'][0]}-{cfg['v1'][1]}",
        "Vùng Gom 2": f"{cfg['v2'][0]}-{cfg['v2'][1]}",
        "Tỷ Trọng (%)": 0
    })

# Tính tỷ trọng thực tế
for item in data:
    if total_value > 0:
        item["Tỷ Trọng (%)"] = round((item["Giá Trị ($)"] / total_value) * 100, 1)

df = pd.DataFrame(data)
st.table(df)
st.metric("Tổng Tài Sản", f"${total_value:,.2f}")
