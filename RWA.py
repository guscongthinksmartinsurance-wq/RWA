import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
import numpy as np

# --- 1. CẤU HÌNH HỆ THỐNG ---
ST_FILE_NAME = "TMC-Sales-Assistant"
ST_SHEET_NAME = "Holdings"

RWA_CONFIG = {
    'LINK':   {'symbol': 'LINK-USD',   'v1': (7.9, 8.3), 'v2': (6.5, 7.2), 'ath': 52.8}, 
    'ONDO':   {'symbol': 'ONDO-USD',   'v1': (0.22, 0.24), 'v2': (0.15, 0.18), 'ath': 2.14},
    'QNT':    {'symbol': 'QNT-USD',    'v1': (58.0, 62.0), 'v2': (45.0, 50.0), 'ath': 428.0},
    'PENDLE': {'symbol': 'PENDLE-USD', 'v1': (1.05, 1.15), 'v2': (0.75, 0.90), 'ath': 7.52},
    'SYRUP':  {'symbol': 'MPL-USD',    'v1': (0.21, 0.25), 'v2': (0.14, 0.17), 'ath': 2.10}, 
    'CFG':    {'symbol': 'CFG-USD',    'v1': (0.32, 0.36), 'v2': (0.22, 0.26), 'ath': 2.59}
}

# Kết nối Google Sheets
def get_gsheet_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(credentials)

def load_data():
    client = get_gsheet_client()
    sheet = client.open(ST_FILE_NAME).worksheet(ST_SHEET_NAME)
    df = pd.DataFrame(sheet.get_all_records())
    return sheet, df

# Tính toán Hỗ trợ/Kháng cự đơn giản (dựa trên 30 ngày)
def get_tech_levels(symbol):
    try:
        hist = yf.download(symbol, period="30d", interval="1d", progress=False)
        support = hist['Low'].min()
        resistance = hist['High'].max()
        return round(float(support), 3), round(float(resistance), 3)
    except:
        return 0, 0

# --- 2. GIAO DIỆN ---
st.set_page_config(page_title="RWA Pro Dashboard", layout="wide")
st.title("🚀 RWA Command Center Pro - 2026")

try:
    sheet, df_holdings = load_data()
    
    # --- SIDEBAR: NHẬP LIỆU TRỰC TIẾP ---
    st.sidebar.header("📥 Cập nhật danh mục")
    with st.sidebar.form("update_form"):
        coin_select = st.selectbox("Chọn đồng coin", list(RWA_CONFIG.keys()))
        new_hold = st.number_input("Số lượng nắm giữ", min_value=0.0)
        new_entry = st.number_input("Giá vốn trung bình ($)", min_value=0.0)
        new_target = st.number_input("Giá mục tiêu chốt lời ($)", min_value=0.0)
        submit = st.form_submit_button("Cập nhật lên Cloud")
        
        if submit:
            # Tìm dòng để update hoặc thêm mới
            cell = sheet.find(coin_select)
            if cell:
                sheet.update(f"B{cell.row}:D{cell.row}", [[new_hold, new_entry, new_target]])
            else:
                sheet.append_row([coin_select, new_hold, new_entry, new_target])
            st.sidebar.success(f"Đã cập nhật {coin_select}!")
            st.rerun()

    # --- MAIN BOARD: PHÂN TÍCH & HIỂN THỊ ---
    st.subheader("📊 Bảng Theo Dõi Chuyên Nghiệp")
    
    data_display = []
    total_market_value = 0
    
    # Lấy giá toàn bộ để tránh bị chặn
    symbols = [cfg['symbol'] for cfg in RWA_CONFIG.values()]
    prices_raw = yf.download(symbols, period="1d", interval="1m", progress=False)['Close']

    for coin, cfg in RWA_CONFIG.items():
        curr_price = prices_raw[cfg['symbol']].iloc[-1]
        sup, res = get_tech_levels(cfg['symbol'])
        
        # Lấy data từ Google Sheet
        user_row = df_holdings[df_holdings['Coin'] == coin]
        hold = user_row['Holdings'].values[0] if not user_row.empty else 0
        entry = user_row['Entry_Price'].values[0] if not user_row.empty else 0
        target = user_row['Target_Price'].values[0] if not user_row.empty else 0
        
        val = curr_price * hold
        total_market_value += val
        
        pnl = ((curr_price / entry) - 1) * 100 if entry > 0 else 0
        upside = (cfg['ath'] / curr_price) if curr_price > 0 else 0
        
        data_display.append({
            "Coin": coin,
            "Giá Hiện Tại": f"${curr_price:.3f}",
            "Giá Vốn (Avg)": f"${entry:.3f}",
            "Lời/Lỗ (%)": pnl,
            "Hỗ Trợ": f"${sup:.3f}",
            "Kháng Cự": f"${res:.3f}",
            "Giá Trị ($)": val,
            "Đỉnh ATH": f"${cfg['ath']:.1f}",
            "Kỳ vọng ATH": f"x{upside:.1f}"
        })

    df_final = pd.DataFrame(data_display)

    # Hiển thị Metric tổng quát
    c1, c2, c3 = st.columns(3)
    c1.metric("Tổng Tài Sản RWA", f"${total_market_value:,.2f}")
    c2.metric("Số lượng mã", len(df_holdings))
    c3.info("💡 Mẹo: Nhập giá vốn bên trái để tính Lời/Lỗ")

    # Định dạng màu sắc cho bảng
    def color_pnl(val):
        color = '#155724' if val > 0 else '#721c24'
        return f'color: {color}; font-weight: bold'

    st.table(df_final.style.format({"Lời/Lỗ (%)": "{:.1f}%", "Giá Trị ($)": "${:,.2f}"}).applymap(color_pnl, subset=['Lời/Lỗ (%)']))

except Exception as e:
    st.error(f"Lỗi kết nối: {e}")
    st.info("Anh kiểm tra lại: 1. Đã share quyền Editor cho email Service Account chưa? 2. Tên file/worksheet đúng chưa?")
