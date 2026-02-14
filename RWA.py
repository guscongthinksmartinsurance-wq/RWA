import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- CONFIG CHIẾN LƯỢC ---
ST_FILE_NAME = "TMC-Sales-Assistant"
ST_SHEET_NAME = "Holdings"
HEADERS = ["Coin", "Holdings", "Entry_Price"] # Bỏ Target_Price theo ý anh

RWA_CONFIG = {
    'LINK':   {'symbol': 'LINK-USD',   'v1': (7.9, 8.3), 'v2': (6.5, 7.2), 'ath': 52.8}, 
    'ONDO':   {'symbol': 'ONDO-USD',   'v1': (0.22, 0.24), 'v2': (0.15, 0.18), 'ath': 2.14},
    'QNT':    {'symbol': 'QNT-USD',    'v1': (58.0, 62.0), 'v2': (45.0, 50.0), 'ath': 428.0},
    'PENDLE': {'symbol': 'PENDLE-USD', 'v1': (1.05, 1.15), 'v2': (0.75, 0.90), 'ath': 7.52},
    'SYRUP':  {'symbol': 'MPL-USD',    'v1': (0.21, 0.25), 'v2': (0.14, 0.17), 'ath': 2.10}, 
    'CFG':    {'symbol': 'CFG-USD',    'v1': (0.32, 0.36), 'v2': (0.22, 0.26), 'ath': 2.59}
}

# --- HỆ THỐNG DỮ LIỆU ---
@st.cache_resource
def get_gsheet_client():
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(Credentials.from_service_account_info(creds_info, scopes=scope))

def load_data():
    client = get_gsheet_client()
    sh = client.open(ST_FILE_NAME)
    try:
        ws = sh.worksheet(ST_SHEET_NAME)
    except:
        ws = sh.add_worksheet(title=ST_SHEET_NAME, rows="100", cols="10")
        ws.append_row(HEADERS)
    data = ws.get_all_records()
    return ws, pd.DataFrame(data) if data else pd.DataFrame(columns=HEADERS)

def get_tech_levels(symbol, days):
    hist = yf.download(symbol, period=f"{days}d", interval="1d", progress=False)
    if hist.empty: return 0.0, 0.0
    return round(float(hist['Low'].min()), 3), round(float(hist['High'].max()), 3)

# --- GIAO DIỆN ELITE ---
st.set_page_config(page_title="RWA Command Center Elite", layout="wide")

# CSS tinh chỉnh giao diện Pro
st.markdown("""
    <style>
    .stMetric { background-color: #1e2130; padding: 20px; border-radius: 12px; border-left: 5px solid #4e73df; }
    [data-testid="stSidebar"] { background-color: #111421; }
    .status-box { padding: 5px 10px; border-radius: 5px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ RWA Iron Hand Command Center - 2026")
st.caption(f"Manager: Anh Công | Chào anh, chúc gia đình và bé Uyên Nghi một năm 2026 rực rỡ.")

try:
    sheet, df_holdings = load_data()
    
    with st.sidebar:
        st.header("⚡ Lệnh Mua DCA Mới")
        with st.form("dca_form"):
            coin_sel = st.selectbox("Chọn Coin", list(RWA_CONFIG.keys()))
            new_qty = st.number_input("Số lượng mua thêm", min_value=0.0, step=0.1)
            new_prc = st.number_input("Giá khớp lệnh ($)", min_value=0.0, step=0.01)
            
            if st.form_submit_button("XÁC NHẬN CỘNG DỒN"):
                user_row = df_holdings[df_holdings['Coin'] == coin_sel]
                if not user_row.empty:
                    old_q = float(user_row['Holdings'].values[0])
                    old_e = float(user_row['Entry_Price'].values[0])
                    # Tính toán DCA
                    total_q = old_q + new_qty
                    avg_e = ((old_q * old_e) + (new_qty * new_prc)) / total_q if total_q > 0 else 0
                    
                    cell = sheet.find(coin_sel)
                    sheet.update(f"B{cell.row}:C{cell.row}", [[total_q, avg_e]])
                else:
                    sheet.append_row([coin_sel, new_qty, new_prc])
                st.success(f"Đã cộng dồn vị thế {coin_sel}")
                st.rerun()
        
        st.divider()
        time_frame = st.select_slider("Khung thời gian Kháng cự/Hỗ trợ (Ngày)", options=[7, 14, 30, 90, 180], value=30)

    # Lấy giá & Quét kỹ thuật
    tickers = yf.Tickers(" ".join([cfg['symbol'] for cfg in RWA_CONFIG.values()]))
    data_final = []
    total_val, total_invest = 0, 0

    for coin, cfg in RWA_CONFIG.items():
        try: cp = tickers.tickers[cfg['symbol']].fast_info['last_price']
        except: cp = 0.0
        
        sup, res = get_tech_levels(cfg['symbol'], time_frame)
        user_data = df_holdings[df_holdings['Coin'] == coin] if not df_holdings.empty else pd.DataFrame()
        
        h = float(user_data['Holdings'].values[0]) if not user_data.empty else 0.0
        e = float(user_data['Entry_Price'].values[0]) if not user_data.empty else 0.0
        
        val = cp * h
        total_val += val
        total_invest += (e * h)
        pnl = ((cp / e) - 1) * 100 if e > 0 else 0.0
        
        # Logic trạng thái thông minh
        if cp >= res * 0.98: st_txt = "🔴 CHẠM KHÁNG CỰ"
        elif cp <= sup * 1.02: st_txt = "🟢 CHẠM HỖ TRỢ"
        elif cfg['v2'][0] <= cp <= cfg['v2'][1]: st_txt = "🔥 VÙNG GOM 2"
        elif cfg['v1'][0] <= cp <= cfg['v1'][1]: st_txt = "✅ VÙNG GOM 1"
        else: st_txt = "⌛ Đang quan sát"

        data_final.append({
            "Coin": coin,
            "Giá Hiện Tại": cp,
            "Trạng Thái": st_txt,
            f"Hỗ Trợ ({time_frame}d)": sup,
            f"Kháng Cự ({time_frame}d)": res,
            "Giá Vốn (Avg)": e,
            "Lời/Lỗ (%)": pnl,
            "Giá Trị ($)": val,
            "Kỳ vọng": f"x{cfg['ath']/cp:.1f}" if cp > 0 else "0"
        })

    # TOP METRICS
    c1, c2, c3 = st.columns(3)
    c1.metric("TỔNG TÀI SẢN", f"${total_val:,.2f}")
    c2.metric("LỜI / LỖ TỔNG", f"${(total_val - total_invest):,.2f}", f"{((total_val/total_invest)-1)*100 if total_invest > 0 else 0:.1f}%")
    c3.metric("VỐN ĐÃ GIẢI NGÂN", f"${total_invest:,.2f}")

    st.subheader("📡 Central Intelligence Board")
    df_res = pd.DataFrame(data_final)

    # Style bảng chuyên nghiệp
    def style_elite(row):
        styles = [''] * len(row)
        idx_st = df_res.columns.get_loc("Trạng Thái")
        if "HỖ TRỢ" in row["Trạng Thái"] or "GOM" in row["Trạng Thái"]:
            styles[idx_st] = 'background-color: #155724; color: white'
        elif "KHÁNG CỰ" in row["Trạng Thái"]:
            styles[idx_st] = 'background-color: #721c24; color: white'
        return styles

    st.dataframe(
        df_res.style.apply(style_elite, axis=1).format({
            "Giá Hiện Tại": "${:.3f}", "Giá Vốn (Avg)": "${:.3f}",
            f"Hỗ Trợ ({time_frame}d)": "${:.3f}", f"Kháng Cự ({time_frame}d)": "${:.3f}",
            "Lời/Lỗ (%)": "{:.1f}%", "Giá Trị ($)": "${:,.2f}"
        }),
        use_container_width=True, hide_index=True
    )

except Exception as e:
    st.error(f"Lỗi: {e}")
