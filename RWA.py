import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
import requests
import feedparser
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components
import plotly.graph_objects as go

# --- 1. FIXED STRATEGY LIST ---
RWA_COINS = {
    'LINK':   {'symbol': 'LINK-USD',   'target_w': 35, 'ath': 52.8}, 
    'ONDO':   {'symbol': 'ONDO-USD',   'target_w': 20, 'ath': 2.14},
    'QNT':    {'symbol': 'QNT-USD',    'target_w': 15, 'ath': 428.0},
    'PENDLE': {'symbol': 'PENDLE-USD', 'target_w': 10, 'ath': 7.52},
    'SYRUP':  {'symbol': 'MPL-USD',    'target_w': 10, 'ath': 2.10}, 
    'CFG':    {'symbol': 'CFG-USD',    'target_w': 10, 'ath': 2.59}
}
HUNTER_COINS = {
    'SOL':  {'symbol': 'SOL-USD',   'ath': 260.0},
    'SUI':  {'symbol': 'SUI-USD',   'ath': 2.18},
    'FET':  {'symbol': 'FET-USD',   'ath': 3.48},
    'ARB':  {'symbol': 'ARB1-USD',  'ath': 2.40},
    'PEPE': {'symbol': 'PEPE1-USD', 'ath': 0.000017}
}
ALL_STRATEGY = {**RWA_COINS, **HUNTER_COINS}

# --- 2. FUNCTIONS ---
@st.cache_data(ttl=3600)
def get_fear_greed_data():
    try:
        r = requests.get('https://api.alternative.me/fng/').json()
        return r['data'][0]['value'], r['data'][0]['value_classification']
    except: return "50", "Neutral"

def get_crypto_news_feed():
    try:
        feed = feedparser.parse("https://cointelegraph.com/rss/tag/bitcoin")
        return "<br>".join([f"🔹 <a href='{e.link}' target='_blank' style='color:#58a6ff;text-decoration:none;'>{e.title}</a>" for e in feed.entries[:3]])
    except: return "⚠️ Connecting 24H News..."

def analyze_logic(df, cp, days_sel, has_holdings, pnl_pct):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi = (100 - (100 / (1 + (gain/(loss + 1e-10))))).iloc[-1]
    vol = df['Volume'].iloc[-1] / (df['Volume'].rolling(10).mean().iloc[-1] + 1e-10)
    std_dev = df['Close'].pct_change().std() * 100 
    eff = (pnl_pct / std_dev) if std_dev > 0 and has_holdings else 0.0
    ma20, std20 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(20).std().iloc[-1]
    low_b, up_b = ma20 - (2 * std20), ma20 + (2 * std20)
    sup, res = float(df['Low'].rolling(window=days_sel).min().iloc[-1]), float(df['High'].rolling(window=days_sel).max().iloc[-1])
    score = 0
    checks = []
    if rsi < 35: score += 1; checks.append("✅ RSI LOW")
    else: checks.append(f"❌ RSI {rsi:.0f}")
    if cp <= low_b: score += 1; checks.append("✅ BB BOTTOM")
    else: checks.append("❌ BB MID")
    if ((cp/sup)-1)*100 < 4: score += 1; checks.append("✅ SUPPORT")
    else: checks.append(f"❌ DIST {((cp/sup)-1)*100:.1f}%")
    if vol > 1.5: score += 1; checks.append("🐳 WHALE")
    else: checks.append("❌ VOL")
    if rsi > 70: stt, col = "EXIT / TAKE PROFIT", "#f85149"
    elif score >= 3: stt, col = "STRONG BUY", "#3fb950"
    elif score == 2: stt, col = ("DCA BUY", "#1f6feb") if has_holdings else ("SPEC BUY", "#58a6ff")
    else: stt, col = "OBSERVE", "#8b949e"
    return sup, res, stt, col, " | ".join(checks), eff

@st.cache_resource
def get_gsheet():
    return gspread.authorize(Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]))

def load_data():
    client = get_gsheet()
    ws = client.open("TMC-Sales-Assistant").worksheet("Holdings")
    df = pd.DataFrame(ws.get_all_records())
    for c in ['Holdings', 'Entry_Price', 'Profit_Realized']:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    return ws, df

# --- 3. UI SETUP ---
st.set_page_config(page_title="RWA Elite Terminal", layout="wide")
ws, df_holdings = load_data()
f_val, f_class = get_fear_greed_data()

with st.sidebar:
    st.header("🏢 MANAGEMENT")
    base_budget = st.number_input("TOTAL BUDGET ($)", value=2000.0)
    st.divider()
    coin_sel = st.selectbox("Select Asset", list(ALL_STRATEGY.keys()))
    with st.form("trade_v18_4"):
        q, p = st.number_input("Qty", min_value=0.0), st.number_input("Price", min_value=0.0)
        if st.form_submit_button("UPDATE DATABASE"):
            row = df_holdings[df_holdings['Coin'] == coin_sel]
            if not row.empty:
                t_q = float(row['Holdings'].values[0]) + q
                a_e = ((float(row['Holdings'].values[0]) * float(row['Entry_Price'].values[0])) + (q * p)) / t_q if t_q > 0 else 0
                ws.update(f"B{ws.find(coin_sel).row}:C{ws.find(coin_sel).row}", [[t_q, a_e]])
            else: ws.append_row([coin_sel, q, p, 0])
            st.rerun()
    days_sel = st.select_slider("Period", options=[7, 30, 90], value=30)
    st.info(f"🎭 F&G: {f_class} ({f_val}/100)")

st.markdown(f"""<div style="background:#161b22;padding:15px;border-radius:15px;border:1px solid #30363d;margin-bottom:20px;"><div style="color:#8b949e;font-size:12px;text-transform:uppercase;font-weight:bold;margin-bottom:8px;">📰 24H NEWS</div><div style="font-size:14px;line-height:1.6;">{get_crypto_news_feed()}</div></div>""", unsafe_allow_html=True)

# FETCH ALL 11 COINS DATA
tickers = yf.Tickers(" ".join([v['symbol'] for v in ALL_STRATEGY.values()]))
total_val, total_invest, total_realized = 0, 0, float(df_holdings['Profit_Realized'].sum())
tab1_data, tab2_data, p_labels, p_values = [], [], [], []

for coin, info in ALL_STRATEGY.items():
    try:
        df_h = tickers.tickers[info['symbol']].history(period="60d")
        cp = float(tickers.tickers[info['symbol']].fast_info['last_price'])
        u_row = df_holdings[df_holdings['Coin'] == coin]
        h, e = (float(u_row['Holdings'].values[0]), float(u_row['Entry_Price'].values[0])) if not u_row.empty else (0.0, 0.0)
        pnl_p = ((cp/e)-1)*100 if e > 0 else 0
        sup, res, stt, col, rs, eff = analyze_logic(df_h, cp, days_sel, h > 0, pnl_p)
        invested, val = h * e, cp * h
        total_val += val; total_invest += invested
        card = {"coin": coin, "cp": cp, "stt": stt, "col": col, "rs": rs, "invested": invested, "e": e, "pnl": pnl_p, "sup": sup, "res": res, "ath": info['ath'], "eff": eff}
        if val > 0: p_labels.append(coin); p_values.append(val)
        if coin in RWA_COINS:
            card.update({"tw": info['target_w'], "rw": (val/base_budget*100), "fill": min((val/base_budget*100)/info['target_w'], 1.0)*100})
            tab1_data.append(card)
        else: tab2_data.append(card)
    except: continue

# DASHBOARD
cash_rem = base_budget - total_invest + total_realized
pnl_tot = total_val - total_invest
p_labels.append("CASH"); p_values.append(max(0, cash_rem))
c1, c2 = st.columns([3, 1.2])
with c1:
    dash_html = f"""<div style="display:flex;gap:15px;margin-bottom:15px;"><div style="flex:1;background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;">Cash</div><div style="color:#58a6ff;font-size:32px;font-weight:900;">${cash_rem:,.0f}</div></div><div style="flex:1;background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;">PnL</div><div style="color:{'#3fb950' if pnl_tot>=0 else '#f85149'};font-size:32px;font-weight:900;">${pnl_tot:,.0f}</div></div></div><div style="background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:12px;">Total Asset</div><div style="color:white;font-size:42px;font-weight:900;">${(total_val + cash_rem):,.0f}</div></div>"""
    components.html(dash_html, height=320)
with c2:
    fig = go.Figure(data=[go.Pie(labels=p_labels, values=p_values, hole=.5)])
    fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), height=320, paper_bgcolor='rgba(0,0,0,0)', font=dict(color="white"), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# RENDER TABS
t1, t2 = st.tabs(["🛡️ RWA STRATEGY", "🔍 HUNTER SCANNER"])
def render_cards(data, is_rwa):
    for d in data:
        eff_color = "#3fb950" if d['eff'] > 1.5 else ("#d29922" if d['eff'] > 0 else "#8b949e")
        progress = f"""<div style="font-size:12px;color:#8b949e;margin-bottom:8px;">WEIGHT: <b>{d['rw']:.1f}%</b> / {d['tw']}% | <span style="color:{eff_color}">EFF: {d['eff']:.1f}</span></div><div style="background:#30363d;border-radius:10px;height:8px;width:100%;"><div style="background:#1f6feb;height:100%;border-radius:10px;width:{d['fill']}%;"></div></div>""" if is_rwa else f"""<div style="font-size:12px;color:{eff_color};margin-bottom:8px;">EFFICIENCY SCORE: {d['eff']:.1f}</div>"""
        html = f"""<div style="background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;font-family:sans-serif;color:white;margin-bottom:20px;"><div style="display:flex;justify-content:space-between;align-items:center;"><div style="width:50%;"><div style="font-size:32px;font-weight:900;color:#58a6ff;">{d['coin']}</div>{progress}</div><div style="text-align:right;"><div style="font-size:38px;font-weight:900;">${d['cp']:.3f}</div><div style="color:{'#3fb950' if d['pnl']>=0 else '#f85149'};font-size:18px;">{d['pnl']:+.1f}%</div></div></div><div style="display:grid;grid-template-columns:repeat(7,1fr);gap:5px;text-align:center;background:rgba(0,0,0,0.3);padding:15px;border-radius:15px;margin-top:20px;"><div><div style="color:#8b949e;font-size:9px;">INVESTED</div><div style="font-size:13px;font-weight:700;">${d['invested']:,.0f}</div></div><div><div style="color:#8b949e;font-size:9px;">AVG</div><div style="font-size:13px;font-weight:700;">${d['e']:.3f}</div></div><div><div style="color:#8b949e;font-size:9px;">SUPP</div><div style="font-size:13px;font-weight:700;color:#3fb950;">${d['sup']:.3f}</div></div><div><div style="color:#8b949e;font-size:9px;">RESIST</div><div style="font-size:13px;font-weight:700;color:#f85149;">${d['res']:.3f}</div></div><div><div style="color:#8b949e;font-size:9px;">ATH</div><div style="font-size:13px;font-weight:700;">${d['ath']:.1f}</div></div><div><div style="color:#8b949e;font-size:9px;">TP1</div><div style="font-size:13px;font-weight:700;color:#3fb950;">${d['cp']*1.5:.2f}</div></div><div><div style="color:#8b949e;font-size:9px;">TP2</div><div style="font-size:13px;font-weight:700;color:#d29922;">${d['cp']*2:.2f}</div></div></div><div style="margin-top:15px;padding:12px;border-radius:10px;border-left:6px solid {d['col']};background:{d['col']}15;color:{d['col']};font-weight:800;font-size:16px;">{d['stt']}<br><span style="font-size:11px;font-weight:400;color:#f0f6fc;">{d['rs']}</span></div></div>"""
        components.html(html, height=380)

with t1: render_cards(tab1_data, True)
with t2: render_cards(tab2_data, False)
