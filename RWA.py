import streamlit as st
import pandas as pd
import gspread
import requests
import feedparser
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components
import plotly.graph_objects as go

# --- 1. BASELINE: 13 CHIẾN MÃ ---
STRATEGY = {
    'RWA': {
        'LINK': {'id': 'chainlink', 'tw': 35, 'ath': 52.8},
        'ONDO': {'id': 'ondo-finance', 'tw': 20, 'ath': 1.48},
        'OM': {'id': 'mantra-chain', 'tw': 15, 'ath': 6.16},
        'QNT': {'id': 'quant-network', 'tw': 10, 'ath': 428.0},
        'PENDLE': {'id': 'pendle', 'tw': 10, 'ath': 7.52},
        'SYRUP': {'id': 'maple', 'tw': 5, 'ath': 2.10},
        'CFG': {'id': 'centrifuge', 'tw': 5, 'ath': 2.59}
    },
    'HUNTER': {
        'SOL': {'id': 'solana', 'ath': 260.0},
        'SUI': {'id': 'sui', 'ath': 3.92},
        'SEI': {'id': 'sei-network', 'ath': 1.14},
        'FET': {'id': 'fetch-ai', 'ath': 3.48},
        'ARB': {'id': 'arbitrum', 'ath': 2.40},
        'PEPE': {'id': 'pepe', 'ath': 0.000017}
    }
}

# --- 2. HÀM TRỢ NĂNG (GỌI RIÊNG LẺ) ---
@st.cache_data(ttl=300)
def get_current_prices():
    ids = ",".join([v['id'] for cat in STRATEGY.values() for v in cat.values()])
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
        return requests.get(url).json()
    except: return {}

def get_hist(cg_id, days):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{cg_id}/market_chart?vs_currency=usd&days={days}&interval=daily"
        r = requests.get(url).json()
        return pd.DataFrame({'Close': [x[1] for x in r['prices']], 'Volume': [x[1] for x in r['total_volumes']]})
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_fng():
    try:
        r = requests.get('https://api.alternative.me/fng/').json()
        return int(r['data'][0]['value']), r['data'][0]['value_classification']
    except: return 50, "Neutral"

# --- 3. BỘ NÃO PHÂN TÍCH V22.0 ---
def analyze_v22(df, cp, has_h, pnl, fng_val):
    if df.empty or len(df) < 5: return 0,0,"WAITING DATA","#8b949e", "Select timeframe", 0
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = delta.where(delta < 0, 0).abs().rolling(14).mean()
    rsi = (100 - (100 / (1 + (gain/(loss + 1e-10))))).iloc[-1]
    vol_r = df['Volume'].iloc[-1] / (df['Volume'].rolling(10).mean().iloc[-1] + 1e-10)
    sup, res = float(df['Close'].min()), float(df['Close'].max())
    
    score = 0
    checks = []
    if rsi < 35: score += 1; checks.append("RSI")
    if cp <= df['Close'].rolling(20).mean().iloc[-1]: score += 1; checks.append("BB")
    if ((cp/sup)-1)*100 < 5: score += 1; checks.append("SUPP")
    if vol_r > 1.3: score += 1; checks.append("WHALE")

    if rsi > 75: s, c = "TAKE PROFIT", "linear-gradient(90deg, #f85149, #ff7b72)"
    elif score >= 3 and fng_val < 35: s, c = "STRONG BUY", "linear-gradient(90deg, #238636, #3fb950)"
    elif score >= 2: s, c = "ACCUMULATE", "linear-gradient(90deg, #1f6feb, #58a6ff)"
    else: s, c = "OBSERVE", "linear-gradient(90deg, #30363d, #484f58)"
    eff = (pnl / (df['Close'].pct_change().std() * 100)) if has_h else 0
    return sup, res, s, c, " • ".join(checks) if checks else "STABLE", eff

# --- 4. DATA SETUP ---
@st.cache_resource
def get_gs():
    return gspread.authorize(Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]))

def load_data():
    ws = get_gs().open("TMC-Sales-Assistant").worksheet("Holdings")
    df = pd.DataFrame(ws.get_all_records())
    for c in ['Holdings', 'Entry_Price', 'Profit_Realized']:
        if col in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    return ws, df

st.set_page_config(page_title="Sovereign Terminal", layout="wide")

# CSS CUSTOM CHO GIAO DIỆN SANG TRỌNG
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;900&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #0d1117; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: transparent; }
    .stTabs [data-baseweb="tab"] { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px 20px; color: #8b949e; }
    .stTabs [aria-selected="true"] { background-color: #1f6feb !important; color: white !important; border: 1px solid #58a6ff; }
</style>
""", unsafe_allow_html=True)

ws, df_h = load_data()
prices = get_current_prices()
f_val, f_class = get_fng()

# DASHBOARD HEADER
total_v, total_i = 0, 0
total_realized = float(df_h['Profit_Realized'].sum())
p_lab, p_val = [], []
for cat, coins in STRATEGY.items():
    for name, info in coins.items():
        cp = prices.get(info['id'], {}).get('usd', 0)
        u_row = df_h[df_h['Coin'] == name]
        h, e = (float(u_row['Holdings'].values[0]), float(u_row['Entry_Price'].values[0])) if not u_row.empty else (0.0, 0.0)
        total_v += (h * cp); total_i += (h * e)
        if (h*cp) > 0: p_lab.append(name); p_val.append(h*cp)

cash = 2000.0 - total_i + total_realized # Baseline budget
st.markdown(f"""
<div style="display: flex; justify-content: space-between; align-items: center; background: #161b22; padding: 25px; border-radius: 20px; border: 1px solid #30363d; margin-bottom: 25px;">
    <div><div style="color: #8b949e; font-size: 12px; font-weight: 600;">TOTAL ASSET</div><div style="color: white; font-size: 36px; font-weight: 900;">${(total_v + cash):,.0f}</div></div>
    <div style="text-align: right;"><div style="color: #8b949e; font-size: 12px; font-weight: 600;">PORTFOLIO PNL</div><div style="color: {'#3fb950' if (total_v-total_i)>=0 else '#f85149'}; font-size: 28px; font-weight: 900;">${(total_v-total_i):,+.0f}</div></div>
</div>
""", unsafe_allow_html=True)

t1, t2 = st.tabs(["🛡️ STRATEGIC RWA", "🔍 HUNTER SCANNER"])

def render_luxury_card(name, info, is_rwa):
    cp = prices.get(info['id'], {}).get('usd', 0)
    u_row = df_h[df_h['Coin'] == name]
    h, e = (float(u_row['Holdings'].values[0]), float(u_row['Entry_Price'].values[0])) if not u_row.empty else (0.0, 0.0)
    pnl = ((cp/e)-1)*100 if e > 0 else 0
    p_fmt = f"{cp:.7f}" if cp < 0.0001 else f"{cp:.4f}"
    
    with st.container():
        st.markdown(f"""<div style="margin-top:20px; margin-bottom:10px;"><span style="font-size:20px; font-weight:900; color:#58a6ff;">{name}</span> <span style="color:#8b949e; font-size:14px;">| {pnl:+.1f}%</span></div>""", unsafe_allow_html=True)
        
        # Nút bấm được làm đẹp lại thành cụm điều hướng
        m_col = st.columns([1,1,1,1,4])
        d_sel = 0
        if m_col[0].button("7D", key=f"7_{name}"): d_sel = 7
        if m_col[1].button("30D", key=f"30_{name}"): d_sel = 30
        if m_col[2].button("90D", key=f"90_{name}"): d_sel = 90
        if m_col[3].button("1Y", key=f"365_{name}"): d_sel = 365
        
        if d_sel > 0:
            df_hist = get_hist(info['id'], d_sel)
            sup, res, stt, col, rs, eff = analyze_v22(df_hist, cp, h>0, pnl, f_val)
        else:
            sup, res, stt, col, rs, eff = "-", "-", "READY TO SCAN", "linear-gradient(90deg, #161b22, #161b22)", "Select period", 0

        # UI LUXURY CARD CONTENT
        weight_html = f"""<div style="font-size:11px; color:#8b949e; margin-bottom:8px;">WEIGHT: {(h*cp/2000*100):.1f}% / {info.get('tw',0)}%</div>""" if is_rwa else ""
        
        card_html = f"""
        <div style="background: #161b22; padding: 25px; border-radius: 20px; border: 1px solid #30363d; color: white;">
            <div style="display: flex; justify-content: space-between; align-items: baseline;">
                <div style="font-size: 38px; font-weight: 900; letter-spacing: -1px;">${p_fmt}</div>
                <div style="font-size: 14px; color: #8b949e; font-weight: 600;">ATH: ${info['ath']}</div>
            </div>
            {weight_html}
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 20px; background: rgba(0,0,0,0.2); padding: 15px; border-radius: 12px;">
                <div style="text-align: center;"><div style="font-size: 10px; color: #8b949e;">INVESTED</div><div style="font-size: 14px; font-weight: 600;">${h*e:,.0f}</div></div>
                <div style="text-align: center;"><div style="font-size: 10px; color: #8b949e;">AVG</div><div style="font-size: 14px; font-weight: 600;">${e:.4f}</div></div>
                <div style="text-align: center;"><div style="font-size: 10px; color: #8b949e;">SUPPORT</div><div style="font-size: 14px; font-weight: 600; color: #3fb950;">{sup if d_sel>0 else '-'}</div></div>
                <div style="text-align: center;"><div style="font-size: 10px; color: #8b949e;">RESIST</div><div style="font-size: 14px; font-weight: 600; color: #f85149;">{res if d_sel>0 else '-'}</div></div>
            </div>
            <div style="margin-top: 20px; padding: 15px; border-radius: 12px; background: {col}; color: white; text-align: center;">
                <div style="font-size: 16px; font-weight: 900; text-transform: uppercase;">{stt}</div>
                <div style="font-size: 11px; font-weight: 400; opacity: 0.9; margin-top: 4px;">{rs}</div>
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

with t1:
    for n, i in STRATEGY['RWA'].items(): render_luxury_card(n, i, True)
with t2:
    for n, i in STRATEGY['HUNTER'].items(): render_luxury_card(n, i, False)
