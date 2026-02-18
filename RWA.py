import streamlit as st
import pandas as pd
import gspread
import requests
import feedparser
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components
import plotly.graph_objects as go

# --- 1. BASELINE: 13 CHIẾN MÃ (ADDS SEI & OM) ---
STRATEGY = {
    'RWA': {
        'LINK': {'id': 'chainlink', 'tw': 35, 'ath': 52.8},
        'ONDO': {'id': 'ondo-finance', 'tw': 20, 'ath': 1.48},
        'OM': {'id': 'mantra-chain', 'tw': 15, 'ath': 6.16}, # New RWA Alpha
        'QNT': {'id': 'quant-network', 'tw': 10, 'ath': 428.0},
        'PENDLE': {'id': 'pendle', 'tw': 10, 'ath': 7.52},
        'SYRUP': {'id': 'maple', 'tw': 5, 'ath': 2.10},
        'CFG': {'id': 'centrifuge', 'tw': 5, 'ath': 2.59}
    },
    'HUNTER': {
        'SOL': {'id': 'solana', 'ath': 260.0},
        'SUI': {'id': 'sui', 'ath': 3.92},
        'SEI': {'id': 'sei-network', 'ath': 1.14}, # New Hunter
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

def get_news():
    try:
        f = feedparser.parse("https://cointelegraph.com/rss/tag/bitcoin")
        return "<br>".join([f"🔹 <a href='{e.link}' target='_blank' style='color:#58a6ff;text-decoration:none;'>{e.title}</a>" for e in f.entries[:3]])
    except: return "⚠️ Connecting News..."

# --- 3. MA TRẬN QUYẾT ĐỊNH ---
def analyze_v21(df, cp, has_h, pnl, fng_val):
    if df.empty or len(df) < 5: return 0,0,"WAITING DATA","#8b949e", "Click a time above", 0
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = delta.where(delta < 0, 0).abs().rolling(14).mean()
    rsi = (100 - (100 / (1 + (gain/(loss + 1e-10))))).iloc[-1]
    ma20 = df['Close'].rolling(min(len(df), 20)).mean().iloc[-1]
    std20 = df['Close'].rolling(min(len(df), 20)).std().iloc[-1]
    lower_b = ma20 - (2*std20)
    vol_r = df['Volume'].iloc[-1] / (df['Volume'].rolling(10).mean().iloc[-1] + 1e-10)
    sup, res = float(df['Close'].min()), float(df['Close'].max())
    
    score = 0
    checks = []
    if rsi < 35: score += 1; checks.append("✅ RSI")
    if cp <= lower_b: score += 1; checks.append("✅ BB")
    if ((cp/sup)-1)*100 < 5: score += 1; checks.append("✅ SUPP")
    if vol_r > 1.3: score += 1; checks.append("🐳 VOL")

    if rsi > 75: s, c = "TAKE PROFIT", "#f85149"
    elif score >= 3 and fng_val < 35: s, c = "STRONG BUY", "#3fb950"
    elif score >= 2: s, c = "DCA BUY" if has_h else "SPEC BUY", "#1f6feb" if has_h else "#58a6ff"
    else: s, c = "OBSERVE", "#8b949e"
    eff = (pnl / (df['Close'].pct_change().std() * 100)) if has_h else 0
    return sup, res, s, c, " | ".join(checks) if checks else "NEUTRAL", eff

# --- 4. DATA SETUP ---
@st.cache_resource
def get_gs():
    return gspread.authorize(Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]))

def load_data():
    ws = get_gs().open("TMC-Sales-Assistant").worksheet("Holdings")
    df = pd.DataFrame(ws.get_all_records())
    for c in ['Holdings', 'Entry_Price', 'Profit_Realized']:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    return ws, df

st.set_page_config(page_title="RWA Elite V21", layout="wide")
ws, df_h = load_data()
prices = get_current_prices()
f_val, f_class = get_fng()

# --- 5. RENDER INTERFACE ---
with st.sidebar:
    st.header("🏢 MANAGEMENT")
    budget = st.number_input("TOTAL BUDGET ($)", value=2000.0)
    st.divider()
    st.info(f"🎭 F&G: {f_class} ({f_val})")
    st.markdown(f"**News:**<br>{get_news()}", unsafe_allow_html=True)

# DASHBOARD TỔNG
total_v, total_i = 0, 0
total_realized = float(df_h['Profit_Realized'].sum())
p_lab, p_val = [], []

# Tính toán nhanh cho Dashboard
for cat, coins in STRATEGY.items():
    for name, info in coins.items():
        cp = prices.get(info['id'], {}).get('usd', 0)
        u_row = df_h[df_h['Coin'] == name]
        h, e = (float(u_row['Holdings'].values[0]), float(u_row['Entry_Price'].values[0])) if not u_row.empty else (0.0, 0.0)
        total_v += (h * cp); total_i += (h * e)
        if (h*cp) > 0: p_lab.append(name); p_val.append(h*cp)

cash = budget - total_i + total_realized
c1, c2 = st.columns([3, 1.2])
with c1:
    dash = f"""<div style="display:flex;gap:10px;margin-bottom:10px;"><div style="flex:1;background:#161b22;padding:20px;border-radius:15px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:10px;">CASH</div><div style="color:#58a6ff;font-size:24px;font-weight:900;">${cash:,.0f}</div></div><div style="flex:1;background:#161b22;padding:20px;border-radius:15px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:10px;">PnL</div><div style="color:{'#3fb950' if (total_v-total_i)>=0 else '#f85149'};font-size:24px;font-weight:900;">${(total_v-total_i):,.0f}</div></div></div><div style="background:#161b22;padding:20px;border-radius:15px;border:1px solid #30363d;text-align:center;"><div style="color:#8b949e;font-size:10px;">TOTAL ASSET</div><div style="color:white;font-size:32px;font-weight:900;">${(total_v + cash):,.0f}</div></div>"""
    components.html(dash, height=200)
with c2:
    p_lab.append("CASH"); p_val.append(max(0, cash))
    fig = go.Figure(data=[go.Pie(labels=p_lab, values=p_val, hole=.5)])
    fig.update_layout(margin=dict(t=0,b=0,l=0,r=0), height=200, paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# TABS HIỂN THỊ
t1, t2 = st.tabs(["🛡️ STRATEGIC RWA", "🔍 HUNTER SCANNER"])

def render_smart_card(name, info, is_rwa):
    cp = prices.get(info['id'], {}).get('usd', 0)
    u_row = df_h[df_h['Coin'] == name]
    h, e = (float(u_row['Holdings'].values[0]), float(u_row['Entry_Price'].values[0])) if not u_row.empty else (0.0, 0.0)
    pnl = ((cp/e)-1)*100 if e > 0 else 0
    p_fmt = f"{cp:.7f}" if cp < 0.0001 else f"{cp:.3f}"
    
    with st.expander(f"**{name}** | **${p_fmt}** | {pnl:+.1f}%", expanded=(h>0)):
        # Nút bấm nhanh (Cách 2)
        m_col = st.columns(4)
        d_sel = 0
        if m_col[0].button(f"7D", key=f"7_{name}"): d_sel = 7
        if m_col[1].button(f"30D", key=f"30_{name}"): d_sel = 30
        if m_col[2].button(f"90D", key=f"90_{name}"): d_sel = 90
        if m_col[3].button(f"365D", key=f"365_{name}"): d_sel = 365
        
        if d_sel > 0:
            with st.spinner(f"Analyzing {name}..."):
                df_hist = get_hist(info['id'], d_sel)
                sup, res, stt, col, rs, eff = analyze_v21(df_hist, cp, h>0, pnl, f_val)
        else:
            sup, res, stt, col, rs, eff = "-", "-", "SELECT TIMEFRAME", "#8b949e", "Click a button above", 0

        # UI Card Content
        eff_c = "#3fb950" if eff > 1.5 else "#8b949e"
        weight_html = f"""<div style="font-size:11px;color:#8b949e;margin-bottom:5px;">WEIGHT: {(h*cp/budget*100):.1f}% / {info.get('tw',0)}% | <span style="color:{eff_c}">EFF: {eff:.1f}</span></div>""" if is_rwa else ""
        
        html = f"""<div style="background:#161b22;padding:20px;border-radius:15px;border:1px solid #30363d;color:white;">
            {weight_html}
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;text-align:center;background:rgba(0,0,0,0.2);padding:10px;border-radius:10px;">
                <div><div style="font-size:8px;color:#8b949e;">INVEST</div><div style="font-size:10px;">${h*e:,.0f}</div></div>
                <div><div style="font-size:8px;color:#8b949e;">AVG</div><div style="font-size:10px;">${e:.3f}</div></div>
                <div><div style="font-size:8px;color:#8b949e;">SUPP</div><div style="font-size:10px;color:#3fb950;">{sup if d_sel>0 else '-'}</div></div>
                <div><div style="font-size:8px;color:#8b949e;">RESIST</div><div style="font-size:10px;color:#f85149;">{res if d_sel>0 else '-'}</div></div>
            </div>
            <div style="margin-top:10px;padding:10px;border-left:5px solid {col};background:{col}15;color:{col};font-weight:800;font-size:14px;">
                {stt}<br><span style="font-size:10px;font-weight:400;color:#f0f6fc;">{rs}</span>
            </div>
        </div>"""
        components.html(html, height=180)

with t1:
    for n, i in STRATEGY['RWA'].items(): render_smart_card(n, i, True)
with t2:
    for n, i in STRATEGY['HUNTER'].items(): render_smart_card(n, i, False)
