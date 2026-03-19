# style.py
import streamlit as st

def apply_custom_style():
    st.markdown("""
        <style>
        .main { background-color: #0d1117; color: #c9d1d9; }
        /* Style cho Dashboard Tổng */
        .header-box {
            background: linear-gradient(135deg, #161b22 0%, #0d1117 100%);
            padding: 20px; border-radius: 15px; border: 1px solid #30363d;
            text-align: center; margin-bottom: 20px;
        }
        .metric-value { font-size: 28px; font-weight: bold; color: white; }
        .metric-label { font-size: 12px; color: #8b949e; text-transform: uppercase; }
        
        /* Style cho Card Coin */
        .coin-card {
            background-color: #161b22; padding: 20px; border-radius: 12px;
            border: 1px solid #30363d; margin-bottom: 15px;
        }
        .status-badge { padding: 3px 10px; border-radius: 5px; font-size: 11px; font-weight: bold; }
        h1, h2 { color: white !important; font-family: 'Inter', sans-serif; }
        </style>
    """, unsafe_allow_html=True)
