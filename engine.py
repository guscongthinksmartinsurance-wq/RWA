# engine.py
import requests
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas_ta as ta
import time
import os
import pickle

CACHE_FILE = "price_cache.pkl"

def save_cache(data):
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(data, f)

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "rb") as f:
                return pickle.load(f)
        except: return {}
    return {}

@st.cache_resource
def get_gspread_client():
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except: return None

def load_data_from_sheet(sheet_name, worksheet_name):
    try:
        client = get_gspread_client()
        data = client.open(sheet_name).worksheet(worksheet_name).get_all_records()
        df = pd.DataFrame(data)
        
        # Sửa triệt để lỗi FutureWarning của Pandas bằng cách viết mới
        cols_to_fix = ['Holdings', 'Entry_Price']
        for c in cols_to_fix:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
                df.fillna({c: 0.0}, inplace=True)
                
        return df
    except Exception as e:
        print(f"Lỗi đọc Google Sheet: {e}")
        return pd.DataFrame()

def get_market_data(coin_ids):
    full_data = load_cache()
    fng, btc_d = "50", 50.0
    
    try:
        # Lấy giá trị tổng hợp (Endpoint nhẹ, CoinGecko vẫn trả về bình thường)
        ids = ",".join(coin_ids)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            p_res = response.json()
            if p_res:
                for c_id, val in p_res.items():
                    if c_id not in full_data or not isinstance(full_data[c_id], dict): 
                        full_data[c_id] = {}
                    full_data[c_id].update(val)
                    full_data[c_id]['last_price_update'] = time.time()
                save_cache(full_data)
        
        # Tâm lý thị trường Fear & Greed
        fng_res = requests.get("https://api.alternative.me/fng/", timeout=10).json()
        fng = fng_res['data'][0]['value']
        
        # Bitcoin Dominance
        btc_res = requests.get("https://api.coingecko.com/api/v3/global", timeout=10).json()
        btc_d = btc_res['data']['market_cap_percentage']['btc']
        
    except Exception as e:
        print(f"Lỗi lấy dữ liệu giá tổng quát: {e}")
        pass
    
    return full_data, fng, btc_d

def get_tech_radar(coin_id):
    # Ánh xạ thông minh từ CoinGecko ID sang Ticker của sàn Binance để lấy nến 30 ngày công khai
    ticker_map = {
        'sei-network': 'SEIUSDT',
        'sei': 'SEIUSDT',
        'pepe': 'PEPEUSDT',
        'chainlink': 'LINKUSDT'
    }
    
    symbol = ticker_map.get(coin_id.lower())
    if not symbol:
        return None

    try:
        # Gọi trực tiếp dữ liệu nến ngày từ Binance (Siêu tốc, mở công khai, KHÔNG BAO GIỜ BỊ CHẶN)
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit=30"
        res = requests.get(url, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            # Bốc tách giá đóng cửa (Cột chỉ số thứ 4 trong cấu trúc klines của Binance)
            closes = [float(item[4]) for item in data]
            df = pd.DataFrame(closes, columns=['close'])
            
            # Tính toán bộ công cụ 6 chỉ số liên kết cho Bot quyết định
            rsi = float(df.ta.rsi(length=14).iloc[-1])
            macd_df = df.ta.macd()
            macd = float(macd_df.iloc[-1][0])
            ema20 = float(df.ta.ema(length=20).iloc[-1])
            ema50 = float(df.ta.ema(length=50).iloc[-1])
            sup = float(df['close'].min())
            res_val = float(df['close'].max())
            
            return rsi, macd, ema20, ema50, sup, res_val
            
    except Exception as e:
        print(f"Lỗi kết nối API Binance của {symbol}: {e}")
        
    return None

def analyze_v25_pro(cp, ath, tech):
    if not tech or len(tech) < 6: 
        return "WAITING", "#8b949e", "Đang săn dữ liệu...", 0
        
    rsi, macd, ema20, ema50, sup, res = tech
    dist = ((ath - cp) / ath) * 100 if ath > 0 else 0
    
    # 1. CHIẾN LƯỢC GOM HÀNG VÙNG ĐÁY (STRONG BUY / ACCUMULATE)
    # Kích hoạt khi RSI quá bán HOẶC giá chạm sát vùng hỗ trợ cứng (cách dưới 5%) kèm RSI thấp
    if rsi < 35 or (cp <= sup * 1.05 and rsi < 45):
        if macd > 0:
            return "STRONG BUY", "#3fb950", "Đáy cứng + Dòng tiền hồi phục", dist
        return "ACCUMULATE", "#2ea043", "Vùng gom an toàn, chia vốn DCA", dist
        
    # 2. ĐỘNG LỰC TĂNG TRƯỞNG THEO SONG ĐƯỜNG XU HƯỚNG MẠNH (BULLISH)
    # Kích hoạt khi đường ngắn hạn nằm trên đường trung hạn (EMA20 > EMA50) VÀ mức giá giữ vững trên EMA50
    if ema20 > ema50 and cp > ema50:
        if macd > 0:
            return "STRONG BULL", "#1f6feb", "Sóng tăng khỏe (EMA Cắt + MACD Dương)", dist
        return "BULLISH", "#58a6ff", "Xu hướng tăng bảo toàn, tiếp tục giữ", dist
        
    # 3. CẢNH BÁO XU HƯỚNG ĐI XUỐNG NGẮN HẠN (CAUTION)
    # Kích hoạt khi EMA20 cắt xuống dưới EMA50 và giá bị đẩy xuống dưới đường trung hạn
    if ema20 < ema50 and cp < ema50:
        return "CAUTION", "#d29922", "Xu hướng yếu, chỉ gom thêm tại hỗ trợ SUP", dist

    # 4. CHỐT LỜI KHI ĐẠT ĐỈNH KHÁNG CỰ / QUÁ MUA (TAKE PROFIT)
    if rsi > 70 or (cp >= res * 0.97 and rsi > 65):
        return "TAKE PROFIT", "#f85149", "Gặp cản cứng + Quá mua ngắn hạn", dist
        
    # 5. TRẠNG THÁI THEO DÕI TÍCH LŨY
    return "HOLD", "#8b949e", "Kiên nhẫn quan sát thêm xu hướng", dist
