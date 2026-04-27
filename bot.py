import os
import requests
import time
from datetime import datetime
from dotenv import load_dotenv

# Tải biến môi trường từ file .env
load_dotenv()

# --- CẤU HÌNH ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CRYPTOQUANT_API_KEY = os.getenv("CRYPTOQUANT_API_KEY")

# Ngưỡng cảnh báo
DXY_THRESHOLD = 103.0
NETFLOW_THRESHOLD = 0.0 # Bất kỳ netflow dương nào đều được coi là cảnh báo theo yêu cầu

# Tần suất kiểm tra (24 giờ = 86400 giây)
CHECK_INTERVAL_SECONDS = 24 * 60 * 60

def send_telegram_alert(message):
    """Gửi tin nhắn cảnh báo qua Telegram Bot"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Lỗi: Chưa cấu hình Telegram Bot Token hoặc Chat ID.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"[{datetime.now()}] Đã gửi cảnh báo Telegram thành công.")
    except Exception as e:
        print(f"[{datetime.now()}] Lỗi khi gửi Telegram: {e}")

def get_dxy_data():
    """Lấy dữ liệu DXY (US Dollar Index) qua Yahoo Finance (miễn phí)"""
    try:
        import yfinance as yf
        # Ticker của DXY trên Yahoo Finance là DX=F
        dxy = yf.Ticker("DX=F")
        # Lấy giá trị đóng cửa gần nhất
        data = dxy.history(period="1d")
        if not data.empty:
            current_dxy = data['Close'].iloc[-1]
            return current_dxy
        else:
            print("Không lấy được dữ liệu DXY từ yfinance.")
            return None
    except Exception as e:
        print(f"Lỗi khi lấy dữ liệu DXY: {e}")
        return None

def get_btc_netflow():
    """
    Lấy dữ liệu BTC Exchange Netflow từ CryptoQuant API.
    """
    if not CRYPTOQUANT_API_KEY or CRYPTOQUANT_API_KEY == "your_cryptoquant_api_key_here":
        print("Cảnh báo: Chưa cấu hình CRYPTOQUANT_API_KEY. Bỏ qua kiểm tra Netflow.")
        return None

    try:
        # Gọi CryptoQuant API để lấy Netflow mới nhất
        url = "https://api.cryptoquant.com/v1/btc/exchange-flows/netflow?limit=1"
        headers = {
            "Authorization": f"Bearer {CRYPTOQUANT_API_KEY}"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        # CryptoQuant API thường trả về dictionary với key 'result' chứa mảng data
        result = data.get("result", {}).get("data", [])
        
        if result and len(result) > 0:
            latest_record = result[0]
            # Tùy thuộc vào cấu trúc trả về, 'netflow' có thể là key trực tiếp
            netflow_value = float(latest_record.get('netflow', 0))
            return netflow_value
        else:
            print("Không có dữ liệu Netflow trả về hoặc sai định dạng từ CryptoQuant.")
            return None
            
    except Exception as e:
        print(f"Lỗi khi lấy dữ liệu BTC Netflow từ CryptoQuant: {e}")
        return None

def check_and_alert():
    """Kiểm tra điều kiện và gửi cảnh báo nếu cần"""
    print(f"\n[{datetime.now()}] Bắt đầu kiểm tra dữ liệu...")
    
    dxy_value = get_dxy_data()
    netflow_value = get_btc_netflow()
    
    print(f"DXY hiện tại: {dxy_value if dxy_value is not None else 'N/A'}")
    print(f"BTC Netflow hiện tại: {netflow_value if netflow_value is not None else 'N/A'}")
    
    alerts = []
    
    if dxy_value is not None and dxy_value > DXY_THRESHOLD:
        alerts.append(f"⚠️ <b>CẢNH BÁO DXY</b>\nChỉ số DXY hiện tại là <b>{dxy_value:.2f}</b> (vượt ngưỡng {DXY_THRESHOLD}).")
        
    if netflow_value is not None and netflow_value > NETFLOW_THRESHOLD:
        alerts.append(f"🚨 <b>CẢNH BÁO BTC NETFLOW</b>\nNetflow hiện tại đang DƯƠNG: <b>{netflow_value:.2f} BTC</b> (dấu hiệu xả hàng).")
        
    if alerts:
        message = "\n\n".join(alerts)
        send_telegram_alert(message)
    else:
        print("Mọi thứ bình thường. Không cần gửi cảnh báo.")

def main():
    print("Khởi động Bot Cảnh báo DXY & BTC Netflow...")
    print("Bot sẽ chạy mỗi 24 giờ.")
    
    while True:
        check_and_alert()
        print(f"[{datetime.now()}] Hoàn tất kiểm tra. Sẽ chạy lại sau 24 giờ...")
        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
