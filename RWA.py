import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
import requests
import feedparser
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components
import plotly.graph_objects as go

# --- 1. CHIẾN LƯỢC RWA ---
RWA_STRATEGY = {
    'LINK':   {'symbol': 'LINK-USD',   'target_w': 35, 'v1': (7.9, 8.3), 'v2': (6.5, 7.2), 'ath': 52.8}, 
    'ONDO':   {'symbol': 'ONDO-USD',   'target_w': 20, 'v1': (0.22, 0.24), 'v2': (0.15, 0.18), 'ath': 2.14},
    'QNT':    {'symbol': 'QNT-USD',    'target_w': 15, 'v1': (58.0, 62.0), 'v2': (45.0, 50.0), 'ath': 428.0},
    'PENDLE': {'symbol': 'PENDLE-USD', 'target_w': 10, 'v1': (1.05, 1.15), 'v2': (0.75, 0.90), 'ath': 7.52},
    'SYRUP':  {'symbol': 'MPL-USD',    'target_w': 10, 'v1': (0.21, 0.25), 'v2': (0.14, 0.17), 'ath': 2.10}, 
    'CFG':    {'symbol': 'CFG-USD',    'target_w': 10, 'v1': (0.32, 0.36), 'v2': (0.22, 0.26), 'ath': 2.59}
}

# --- 2. BỘ NÃO PHÂN TÍCH ---
def analyze_whale_logic(df, cp, days_sel, has_holdings):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi = (100 - (100 / (1 + (gain/(loss + 1e-10))))).iloc[-1]
    vol = df['Volume'].iloc[-1] / (df['Volume'].rolling(10).mean().iloc[-1] + 1e-10)
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    std20 = df['Close'].rolling(20).std().iloc[-1]
    lower_b, upper_b = ma20 - (2 * std20), ma20 + (2 * std20)
    sup = float(df['Low'].rolling(window=days_sel).min().iloc[-1])
    res = float(df['High'].rolling(window=days_sel).max().iloc[-1])
    
    score = 0
    checks = []
    if rsi < 35: score += 1; checks.append(f"✅ RSI thấp ({rsi:.1f})")
    else: checks.append(f"❌ RSI ({rsi:.1f})")
    if cp <= lower_b: score += 1; checks.append(f"✅ BB: Dưới biên")
    else: checks.append(f"❌ BB: Vùng giữa")
    dist_s = ((cp/sup)-1)*100
    if dist_s < 4: score += 1; checks.append(f"✅ Sát Hỗ trợ (${sup:.2f})")
    else: checks.append(f"❌ Cách Support {dist_s:.1f}%")
    if vol > 1.5: score += 1; checks.append(f"🐳 Whale Gom (Vol x{vol:.1f})")
    else: checks.append(f"❌ Vol yếu (x{vol:.1f})")

    if rsi > 70 or cp >= upper_b * 0.98: stt, col = "BÁN / CHỐT LỜI", "#f85149"
    elif score >= 3: stt, col = "MUA MẠNH", "#3fb950"
    elif score == 2: stt, col = ("DCA THÊM", "#1f6feb") if has_holdings else ("MUA THĂM DÒ", "#58a6ff")
    else: stt, col = "QUAN SÁT", "#8b949e"
    
    return rsi, vol, sup, res, stt, col, " | ".join(checks), float(df['High'].max()), cp*1.5, cp*2.0

@st.cache_resource
def get_gsheet_client():
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(Credentials.from_service_account_info(creds_info, scopes=scope))

def load_data():
    client = get_gsheet_client()
    sh = client.open("TMC-Sales-Assistant")
    ws = sh.worksheet("Holdings")
    df = pd.DataFrame(ws.get_all_records())
    # Đảm bảo cột Profit_Realized tồn tại và sạch
    if 'Profit_Realized' not in df.columns:
        ws.update('D1', [['Profit_Realized']])
        df['Profit_Realized'] = 0
    df['Profit_Realized'] = pd.to_numeric(df['Profit_Realized'], errors='coerce').fillna(0)
    df['Holdings'] = pd.to_numeric(df['Holdings'], errors='coerce').fillna(0)
    df['Entry_Price'] = pd.to_numeric(df['Entry_Price'], errors='coerce').fillna(0)
    return ws, df

# --- 3. UI CHÍNH ---
st.set_page_config(page_title="RWA Elite Terminal", layout="wide")
ws, df_holdings = load_data()

with st.sidebar:
    st.header("🏢 TỔNG TRẠM")
    base_budget = st.number_input("VỐN GỐC ĐẦU TƯ ($)", value=2000.0)
    st.divider()
    c_list = sorted(list(set(["BTC", "ETH", "SOL", "LINK", "ONDO", "QNT", "PENDLE", "CFG"] + df_holdings['Coin'].tolist())))
    coin_sel = st.selectbox("Chọn mã", ["+ Nhập mã mới..."] + c_list)
    final_coin = st.text_input("Mã mới").upper() if coin_sel == "+ Nhập mã mới..." else coin_sel
    with st.form("trade_v10_final"):
        q_trade = st.number_input("Số lượng", min_value=0.0)
        p_trade = st.number_input("Giá ($)", min_value=0.0)
        if st.form_submit_button("XÁC NHẬN"):
            if final_coin:
                row = df_holdings[df_holdings['Coin'] == final_coin]
                if not row.empty:
                    old_q, old_e = float(row['Holdings'].values[0]), float(row['Entry_Price'].values[0])
                    t_q = old_q + q_trade
                    a_e = ((old_q * old_e) + (q_trade * p_trade)) / t_q if t_q > 0 else 0
                    cell = ws.find(final_coin); ws.update(f"B{cell.row}:C{cell.row}", [[t_q, a_e]])
                else: ws.append_row([final_coin, q_trade, p_trade, 0])
                st.rerun()
    days_sel = st.select_slider("Khung Kỹ thuật", options=[7, 30, 90], value=30)

# DASHBOARD
all_coins = list(set(list(RWA_STRATEGY.keys()) + df_holdings['Coin'].tolist()))
tickers = yf.Tickers(" ".join([f"{c}-USD" for c in all_coins if c]))
total_val, total_invest = 0, 0
total_realized = float(df_holdings['Profit_Realized'].sum())

tab1_data, tab2_data, p_labels, p_values = [], [], [], []
for coin in all_coins:
    if not coin: continue
    try:
        symbol = f"{coin}-USD"
        df_h = tickers.tickers[symbol].history(period="60d")
        cp = float(tickers.tickers[symbol].fast_info['last_price'])
        u_row = df_holdings[df_holdings['Coin'] == coin]
        h, e = float(u_row['Holdings'].values[0]), float(u_row['Entry_Price'].values[0])
        rsi, vol, sup, res, stt, col, rs, ath_real, tp1, tp2 = analyze_whale_logic(df_h, cp, days_sel, h > 0)
        ath_val = RWA_STRATEGY[coin]['ath'] if coin in RWA_STRATEGY else ath_real
        invested = h * e; val = cp * h
        total_val += val; total_invest += invested
        card = {"coin": coin, "cp": cp, "stt": stt, "col": col, "rs": rs, "invested": invested, "e": e, "pnl": ((cp/e)-1)*100 if e>0 else 0, "sup": sup, "res": res, "ath": ath_val, "tp1": tp1, "tp2": tp2}
        if val > 0: p_labels.append(coin); p_values.append(val)
        if coin in RWA_STRATEGY:
            tw = RWA_STRATEGY[coin]['target_w']
            card.update({"tw": tw, "rw": (val/base_budget*100), "fill": min((val/base_budget*100)/tw, 1.0)*100})
            tab1_data.append(card)
        else: tab2_data.append(card)
    except: continue

# VIEW
cash_remain = float(base_budget) - float(total_invest) + total_realized
pnl_total = total_val - total_invest
p_labels.append("CASH"); p_values.append(max(0, cash_remain))
c1, c2 = st.columns([3, 1.2])
with c1:
    dash_html = f"""<div style="display:flex;gap:15px;margin-bottom:15px;"><div style="flex:1;background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;text-transform:uppercase;">Cash (Vốn + Lãi chốt)</div><div style="color:#58a6ff;font-size:42px;font-weight:900;">${cash_remain:,.0f}</div></div><div style="flex:1;background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;text-transform:uppercase;">PnL</div><div style="color:{'#3fb950' if pnl_total>=0 else '#f85149'};font-size:42px;font-weight:900;">${pnl_total:,.0f}</div></div></div><div style="background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;text-transform:uppercase;">Tổng Tài Sản</div><div style="color:white;font-size:48px;font-weight:900;">${(total_val + cash_remain):,.0f}</div></div>"""
    components.html(dash_html, height=320)
with c2:
    fig = go.Figure(data=[go.Pie(labels=p_labels, values=p_values, hole=.5)])
    fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), height=320, paper_bgcolor='rgba(0,0,0,0)', font=dict(color="white"), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

t1, t2 = st.tabs(["🛡️ CHIẾN LƯỢC RWA", "🔍 MÁY QUÉT HUNTER"])
def render_final(data, is_rwa):
    for d in data:
        progress = f"""<div style="font-size:12px;color:#8b949e;margin-bottom:8px;">Tiến độ: <b>{d['rw']:.1f}%</b> / {d['tw']}%</div><div style="background:#30363d;border-radius:10px;height:8px;width:100%;"><div style="background:#1f6feb;height:100%;border-radius:10px;width:{d['fill']}%;"></div></div>""" if is_rwa else ""
        html = f"""<div style="background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;font-family:sans-serif;color:white;margin-bottom:20px;"><div style="display:flex;justify-content:space-between;align-items:center;"><div><div style="font-size:36px;font-weight:900;color:#58a6ff;">{d['coin']}</div>{progress}</div><div style="text-align:right;"><div style="font-size:46px;font-weight:900;">${d['cp']:.3f}</div><div style="color:{'#3fb950' if d['pnl']>=0 else '#f85149'};font-size:22px;font-weight:800;">{d['pnl']:+.1f}%</div></div></div><div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;text-align:center;background:rgba(0,0,0,0.3);padding:20px;border-radius:15px;margin-top:20px;"><div><div style="color:#8b949e;font-size:10px;">VỐN VÀO</div><div style="font-size:18px;font-weight:700;color:#58a6ff;">${d['invested']:,.0f}</div></div><div><div style="color:#8b949e;font-size:10px;">HỖ TRỢ</div><div style="font-size:18px;font-weight:700;color:#3fb950;">${d['sup']:.3f}</div></div><div><div style="color:#8b949e;font-size:10px;">🏆 ATH</div><div style="font-size:18px;font-weight:700;color:#d29922;">${d['ath']:.1f}</div></div><div><div style="color:#8b949e;font-size:10px;">🟢 TP1</div><div style="font-size:18px;font-weight:700;color:#3fb950;">${d['tp1']:.2f}</div></div><div><div style="color:#8b949e;font-size:10px;">🟠 TP2</div><div style="font-size:18px;font-weight:700;color:#d29922;">${d['tp2']:.2f}</div></div></div><div style="margin-top:20px;padding:15px;border-radius:12px;border-left:8px solid {d['col']};background:{d['col']}15;color:{d['col']};font-weight:800;font-size:18px;">{d['stt']}<br><span style="font-size:13px;font-weight:400;color:#f0f6fc;">{d['rs']}</span></div></div>"""
        components.html(html, height=410)

with t1: render_final(tab1_data, True)
with t2: render_final(tab2_data, False)
