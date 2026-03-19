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
        worksheet = sh.worksheet(worksheet_name)
        df = pd.DataFrame(worksheet.get_all_records())
        
        # Ép kiểu dữ liệu về số như file cũ của anh
        for c in ['Holdings', 'Entry_Price']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=120)
def get_market_data(coin_ids_list):
    ids = ",".join(coin_ids_list)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
    try:
        return requests.get(url).json()
    except:
        return {}

def analyze_v25(current_price, ath):
    dist_ath = ((ath - current_price) / ath) * 100 if ath > 0 else 0
    if dist_ath > 70:
        return "ACCUMULATE", "#3fb950", "Vùng gom cực đẹp", dist_ath
    elif dist_ath > 40:
        return "HOLD", "#d29922", "Đang tích lũy, kiên nhẫn", dist_ath
    return "TAKE PROFIT", "#f85149", "Cẩn thận vùng đỉnh", dist_ath
