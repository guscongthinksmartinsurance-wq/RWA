import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CẤU HÌNH ---
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

def get_gsheet_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(credentials)

def load_data():
    client = get_gsheet_client()
    sh = client.open(ST_FILE_NAME)
    
    # Kiểm tra tab Holdings tồn tại chưa
    try:
        worksheet = sh.worksheet(ST_SHEET_NAME)
    except:
        worksheet = sh.add_worksheet(title=ST_SHEET_NAME, rows="100", cols="20")
        worksheet.append_row(HEADERS)
    
    data = worksheet.get_all_records()
    if not data: # Nếu sheet có tiêu đề nhưng chưa có dữ liệu
        return worksheet, pd.DataFrame(columns=HEADERS)
    return worksheet, pd.DataFrame(data)

# --- 2. GIAO DIỆN ---
st.set_page_config(page_title="RWA Pro Dashboard", layout="wide")
st.title("🚀 RWA Command Center Pro - 2026")

try:
    sheet, df_holdings = load_data()
    
    # Sidebar nhập liệu
    st.sidebar.header("📥 Cập nhật danh mục")
    with st.sidebar.form("update_form"):
        coin_select = st.selectbox("Chọn đồng coin", list(RWA_CONFIG.keys()))
        new_hold = st.number_input("Số lượng nắm giữ", min_value=0.0, step=0.1)
        new_entry = st.number_input("Giá vốn trung bình ($)", min_value=0.0, step=0.01)
        new_target = st.number_input("Giá mục tiêu chốt lời ($)", min_value=0.0, step=0.01)
        submit = st.form_submit_button("Cập nhật lên Cloud")
        
        if submit:
            # Kiểm tra nếu đồng coin đã tồn tại thì update, chưa thì thêm mới
            if not df_holdings.empty and coin_select in df_holdings['Coin'].values:
                cell = sheet.find(coin_select)
                sheet.update(f"B{cell.row}:D{cell.row}", [[new_hold, new_entry, new_target]])
            else:
                sheet.append_row([coin_select, new_hold, new_entry, new_target])
            st.sidebar.success(f"Đã lưu {coin_select} thành công!")
            st.rerun()

    # Lấy giá thị trường
    symbols = [cfg['symbol'] for cfg in RWA_CONFIG.values()]
    prices_raw = yf.download(symbols, period="1d", interval="1m", progress=False)['Close']

    data_display = []
    total_market_value = 0

    for coin, cfg in RWA_CONFIG.items():
        curr_price = float(prices_raw[cfg['symbol']].iloc[-1])
        
        # Tìm dữ liệu người dùng trong df_holdings
        user_data = df_holdings[df_holdings['Coin'] == coin] if not df_holdings.empty else pd.DataFrame()
        hold = float(user_data['Holdings'].values[0]) if not user_data.empty else 0.0
        entry = float(user_data['Entry_Price'].values[0]) if not user_data.empty else 0.0
        
        val = curr_price * hold
        total_market_value += val
        pnl = ((curr_price / entry) - 1) * 100 if entry > 0 else 0.0
        
        data_display.append({
            "Coin": coin,
            "Giá Hiện Tại": f"${curr_price:.3f}",
            "Giá Vốn (Avg)": f"${entry:.3f}",
            "Lời/Lỗ (%)": pnl,
            "Số Lượng": hold,
            "Giá Trị ($)": val,
            "Đỉnh ATH": f"${cfg['ath']:.1f}",
            "Kỳ vọng": f"x{cfg['ath']/curr_price:.1f}"
        })

    st.header(f"💰 Tổng Tài Sản: ${total_market_value:,.2f}")
    st.table(pd.DataFrame(data_display).style.format({"Lời/Lỗ (%)": "{:.1f}%", "Giá Trị ($)": "${:,.2f}"}))

except Exception as e:
    st.error(f"Lỗi: {e}")
    st.info("💡 Anh hãy Share quyền cho: tmc-assistant@caramel-hallway-481517-q8.iam.gserviceaccount.com")
