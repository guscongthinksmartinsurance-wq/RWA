# RWA.py
import streamlit as st
import pandas as pd
from config import STRATEGY, SHEET_NAME, WORKSHEET_NAME
from style import apply_custom_style
from engine import load_data_from_sheet, get_market_data, get_tech_radar, analyze_v25_pro

st.set_page_config(page_title="Sovereign V25", layout="wide")
apply_custom_style()

# 1. LẤY DỮ LIỆU
df_h = load_data_from_sheet(SHEET_NAME, WORKSHEET_NAME)
all_ids = [info['id'] for cat in STRATEGY.values() for info in cat.values()]
prices, fng_val, btc_dom = get_market_data(all_ids)

# --- DASHBOARD TỔNG --- (Giữ nguyên phong cách anh thích)
st.title("🛡️ SOVEREIGN COMMAND CENTER")
# ... (Phần tính toán Total Value và PnL giữ nguyên như bản trước) ...
# ... (Phần hiển thị 4 cột Dashboard giữ nguyên) ...

# 2. TABS CHIẾN LƯỢC
t1, t2 = st.tabs(["🛡️ RWA STRATEGY", "🔍 HUNTER STRATEGY"])

def render_tab(category, tab_obj):
    with tab_obj:
        cols = st.columns(4)
        for i, (symbol, info) in enumerate(STRATEGY[category].items()):
            coin_m = prices.get(info['id'], {})
            cp = coin_m.get('usd', 0)
            chg = coin_m.get('usd_24h_change', 0)
            vol = coin_m.get('usd_24h_vol', 0)
            
            # Lấy Radar kỹ thuật
            tech = get_tech_radar(info['id'])
            
            # Data từ Sheet
            u = df_h[df_h['Coin'] == symbol] if not df_h.empty else pd.DataFrame()
            h, e = (u['Holdings'].iloc[0], u['Entry_Price'].iloc[0]) if not u.empty else (0, 0)
            pnl_p = ((cp/e)-1)*100 if e > 0 else 0
            
            # Phân tích
            stt, col, msg, dist = analyze_v25_pro(cp, info['ath'], tech)
            
            # Giải nén tech data để hiển thị (nếu có)
            rsi, macd, ema20, sup, res = tech if tech else (0,0,0,0,0)

            with cols[i % 4]:
                st.markdown(f"""
                <div class="coin-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <b style="font-size:16px; color:#58a6ff;">{symbol}</b>
                        <span class="status-badge" style="background:{col}; color:white;">{stt}</span>
                    </div>
                    <h2 style="margin:8px 0;">${cp:,.4f} <small style="font-size:11px; color:{'#3fb950' if chg>0 else '#f85149'};">{chg:+.2f}%</small></h2>
                    
                    <div style="font-size:11px; color:#8b949e; display:grid; grid-template-columns:1fr 1fr; gap:4px; line-height:1.5;">
                        <span>Holdings: <b>{h:,.0f}</b></span>
                        <span>PnL: <b style="color:{'#3fb950' if pnl_p>=0 else '#f85149'};">{pnl_p:+.1f}%</b></span>
                        <span>Vol 24h: <b>${vol/1e6:.1f}M</b></span>
                        <span>RSI: <b>{rsi:.1f}</b></span>
                        <span>MACD: <b style="color:{'#3fb950' if macd>0 else '#f85149'};">{macd:.4f}</b></span>
                        <span>Cách ATH: <b>{dist:.1f}%</b></span>
                        <span style="color:#3fb950;">SUP: {sup:,.2f}</span>
                        <span style="color:#f85149;">RES: {res:,.2f}</span>
                    </div>
                    
                    <div style="margin-top:10px; border-top:1px solid #30363d; padding-top:8px; display:flex; justify-content:space-between; font-size:11px;">
                        <span style="color:#3fb950; font-weight:bold;">TP1: ${cp*1.5:,.2f}</span>
                        <span style="color:#d29922; font-weight:bold;">TP2: ${cp*2.0:,.2f}</span>
                    </div>
                    <p style="font-size:10px; color:{col}; margin-top:8px; font-style: italic;">💡 {msg}</p>
                </div>
                """, unsafe_allow_html=True)

render_tab('RWA', t1)
render_tab('HUNTER', t2)
