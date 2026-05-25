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
        
        # Sửa lỗi gán dữ liệu kiểu cũ của Pandas gây ra dòng cảnh báo màu vàng
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
        ids = ",".join(coin_ids)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            p_res = response.json()
            if p_res:
                for c_id, val in p_res.items():
                    if c_id not in full_data: full_data[c_id] = {}
                    full_data[c_id].update(val)
                    full_data[c_id]['last_price_update'] = time.time()
                save_cache(full_data)
        
        # Lấy dữ liệu tâm lý Fear & Greed
        fng_res = requests.get("https://api.alternative.me/fng/", timeout=10).json()
        fng = fng_res['data'][0]['value']
        
        # Lấy dữ liệu thống trị Bitcoin (BTC Dominance)
        btc_res = requests.get("https://api.coingecko.com/api/v3/global", timeout=10).json()
        btc_d = btc_res['data']['market_cap_percentage']['btc']
        
    except Exception as e:
        print(f"Lỗi lấy dữ liệu giá tổng quát: {e}")
        pass
    
    return full_data, fng, btc_d

def get_tech_radar(coin_id):
    full_data = load_cache()
    current_time = time.time()
    
    cache_entry = full_data.get(coin_id, {})
    
    # Nếu dữ liệu kỹ thuật cũ chưa quá 15 phút, lấy dùng luôn để giải phóng luồng chạy
    if 'rsi' in cache_entry and (current_time - cache_entry.get('last_update', 0) < 900):
        return cache_entry['rsi'], cache_entry['macd'], cache_entry['ema20'], cache_entry['ema50'], cache_entry['sup'], cache_entry['res']

    # Cơ chế phòng thủ chống block API (Nếu có con coin khác vừa gọi API dưới 5 giây, dùng tạm cache cũ)
    last_global_call = full_data.get('last_global_api_call', 0)
    if (current_time - last_global_call) < 5:
        if 'rsi' in cache_entry:
            return cache_entry['rsi'], cache_entry['macd'], cache_entry['ema20'], cache_entry['ema50'], cache_entry['sup'], cache_entry['res']
        return None

    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=30"
        res = requests.get(url, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            if 'prices' in data:
                df = pd.DataFrame([p[1] for p in data['prices']], columns=['close'])
                
                # Tính toán các chỉ báo kỹ thuật
                rsi = df.ta.rsi(length=14).iloc[-1]
                macd_df = df.ta.macd()
                macd = macd_df.iloc[-1][0]
                
                # Tích hợp song đường xu hướng EMA20 và EMA50 theo chuẩn phân tích dòng tiền
                ema20 = df.ta.ema(length=20).iloc[-1]
                ema50 = df.ta.ema(length=50).iloc[-1]
                
                sup, res_val = df['close'].min(), df['close'].max()
                
                # Ghi nhận và lưu trữ vào bộ nhớ cache
                if coin_id not in full_data: full_data[coin_id] = {}
                full_data[coin_id].update({
                    'rsi': rsi, 'macd': macd, 'ema20': ema20, 'ema50': ema50,
                    'sup': sup, 'res': res_val, 'last_update': current_time
                })
                full_data['last_global_api_call'] = current_time
                save_cache(full_data)
                
                return rsi, macd, ema20, ema50, sup, res_val
        elif res.status_code == 429:
            print(f"Bị giới hạn tần suất truy cập tại {coin_id}, chuyển hướng sang sử dụng cache cũ.")
    except Exception as e:
        print(f"Lỗi lấy dữ liệu kỹ thuật của {coin_id}: {e}")
    
    # Cứu cánh cuối cùng nếu nghẽn mạng: Bốc dữ liệu cũ nhất ra để giao diện không bị lỗi hiển thị
    if 'rsi' in cache_entry:
        return cache_entry['rsi'], cache_entry['macd'], cache_entry['ema20'], cache_entry['ema50'], cache_entry['sup'], cache_entry['res']
    
    return None

def analyze_v25_pro(cp, ath, tech):
    if not tech: return "WAITING", "#8b949e", "Đang săn dữ liệu...", 0
    rsi, macd, ema20, ema50, sup, res = tech
    dist = ((ath - cp) / ath) * 100 if ath > 0 else 0
    
    # 1. CHIẾN LƯỢC GOM HÀNG (ACCUMULATE / STRONG BUY)
    # Kích hoạt khi RSI quá bán HOẶC giá chạm sát vùng hỗ trợ cứng (cách dưới 5%) kèm RSI thấp
    if rsi < 35 or (cp <= sup * 1.05 and rsi < 45):
        if macd > 0:
            return "STRONG BUY", "#3fb950", "Đáy cứng + Lực mua phục hồi", dist
        return "ACCUMULATE", "#2ea043", "Vùng gom an toàn, chia vốn DCA", dist
        
    # 2. XU HƯỚNG TĂNG TRƯỞNG MẠNH (BULLISH RIDE - Theo cơ chế dòng tiền của Quỹ)
    # Kích hoạt khi đường ngắn hạn nằm trên đường trung hạn (EMA20 > EMA50) VÀ mức giá giữ vững trên EMA50
    if ema20 > ema50 and cp > ema50:
        if macd > 0:
            return "STRONG BULL", "#1f6feb", "Sóng tăng khỏe (EMA Cắt + MACD Dương)", dist
        return "BULLISH", "#58a6ff", "Xu hướng tăng bảo toàn, tiếp tục giữ", dist
        
    # 3. VÙNG ĐIỀU CHỈNH / NGUY HIỂM TRONG NGẮN HẠN (CAUTION)
    # Kích hoạt khi EMA20 cắt xuống dưới EMA50 và giá bị đẩy xuống dưới đường trung hạn
    if ema20 < ema50 and cp < ema50:
        return "CAUTION", "#d29922", "Xu hướng yếu, chỉ mua khi chạm đáy SUP", dist

    # 4. CHỐT LỜI CHỦ ĐỘNG (TAKE PROFIT)
    # Kích hoạt khi RSI tiến vào vùng hưng phấn Quá mua HOẶC giá áp sát đỉnh kháng cự cũ (cách dưới 3%)
    if rsi > 70 or (cp >= res * 0.97 and rsi > 65):
        return "TAKE PROFIT", "#f85149", "Gặp cản cứng + Quá mua ngắn hạn", dist
        
    # 5. TRẠNG THÁI ĐI NGANG TÍCH LŨY
    return "HOLD", "#8b949e", "Kiên nhẫn quan sát thêm xu hướng", dist
