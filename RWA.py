import streamlit as st
import pandas as pd
import yfinance as yf

# --- 1. CẤU HÌNH DANH MỤC ---
RWA_CONFIG = {
    'LINK':   {'symbol': 'LINK-USD',   'weight': 0.35, 'v1': (7.9, 8.3), 'v2': (6.5, 7.2), 'ath': 52.8}, 
    'ONDO':   {'symbol': 'ONDO-USD',   'weight': 0.20, 'v1': (0.22, 0.24), 'v2': (0.15, 0.18), 'ath': 2.14},
    'QNT':    {'symbol': 'QNT-USD',    'weight': 0.15, 'v1': (58.0, 62.0), 'v2': (45.0, 50.0), 'ath': 428.0},
    'PENDLE': {'symbol': 'PENDLE-USD', 'weight': 0.10, 'v1': (1.05, 1.15), 'v2': (0.75, 0.90), 'ath': 7.52},
    'SYRUP':  {'symbol': 'MPL-USD',    'weight': 0.10, 'v1': (0.21, 0.25), 'v2': (0.14, 0.17), 'ath': 2.10}, # Dùng MPL thay cho Syrup vì Yahoo chưa cập nhật mã mới
    'CFG':    {'symbol': 'CFG-USD',    'weight': 0.10, 'v1': (0.32, 0.36), 'v2': (0.22, 0.26), 'ath': 2.59}
}

def get_holding(coin):
    try:
        return st.secrets["holdings"][coin]
    except:
        return 0.0

# --- 2. GIAO DIỆN ---
st.set_page_config(page_title="RWA Iron Hand 2026", layout="wide")
st.title("🛡️ RWA Iron Hand Command Center - 2026")
st.markdown(f"**Chào anh Công!** Tầm nhìn dài hạn cho chị Hân và bé Uyên Nghi.")

# --- 3. LẤY GIÁ TỪ YAHOO FINANCE (ỔN ĐỊNH HƠN) ---
@st.cache_data(ttl=300) # Lưu 5 phút để cực kỳ an toàn
def fetch_prices():
    prices = {}
    try:
        symbols = [cfg['symbol'] for cfg in RWA_CONFIG.values()]
        data = yf.download(symbols, period="1d", interval="1m")['Close']
        for coin, cfg in RWA_CONFIG.items():
            # Lấy giá đóng cửa mới nhất
            prices[coin] = data[cfg['symbol']].iloc[-1]
        return prices
    except Exception as e:
        st.error(f"Nguồn dữ liệu đang bận, anh vui lòng đợi chút... (Lỗi: {e})")
        return None

def get_status(price, v1, v2):
    if v2[0] <= price <= v2[1]: return "🔥 VÙNG GOM 2"
    if v1[0] <= price <= v1[1]: return "✅ VÙNG GOM 1"
    if price < v2[0]: return "⚠️ GIÁ CỰC RẺ"
    return "⌛ Đang quan sát"

# --- 4. XỬ LÝ DỮ LIỆU ---
prices = fetch_prices()

if prices:
    data_list = []
    total_value = 0
    
    for coin, cfg in RWA_CONFIG.items():
        price = prices[coin]
        hold = get_holding(coin)
        total_value += (price * hold)
        
    for coin, cfg in RWA_CONFIG.items():
        price = prices[coin]
        hold = get_holding(coin)
        val = price * hold
        weight_real = (val / total_value * 100) if total_value > 0 else 0
        
        data_list.append({
            "Coin": coin,
            "Giá Hiện Tại": f"${price:.3f}",
            "Trạng Thái": get_status(price, cfg['v1'], cfg['v2']),
            "Vùng Gom 1": f"{cfg['v1'][0]}-{cfg['v1'][1]}",
            "Vùng Gom 2": f"{cfg['v2'][0]}-{cfg['v2'][1]}",
            "Giá Trị ($)": f"${val:,.2f}",
            "Tỷ Trọng (%)": f"{weight_real:.1f}%",
            "Cách ATH (%)": f"{((price/cfg['ath'])-1)*100:.1f}%"
        })

    st.table(pd.DataFrame(data_list))
    st.metric("Tổng vốn RWA (USDT)", f"${total_value:,.2f}")
else:
    st.warning("Đang tải dữ liệu từ Yahoo Finance... Anh vui lòng đợi.")
