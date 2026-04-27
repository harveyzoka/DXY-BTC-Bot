import os
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv
import yfinance as yf

# Tải biến môi trường từ file .env
load_dotenv()

# --- CẤU HÌNH ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BGEOMETRICS_API_KEY = os.getenv("BGEOMETRICS_API_KEY")

# Ngưỡng cảnh báo
DXY_THRESHOLD = 103.0
NETFLOW_THRESHOLD = 2000.0 # Cảnh báo khi Netflow Dương đột biến trên 2000 BTC

# File lưu trạng thái DXY ngày hôm trước
STATE_FILE = "dxy_state.txt"

# --- THIẾT LẬP LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot_alert.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def send_telegram_alert(message):
    """Gửi tin nhắn cảnh báo qua Telegram Bot"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.error("Chưa cấu hình Telegram Bot Token hoặc Chat ID.")
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
        logging.info("Đã gửi cảnh báo Telegram thành công.")
    except Exception as e:
        logging.error(f"Lỗi khi gửi Telegram: {e}")

def get_dxy_data():
    """Lấy dữ liệu DXY (US Dollar Index) qua Yahoo Finance (miễn phí)"""
    try:
        # Ticker của DXY trên Yahoo Finance là DX-Y.NYB
        dxy = yf.Ticker("DX-Y.NYB")
        # Lấy giá trị đóng cửa gần nhất
        data = dxy.history(period="1d")
        if not data.empty:
            current_dxy = data['Close'].iloc[-1]
            return current_dxy
        else:
            logging.warning("Không lấy được dữ liệu DXY từ yfinance.")
            return None
    except Exception as e:
        logging.error(f"Lỗi khi lấy dữ liệu DXY: {e}")
        return None

def get_btc_netflow():
    """
    Lấy dữ liệu BTC Exchange Netflow.
    Lưu ý: CryptoQuant API không có free tier cho Data API. 
    Chúng ta dùng BGeometrics làm giải pháp thay thế miễn phí.
    """
    if not BGEOMETRICS_API_KEY or BGEOMETRICS_API_KEY == "your_bgeometrics_api_key_here":
        logging.warning("Chưa cấu hình BGEOMETRICS_API_KEY. Bỏ qua kiểm tra Netflow.")
        return None

    try:
        # Gọi BGeometrics API để lấy Netflow
        url = "https://api.bitcoin-data.com/v1/exchange-netflow-btc"
        headers = {
            "Authorization": f"Bearer {BGEOMETRICS_API_KEY}"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        # Xử lý kết quả trả về dựa trên cấu trúc JSON của API.
        if data and isinstance(data, list) and len(data) > 0:
            # Lấy record mới nhất
            latest_record = data[-1]
            netflow_value = float(latest_record.get('value', 0))
            return netflow_value
        else:
            logging.warning("Không có dữ liệu Netflow trả về hoặc sai định dạng.")
            return None
            
    except Exception as e:
        logging.error(f"Lỗi khi lấy dữ liệu BTC Netflow: {e}")
        return None

def get_previous_dxy():
    """Đọc giá trị DXY ngày hôm trước từ file state"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return float(f.read().strip())
        except Exception as e:
            logging.error(f"Lỗi đọc file trạng thái DXY: {e}")
    return None

def save_current_dxy(dxy_value):
    """Lưu giá trị DXY hiện tại vào file state"""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            f.write(str(dxy_value))
    except Exception as e:
        logging.error(f"Lỗi lưu file trạng thái DXY: {e}")

def check_and_alert():
    """Kiểm tra điều kiện và gửi cảnh báo nếu cần"""
    logging.info("Bắt đầu kiểm tra dữ liệu DXY và BTC Netflow...")
    
    dxy_value = get_dxy_data()
    netflow_value = get_btc_netflow()
    
    logging.info(f"DXY hiện tại: {dxy_value if dxy_value is not None else 'N/A'}")
    logging.info(f"BTC Netflow hiện tại: {netflow_value if netflow_value is not None else 'N/A'}")
    
    alerts = []
    
    # 1. Logic kiểm tra DXY
    if dxy_value is not None:
        prev_dxy = get_previous_dxy()
        
        if dxy_value > DXY_THRESHOLD:
            # Chỉ cảnh báo nếu DXY > 103 VÀ đang trong đà tăng (DXY hôm nay > DXY hôm qua)
            if prev_dxy is None or dxy_value > prev_dxy:
                alerts.append(f"⚠️ <b>CẢNH BÁO DXY</b>\nChỉ số DXY hiện tại là <b>{dxy_value:.2f}</b> (vượt ngưỡng {DXY_THRESHOLD} và đang tăng so với trước đó).")
            else:
                logging.info(f"DXY vượt ngưỡng {DXY_THRESHOLD} nhưng đang giảm ({dxy_value:.2f} <= {prev_dxy:.2f}). Bỏ qua cảnh báo.")
                
        # Lưu lại giá trị cho ngày mai
        save_current_dxy(dxy_value)
        
    # 2. Logic kiểm tra Netflow
    if netflow_value is not None and netflow_value > NETFLOW_THRESHOLD:
        alerts.append(f"🚨 <b>CẢNH BÁO BTC NETFLOW</b>\nNetflow hiện tại đang DƯƠNG đột biến: <b>{netflow_value:.2f} BTC</b> (dấu hiệu xả hàng).")
        
    # 3. Tổng hợp và gửi tin nhắn
    if alerts:
        message = "\n\n".join(alerts)
        send_telegram_alert(message)
    else:
        logging.info("Mọi thứ bình thường. Không cần gửi cảnh báo.")

if __name__ == "__main__":
    # Chạy 1 lần duy nhất thay vì vòng lặp while True, để tiện cấu hình Cronjob
    check_and_alert()
    logging.info("Hoàn tất phiên kiểm tra.")
