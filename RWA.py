import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
import requests
import feedparser
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components
import plotly.graph_objects as go

# --- 1. CHIẾN LƯỢC RWA & NHÓM ---
RWA_STRATEGY = {
    'LINK':   {'symbol': 'LINK-USD',   'target_w': 35, 'group': 'RWA', 'ath': 52.8}, 
    'ONDO':   {'symbol': 'ONDO-USD',   'target_w': 20, 'group': 'RWA', 'ath': 2.14},
    'QNT':    {'symbol': 'QNT-USD',    'target_w': 15, 'group': 'RWA', 'ath': 428.0},
    'PENDLE': {'symbol': 'PENDLE-USD', 'target_w': 10, 'group': 'RWA', 'ath': 7.52},
    'SYRUP':  {'symbol': 'MPL-USD',    'target_w': 10, 'group': 'RWA', 'ath': 2.10}, 
    'CFG':    {'symbol': 'CFG-USD',    'target_w': 10, 'group': 'RWA', 'ath': 2.59}
}

# FIX TRIỆT ĐỂ MÃ ARB: Dùng ARB1-USD hoặc ARB-USD tùy vùng dữ liệu
HUNTER_SYMBOLS = {
    'SOL': 'SOL-USD', 'SEI': 'SEI-USD', 'SUI': 'SUI-USD',
    'FET': 'FET-USD', 'ARB': 'ARB1-USD', 'PEPE': 'PEPE1-USD'
}

# --- 2. HÀM PHÂN TÍCH ---
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
    if rsi < 35: score += 1; checks.append(f"✅ RSI LOW ({rsi:.1f})")
    else: checks.append(f"❌ RSI ({rsi:.1f})")
    if cp <= lower_b: score += 1; checks.append(f"✅ BB BOTTOM")
    else: checks.append(f"❌ BB MID")
    if ((cp/sup)-1)*100 < 4: score += 1; checks.append(f"✅ NEAR SUPPORT")
    else: checks.append(f"❌ DISTANCE {((cp/sup)-1)*100:.1f}%")
    if vol > 1.5: score += 1; checks.append(f"🐳 WHALE ACCUMULATION (x{vol:.1f})")
    else: checks.append(f"❌ WEAK VOL (x{vol:.1f})")

    if rsi > 70 or cp >= upper_b * 0.98: stt, col = "EXIT / TAKE PROFIT", "#f85149"
    elif score >= 3: stt, col = "STRONG BUY", "#3fb950"
    elif score == 2: stt, col = ("DCA BUY", "#1f6feb") if has_holdings else ("SPECULATIVE BUY", "#58a6ff")
    else: stt, col = "OBSERVE", "#8b949e"
    return rsi, vol, sup, res, stt, col, " | ".join(checks), float(df['High'].max()), cp*1.5, cp*2.0, eff_score

# --- 3. DỮ LIỆU ---
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
    for col in ['Profit_Realized', 'Holdings', 'Entry_Price']:
        if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return ws, df

st.set_page_config(page_title="RWA Elite Terminal", layout="wide")
ws, df_holdings = load_data()

# --- 4. DASHBOARD & LOGIC ---
all_coins = list(set(list(RWA_STRATEGY.keys()) + list(HUNTER_SYMBOLS.keys()) + df_holdings['Coin'].tolist()))
tickers = yf.Tickers(" ".join([HUNTER_SYMBOLS.get(c, f"{c}-USD") for c in all_coins if c]))
total_val, total_invest, total_realized = 0, 0, float(df_holdings['Profit_Realized'].sum())
tab1_data, tab2_data, p_labels, p_values = [], [], [], []

for coin in all_coins:
    if not coin: continue
    try:
        symbol = HUNTER_SYMBOLS.get(coin, f"{coin}-USD")
        df_h = tickers.tickers[symbol].history(period="60d")
        cp = float(tickers.tickers[symbol].fast_info['last_price'])
        u_row = df_holdings[df_holdings['Coin'] == coin]
        h, e = (float(u_row['Holdings'].values[0]), float(u_row['Entry_Price'].values[0])) if not u_row.empty else (0.0, 0.0)
        pnl_p = ((cp/e)-1)*100 if e > 0 else 0
        rsi, vol, sup, res, stt, col, rs, ath_real, tp1, tp2, eff = analyze_advanced_logic(df_h, cp, 30, h > 0, pnl_p)
        ath_val = RWA_STRATEGY[coin]['ath'] if coin in RWA_STRATEGY else ath_real
        invested, val = h * e, cp * h
        total_val += val; total_invest += invested
        
        card = {"coin": coin, "cp": cp, "stt": stt, "col": col, "rs": rs, "invested": invested, "e": e, "pnl": pnl_p, "sup": sup, "res": res, "ath": ath_val, "tp1": tp1, "tp2": tp2, "eff": eff}
        if val > 0: p_labels.append(coin); p_values.append(val)
        
        # PHÂN BỔ THEO CHIẾN LƯỢC
        if coin in RWA_STRATEGY:
            tw = RWA_STRATEGY[coin]['target_w']
            card.update({"tw": tw, "rw": (val/2000*100), "fill": min((val/2000*100)/tw, 1.0)*100})
            tab1_data.append(card)
        else:
            tab2_data.append(card)
    except: continue

# --- 5. RENDER CARD (PHỤC HỒI THANH TỶ TRỌNG) ---
t1, t2 = st.tabs(["🛡️ STRATEGIC RWA", "🔍 HUNTER SCANNER"])
def render_v12_5(data, is_rwa):
    for d in data:
        eff_color = "#3fb950" if d['eff'] > 1.5 else ("#d29922" if d['eff'] > 0 else "#8b949e")
        # PHỤC HỒI THANH TỶ TRỌNG (PROGRESS BAR)
        progress_html = f"""
        <div style="font-size:12px;color:#8b949e;margin-bottom:8px;">WEIGHT: <b>{d['rw']:.1f}%</b> / {d['tw']}%</div>
        <div style="background:#30363d;border-radius:10px;height:8px;width:100%;margin-bottom:10px;">
            <div style="background:#1f6feb;height:100%;border-radius:10px;width:{d['fill']}%;"></div>
        </div>
        """ if is_rwa and 'tw' in d else ""
        
        html = f"""
        <div style="background:#161b22;padding:25px;border-radius:20px;border:1px solid #30363d;font-family:sans-serif;color:white;margin-bottom:20px;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div style="width:55%;">
                    <div style="font-size:36px;font-weight:900;color:#58a6ff;margin-bottom:2px;">{d['coin']}</div>
                    <div style="font-size:12px;color:{eff_color};font-weight:bold;margin-bottom:8px;">EFFICIENCY SCORE: {d['eff']:.1f}</div>
                    {progress_html}
                </div>
                <div style="text-align:right;"><div style="font-size:46px;font-weight:900;">${d['cp']:.3f}</div><div style="color:{'#3fb950' if d['pnl']>=0 else '#f85149'};font-size:22px;font-weight:800;">{d['pnl']:+.1f}%</div></div>
            </div>
            <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:8px;text-align:center;background:rgba(0,0,0,0.3);padding:20px;border-radius:15px;margin-top:20px;">
                <div><div style="color:#8b949e;font-size:10px;">INVESTED</div><div style="font-size:15px;font-weight:700;color:#58a6ff;">${d['invested']:,.0f}</div></div>
                <div><div style="color:#8b949e;font-size:10px;">AVG</div><div style="font-size:15px;font-weight:700;">${d['e']:.3f}</div></div>
                <div><div style="color:#8b949e;font-size:10px;">SUPPORT</div><div style="font-size:15px;font-weight:700;color:#3fb950;">${d['sup']:.3f}</div></div>
                <div><div style="color:#8b949e;font-size:10px;">RESISTANCE</div><div style="font-size:15px;font-weight:700;color:#f85149;">${d['res']:.3f}</div></div>
                <div><div style="color:#8b949e;font-size:10px;">ATH</div><div style="font-size:15px;font-weight:700;color:#d29922;">${d['ath']:.1f}</div></div>
                <div><div style="color:#8b949e;font-size:10px;">TP1</div><div style="font-size:15px;font-weight:700;color:#3fb950;">${d['tp1']:.2f}</div></div>
                <div><div style="color:#8b949e;font-size:10px;">TP2</div><div style="font-size:15px;font-weight:700;color:#d29922;">${d['tp2']:.2f}</div></div>
            </div>
            <div style="margin-top:20px;padding:15px;border-radius:12px;border-left:8px solid {d['col']};background:{d['col']}15;color:{d['col']};font-weight:800;font-size:18px;">
                {d['stt']}<br><span style="font-size:13px;font-weight:400;color:#f0f6fc;">{d['rs']}</span>
            </div>
        </div>"""
        components.html(html, height=430)

with t1: render_v12_5(tab1_data, True)
with t2: render_v12_5(tab2_data, False)
