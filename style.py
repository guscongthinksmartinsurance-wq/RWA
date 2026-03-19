# style.py
import streamlit as st

def apply_custom_style():
    st.markdown("""
        <style>
        .main { background-color: #0d1117; color: #c9d1d9; }
        .stMetric { background: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
        .coin-card {
            background-color: #161b22; padding: 18px; border-radius: 12px;
            border: 1px solid #30363d; margin-bottom: 15px; min-height: 240px;
        }
        .status-badge { padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; text-transform: uppercase; }
        h1, h2, h3 { color: white !important; }
        /* Tối ưu hiển thị cho mobile */
        @media (max-width: 640px) { .stColumn { margin-bottom: 10px; } }
        </style>
    """, unsafe_allow_html=True)
