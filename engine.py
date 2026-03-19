# engine.py
import requests
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas_ta as ta

# --- 1. KẾT NỐI GOOGLE SHEET ---
@st.cache_resource
def get_gspread_client():
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        # Anh đảm bảo st.secrets đã có gcp_service_account nhé
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Lỗi cấu hình Google Auth: {e}")
        return None

def load_data_from_sheet(sheet_name, worksheet_name):
    try:
        client = get_gspread_client()
        if client:
            sh = client.open(sheet_name)
            worksheet = sh.worksheet(worksheet_name)
            df = pd.DataFrame(worksheet.get_all_records())
            
            # Ép kiểu dữ liệu số cho các cột tính toán của anh Công
            for c in ['Holdings', 'Entry_Price']:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.sidebar.error(f"Không tìm thấy Sheet hoặc Worksheet: {e}")
        return pd.DataFrame()

# --- 2. LẤY DỮ LIỆU THỊ TRƯỜNG & VĨ MÔ ---
@st.cache_data(ttl=120)
def get_market_data(coin_ids):
    try:
        ids = ",".join(coin_ids)
        # Lấy giá và biến động 24h
        price_url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
        prices = requests.get(price_url).json()
        
        # Lấy Fear & Greed Index
        fng_url = "https://api.alternative.me/fng/"
        fng = requests.get(fng_url).json()['data'][0]['value']
        
        # Lấy BTC Dominance
        global_url = "https://api.coingecko.com/api/v3/global"
        btc_d = requests.get(global_url).json()['data']['market_cap_percentage']['btc']
        
        return prices, fng, btc_d
    except:
        return {}, "50", 50.0

# --- 3. RADAR KỸ THUẬT (RSI, MACD, EMA, SUP/RES) ---
@st.cache_data(ttl=300) # Lưu 5 phút để tránh bị CoinGecko chặn (Rate Limit)
def get_technical_indicators(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=30"
        response = requests.get(url)
        data = response.json()
        
        # Kiểm tra nếu bị chặn hoặc không có dữ liệu 'prices'
        if 'prices' not in data:
            return 50.0, 0.0, None, 0.0, 0.0, 0.0

        # Tạo DataFrame từ list giá
        df = pd.DataFrame([p[1] for p in data['prices']], columns=['close'])
        
        # Tính RSI
        rsi = df.ta.rsi(length=14).iloc[-1] if len(df) > 14 else 50.0
        
        # Tính MACD
        macd_df = df.ta.macd()
        macd = macd_df.iloc[-1][0] if not macd_df.empty else 0.0
        
        # Tính EMA 20 (Hỗ trợ động)
        ema20 = df.ta.ema(length=20).iloc[-1] if len(df) > 20 else df['close'].iloc[-1]
        
        # Tính Hỗ trợ/Kháng cự tĩnh trong 30 ngày
        sup = df['close'].min()
        res = df['close'].max()
        
        return rsi, macd, None, ema20, sup, res
    except:
        # Trả về giá trị an toàn nếu có lỗi API
        return 50.0, 0.0, None, 0.0, 0.0, 0.0

# --- 4. LOGIC PHÂN TÍCH V25 PRO ---
def analyze_v25_pro(cp, ath, rsi, macd, ema20):
    dist_ath = ((ath - cp) / ath) * 100 if ath > 0 else 0
    
    # Kết hợp Kỹ thuật + Tâm lý học hành vi
    if rsi < 35:
        return "ACCUMULATE", "#3fb950", "Vùng gom cực đẹp (Tâm lý chán nản)", dist_ath
    elif rsi > 70:
        return "TAKE PROFIT", "#f85149", "Đám đông quá hưng phấn, nên tỉa lãi", dist_ath
    elif macd > 0 and cp > ema20:
        return "BULLISH", "#58a6ff", "Xu hướng tăng bền vững", dist_ath
    
    return "HOLD", "#d29922", "Kiên nhẫn gồng, chưa có biến động lớn", dist_ath
