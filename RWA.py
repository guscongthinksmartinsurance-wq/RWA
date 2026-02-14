import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

# --- CHIẾN LƯỢC CHI TIẾT ---
ST_FILE_NAME = "TMC-Sales-Assistant"
ST_SHEET_NAME = "Holdings"
HEADERS = ["Coin", "Holdings", "Entry_Price"]

RWA_STRATEGY = {
    'LINK':   {'symbol': 'LINK-USD',   'target_w': 35, 'v1': (7.9, 8.3), 'v2': (6.5, 7.2), 'ath': 52.8}, 
    'ONDO':   {'symbol': 'ONDO-USD',   'target_w': 20, 'v1': (0.22, 0.24), 'v2': (0.15, 0.18), 'ath': 2.14},
    'QNT':    {'symbol': 'QNT-USD',    'target_w': 15, 'v1': (58.0, 62.0), 'v2': (45.0, 50.0), 'ath': 428.0},
    'PENDLE': {'symbol': 'PENDLE-USD', 'target_w': 10, 'v1': (1.05, 1.15), 'v2': (0.75, 0.90), 'ath': 7.52},
    'SYRUP':  {'symbol': 'MPL-USD',    'target_w': 10, 'v1': (0.21, 0.25), 'v2': (0.14, 0.17), 'ath': 2.10}, 
    'CFG':    {'symbol': 'CFG-USD',    'target_w': 10, 'v1': (0.32, 0.36), 'v2': (0.22, 0.26), 'ath': 2.59}
}

# --- KẾT NỐI AN TOÀN ---
@st.cache_resource
def get_gsheet_client():
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(Credentials.from_service_account_info(creds_info, scopes=scope))

def load_data():
    client = get_gsheet_client()
    try:
        sh = client.open(ST_FILE_NAME)
        ws = sh.worksheet(ST_SHEET_NAME)
    except:
        sh = client.open(ST_FILE_NAME)
        ws = sh.add_worksheet(title=ST_SHEET_NAME, rows="100", cols="10")
        ws.append_row(HEADERS)
    df = pd.DataFrame(ws.get_all_records())
    if df.empty or 'Coin' not in df.columns:
        df = pd.DataFrame(columns=HEADERS)
    return ws, df

def get_levels(symbol, days):
    try:
        hist = yf.download(symbol, period=f"{days}d", progress=False)
        if hist.empty: return 0.0, 0.0
        return float(hist['Low'].min()), float(hist['High'].max())
    except: return 0.0, 0.0

# --- GIAO DIỆN PREMIUM ---
st.set_page_config(page_title="RWA Elite Terminal", layout="wide")

st.markdown("""
    <style>
    /* Tổng thể */
    .main { background-color: #0e1117; }
    
    /* Asset Card */
    .asset-card { 
        background: linear-gradient(145deg, #161b22, #0d1117); 
        padding: 30px; border-radius: 20px; border: 1px solid #30363d; 
        margin-bottom: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    
    /* Typography */
    .coin-name { font-size: 32px !important; font-weight: 800; color: #58a6ff; letter-spacing: 1px; }
    .price-large { font-size: 36px !important; font-weight: 900; color: #ffffff; text-shadow: 0 0 10px rgba(255,255,255,0.2); }
    .data-label { color: #8b949e; font-size: 13px; text-transform: uppercase; font-weight: 600; margin-bottom: 5px; }
    .data-value { font-size: 22px; font-weight: 700; color: #f0f6fc; }
    
    /* Trạng thái */
    .rec-box { padding: 15px; border-radius: 12px; font-weight: bold; margin-top: 20px; border-left: 8px solid; font-size: 16px; }
    
    /* Progress Bar */
    .progress-bg { background: #30363d; border-radius: 20px; height: 12px; width: 100%; margin: 15px 0; overflow: hidden; }
    .progress-fill { background: linear-gradient(90deg, #1f6feb, #58a6ff); height: 100%; border-radius: 20px; }
    
    /* Metrics Top */
    [data-testid="stMetricValue"] { font-size: 40px !important; font-weight: 900 !important; color: #ffffff !important; }
    </style>
    """, unsafe_allow_html=True)

try:
    ws, df_holdings = load_data()
    
    with st.sidebar:
        st.header("🏢 TRẠM DCA")
        with st.form("dca"):
            c_sel = st.selectbox("Chọn Coin", list(RWA_STRATEGY.keys()))
            q_add = st.number_input("Số lượng mua", min_value=0.0, step=0.1)
            p_add = st.number_input("Giá lúc mua ($)", min_value=0.0, step=0.01)
            if st.form_submit_button("XÁC NHẬN LỆNH"):
                row = df_holdings[df_holdings['Coin'] == c_sel]
                old_q = float(row['Holdings'].values[0]) if not row.empty else 0
                old_e = float(row['Entry_Price'].values[0]) if not row.empty else 0
                new_q = old_q + q_add
                new_e = ((old_q * old_e) + (q_add * p_add)) / new_q if new_q > 0 else 0
                if not row.empty:
                    cell = ws.find(c_sel)
                    ws.update(f"B{cell.row}:C{cell.row}", [[new_q, new_e]])
                else: ws.append_row([c_sel, new_q, new_e])
                st.rerun()
        days_sel = st.select_slider("Khung Kỹ thuật (Ngày)", options=[7, 30, 90], value=30)

    # XỬ LÝ DỮ LIỆU
    tickers = yf.Tickers(" ".join([cfg['symbol'] for cfg in RWA_STRATEGY.values()]))
    processed = []
    total_val, total_invest = 0, 0

    current_prices = {}
    for coin, cfg in RWA_STRATEGY.items():
        try: current_prices[coin] = float(tickers.tickers[cfg['symbol']].fast_info['last_price'])
        except: current_prices[coin] = 0.0
        h = float(df_holdings[df_holdings['Coin'] == coin]['Holdings'].values[0]) if not df_holdings[df_holdings['Coin'] == coin].empty else 0.0
        total_val += (current_prices[coin] * h)

    for coin, cfg in RWA_STRATEGY.items():
        cp = current_prices[coin]
        sup, res = get_levels(cfg['symbol'], days_sel)
        user_row = df_holdings[df_holdings['Coin'] == coin] if not df_holdings.empty else pd.DataFrame()
        h, e = (float(user_row['Holdings'].values[0]), float(user_row['Entry_Price'].values[0])) if not user_row.empty else (0.0, 0.0)
        
        val = cp * h
        total_invest += (e * h)
        pnl = ((cp / e) - 1) * 100 if e > 0 else 0
        real_w = (val / total_val * 100) if total_val > 0 else 0
        fill_pct = min(real_w / cfg['target_w'], 1.0) * 100

        # LOGIC TƯ VẤN ĐỊNH LƯỢNG
        if cp > 0:
            if cp <= sup * 1.02: rec, col, reason = "NÊN MUA MẠNH", "#238636", f"Giá sát Hỗ trợ cứng {days_sel}d (${sup:.3f}). Cơ hội DCA."
            elif cfg['v2'][0] <= cp <= cfg['v2'][1]: rec, col, reason = "VÙNG GOM 2", "#2ea043", "Giá cực tốt, thuộc vùng gom chiến lược 2."
            elif cfg['v1'][0] <= cp <= cfg['v1'][1]: rec, col, reason = "VÙNG GOM 1", "#d29922", "Giá hợp lý, thuộc vùng gom chiến lược 1."
            elif cp >= res * 0.98: rec, col, reason = "KHÁNG CỰ - ĐỢI", "#f85149", f"Giá sát Kháng cự {days_sel}d (${res:.3f}). Rủi ro đu đỉnh."
            else: rec, col, reason = "QUAN SÁT", "#8b949e", "Giá trung lập, chưa có tín hiệu rõ ràng."
        else: rec, col, reason = "CHỜ DỮ LIỆU", "#30363d", "Đang đồng bộ dữ liệu thị trường..."

        processed.append({
            "coin": coin, "cp": cp, "val": val, "h": h, "e": e, "pnl": pnl, 
            "rec": rec, "col": col, "reason": reason, "ath": cfg['ath'],
            "sup": sup, "res": res, "tw": cfg['target_w'], "rw": real_w, "fill": fill_pct
        })

    # UI CHÍNH
    st.title("🛡️ RWA Intelligence Terminal - 2026")
    
    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("TỔNG TÀI SẢN (USDT)", f"${total_val:,.2f}")
    m_col2.metric("LỜI / LỖ TỔNG", f"${(total_val - total_invest):,.2f}", f"{((total_val/total_invest)-1)*100 if total_invest > 0 else 0:.1f}%")
    m_col3.metric("KHUNG CHIẾN THUẬT", f"{days_sel} NGÀY")

    st.markdown("<br>", unsafe_allow_html=True)

    for d in processed:
        st.markdown(f"""
        <div class="asset-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <div style="width: 50%;">
                    <div class="coin-name">{d['coin']}</div>
                    <div style="font-size: 14px; color: #8b949e; margin-top: 5px; font-weight: 500;">
                        Tiến độ mục tiêu: <b>{d['rw']:.1f}%</b> / {d['tw']}% 
                    </div>
                    <div class="progress-bg"><div class="progress-fill" style="width: {d['fill']}%;"></div></div>
                </div>
                <div style="text-align: right;">
                    <div class="price-large">${d['cp']:.3f}</div>
                    <div style="color:{'#3fb950' if d['pnl']>=0 else '#f85149'}; font-size: 20px; font-weight: 800; margin-top: 5px;">
                        {'+' if d['pnl']>=0 else ''}{d['pnl']:.1f}%
                    </div>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; text-align: center; background: rgba(255,255,255,0.03); padding: 20px; border-radius: 12px;">
                <div><div class="data-label">Vốn Avg</div><div class="data-value">${d['e']:.3f}</div></div>
                <div><div class="data-label">🛡️ Hỗ trợ</div><div class="data-value" style="color:#3fb950">${d['sup']:.3f}</div></div>
                <div><div class="data-label">⛔ Kháng cự</div><div class="data-value" style="color:#f85149">${d['res']:.3f}</div></div>
                <div><div class="data-label">Đỉnh ATH</div><div class="data-value" style="color:#d29922">${d['ath']}</div></div>
            </div>
            
            <div class="rec-box" style="border-left-color: {d['col']}; background: {d['col']}10; color: {d['col']};">
                PHÂN TÍCH HÀNH VI: {d['rec']} <br>
                <span style="font-size: 14px; font-weight: 400; color: #f0f6fc; opacity: 0.9;">Hệ thống: {d['reason']}</span>
            </div>
            
            <div style="text-align: right; margin-top: 15px; font-size: 16px; font-weight: 600; color: #8b949e;">
                Giá trị nắm giữ: <span style="color: #ffffff;">${d['val']:,.2f} USDT</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

except Exception as e:
    st.info("Chào anh Công! Hãy thực hiện lệnh nhập DCA đầu tiên để hệ thống khởi chạy dữ liệu chuyên nghiệp.")
