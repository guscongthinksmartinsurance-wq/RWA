import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
import requests
import feedparser
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components
import plotly.graph_objects as go

# --- 1. CHIẾN LƯỢC RWA & MAPPING DỮ LIỆU ---
RWA_STRATEGY = {
    'LINK':   {'symbol': 'LINK-USD',   'target_w': 35, 'ath': 52.8}, 
    'ONDO':   {'symbol': 'ONDO-USD',   'target_w': 20, 'ath': 2.14},
    'QNT':    {'symbol': 'QNT-USD',    'target_w': 15, 'ath': 428.0},
    'PENDLE': {'symbol': 'PENDLE-USD', 'target_w': 10, 'ath': 7.52},
    'SYRUP':  {'symbol': 'MPL-USD',    'target_w': 10, 'ath': 2.10}, 
    'CFG':    {'symbol': 'CFG-USD',    'target_w': 10, 'ath': 2.59}
}

# Fix lỗi mã ARB để lấy đúng giá thị trường
MAP = {'ARB': 'ARB1-USD', 'SUI': 'SUI-USD', 'PEPE': 'PEPE1-USD'}

# --- 2. HÀM TRỢ NĂNG (NEWS & FEAR/GREED) ---
@st.cache_data(ttl=3600)
def get_fear_greed_data():
    try:
        r = requests.get('https://api.alternative.me/fng/').json()
        return r['data'][0]['value'], r['data'][0]['value_classification']
    except: return "50", "Neutral"

def get_crypto_news_feed():
    try:
        feed = feedparser.parse("https://cointelegraph.com/rss/tag/bitcoin")
        news = [f"🔹 <a href='{e.link}' target='_blank' style='color:#58a6ff;text-decoration:none;'>{e.title}</a>" for e in feed.entries[:3]]
        return "<br>".join(news)
    except: return "⚠️ Connecting News Terminal..."

# --- 3. BỘ NÃO PHÂN TÍCH (4 CHỈ SỐ & CẢNH BÁO) ---
def analyze_advanced_logic(df, cp, days_sel, has_holdings, pnl_pct):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi = (100 - (100 / (1 + (gain/(loss + 1e-10))))).iloc[-1]
    vol = df['Volume'].iloc[-1] / (df['Volume'].rolling(10).mean().iloc[-1] + 1e-10)
    std_dev = df['Close'].pct_change().std() * 100 
    eff_score = (pnl_pct / std_dev) if std_dev > 0 and has_holdings else 0.0
    
    ma20, std20 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(20).std().iloc[-1]
    lower_b, upper_b = ma20 - (2 * std20), ma20 + (2 * std20)
    sup, res = float(df['Low'].rolling(window=days_sel).min().iloc[-1]), float(df['High'].rolling(window=days_sel).max().iloc[-1])
    
    score = 0
    checks = []
    # 4 CHỈ SỐ CẢNH BÁO
    if rsi < 35: score += 1; checks.append(f"✅ RSI LOW ({rsi:.1f})")
    else: checks.append(f"❌ RSI ({rsi:.1f})")
    if cp <= lower_b: score += 1; checks.append(f"✅ BB BOTTOM")
    else: checks.append(f"❌ BB MID")
    if ((cp/sup)-1)*100 < 4: score += 1; checks.append(f"✅ NEAR SUPPORT")
    else: checks.append(f"❌ DISTANCE {((cp/sup)-1)*100:.1f}%")
    if vol > 1.5: score += 1; checks.append(f"🐳 WHALE ACCUM (x{vol:.1f})")
    else: checks.append(f"❌ WEAK VOL (x{vol:.1f})")

    # TRẠNG THÁI CẢNH BÁO
    if rsi > 70 or cp >= upper_b * 0.98: stt, col = "EXIT / TAKE PROFIT", "#f85149"
    elif score >= 3: stt, col = "STRONG BUY", "#3fb950"
    elif score == 2: stt, col = ("DCA BUY", "#1f6feb") if has_holdings else ("SPEC BUY", "#58a6ff")
    else: stt, col = "OBSERVE", "#8b949e"
    
    return sup, res, stt, col, " | ".join(checks), float(df['High'].max()), cp*1.5, cp*2.0, eff_score

# --- 4. DỮ LIỆU ---
@st.cache_resource
def get_gsheet_client():
    creds_info = st.secrets["gcp_service_account"]
    return gspread.authorize(Credentials.from_service_account_info(creds_info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]))

def load_data():
    client = get_gsheet_client()
    ws = client.open("TMC-Sales-Assistant").worksheet("Holdings")
    df = pd.DataFrame(ws.get_all_records())
    for col in ['Profit_Realized', 'Holdings', 'Entry_Price']:
        if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return ws, df

# --- 5. GIAO DIỆN PHỤC HỒI ---
st.set_page_config(page_title="RWA Elite Terminal", layout="wide")
ws, df_holdings = load_data()
f_val, f_class = get_fear_greed_data()

with st.sidebar:
    st.header("🏢 MANAGEMENT")
    base_budget = st.number_input("TOTAL BUDGET ($)", value=2000.0)
    st.divider()
    all_coins_list = sorted(list(set(list(RWA_STRATEGY.keys()) + list(MAP.keys()) + df_holdings['Coin'].tolist())))
    coin_sel = st.selectbox("Select Asset", ["+ New Asset..."] + all_coins_list)
    final_coin = st.text_input("Symbol").upper() if coin_sel == "+ New Asset..." else coin_sel
    with st.form("trade_v16"):
        q, p = st.number_input("Quantity", min_value=0.0), st.number_input("Price ($)", min_value=0.0)
        if st.form_submit_button("EXECUTE"):
            if final_coin:
                row = df_holdings[df_holdings['Coin'] == final_coin]
                if not row.empty:
                    old_q, old_e = float(row['Holdings'].values[0]), float(row['Entry_Price'].values[0])
                    t_q = old_q + q
                    a_e = ((old_q * old_e) + (q * p)) / t_q if t_q > 0 else 0
                    ws.update(f"B{ws.find(final_coin).row}:C{ws.find(final_coin).row}", [[t_q, a_e]])
                else: ws.append_row([final_coin, q, p, 0])
                st.rerun()
    days_sel = st.select_slider("Period", options=[7, 30, 90], value=30)
    st.info(f"🎭 F&G: {f_class} ({f_val}/100)")

st.markdown(f"""<div style="background:#161b22;padding:15px;border-radius:15px;border:1px solid #30363d;margin-bottom:20px;"><div style="color:#8b949e;font-size:12px;text-transform:uppercase;font-weight:bold;margin-bottom:8px;">📰 24H INTELLIGENCE</div><div style="font-size:14px;line-height:1.6;">{get_crypto_news_feed()}</div></div>""", unsafe_allow_html=True)

all_assets = list(set(list(RWA_STRATEGY.keys()) + df_holdings['Coin'].tolist()))
tickers = yf.Tickers(" ".join([MAP.get(c, f"{c}-USD") for c in all_assets if c]))
total_val, total_invest, total_realized = 0, 0, float(df_holdings['Profit_Realized'].sum())
tab1_data, tab2_data, p_labels, p_values = [], [], [], []

for coin in all_assets:
    try:
        sym = MAP.get(coin, f"{coin}-USD")
        df_h = tickers.tickers[sym].history(period="60d")
        cp = float(tickers.tickers[sym].fast_info['last_price'])
        u_row = df_holdings[df_holdings['Coin'] == coin]
        h, e = (float(u_row['Holdings'].values[0]), float(u_row['Entry_Price'].values[0])) if not u_row.empty else (0.0, 0.0)
        pnl_p = ((cp/e)-1)*100 if e > 0 else 0
        sup, res, stt, col, rs, ath_real, tp1, tp2, eff = analyze_advanced_logic(df_h, cp, days_sel, h > 0, pnl_p)
        
        invested, val = h * e, cp * h
        total_val += val; total_invest += invested
        card = {"coin": coin, "cp": cp, "stt": stt, "col": col, "rs": rs, "invested": invested, "e": e, "pnl": pnl_p, "sup": sup, "res": res, "ath": RWA_STRATEGY[coin]['ath'] if coin in RWA_STRATEGY else ath_real, "tp1": tp1, "tp2": tp2, "eff": eff}
        if val > 0: p_labels.append(coin); p_values.append(val)
        if coin in RWA_STRATEGY:
            card.update({"tw": RWA_STRATEGY[coin]['target_w'], "rw": (val/base_budget*100), "fill": min((val/base_budget*100)/RWA_STRATEGY[coin]['target_w'], 1.0)*100})
            tab1_data.append(card)
        else: tab2_data.append(card)
    except: continue

# DASHBOARD
c1, c2 = st.columns([3, 1.2])
with c1:
    cash = float(base_budget) - float(total_invest) + total_realized
    dash_html = f"""<div style="display:flex;gap:15px;margin-bottom:15px;"><div style="flex:1;background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;text-transform:uppercase;">Liquidity (Cash)</div><div style="color:#58a6ff;font-size:42px;font-weight:900;">${cash:,.0f}</div></div><div style="flex:1;background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;text-transform:uppercase;">PnL</div><div style="color:{'#3fb950' if (total_val-total_invest)>=0 else '#f85149'};font-size:42px;font-weight:900;">${(total_val-total_invest):,.0f}</div></div></div><div style="background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;text-transform:uppercase;">Total Asset Value</div><div style="color:white;font-size:48px;font-weight:900;">${(total_val + cash):,.0f}</div></div>"""
    components.html(dash_html
