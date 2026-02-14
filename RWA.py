import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

# --- CẤU HÌNH CHIẾN LƯỢC ---
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

# --- XỬ LÝ LOGIC ---
def get_status(price, v1, v2):
    if price is None: return "⌛ Đang tải..."
    if v2[0] <= price <= v2[1]: return "🔥 VÙNG GOM 2"
    if v1[0] <= price <= v1[1]: return "✅ VÙNG GOM 1"
    if price < v2[0]: return "⚠️ GIÁ CỰC RẺ"
    return "⌛ Đang quan sát"

# --- GIAO DIỆN PREMIUM ---
st.set_page_config(page_title="RWA Command Center Pro", layout="wide")

# CSS để Dashboard trông "xịn" hơn
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e4259; }
    div[data-testid="stExpander"] { border: none !important; box-shadow: none !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ RWA Iron Hand Command Center - 2026")
st.caption("Tầm nhìn dài hạn cho chị Hân và bé Uyên Nghi - Thiết lập bởi Công (Sales Manager)")

try:
    sheet, df_holdings = load_data()
    
    # Sidebar nhập liệu tinh gọn
    with st.sidebar:
        st.header("📥 Cập nhật danh mục")
        with st.form("update_form"):
            coin_select = st.selectbox("Chọn đồng coin", list(RWA_CONFIG.keys()))
            new_hold = st.number_input("Số lượng", min_value=0.0, step=0.1)
            new_entry = st.number_input("Giá vốn trung bình ($)", min_value=0.0, step=0.01)
            new_target = st.number_input("Giá mục tiêu ($)", min_value=0.0, step=0.01)
            if st.form_submit_button("LƯU LÊN CLOUD"):
                if not df_holdings.empty and coin_select in df_holdings['Coin'].values:
                    cell = sheet.find(coin_select)
                    sheet.update(f"B{cell.row}:D{cell.row}", [[new_hold, new_entry, new_target]])
                else:
                    sheet.append_row([coin_select, new_hold, new_entry, new_target])
                st.success("Đã cập nhật!")
                st.rerun()

    # Lấy giá thị trường (Tối ưu gọi 1 lần)
    symbols = [cfg['symbol'] for cfg in RWA_CONFIG.values()]
    prices_raw = yf.download(symbols, period="1d", interval="1m", progress=False)['Close']

    data_display = []
    total_value = 0
    total_profit = 0

    for coin, cfg in RWA_CONFIG.items():
        curr_price = float(prices_raw[cfg['symbol']].iloc[-1]) if not prices_raw[cfg['symbol']].empty else 0.0
        user_data = df_holdings[df_holdings['Coin'] == coin] if not df_holdings.empty else pd.DataFrame()
        
        hold = float(user_data['Holdings'].values[0]) if not user_data.empty else 0.0
        entry = float(user_data['Entry_Price'].values[0]) if not user_data.empty else 0.0
        
        val = curr_price * hold
        total_value += val
        pnl_val = (curr_price - entry) * hold if entry > 0 else 0.0
        total_profit += pnl_val
        pnl_pct = ((curr_price / entry) - 1) * 100 if entry > 0 else 0.0
        
        data_display.append({
            "Coin": coin,
            "Giá Hiện Tại": curr_price,
            "Trạng Thái": get_status(curr_price, cfg['v1'], cfg['v2']),
            "Vùng Gom 1": f"{cfg['v1'][0]}-{cfg['v1'][1]}",
            "Vùng Gom 2": f"{cfg['v2'][0]}-{cfg['v2'][1]}",
            "Giá Vốn": entry,
            "Lời/Lỗ (%)": pnl_pct,
            "Giá Trị ($)": val,
            "Kỳ vọng": f"x{cfg['ath']/curr_price:.1f}" if curr_price > 0 else "0"
        })

    # Hiển thị Top Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("TỔNG TÀI SẢN (USDT)", f"${total_value:,.2f}")
    col2.metric("LỜI / LỖ TỔNG", f"${total_profit:,.2f}", f"{ (total_profit/(total_value-total_profit)*100) if (total_value-total_profit)>0 else 0:.1f}%")
    col3.metric("MÃ ĐANG THEO DÕI", len(RWA_CONFIG))

    st.divider()

    # Bảng dữ liệu chính với Style chuyên nghiệp
    df_final = pd.DataFrame(data_display)

    def color_df(row):
        cols = [''] * len(row)
        if 'GOM' in str(row['Trạng Thái']):
            cols[df_final.columns.get_loc('Trạng Thái')] = 'background-color: #155724; color: white'
        if row['Lời/Lỗ (%)'] > 0:
            cols[df_final.columns.get_loc('Lời/Lỗ (%)')] = 'color: #28a745; font-weight: bold'
        elif row['Lời/Lỗ (%)'] < 0:
            cols[df_final.columns.get_loc('Lời/Lỗ (%)')] = 'color: #dc3545; font-weight: bold'
        return cols

    st.subheader("📡 Central Action Board")
    st.dataframe(
        df_final.style.apply(color_df, axis=1).format({
            "Giá Hiện Tại": "${:.3f}",
            "Giá Vốn": "${:.3f}",
            "Lời/Lỗ (%)": "{:.1f}%",
            "Giá Trị ($)": "${:,.2f}"
        }),
        use_container_width=True,
        hide_index=True
    )

except Exception as e:
    st.error(f"Lỗi vận hành: {e}")
    st.info(f"💡 Đừng quên Share quyền Editor cho: {st.secrets['gcp_service_account']['client_email']}")
