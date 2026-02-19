import streamlit as st
import pandas as pd
import gspread
import requests
import feedparser
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components
import plotly.graph_objects as go

# --- 1. CONFIG & STRATEGY ---
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

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=300)
def get_current_prices():
    ids = ",".join([v['id'] for cat in STRATEGY.values() for v in cat.values()])
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
        return requests.get(url).json()
    except: return {}

def get_hist_data(cg_id, days):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{cg_id}/market_chart?vs_currency=usd&days={days}&interval=daily"
        r = requests.get(url).json()
        return pd.DataFrame({'Close': [x[1] for x in r['prices']], 'Volume': [x[1] for x in r['total_volumes']]})
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_fng():
    try:
        r = requests.get('https://api.alternative.me/fng/').json()
        return int(r['data'][0]['value']), r['data'][0]['classification']
    except: return 50, "Neutral"

# --- 3. DECISION MATRIX ---
def analyze_v23(df, cp, has_h, pnl, fng_val):
    if df.empty or len(df) < 5: return 0,0,"WAITING","#8b949e", "Scanning...", 0
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = delta.where(delta < 0, 0).abs().rolling(14).mean()
    rsi = (100 - (100 / (1 + (gain/(loss + 1e-10))))).iloc[-1]
    vol_r = df['Volume'].iloc[-1] / (df['Volume'].rolling(min(len(df), 10)).mean().iloc[-1] + 1e-10)
    sup, res = float(df['Close'].min()), float(df['Close'].max())
    
    score = 0
    checks = []
    if rsi < 35: score += 1; checks.append("RSI LOW")
    if cp <= df['Close'].rolling(min(len(df), 20)).mean().iloc[-1]: score += 1; checks.append("BB LOW")
    if ((cp/sup)-1)*100 < 5: score += 1; checks.append("SUPPORT")
    if vol_r > 1.3: score += 1; checks.append("WHALE")

    if rsi > 75: s, c = "TAKE PROFIT", "linear-gradient(90deg, #f85149, #ff7b72)"
    elif score >= 3 and fng_val < 35: s, c = "STRONG BUY", "linear-gradient(90deg, #238636, #3fb950)"
    elif score >= 2: s, c = "ACCUMULATE", "linear-gradient(90deg, #1f6feb, #58a6ff)"
    else: s, c = "OBSERVE", "linear-gradient(90deg, #30363d, #484f58)"
    eff = (pnl / (df['Close'].pct_change().std() * 100)) if has_h else 0
    return sup, res, s, c, " • ".join(checks), eff

# --- 4. DATA SETUP ---
@st.cache_resource
def get_gs():
    return gspread.authorize(Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]))

def load_data():
    try:
        ws = get_gs().open("TMC-Sales-Assistant").worksheet("Holdings")
        df = pd.DataFrame(ws.get_all_records())
        for c in ['Holdings', 'Entry_Price', 'Profit_Realized']:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        return ws, df
    except: return None, pd.DataFrame(columns=['Coin', 'Holdings', 'Entry_Price', 'Profit_Realized'])

st.set_page_config(page_title="Sovereign Terminal", layout="wide")
st.markdown("""<style>
    .stSelectbox div[data-baseweb="select"] { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; }
    .stExpander { border-radius: 12px !important; border: 1px solid #30363d !important; background-color: #161b22 !important; }
</style>""", unsafe_allow_html=True)

ws, df_h = load_data()
prices = get_current_prices()
f_val, f_class = get_fng()

# DASHBOARD HEADER
total_v, total_i = 0.0, 0.0
total_realized = float(df_h['Profit_Realized'].sum()) if not df_h.empty else 0.0
for cat, coins in STRATEGY.items():
    for name, info in coins.items():
        cp = float(prices.get(info['id'], {}).get('usd', 0.0))
        u_row = df_h[df_h['Coin'] == name] if not df_h.empty else pd.DataFrame()
        h = float(u_row['Holdings'].values[0]) if not u_row.empty else 0.0
        e = float(u_row['Entry_Price'].values[0]) if not u_row.empty else 0.0
        total_v += (h * cp); total_i += (h * e)

cash = 2000.0 - total_i + total_realized
pnl_val = total_v - total_i

st.markdown(f"""
<div style="background: #161b22; padding: 20px; border-radius: 15px; border: 1px solid #30363d; margin-bottom: 20px;">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div><div style="color: #8b949e; font-size: 10px; font-weight: 600;">PORTFOLIO VALUE</div><div style="color: white; font-size: 28px; font-weight: 900;">${(total_v + cash):,.0f}</div></div>
        <div style="text-align: right;"><div style="color: #8b949e; font-size: 10px; font-weight: 600;">PnL</div><div style="color: {'#3fb950' if pnl_val>=0 else '#f85149'}; font-size: 22px; font-weight: 900;">${pnl_val:,.0f}</div></div>
    </div>
</div>
""", unsafe_allow_html=True)

t1, t2 = st.tabs(["🛡️ RWA", "🔍 HUNTER"])

def render_elite_card(name, info, is_rwa):
    cp = float(prices.get(info['id'], {}).get('usd', 0.0))
    u_row = df_h[df_h['Coin'] == name] if not df_h.empty else pd.DataFrame()
    h = float(u_row['Holdings'].values[0]) if not u_row.empty else 0.0
    e = float(u_row['Entry_Price'].values[0]) if not u_row.empty else 0.0
    pnl = ((cp/e)-1)*100 if e > 0 else 0.0
    p_fmt = f"{cp:.7f}" if cp < 0.0001 else f"{cp:.4f}"
    
    # CARD FRAME
    with st.container():
        st.markdown(f"#### {name} | ${p_fmt} | {pnl:+.1f}%")
        
        # TIME SELECTOR & ACTIONS
        col_s, col_a = st.columns([2, 3])
        with col_s:
            period = st.selectbox("Timeline", ["-", "7D", "30D", "90D", "1Y"], key=f"sel_{name}")
        
        d_map = {"7D": 7, "30D": 30, "90D": 90, "1Y": 365}
        d_val = d_map.get(period, 0)
        
        if d_val > 0:
            with st.spinner('Analysing...'):
                df_hist = get_hist_data(info['id'], d_val)
                sup, res, stt, col, rs, eff = analyze_v23(df_hist, cp, h>0, pnl, f_val)
        else:
            sup, res, stt, col, rs, eff = 0.0, 0.0, "SELECT PERIOD", "#161b22", "Ready for scan", 0.0

        # ELITE DATA GRID (7 Cột Baseline)
        card_html = f"""
        <div style="background: #0d1117; padding: 18px; border-radius: 12px; border: 1px solid #30363d; margin-top: 5px; margin-bottom: 25px;">
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; text-align: center; margin-bottom: 12px;">
                <div><div style="font-size: 8px; color: #8b949e;">INVESTED</div><div style="font-size: 11px; font-weight: 700; color: #58a6ff;">${(h*e):,.0f}</div></div>
                <div><div style="font-size: 8px; color: #8b949e;">AVG</div><div style="font-size: 11px; font-weight: 700;">${e:.3f}</div></div>
                <div><div style="font-size: 8px; color: #8b949e;">SUPPORT</div><div style="font-size: 11px; font-weight: 700; color: #3fb950;">{f"{sup:.3f}" if d_val>0 else "-"}</div></div>
                <div><div style="font-size: 8px; color: #8b949e;">RESIST</div><div style="font-size: 11px; font-weight: 700; color: #f85149;">{f"{res:.3f}" if d_val>0 else "-"}</div></div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; text-align: center; border-top: 1px solid #30363d; padding-top: 10px;">
                <div><div style="font-size: 8px; color: #8b949e;">ATH</div><div style="font-size: 11px; font-weight: 700; color: #d29922;">${info['ath']}</div></div>
                <div><div style="font-size: 8px; color: #8b949e;">TP1 (1.5x)</div><div style="font-size: 11px; font-weight: 700; color: #3fb950;">${(cp*1.5):.2f}</div></div>
                <div><div style="font-size: 8px; color: #8b949e;">TP2 (2x)</div><div style="font-size: 11px; font-weight: 700; color: #d29922;">${(cp*2.0):.2f}</div></div>
            </div>
            <div style="margin-top: 15px; padding: 12px; border-radius: 8px; background: {col}; color: white; text-align: center;">
                <div style="font-size: 14px; font-weight: 900; letter-spacing: 1px;">{stt}</div>
                <div style="font-size: 10px; font-weight: 400; opacity: 0.9; margin-top: 3px;">{rs}</div>
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

with t1:
    for n, i in STRATEGY['RWA'].items(): render_elite_card(n, i, True)
with t2:
    for n, i in STRATEGY['HUNTER'].items(): render_elite_card(n, i, False)
