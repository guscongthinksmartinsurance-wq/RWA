import streamlit as st
import pandas as pd
import ccxt

# --- 1. CẤU HÌNH DANH MỤC (AN TOÀN & BẢO MẬT) ---
# Tỷ trọng mục tiêu cho chiến lược RWA 2026 của anh Công
RWA_CONFIG = {
    'LINK':   {'weight': 0.35, 'v1': (7.9, 8.3), 'v2': (6.5, 7.2), 'ath': 52.8}, 
    'ONDO':   {'weight': 0.20, 'v1': (0.22, 0.24), 'v2': (0.15, 0.18), 'ath': 2.14},
    'QNT':    {'weight': 0.15, 'v1': (58.0, 62.0), 'v2': (45.0, 50.0), 'ath': 428.0},
    'PENDLE': {'weight': 0.10, 'v1': (1.05, 1.15), 'v2': (0.75, 0.90), 'ath': 7.52},
    'SYRUP':  {'weight': 0.10, 'v1': (0.21, 0.25), 'v2': (0.14, 0.17), 'ath': 2.10},
    'CFG':    {'weight': 0.10, 'v1': (0.32, 0.36), 'v2': (0.22, 0.26), 'ath': 2.59}
}

# Hàm lấy số dư từ Secrets để bảo mật tài sản cho chị Hân và bé Uyên Nghi
def get_holding(coin):
    try:
        return st.secrets["holdings"][coin]
    except:
        return 0.0

# --- 2. GIAO DIỆN & CẤU HÌNH ---
st.set_page_config(page_title="RWA Iron Hand 2026", layout="wide")
st.title("🛡️ RWA Iron Hand Command Center - 2026")
st.markdown(f"**Chào anh Công!** Đã chơi là chơi cho tới. Chúc anh tích lũy vững vàng cho gia đình!")

# --- 3. KẾT NỐI BYBIT & LẤY GIÁ (TỐI ƯU RATE LIMIT) ---
exchange = ccxt.bybit()

@st.cache_data(ttl=60) # Lưu bộ nhớ đệm 60 giây để tránh bị sàn chặn IP
def fetch_rwa_prices():
    try:
        symbols = [f"{c}/USDT" for c in RWA_CONFIG.keys()]
        # Gọi 1 lần duy nhất để lấy giá của toàn bộ danh sách
        tickers = exchange.fetch_tickers(symbols)
        return {c: tickers[f"{c}/USDT"]['last'] for c in RWA_CONFIG.keys()}
    except Exception as e:
        st.error(f"Bybit đang quá tải, sẽ thử lại sau... (Chi tiết: {e})")
        return None

def get_status(price, v1, v2):
    if v2[0] <= price <= v2[1]: return "🔥 VÙNG GOM 2 (QUÉT RÂU)"
    if v1[0] <= price <= v1[1]: return "✅ VÙNG GOM 1 (CHỦ ĐỘNG)"
    if price < v2[0]: return "⚠️ GIÁ CỰC RẺ"
    return "⌛ Đang quan sát"

# --- 4. XỬ LÝ DỮ LIỆU ---
prices = fetch_rwa_prices()

if prices:
    data = []
    total_value = 0
    
    # Tính toán tổng giá trị trước để tính tỷ trọng
    for coin, cfg in RWA_CONFIG.items():
        price = prices[coin]
        hold = get_holding(coin)
        total_value += (price * hold)
        
    for coin, cfg in RWA_CONFIG.items():
        price = prices[coin]
        hold = get_holding(coin)
        val = price * hold
        weight_real = (val / total_value * 100) if total_value > 0 else 0
        
        data.append({
            "Coin": coin,
            "Giá Hiện Tại": f"${price:.3f}",
            "Trạng Thái": get_status(price, cfg['v1'], cfg['v2']),
            "Vùng Gom 1": f"{cfg['v1'][0]}-{cfg['v1'][1]}",
            "Vùng Gom 2": f"{cfg['v2'][0]}-{cfg['v2'][1]}",
            "Giá Trị ($)": f"${val:,.2f}",
            "Tỷ Trọng (%)": f"{weight_real:.1f}%",
            "Cách ATH (%)": f"{((price/cfg['ath'])-1)*100:.1f}%"
        })

    df = pd.DataFrame(data)

    # --- 5. HIỂN THỊ KẾT QUẢ ---
    c1, c2 = st.columns([3, 1])
    
    with c1:
        st.subheader("📊 Bảng Theo Dõi Vùng Gom")
        def style_status(val):
            if 'GOM 2' in val: return 'background-color: #721c24; color: white'
            if 'GOM 1' in val: return 'background-color: #155724; color: white'
            return ''
        
        st.table(df.style.applymap(style_status, subset=['Trạng Thái']))

    with c2:
        st.subheader("💰 Tổng Tài Sản")
        st.metric("Tổng vốn RWA (USDT)", f"${total_value:,.2f}")
        st.caption("Lưu ý: Dữ liệu cập nhật mỗi 60s để bảo vệ kết nối.")

    st.info("💡 Lời nhắc từ AI: Đừng để FOMO làm lệch hướng. Kỷ luật là chìa khóa của Manager.")
else:
    st.warning("Đang chờ dữ liệu từ sàn Bybit... Anh vui lòng nhấn F5 sau 1 phút.")
