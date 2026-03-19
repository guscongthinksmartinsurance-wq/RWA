# RWA.py
import streamlit as st
import pandas as pd
from config import STRATEGY, SHEET_NAME, WORKSHEET_NAME
from style import apply_custom_style
from engine import load_data_from_sheet, get_market_data, analyze_v25

st.set_page_config(page_title="Sovereign V25", layout="wide")
apply_custom_style()

# 1. Lấy dữ liệu
df_holdings = load_data_from_sheet(SHEET_NAME, WORKSHEET_NAME)
all_ids = [info['id'] for cat in STRATEGY.values() for info in cat.values()]
market_data = get_market_data(all_ids)

st.title("🛡️ SOVEREIGN PORTFOLIO V25")
st.sidebar.write(f"Đã kết nối: {WORKSHEET_NAME}")

# 2. Tabs chiến lược
t1, t2 = st.tabs(["🛡️ RWA STRATEGY", "🔍 HUNTER STRATEGY"])

def render_tab(category, tab_obj):
    with tab_obj:
        cols = st.columns(4)
        for i, (symbol, info) in enumerate(STRATEGY[category].items()):
            price = market_data.get(info['id'], {}).get('usd', 0)
            status, color, msg, dist = analyze_v25(price, info['ath'])
            
            # Khớp dữ liệu từ sheet "Holdings"
            # Lưu ý: Cột trong file của anh phải tên là 'Ticker' hoặc 'Symbol'
            holding_row = df_holdings[df_holdings['Ticker'] == symbol] if not df_holdings.empty else pd.DataFrame()
            entry = holding_row['Entry'].values[0] if not holding_row.empty else 0
            qty = holding_row['Holdings'].values[0] if not holding_row.empty else 0
            
            with cols[i]:
                st.markdown(f"""
                <div style="background:#161b22; padding:15px; border-radius:10px; border:1px solid #30363d; margin-bottom:15px;">
                    <div style="display:flex; justify-content:space-between;">
                        <b style="font-size:16px;">{symbol}</b>
                        <span style="font-size:10px; color:{color}; font-weight:bold;">{status}</span>
                    </div>
                    <h2 style="margin:10px 0; color:#c9d1d9;">${price:,.4f}</h2>
                    <div style="font-size:12px; color:#8b949e; line-height:1.6;">
                        Holdings: <b>{qty:,.2f}</b><br/>
                        Entry: <b>${entry:,.4f}</b><br/>
                        Cách ATH: <b>{dist:.1f}%</b>
                    </div>
                    <hr style="border:0; border-top:1px solid #30363d; margin:10px 0;">
                    <p style="font-size:11px; color:{color}; margin:0;">💡 {msg}</p>
                </div>
                """, unsafe_allow_html=True)

render_tab('RWA', t1)
render_tab('HUNTER', t2)