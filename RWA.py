import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

# --- CẤU HÌNH ---
ST_FILE_NAME = "TMC-Sales-Assistant"
ST_SHEET_NAME = "Holdings"
HEADERS = ["Coin", "Holdings", "Entry_Price", "Target_Price"]

RWA_CONFIG = {
    'LINK':   {'symbol': 'LINK-USD',   'v1': (7.9, 8.3), 'v2': (6.5, 7.2), 'ath': 52.8}, 
    'ONDO':   {'symbol': 'ONDO-USD',   'v1': (0.22, 0.24), 'v2': (0.15, 0.18), 'ath': 2.14},
    'QNT':    {'symbol': 'QNT-USD',    'v1': (58.0, 62.0), 'v2': (45.0, 50.0), 'ath': 428.0},
    'PENDLE': {'symbol': 'PENDLE-USD', 'v1': (1.05, 1.15), 'v2': (0.75, 0.90), 'ath': 7.52},
    'SYRUP':  {'symbol': 'MPL-USD',    'v1': (0.21, 0.25), 'v2': (0.14, 0.17), 'ath': 2.10}, 
    'CFG':    {'symbol': 'CFG-USD',    'v1': (0.32, 0.36), 'v2': (0.22, 0.26), 'ath': 2.59}
}

# --- KẾT NỐI DỮ LIỆU ---
@st.cache_resource
def get_gsheet_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(credentials)

def load_data():
    client = get_gsheet_client()
    sh = client.open(ST_FILE_NAME)
    try:
        worksheet = sh.worksheet(ST_SHEET_NAME)
    except:
        worksheet = sh.add_worksheet(title=ST_SHEET_NAME, rows="100", cols="20")
        worksheet.append_row(HEADERS)
    data = worksheet.get_all_records()
    return worksheet, pd.DataFrame(data) if data else pd.DataFrame(columns=HEADERS)

def get_tech_levels(symbol):
    try:
        hist = yf.download(symbol, period="30d", interval="1d", progress=False)
        return round(float(hist['Low'].min()), 3), round(float(hist['High'].max()), 3)
    except: return 0.0, 0.0

# --- GIAO DIỆN ---
st.set_page_config(page_title="RWA Command Center Pro", layout="wide")

try:
    sheet, df_holdings = load_data()
    
    with st.sidebar:
        st.header("➕ Thêm lệnh mua mới (DCA)")
        with st.form("dca_form"):
            coin_select = st.selectbox("Chọn đồng coin", list(RWA_CONFIG.keys()))
            buy_amount = st.number_input("Số lượng vừa mua thêm", min_value=0.0, step=0.1)
            buy_price = st.number_input("Giá khớp lệnh ($)", min_value=0.0, step=0.01)
            target_p = st.number_input("Cập nhật giá mục tiêu ($)", min_value=0.0, step=0.01)
            
            if st.form_submit_button("XÁC NHẬN CỘNG DỒN VỊ THẾ"):
                user_row = df_holdings[df_holdings['Coin'] == coin_select]
                if not user_row.empty:
                    old_h = float(user_row['Holdings'].values[0])
                    old_e = float(user_row['Entry_Price'].values[0])
                    
                    # Công thức tính Giá vốn bình quân (DCA)
                    new_total_hold = old_h + buy_amount
                    new_avg_entry = ((old_h * old_e) + (buy_amount * buy_price)) / new_total_hold if new_total_hold > 0 else 0
                    
                    cell = sheet.find(coin_select)
                    sheet.update(f"B{cell.row}:D{cell.row}", [[new_total_hold, new_avg_entry, target_p]])
                else:
                    sheet.append_row([coin_select, buy_amount, buy_price, target_p])
                
                st.success("Đã tự động cộng dồn tài sản!")
                st.rerun()

    # LẤY GIÁ & PHÂN TÍCH
    tickers = yf.Tickers(" ".join([cfg['symbol'] for cfg in RWA_CONFIG.values()]))
    data_display = []
    total_market_val = 0
    total_invested = 0

    for coin, cfg in RWA_CONFIG.items():
        try: curr_p = tickers.tickers[cfg['symbol']].fast_info['last_price']
        except: curr_p = 0.0
        
        sup, res = get_tech_levels(cfg['symbol'])
        user_data = df_holdings[df_holdings['Coin'] == coin] if not df_holdings.empty else pd.DataFrame()
        
        hold = float(user_data['Holdings'].values[0]) if not user_data.empty else 0.0
        entry = float(user_data['Entry_Price'].values[0]) if not user_data.empty else 0.0
        
        val = curr_p * hold
        total_market_val += val
        total_invested += (entry * hold)
        pnl_pct = ((curr_p / entry) - 1) * 100 if entry > 0 else 0.0
        
        # Logic trạng thái vùng gom
        if res > 0 and curr_p >= res * 0.98: status = "⛔ KHÁNG CỰ (Bán?)"
        elif sup > 0 and curr_p <= sup * 1.02: status = "🛒 HỖ TRỢ (Mua!)"
        elif cfg['v2'][0] <= curr_p <= cfg['v2'][1]: status = "🔥 VÙNG GOM 2"
        elif cfg['v1'][0] <= curr_p <= cfg['v1'][1]: status = "✅ VÙNG GOM 1"
        else: status = "⌛ Đang quan sát"

        data_display.append({
            "Coin": coin,
            "Giá Hiện Tại": curr_p,
            "Trạng Thái": status,
            "Hỗ Trợ (30d)": sup,
            "Kháng Cự (30d)": res,
            "Giá Vốn (Avg)": entry,
            "Lời/Lỗ (%)": pnl_pct,
            "Giá Trị ($)": val,
            "Kỳ vọng": f"x{cfg['ath']/curr_p:.1f}" if curr_p > 0 else "0"
        })

    # METRICS
    c1, c2, c3 = st.columns(3)
    c1.metric("TỔNG TÀI SẢN (USDT)", f"${total_market_val:,.2f}")
    c2.metric("LỜI / LỖ TỔNG", f"${(total_market_val - total_invested):,.2f}", f"{((total_market_val/total_invested)-1)*100 if total_invested > 0 else 0:.1f}%")
    c3.metric("VỐN ĐÃ GIẢI NGÂN", f"${total_invested:,.2f}")

    st.subheader("📡 Central Action Board (Pro)")
    df_final = pd.DataFrame(data_display)

    def style_pro(row):
        styles = [''] * len(row)
        if 'HỖ TRỢ' in str(row['Trạng Thái']) or 'GOM' in str(row['Trạng Thái']):
            styles[df_final.columns.get_loc('Trạng Thái')] = 'background-color: #155724; color: white'
        if 'KHÁNG CỰ' in str(row['Trạng Thái']):
            styles[df_final.columns.get_loc('Trạng Thái')] = 'background-color: #721c24; color: white'
        return styles

    st.dataframe(
        df_final.style.apply(style_pro, axis=1).format({
            "Giá Hiện Tại": "${:.3f}", "Giá Vốn (Avg)": "${:.3f}",
            "Hỗ Trợ (30d)": "${:.3f}", "Kháng Cự (30d)": "${:.3f}",
            "Lời/Lỗ (%)": "{:.1f}%", "Giá Trị ($)": "${:,.2f}"
        }),
        use_container_width=True, hide_index=True
    )

except Exception as e:
    st.error(f"Lỗi hệ thống: {e}")
