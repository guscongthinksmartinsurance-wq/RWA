# engine.py
import requests
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

@st.cache_resource
def get_gspread_client():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

def load_data_from_sheet(sheet_name, worksheet_name):
    try:
        client = get_gspread_client()
        sh = client.open(sheet_name)
        df = pd.DataFrame(sh.worksheet(worksheet_name).get_all_records())
        for c in ['Holdings', 'Entry_Price']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=120)
def get_market_data(coin_ids):
    ids = ",".join(coin_ids)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true"
    # Thêm logic lấy F&G, BTC.D và Funding Rate ở đây...
    return requests.get(url).json()

def analyze_v25_pro(current_price, ath, rsi, macd, ema20):
    # Logic kết hợp kỹ thuật + tâm lý của anh Công
    dist_ath = ((ath - current_price) / ath) * 100 if ath > 0 else 0
    
    if rsi < 35 and current_price > ema20:
        return "ACCUMULATE", "#3fb950", "Dòng tiền đang nén, vùng gom đẹp"
    elif rsi > 70:
        return "BE CAREFUL", "#f85149", "Đám đông đang hưng phấn quá đà"
    return "HOLD", "#d29922", "Kiên nhẫn gồng, chưa có biến động lạ"
