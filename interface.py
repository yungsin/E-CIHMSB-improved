"""
🔐 藏圖秘語 - 方案 A：等比例縮放版
設計基準：1920×1080，所有螢幕等比例縮放
"""

import streamlit as st
import streamlit.components.v1 as components
import numpy as np
from PIL import Image, ImageDraw
import requests
from io import BytesIO
import os
import math
import time
import base64
import json
import qrcode

# 延遲載入 pyzbar（較慢的套件）
@st.cache_resource
def load_pyzbar():
    from pyzbar.pyzbar import decode as decode_qr
    return decode_qr

from config import *
from embed import embed_secret
from extract import detect_and_extract
from secret_encoding import text_to_binary, image_to_binary, binary_to_image

# ==================== 生成高質量圖片函數 ====================
def generate_gradient_image(size, color1, color2, direction='horizontal'):
    img = Image.new('RGB', (size, size))
    for i in range(size):
        ratio = i / size
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)
        for j in range(size):
            if direction == 'horizontal':
                img.putpixel((i, j), (r, g, b))
            else:
                img.putpixel((j, i), (r, g, b))
    return img

# ==================== Icon 圖片轉 Base64 ====================
def get_icon_base64(icon_name):
    """讀取 icons 資料夾的圖片並轉成 base64"""
    icon_path = os.path.join("icons", f"{icon_name}.png")
    if os.path.exists(icon_path):
        with open(icon_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{data}"
    return ""

# ==================== 全局緩存 ====================
if 'embed_result' not in st.session_state:
    st.session_state.embed_result = None
if 'extract_result' not in st.session_state:
    st.session_state.extract_result = None

# ==================== 對象管理 ====================
CONTACTS_FILE = "contacts.json"

def load_contacts():
    """讀取對象資料"""
    try:
        if os.path.exists(CONTACTS_FILE):
            with open(CONTACTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_contacts(contacts):
    """儲存對象資料"""
    with open(CONTACTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(contacts, f, ensure_ascii=False, indent=2)

if 'contacts' not in st.session_state:
    st.session_state.contacts = load_contacts()

# ==================== 圖片庫設定 ====================
STYLE_CATEGORIES = {
    "建築": "建築", "動物": "動物", "植物": "植物",
    "食物": "食物", "交通": "交通",
}

AVAILABLE_SIZES = [64, 128, 256, 512, 1024, 2048, 4096]

IMAGE_LIBRARY = {
    "建築": [
        {"id": 29493117, "name": "哈里發塔"},
        {"id": 34132869, "name": "比薩斜塔"},
        {"id": 16457365, "name": "埃菲爾鐵塔"},
        {"id": 236294, "name": "聖彼得大教堂"},
        {"id": 16681013, "name": "謝赫扎耶德大清真寺"},
        {"id": 29144355, "name": "熨斗大樓"},
        {"id": 1650904, "name": "泰坦尼克博物館"},
    ],
    "動物": [
        {"id": 1108099, "name": "拉布拉多"},
        {"id": 568022, "name": "白羊"},
        {"id": 19613749, "name": "兔子"},
        {"id": 7060929, "name": "刺蝟"},
        {"id": 19597261, "name": "松鼠"},
        {"id": 10386190, "name": "梅花鹿"},
        {"id": 34954771, "name": "栗頭蜂虎"},
    ],
    "植物": [
        {"id": 1048024, "name": "仙人掌"},
        {"id": 11259955, "name": "雛菊"},
        {"id": 6830332, "name": "櫻花"},
        {"id": 7048610, "name": "鬱金香"},
        {"id": 18439973, "name": "洋牡丹"},
        {"id": 244796, "name": "木槿花"},
        {"id": 206837, "name": "勿忘我"},
    ],
    "食物": [
        {"id": 28503601, "name": "海鮮燉飯"},
        {"id": 32538755, "name": "紅醬義大利麵"},
        {"id": 1566837, "name": "比薩"},
        {"id": 7245468, "name": "壽司"},
        {"id": 4110272, "name": "水果拼盤"},
        {"id": 6441084, "name": "草莓蛋糕"},
        {"id": 7144558, "name": "鬆餅"},
    ],
    "交通": [
        {"id": 33435422, "name": "摩托車"},
        {"id": 1595483, "name": "自行車"},
        {"id": 2263673, "name": "巴士"},
        {"id": 33519108, "name": "火車"},
        {"id": 33017407, "name": "飛機"},
        {"id": 843633, "name": "遊艇"},
        {"id": 586040, "name": "火箭"},
    ],
}

def get_recommended_size(secret_bits):
    """根據機密大小推薦最小適合尺寸"""
    for size in AVAILABLE_SIZES:
        capacity = calculate_image_capacity(size)
        if capacity >= secret_bits:
            return size
    return AVAILABLE_SIZES[-1]

@st.cache_data(ttl=86400, show_spinner=False)
def download_image_cached(pexels_id, size):
    """下載並快取圖片（持久化）"""
    url = f"https://images.pexels.com/photos/{pexels_id}/pexels-photo-{pexels_id}.jpeg?auto=compress&cs=tinysrgb&w={size}&h={size}&fit=crop"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.content
    except:
        pass
    return None

def download_image_by_id(pexels_id, size):
    """下載指定 ID 和尺寸的圖片"""
    image_data = download_image_cached(pexels_id, size)
    
    if image_data:
        img = Image.open(BytesIO(image_data)).convert('RGB')
        if img.size[0] != size or img.size[1] != size:
            img = img.resize((size, size), Image.LANCZOS)
        img_gray = img.convert('L')
        return img, img_gray
    
    img = generate_gradient_image(size, (100, 150, 200), (150, 200, 250))
    return img, img.convert('L')

# ==================== 輔助函數 ====================
def calculate_image_capacity(size):
    return (size * size) // 64 * 21

def calculate_required_bits_for_image(image, target_capacity=None):
    original_size, original_mode = image.size, image.mode
    is_color = original_mode not in ['L', '1', 'LA']
    
    if not is_color:
        has_alpha = False
    elif original_mode == 'P':
        temp_img = image.convert('RGBA')
        if temp_img.mode == 'RGBA':
            alpha_channel = temp_img.split()[-1]
            has_alpha = alpha_channel.getextrema()[0] < 255
        else:
            has_alpha = False
    elif original_mode in ['RGBA', 'PA']:
        has_alpha = True
    else:
        has_alpha = False
    
    if is_color:
        header_bits = 66
        bits_per_pixel = 32 if has_alpha else 24
    else:
        header_bits, bits_per_pixel = 66, 8
    
    if target_capacity is None:
        w, h = original_size[0], original_size[1]
        return header_bits + w * h * bits_per_pixel, (w, h)
    
    max_pixels = (target_capacity - header_bits) // bits_per_pixel
    current_pixels = original_size[0] * original_size[1]
    if current_pixels <= max_pixels:
        scaled = original_size
    else:
        ratio = math.sqrt(max_pixels / current_pixels)
        scaled = (max(8, (int(original_size[0] * ratio) // 8) * 8), max(8, (int(original_size[1] * ratio) // 8) * 8))
    return header_bits + scaled[0] * scaled[1] * bits_per_pixel, scaled

# ==================== Z碼圖編碼/解碼 ====================
def encode_z_as_image_with_header(z_bits, img_num, img_size):
    """Z碼圖編碼（含編號和尺寸）"""
    length = len(z_bits)
    header_bits = [int(b) for b in format(length, '032b')]
    header_bits += [int(b) for b in format(img_num, '016b')]
    header_bits += [int(b) for b in format(img_size, '016b')]
    full_bits = header_bits + z_bits
    
    if len(full_bits) % 8 != 0:
        padding = 8 - (len(full_bits) % 8)
        full_bits = full_bits + [0] * padding
    
    pixels = []
    for i in range(0, len(full_bits), 8):
        byte = full_bits[i:i+8]
        pixel_value = int(''.join(map(str, byte)), 2)
        pixels.append(pixel_value)
    
    num_pixels = len(pixels)
    width = int(math.sqrt(num_pixels))
    height = math.ceil(num_pixels / width)
    
    while len(pixels) < width * height:
        pixels.append(0)
    
    image = Image.new('L', (width, height))
    image.putdata(pixels[:width * height])
    
    return image, length

def decode_image_to_z_with_header(image):
    """Z碼圖解碼（含編號和尺寸）"""
    if image.mode != 'L':
        image = image.convert('L')
    
    pixels = list(image.getdata())
    
    all_bits = []
    for pixel in pixels:
        bits = [int(b) for b in format(pixel, '08b')]
        all_bits.extend(bits)
    
    if len(all_bits) < 64:
        raise ValueError("Z碼圖格式錯誤：太小")
    
    z_length = int(''.join(map(str, all_bits[:32])), 2)
    img_num = int(''.join(map(str, all_bits[32:48])), 2)
    img_size = int(''.join(map(str, all_bits[48:64])), 2)
    
    if z_length <= 0 or z_length > len(all_bits) - 64:
        raise ValueError(f"Z碼長度無效：{z_length}")
    
    z_bits = all_bits[64:64 + z_length]
    
    return z_bits, img_num, img_size

# ==================== Streamlit 頁面配置 ====================
st.set_page_config(page_title="🔐 高效能無載體之機密編碼技術", page_icon="🔐", layout="wide", initial_sidebar_state="collapsed")

# ==================== CSS 樣式 ====================
st.markdown("""
<style>
/* 背景圖片 */
.stApp {
    background-image: url('https://i.pinimg.com/736x/53/1a/01/531a01457eca178f01c83ac2ede3f102.jpg');
    background-size: 100% 100%;
    background-position: center;
    background-repeat: no-repeat;
    background-attachment: fixed;
}

/* 隱藏 Streamlit 預設元素 */
header[data-testid="stHeader"],
#MainMenu, footer, .stDeployButton, div[data-testid="stToolbar"],
.viewerBadge_container__r5tak, .viewerBadge_link__qRIco,
div[class*="viewerBadge"], div[class*="StatusWidget"],
[data-testid="manage-app-button"], .stApp > footer,
iframe[title="Streamlit"], div[class*="styles_viewerBadge"],
.stAppDeployButton, section[data-testid="stStatusWidget"] {
    display: none !important;
    visibility: hidden !important;
}

.block-container { padding-top: 1rem !important; }

/* 隱藏側邊欄控制按鈕 */
button[data-testid="collapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
button[data-testid="baseButton-header"],
[data-testid="stSidebarNavCollapseIcon"],
[data-testid="stSidebar"] > button,
[data-testid="stSidebarNav"] button,
[data-testid="stSidebarNavSeparator"],
[data-testid="stSidebarCollapseButton"],
section[data-testid="stSidebar"] > div > button,
section[data-testid="stSidebar"] button[kind="header"],
.st-emotion-cache-1rtdyuf,
.st-emotion-cache-eczf16 {
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    height: 0 !important;
    opacity: 0 !important;
    pointer-events: none !important;
}

/* 自訂標籤：可點擊 */
#sidebar-toggle-label {
    position: fixed;
    top: 88px;
    left: 0;
    background: #4A6B8A;
    color: white;
    writing-mode: vertical-rl;
    padding: 15px 8px;
    border-radius: 0 6px 6px 0;
    font-size: 24px;
    font-weight: bold;
    z-index: 999999;
    cursor: pointer;
    box-shadow: 2px 0 8px rgba(0,0,0,0.15);
    transition: all 0.3s ease;
}
#sidebar-toggle-label:hover {
    padding-left: 12px;
    background: #5C8AAD;
}

/* 主內容區 */
[data-testid="stMain"] {
    margin-left: 0 !important;
    width: 100% !important;
}

/* 側邊欄樣式 */
[data-testid="stSidebar"] {
    position: fixed !important;
    left: 0 !important;
    top: 0 !important;
    height: 100vh !important;
    width: 18rem !important;
    min-width: 18rem !important;
    z-index: 999 !important;
    transition: transform 0.3s ease !important;
    transform: translateX(-100%);
    background-image: url('https://i.pinimg.com/736x/53/1a/01/531a01457eca178f01c83ac2ede3f102.jpg') !important;
    background-size: cover !important;
    background-position: center !important;
    box-shadow: 4px 0 15px rgba(0,0,0,0.2) !important;
}

[data-testid="stSidebar"].sidebar-open {
    transform: translateX(0) !important;
}

[data-testid="stSidebar"] * { color: #443C3C !important; }

[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea {
    background-color: #ecefef !important;
    color: #333 !important;
    border: 1px solid #ccc !important;
}

[data-testid="stSidebar"] h3 {
    font-size: 38px !important;
    font-weight: bold !important;
    color: #4A6B8A !important;
    text-align: center !important;
}

[data-testid="stSidebar"] strong { font-size: 18px !important; }

[data-testid="stSidebar"] [data-testid="stExpander"] summary,
[data-testid="stSidebar"] details summary span {
    font-size: 24px !important;
}

[data-testid="stSidebar"] [data-testid="stExpander"] {
    width: 100% !important;
    background-color: #f7f3ec !important;
    border: 2px solid rgba(200, 200, 200, 0.6) !important;
    border-radius: 10px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
    margin-bottom: 8px !important;
}

/* Expander 標題列背景 */
[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary {
    background-color: #f7f3ec !important;
    border-radius: 8px !important;
}

/* Expander 展開後內容背景 */
[data-testid="stSidebar"] [data-testid="stExpander"] > div {
    background-color: transparent !important;
}

[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    background-color: #e9ded0 !important;
}

/* 側邊欄下拉選單 */
[data-testid="stSidebar"] .stSelectbox > div > div {
    background-color: #ecefef !important;
    color: #333 !important;
    border: 1px solid #ccc !important;
    min-height: 45px !important;
    display: flex !important;
    align-items: center !important;
}

[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] span,
[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] div {
    color: #333 !important;
    font-size: 18px !important;
    overflow: visible !important;
}

[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] > div {
    padding-top: 3px !important;
    padding-bottom: 6px !important;
}

/* 只禁用 selectbox 的搜索輸入，不影響 text_input */
[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] input {
    pointer-events: none !important;
    caret-color: transparent !important;
    opacity: 0 !important;
    width: 1px !important;
}

/* 側邊欄輸入框 - 確保可以輸入 */
[data-testid="stSidebar"] .stTextInput input {
    background-color: #ecefef !important;
    color: #333 !important;
    border: 1px solid #ccc !important;
    pointer-events: auto !important;
    opacity: 1 !important;
    caret-color: #333 !important;
}

[data-testid="stSidebar"] input,
[data-testid="stSidebar"] select,
[data-testid="stSidebar"] button {
    font-size: 18px !important;
}

/* 側邊欄按鈕白色背景 */
[data-testid="stSidebar"] .stButton button {
    background-color: #ecefef !important;
    color: #333 !important;
    border: 1px solid #ccc !important;
}

[data-testid="stSidebar"] .stButton button:hover {
    background-color: #e8e8e8 !important;
    border-color: #999 !important;
}

/* 側邊欄 primary 按鈕 */
[data-testid="stSidebar"] .stButton button[kind="primary"] {
    background: #8ba7c8 !important;
    color: white !important;
    border: none !important;
}

[data-testid="stSidebar"] [data-testid="stBaseButton-header"],
[data-testid="stSidebar"] button[kind="header"] {
    display: none !important;
}

/* 首頁樣式 */
.home-fullscreen {
    width: 100%;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: center;
    padding: 35px 0;
    box-sizing: border-box;
}

.welcome-title {
    font-size: 68px;
    font-weight: bold;
    letter-spacing: 0.18em;
    padding-left: 0.18em;
    white-space: nowrap;
    background: linear-gradient(135deg, #4A6B8A 0%, #7D5A6B 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.cards-container {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 40px;
}

.footer-credits {
    text-align: center;
    color: #5D5D5D;
    font-size: 28px;
    font-weight: 500;
}

/* 動畫卡片 */
.anim-card {
    width: 500px;
    height: 340px;
    padding: 30px 40px;
    border-radius: 20px;
    text-align: center;
    cursor: pointer;
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    position: relative;
    overflow: hidden;
    box-shadow: 8px 8px 0px 0px rgba(60, 80, 100, 0.4);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
}

.anim-card:hover {
    transform: translateY(-8px) scale(1.02);
    box-shadow: 12px 12px 0px 0px rgba(60, 80, 100, 0.5);
}

.anim-card-embed { background: linear-gradient(145deg, #7BA3C4 0%, #5C8AAD 100%); }
.anim-card-extract { background: linear-gradient(145deg, #C4A0AB 0%, #A67B85 100%); }

.anim-flow {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    margin-bottom: 20px;
    font-size: 36px;
    height: 100px;
}

.anim-flow img { width: 90px !important; height: 90px !important; }
.anim-flow .arrow { width: 70px !important; height: 70px !important; }

.anim-title {
    font-size: 56px;
    font-weight: bold;
    color: #FFFFFF;
    margin-bottom: 15px;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
}

.anim-desc {
    font-size: 36px;
    color: rgba(255,255,255,0.9);
    line-height: 1.5;
    white-space: nowrap;
}

/* 功能頁面樣式 */
.page-title-embed {
    font-size: clamp(36px, 4vw, 56px);
    font-weight: bold;
    background: linear-gradient(135deg, #4A6B8A 0%, #5C8AAD 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.page-title-extract {
    font-size: clamp(36px, 4vw, 56px);
    font-weight: bold;
    background: linear-gradient(135deg, #7D5A6B 0%, #A67B85 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

/* 訊息框 */
.success-box {
    background: linear-gradient(135deg, #4A6B8A 0%, #5C8AAD 100%);
    color: white; padding: 20px 30px; border-radius: 10px;
    margin: 10px 0; display: inline-block; font-size: clamp(20px, 2.5vw, 28px); min-width: 300px;
}
.info-box {
    background: linear-gradient(135deg, #4A6B8A 0%, #5C8AAD 100%);
    color: white; padding: 20px 30px; border-radius: 10px;
    margin: 10px 0; display: inline-block; font-size: clamp(18px, 2vw, 26px); line-height: 1.9; min-width: 300px;
}
.error-box {
    background: linear-gradient(135deg, #8B5A5A 0%, #A67B7B 100%);
    color: white; padding: 20px 30px; border-radius: 10px;
    margin: 10px 0; display: inline-block; font-size: clamp(18px, 2vw, 26px); min-width: 300px;
}

/* 字體放大 */
[data-testid="stMain"] .stMarkdown p,
[data-testid="stMain"] .stText p {
    font-size: clamp(22px, 2.5vw, 30px) !important;
    font-weight: bold !important;
}

h3 { font-size: clamp(28px, 3vw, 36px) !important; font-weight: bold !important; }

/* 按鈕樣式 */
.stButton button span,
.stButton button p {
    font-size: 18px !important;
    font-weight: bold !important;
}

[data-testid="stMain"] .stButton button[kind="primary"] {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
}

[data-testid="stSidebar"] .stButton button[kind="primary"] {
    background: #8ba7c8 !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
}

/* 表單元素 */
.stSelectbox label, .stRadio label, .stTextArea label, .stFileUploader label,
[data-testid="stWidgetLabel"] p {
    font-size: clamp(18px, 2vw, 24px) !important;
    font-weight: bold !important;
}

.stRadio [role="radiogroup"] label,
.stRadio [role="radiogroup"] label p {
    font-size: clamp(20px, 2.2vw, 28px) !important;
    color: #443C3C !important;
    font-weight: bold !important;
}

/* Radio 按鈕水平對齊 */
.stRadio [role="radiogroup"] label {
    display: flex !important;
    align-items: center !important;
}

.stRadio [role="radiogroup"] label > div:first-child {
    display: flex !important;
    align-items: center !important;
}

.stTextArea textarea {
    font-size: clamp(22px, 2.5vw, 30px) !important;
    background-color: #ecefef !important;
    border: 1px solid #ccc !important;
    border-radius: 8px !important;
    color: #333 !important;
    padding: 12px !important;
    caret-color: #333 !important;
}

/* 隱藏 textarea 滾動條 */
.stTextArea textarea::-webkit-scrollbar,
.stTextArea *::-webkit-scrollbar,
.stTextArea > div::-webkit-scrollbar,
.stTextArea > div > div::-webkit-scrollbar {
    display: none !important;
    width: 0 !important;
}

.stTextArea textarea,
.stTextArea *,
.stTextArea > div,
.stTextArea > div > div {
    scrollbar-width: none !important;
    -ms-overflow-style: none !important;
}

.stTextArea textarea {
    overflow-y: auto !important;
    overflow-x: hidden !important;
}

.stTextArea [data-baseweb="textarea"],
.stTextArea [data-baseweb="base-input"] {
    overflow: hidden !important;
}

.stTextArea textarea:focus {
    outline: none !important;
    border-color: #ccc !important;
}

.stTextArea textarea::placeholder {
    color: #888 !important;
    opacity: 1 !important;
}

/* 移除 textarea 底部黑線 */
.stTextArea [data-baseweb="textarea"] {
    border: none !important;
    background-color: transparent !important;
}

.stTextArea [data-baseweb="base-input"] {
    border-bottom: none !important;
    border: none !important;
    background-color: transparent !important;
}

.stTextArea > div > div {
    border-bottom: none !important;
    background-color: transparent !important;
}

.stTextArea > div > div > div {
    border-bottom: none !important;
    background-color: #ecefef !important;
}

.stTextArea [data-baseweb="textarea"]::after,
.stTextArea [data-baseweb="base-input"]::after {
    display: none !important;
}

/* 隱藏 Ctrl+Enter 提示 */
.stTextArea [data-testid="stTextAreaRootContainer"] > div:last-child,
.stTextArea .st-emotion-cache-1gulkj5 {
    display: none !important;
}

.stCaption, [data-testid="stCaptionContainer"] {
    color: #443C3C !important;
    font-size: clamp(16px, 1.8vw, 22px) !important;
}

/* Selectbox 樣式 */
[data-testid="stMain"] .stSelectbox > div > div {
    background-color: #ecefef !important;
    border-radius: 8px !important;
    min-height: 55px !important;
    border: 1px solid #ccc !important;
}

[data-testid="stMain"] .stSelectbox [data-baseweb="select"] span,
[data-testid="stMain"] .stSelectbox [data-baseweb="select"] div {
    font-size: 20px !important;
    font-weight: bold !important;
    color: #333 !important;
}

[data-baseweb="popover"] li {
    background-color: #ecefef !important;
    font-size: 22px !important;
    font-weight: normal !important;
    color: #333 !important;
    min-height: 50px !important;
    padding: 12px 16px !important;
}

/* 下拉列表容器背景 */
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
ul[role="listbox"] {
    background-color: #ecefef !important;
}

[data-baseweb="popover"] li span,
[data-baseweb="popover"] li div,
[data-baseweb="popover"] [role="option"],
[data-baseweb="popover"] [role="option"] *,
[data-baseweb="menu"] li,
[data-baseweb="menu"] li *,
ul[role="listbox"] li,
ul[role="listbox"] li * {
    color: #333 !important;
    background-color: #ecefef !important;
    font-size: 22px !important;
    font-weight: normal !important;
}

ul[role="listbox"] li:hover,
[data-baseweb="menu"] li:hover {
    background-color: #dce0e0 !important;
}

/* ===== 下拉選單勾選標記顏色 ===== */
[data-baseweb="menu"] li svg,
[data-baseweb="select"] svg[data-baseweb="icon"],
ul[role="listbox"] li svg,
[data-baseweb="popover"] li svg,
[data-baseweb="menu"] [aria-selected="true"] svg,
ul[role="listbox"] [aria-selected="true"] svg {
    fill: #443C3C !important;
    color: #443C3C !important;
}

/* ===== 下拉選單滾動條樣式 ===== */
[data-baseweb="menu"]::-webkit-scrollbar,
[data-baseweb="popover"]::-webkit-scrollbar,
[data-baseweb="popover"] > div::-webkit-scrollbar,
[data-baseweb="popover"] ul::-webkit-scrollbar,
ul[role="listbox"]::-webkit-scrollbar,
div[data-baseweb="popover"] *::-webkit-scrollbar {
    width: 8px !important;
    background: #f5f0e6 !important;
}

[data-baseweb="menu"]::-webkit-scrollbar-track,
[data-baseweb="popover"]::-webkit-scrollbar-track,
[data-baseweb="popover"] > div::-webkit-scrollbar-track,
[data-baseweb="popover"] ul::-webkit-scrollbar-track,
ul[role="listbox"]::-webkit-scrollbar-track,
div[data-baseweb="popover"] *::-webkit-scrollbar-track {
    background: #f5f0e6 !important;
    border-radius: 4px !important;
}

[data-baseweb="menu"]::-webkit-scrollbar-thumb,
[data-baseweb="popover"]::-webkit-scrollbar-thumb,
[data-baseweb="popover"] > div::-webkit-scrollbar-thumb,
[data-baseweb="popover"] ul::-webkit-scrollbar-thumb,
ul[role="listbox"]::-webkit-scrollbar-thumb,
div[data-baseweb="popover"] *::-webkit-scrollbar-thumb {
    background: #b8a88a !important;
    border-radius: 4px !important;
}

[data-baseweb="menu"]::-webkit-scrollbar-thumb:hover,
[data-baseweb="popover"]::-webkit-scrollbar-thumb:hover,
[data-baseweb="popover"] > div::-webkit-scrollbar-thumb:hover,
[data-baseweb="popover"] ul::-webkit-scrollbar-thumb:hover,
ul[role="listbox"]::-webkit-scrollbar-thumb:hover,
div[data-baseweb="popover"] *::-webkit-scrollbar-thumb:hover {
    background: #9a8b6e !important;
}

/* Firefox 滾動條 */
[data-baseweb="menu"],
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="popover"] ul,
ul[role="listbox"] {
    scrollbar-width: thin !important;
    scrollbar-color: #b8a88a #f5f0e6 !important;
}

/* 全局下拉選單滾動條覆蓋 */
body div[data-baseweb="popover"] *::-webkit-scrollbar,
body [data-baseweb="select"] ~ div *::-webkit-scrollbar,
[data-baseweb="base-popover"] *::-webkit-scrollbar {
    width: 8px !important;
    background: #f5f0e6 !important;
}

body div[data-baseweb="popover"] *::-webkit-scrollbar-thumb,
body [data-baseweb="select"] ~ div *::-webkit-scrollbar-thumb,
[data-baseweb="base-popover"] *::-webkit-scrollbar-thumb {
    background: #b8a88a !important;
    border-radius: 4px !important;
}

body div[data-baseweb="popover"] *::-webkit-scrollbar-track,
body [data-baseweb="select"] ~ div *::-webkit-scrollbar-track,
[data-baseweb="base-popover"] *::-webkit-scrollbar-track {
    background: #f5f0e6 !important;
    border-radius: 4px !important;
}

/* 確保選中的值完整顯示 */
[data-baseweb="select"] > div {
    min-height: 45px !important;
    padding: 8px !important;
}

[data-baseweb="select"] [data-testid="stMarkdownContainer"],
[data-baseweb="select"] .css-1dimb5e-singleValue,
[data-baseweb="select"] div[class*="singleValue"] {
    overflow: visible !important;
    text-overflow: unset !important;
    white-space: nowrap !important;
}

/* 固定按鈕容器 */
.fixed-btn-next {
    position: fixed !important;
    bottom: 50px !important;
    right: 30px !important;
    z-index: 1000 !important;
}

.fixed-btn-back {
    position: fixed !important;
    bottom: 50px !important;
    left: 30px !important;
    z-index: 1000 !important;
}

.fixed-btn-next button,
.fixed-btn-back button {
    font-size: 18px !important;
    padding: 12px 36px !important;
    min-width: 120px !important;
    border-radius: 8px !important;
}

/* 間距調整 */
.block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 7rem !important;
    max-width: 1400px !important;
    margin: 0 auto !important;
}

/* 功能頁面容器居中 */
[data-testid="stMain"] > .block-container {
    max-width: 1400px !important;
    margin: 0 auto !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}

/* 內容區域對齊步驟條 */
[data-testid="stMain"] .stSelectbox,
[data-testid="stMain"] .stTextArea,
[data-testid="stMain"] .stFileUploader,
[data-testid="stMain"] .stRadio {
    max-width: 1200px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

[data-testid="stMain"] .stMarkdown {
    max-width: 1200px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

/* 大螢幕優化 */
@media (min-width: 1600px) {
    [data-testid="stMain"] > .block-container {
        max-width: 1500px !important;
        padding-left: 3rem !important;
        padding-right: 3rem !important;
    }
    
    .page-title-embed, .page-title-extract {
        font-size: 56px !important;
    }
}

/* 全螢幕模式優化 */
@media (min-height: 900px) {
    .block-container {
        padding-top: 1rem !important;
    }
}

.stMarkdown hr { margin: 0.5rem 0 !important; }
.stSelectbox, .stTextArea, .stFileUploader, .stRadio { margin-bottom: 0.3rem !important; }

[data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    gap: 0.5rem !important;
    max-width: 1200px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}
</style>
""", unsafe_allow_html=True)

# JavaScript 強制修改下拉選單滾動條顏色
components.html("""
<script>
function injectScrollbarStyle() {
    const css = `
        *::-webkit-scrollbar { width: 8px !important; }
        *::-webkit-scrollbar-track { background: #f5f0e6 !important; border-radius: 4px !important; }
        *::-webkit-scrollbar-thumb { background: #b8a88a !important; border-radius: 4px !important; }
        *::-webkit-scrollbar-thumb:hover { background: #9a8b6e !important; }
        * { scrollbar-width: thin !important; scrollbar-color: #b8a88a #f5f0e6 !important; }
        
        /* 隱藏 textarea 滾動條 */
        .stTextArea *::-webkit-scrollbar { display: none !important; width: 0 !important; }
        .stTextArea * { scrollbar-width: none !important; -ms-overflow-style: none !important; }
        textarea::-webkit-scrollbar { display: none !important; width: 0 !important; }
        textarea { scrollbar-width: none !important; -ms-overflow-style: none !important; }
        [data-baseweb="textarea"] *::-webkit-scrollbar { display: none !important; width: 0 !important; }
        [data-baseweb="base-input"] *::-webkit-scrollbar { display: none !important; width: 0 !important; }
    `;
    
    // 注入到當前 document
    const style1 = document.createElement('style');
    style1.textContent = css;
    document.head.appendChild(style1);
    
    // 注入到 parent document (Streamlit 主頁面)
    if (window.parent && window.parent.document && window.parent.document.head) {
        const style2 = document.createElement('style');
        style2.textContent = css;
        style2.id = 'custom-scrollbar-style';
        if (!window.parent.document.getElementById('custom-scrollbar-style')) {
            window.parent.document.head.appendChild(style2);
        }
        
        // 直接找到所有 textarea 並設定樣式
        const textareas = window.parent.document.querySelectorAll('textarea');
        textareas.forEach(ta => {
            ta.style.overflow = 'hidden';
            ta.style.scrollbarWidth = 'none';
            ta.style.msOverflowStyle = 'none';
        });
        
        // 找到 stTextArea 容器
        const textAreaContainers = window.parent.document.querySelectorAll('.stTextArea, [data-baseweb="textarea"]');
        textAreaContainers.forEach(container => {
            container.style.overflow = 'hidden';
            const allChildren = container.querySelectorAll('*');
            allChildren.forEach(child => {
                child.style.overflow = 'hidden';
                child.style.scrollbarWidth = 'none';
            });
        });
    }
}

injectScrollbarStyle();
setTimeout(injectScrollbarStyle, 300);
setTimeout(injectScrollbarStyle, 1000);
setTimeout(injectScrollbarStyle, 2000);

// 監聽 DOM 變化，新元素出現時也隱藏滾動條
if (window.parent && window.parent.document) {
    const observer = new MutationObserver(injectScrollbarStyle);
    observer.observe(window.parent.document.body, { childList: true, subtree: true });
}
</script>
""", height=0)

# ==================== 初始化狀態 ====================
if 'current_mode' not in st.session_state:
    st.session_state.current_mode = None

# ==================== 側邊欄 - 對象管理 ====================
if st.session_state.current_mode is not None:
    with st.sidebar:
        st.markdown("""
        <style>
        section[data-testid="stSidebar"] details summary span p { font-size: 22px !important; }
        #built-contacts-title { font-size: 28px !important; font-weight: bold !important; margin-bottom: 10px !important; text-align: center !important; }
        </style>
        <div id="sidebar-close-btn" style="position: absolute; top: -15px; right: 0px; 
            width: 30px; height: 30px; background: #e0e0e0; border-radius: 50%; 
            display: flex; align-items: center; justify-content: center; 
            cursor: pointer; font-size: 18px; color: #666; z-index: 9999;">✕</div>
        """, unsafe_allow_html=True)
        
        st.markdown('<h3 style="font-size: 36px; margin-bottom: 15px;">對象管理</h3>', unsafe_allow_html=True)
        
        contacts = st.session_state.contacts
        style_options = ["選擇"] + list(STYLE_CATEGORIES.keys())
        
        # 新增對象
        with st.expander("新增對象", expanded=False):
            add_counter = st.session_state.get('add_contact_counter', 0)
            new_name = st.text_input("名稱", key=f"sidebar_new_name_{add_counter}")
            new_style = st.selectbox("綁定風格", style_options, key=f"sidebar_new_style_{add_counter}")
            
            can_add = new_name and new_name.strip() and new_style != "選擇"
            if st.button("新增", key="sidebar_add_btn", use_container_width=True, disabled=not can_add, type="primary" if can_add else "secondary"):
                st.session_state.contacts[new_name.strip()] = new_style
                save_contacts(st.session_state.contacts)
                st.toast(f"✅ 已新增「{new_name.strip()}」")
                st.session_state.add_contact_counter = add_counter + 1
                st.rerun()
        
        st.markdown("---")
        st.markdown('<div id="built-contacts-title">對象列表</div>', unsafe_allow_html=True)
        
        if contacts:
            for name, style in contacts.items():
                style_display = STYLE_CATEGORIES.get(style, style) if style else "未綁定"
                display_text = f"{name}（{style_display}）"
                
                with st.expander(display_text, expanded=False):
                    new_nickname = st.text_input("名稱", value=name, key=f"new_name_{name}")
                    new_style_edit = st.selectbox("風格", style_options, 
                        index=style_options.index(style) if style in style_options else 0,
                        key=f"new_style_{name}")
                    
                    has_change = (new_nickname.strip() != name) or (new_style_edit != style)
                    
                    if st.button("儲存修改", key=f"save_{name}", use_container_width=True, type="primary" if has_change else "secondary"):
                        if new_nickname.strip() != name:
                            del st.session_state.contacts[name]
                        st.session_state.contacts[new_nickname.strip()] = new_style_edit if new_style_edit != "選擇" else None
                        save_contacts(st.session_state.contacts)
                        st.rerun()
                    
                    if st.button("刪除", key=f"del_{name}", use_container_width=True):
                        del st.session_state.contacts[name]
                        save_contacts(st.session_state.contacts)
                        st.rerun()
        else:
            st.markdown('<p style="font-size: 22px; color: #666;">尚無對象</p>', unsafe_allow_html=True)

# ==================== 主要邏輯 ====================
if st.session_state.current_mode is None:
    # ==================== 首頁 ====================
    
    st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"], .main, [data-testid="stMain"] {
        overflow: hidden !important;
        height: 100vh !important;
    }
    .block-container {
        padding-bottom: 0 !important;
        height: 100vh !important;
        overflow: hidden !important;
    }
    iframe {
        height: calc(100vh - 20px) !important;
        min-height: 700px !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    icon_secret = get_icon_base64("secret-message")
    icon_image = get_icon_base64("public-image")
    icon_arrow = get_icon_base64("arrow")
    icon_zcode = get_icon_base64("z-code")
    
    components.html(f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html, body {{ 
        height: 100%;
        min-height: 100vh;
    }}
    body {{ 
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        background: transparent;
        overflow: hidden;
        display: flex;
        justify-content: center;
        align-items: center;
    }}
    
    .home-fullscreen {{
        width: 100%;
        max-width: 1920px;
        margin: 0 auto;
        height: 100%;
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        align-items: center;
        padding: 5vh 2vw 3vh 2vw;
    }}
    
    .welcome-container {{
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
    }}
    
    .welcome-title {{
        font-size: clamp(37px, 6.3vw, 115px);
        font-weight: bold;
        letter-spacing: 0.1em;
        white-space: nowrap;
        background: linear-gradient(135deg, #4A6B8A 0%, #7D5A6B 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }}
    
    .cards-container {{
        display: flex;
        justify-content: center;
        align-items: center;
        gap: clamp(40px, 6vw, 100px);
        flex-wrap: nowrap;
        padding: 0 2vw;
        max-width: 1600px;
    }}
    
    .anim-card {{
        width: clamp(280px, 38vw, 620px);
        height: clamp(200px, 28vw, 420px);
        padding: clamp(15px, 2vw, 35px) clamp(20px, 3vw, 50px);
        border-radius: 20px;
        text-align: center;
        cursor: pointer;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        box-shadow: 8px 8px 0px 0px rgba(60, 80, 100, 0.4);
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }}
    
    .anim-card:hover {{
        transform: translateY(-8px) scale(1.02);
        box-shadow: 12px 12px 0px 0px rgba(60, 80, 100, 0.5);
    }}
    
    .anim-card-embed {{ background: linear-gradient(145deg, #7BA3C4 0%, #5C8AAD 100%); }}
    .anim-card-extract {{ background: linear-gradient(145deg, #C4A0AB 0%, #A67B85 100%); }}
    
    .anim-flow {{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: clamp(5px, 1vw, 10px);
        margin-bottom: clamp(15px, 2vw, 32px);
        height: clamp(60px, 10vw, 150px);
    }}
    
    .anim-flow img {{
        width: clamp(50px, 8vw, 130px);
        height: clamp(45px, 7vw, 110px);
        object-fit: contain;
    }}
    
    .anim-flow img.arrow {{
        width: clamp(40px, 6vw, 100px);
        height: clamp(35px, 5vw, 85px);
    }}
    
    .anim-flow span {{
        font-size: clamp(24px, 3.5vw, 52px);
        color: white;
        font-weight: bold;
    }}
    
    .anim-title {{
        font-size: clamp(28px, 4.5vw, 68px);
        font-weight: bold;
        color: white;
        margin-bottom: clamp(10px, 1.5vw, 22px);
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
    }}
    
    .anim-desc {{
        font-size: clamp(18px, 3vw, 52px);
        color: rgba(255,255,255,0.9);
        line-height: 1.4;
        white-space: nowrap;
    }}
    
    .footer-credits {{
        text-align: center;
        color: #5D5D5D;
        font-size: clamp(20px, 3vw, 50px);
        font-weight: 500;
        padding-bottom: 2vh;
    }}
    
    /* 統一脈動動畫 - 排除載體圖（第2張） */
    .anim-card-embed img:not(:nth-of-type(2)),
    .anim-card-extract img:not(:nth-of-type(2)) {{
        animation: pulse 2s ease-in-out infinite;
    }}
    
    @keyframes pulse {{
        0%, 100% {{ transform: scale(1); }}
        50% {{ transform: scale(1.1); }}
    }}
    </style>
    </head>
    <body>
    <div class="home-fullscreen">
        <div class="welcome-container">
            <div class="welcome-title">高效能無載體之機密編碼技術</div>
        </div>
        
        <div class="cards-container">
            <div class="anim-card anim-card-embed" onclick="clickEmbed()">
                <div class="anim-flow">
                    <img src="{icon_secret}" alt="secret">
                    <span>+</span>
                    <img src="{icon_image}" alt="image">
                    <img src="{icon_arrow}" class="arrow" alt="arrow">
                    <img src="{icon_zcode}" alt="zcode">
                </div>
                <div class="anim-title">嵌入機密</div>
                <div class="anim-desc">基於載體圖像<br>生成編碼圖像</div>
            </div>
            
            <div class="anim-card anim-card-extract" onclick="clickExtract()">
                <div class="anim-flow">
                    <img src="{icon_zcode}" alt="zcode">
                    <span>+</span>
                    <img src="{icon_image}" alt="image">
                    <img src="{icon_arrow}" class="arrow" alt="arrow">
                    <img src="{icon_secret}" alt="secret">
                </div>
                <div class="anim-title">提取機密</div>
                <div class="anim-desc">參考相同載體圖像<br>重建機密訊息</div>
            </div>
        </div>
        
        <div class="footer-credits">
            組員：鄭凱譽、劉佳典、王于婕
        </div>
    </div>
    
    <script>
    const parentDoc = window.parent.document;
    
    function clickEmbed() {{
        const buttons = parentDoc.querySelectorAll('button');
        buttons.forEach(b => {{ if (b.innerText.includes('嵌入')) b.click(); }});
    }}
    
    function clickExtract() {{
        const buttons = parentDoc.querySelectorAll('button');
        buttons.forEach(b => {{ if (b.innerText.includes('提取')) b.click(); }});
    }}
    
    function hideStreamlitBadges() {{
        const selectors = [
            '[class*="viewerBadge"]',
            'a[href*="streamlit.io"]',
            '[class*="StatusWidget"]',
            '[data-testid="manage-app-button"]',
            '.stAppDeployButton',
            'section[data-testid="stStatusWidget"]',
            '[class*="stDeployButton"]',
            '[class*="AppDeployButton"]'
        ];
        selectors.forEach(sel => {{
            parentDoc.querySelectorAll(sel).forEach(el => {{
                el.style.display = 'none';
            }});
        }});
    }}
    
    hideStreamlitBadges();
    setTimeout(hideStreamlitBadges, 500);
    setTimeout(hideStreamlitBadges, 1000);
    setTimeout(hideStreamlitBadges, 2000);
    </script>
    </body>
    </html>
    """, height=900, scrolling=False)
    
    # 動態調整 iframe 高度
    components.html("""
    <script>
    (function() {
        const iframe = window.frameElement;
        if (iframe) {
            iframe.style.height = 'calc(100vh - 50px)';
            iframe.style.minHeight = '700px';
        }
    })();
    </script>
    """, height=0)
    
    # 隱藏的按鈕
    col1, col2 = st.columns(2)
    with col1:
        if st.button("開始嵌入", key="btn_embed", use_container_width=True):
            st.session_state.current_mode = 'embed'
            st.session_state.prev_embed_image_select = None
            st.session_state.prev_contact = None
            st.rerun()
    with col2:
        if st.button("開始提取", key="btn_extract", use_container_width=True):
            st.session_state.current_mode = 'extract'
            st.rerun()
    
    components.html("""
<script>
const doc = window.parent.document;
function hideHomeButtons() {
    const buttons = doc.querySelectorAll('button');
    buttons.forEach(btn => {
        const text = btn.innerText || btn.textContent;
        if (text.includes('開始嵌入') || text.includes('開始提取')) {
            btn.style.cssText = 'position:fixed!important;top:-9999px!important;left:-9999px!important;opacity:0!important;';
        }
    });
}
hideHomeButtons();
setTimeout(hideHomeButtons, 100);
new MutationObserver(hideHomeButtons).observe(doc.body, { childList: true, subtree: true });
</script>
""", height=0)


elif st.session_state.current_mode == 'embed':
    # ==================== 嵌入模式 ====================
    
    if 'embed_page' not in st.session_state:
        st.session_state.embed_page = 'input'
    
    # 結果頁
    if st.session_state.embed_page == 'result' and st.session_state.embed_result and st.session_state.embed_result.get('success'):
        st.markdown('<style>.main { overflow: auto !important; }</style>', unsafe_allow_html=True)
        
        r = st.session_state.embed_result
        
        st.markdown('<div class="page-title-embed" style="text-align: center; margin-bottom: 30px;">嵌入結果</div>', unsafe_allow_html=True)
        
        spacer_left, col_left, col_gap, col_right, spacer_right = st.columns([1.2, 2, 0.5, 2, 0.3])
        
        with col_left:
            st.markdown(f'<div class="success-box">嵌入成功! ({r["elapsed_time"]:.2f} 秒)</div>', unsafe_allow_html=True)
            
            img_num = r["embed_image_choice"].split("-")[1]
            img_name = r.get("image_name", "")
            img_size = r.get("image_size", "")
            secret_filename = r.get("secret_filename", "")
            secret_bits = r.get("secret_bits", 0)
            capacity = r.get("capacity", 0)
            usage_percent = r.get("usage_percent", 0)
            
            if r['embed_secret_type'] == "文字":
                secret_display = r["secret_desc"]
            else:
                size_info = r["secret_desc"].replace("圖片: ", "")
                secret_display = f'圖片: {secret_filename} ({size_info})' if secret_filename else r["secret_desc"]
            
            st.markdown(f'<div class="info-box"><strong>嵌入資訊</strong><br><br>載體圖像編號：<strong>{img_num}</strong>（{img_name}）<br>載體圖像尺寸：{img_size}×{img_size}<br>機密內容：<br>{secret_display}<br>容量：{secret_bits:,} / {capacity:,} bits ({usage_percent:.1f}%)</div>', unsafe_allow_html=True)
        
        with col_right:
            if r['embed_secret_type'] == "文字":
                z_text = ''.join(str(b) for b in r['z_bits'])
                img_num = r["embed_image_choice"].split("-")[1]
                img_size = r["embed_image_choice"].split("-")[2]
                qr_content = f"{img_num}-{img_size}|{z_text}"
                
                try:
                    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=2)
                    qr.add_data(qr_content)
                    qr.make(fit=True)
                    qr_pil = qr.make_image(fill_color="black", back_color="white").convert('RGB')
                    
                    buf = BytesIO()
                    qr_pil.save(buf, format='PNG')
                    qr_bytes = buf.getvalue()
                    
                    st.markdown('<p style="font-size: 34px; font-weight: bold;">Z碼圖</p>', unsafe_allow_html=True)
                    st.image(qr_bytes, width=250)
                    st.download_button("下載 Z碼圖", qr_bytes, "z_code.png", "image/png", key="dl_z_qr")
                    st.markdown('<p style="font-size: 30px; color: #443C3C;">傳送 Z碼圖給對方</p>', unsafe_allow_html=True)
                except:
                    img_num_int = int(img_num)
                    img_size_int = int(img_size)
                    z_img, _ = encode_z_as_image_with_header(r['z_bits'], img_num_int, img_size_int)
                    
                    st.markdown('<p style="font-size: 34px; font-weight: bold;">Z碼圖</p>', unsafe_allow_html=True)
                    st.image(z_img, width=250)
                    buf = BytesIO()
                    z_img.save(buf, format='PNG')
                    st.download_button("下載圖片", buf.getvalue(), "z_code.png", "image/png", key="dl_z_img_fallback")
                    st.markdown('<p style="font-size: 30px; color: #443C3C;">傳送 Z碼圖給對方</p>', unsafe_allow_html=True)
            else:
                img_num = int(r["embed_image_choice"].split("-")[1])
                img_size = int(r["embed_image_choice"].split("-")[2])
                z_img, _ = encode_z_as_image_with_header(r['z_bits'], img_num, img_size)
                
                st.markdown('<p style="font-size: 34px; font-weight: bold;">Z碼圖</p>', unsafe_allow_html=True)
                st.image(z_img, width=250)
                buf = BytesIO()
                z_img.save(buf, format='PNG')
                st.download_button("下載圖片", buf.getvalue(), "z_code.png", "image/png", key="dl_z_img")
                st.markdown('<p style="font-size: 30px; color: #443C3C;">傳送 Z碼圖給對方</p>', unsafe_allow_html=True)
        
        st.markdown("""
        <style>
        #btn-back-home { position: fixed !important; bottom: 5px !important; right: 30px !important; z-index: 1000 !important; background: white !important; color: #333 !important; border: 2px solid #ccc !important; border-radius: 8px !important; }
        </style>
        """, unsafe_allow_html=True)
        
        col_left, col_right = st.columns([1, 1])
        with col_right:
            if st.button("返回首頁", key="back_to_home_from_embed"):
                st.session_state.embed_page = 'input'
                st.session_state.embed_result = None
                st.session_state.embed_step = 1
                st.session_state.current_mode = None
                st.rerun()
        
        components.html("""
        <script>
        const buttons = window.parent.document.querySelectorAll('button');
        for (let btn of buttons) { if (btn.innerText === '返回首頁') btn.id = 'btn-back-home'; }
        </script>
        """, height=0)
    
    # 輸入頁
    else:
        st.session_state.embed_page = 'input'
        st.markdown('<div id="sidebar-toggle-label">對象管理</div>', unsafe_allow_html=True)
        
        components.html("""
<script>
(function() {
    const doc = window.parent.document;
    
    function closeSidebar() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        const label = doc.getElementById('sidebar-toggle-label');
        if (sidebar) sidebar.classList.remove('sidebar-open');
        if (label) label.style.display = 'block';
    }
    
    function openSidebar() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        const label = doc.getElementById('sidebar-toggle-label');
        if (sidebar) sidebar.classList.add('sidebar-open');
        if (label) label.style.display = 'none';
    }
    
    function setup() {
        const label = doc.getElementById('sidebar-toggle-label');
        if (label && !label.hasAttribute('data-bound')) {
            label.setAttribute('data-bound', 'true');
            label.addEventListener('click', openSidebar);
        }
        const closeBtn = doc.getElementById('sidebar-close-btn');
        if (closeBtn) closeBtn.onclick = closeSidebar;
    }
    
    setup();
    setTimeout(setup, 100);
    setTimeout(setup, 500);
    new MutationObserver(setup).observe(doc.body, { childList: true, subtree: true });
})();
</script>
""", height=0)
        
        st.markdown('<div class="page-title-embed" style="text-align: center; margin-bottom: 20px; margin-top: 3rem;">嵌入機密</div>', unsafe_allow_html=True)
        
        embed_text, embed_image, secret_bits_needed = None, None, 0
        embed_image_choice, selected_size = None, None
        
        contacts = st.session_state.contacts
        contact_names = list(contacts.keys())
        
        # 初始化狀態
        if 'embed_step1_done' not in st.session_state:
            st.session_state.embed_step1_done = False
        if 'embed_step2_done' not in st.session_state:
            st.session_state.embed_step2_done = False
        
        # 檢查各步驟完成狀態
        selected_contact = st.session_state.get('selected_contact_saved', None)
        step1_done = selected_contact and selected_contact != "選擇"
        
        secret_bits_saved = st.session_state.get('secret_bits_saved', 0)
        step2_done = secret_bits_saved > 0
        
        # 三欄並排佈局 - 加大寬度
        st.markdown("""
        <style>
        [data-testid="stMain"] [data-testid="stHorizontalBlock"] {
            max-width: 100% !important;
            width: 100% !important;
            gap: 2rem !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1, 1], gap="large")
        
        # ===== 第一步：選擇對象 =====
        with col1:
            st.markdown(f"""
            <div style="text-align: center; padding: 10px; border-bottom: {'4px solid #4A6B8A' if not step1_done else '4px solid #28a745'}; margin-bottom: 15px;">
                <span style="font-size: 28px; font-weight: bold; color: {'#4A6B8A' if not step1_done else '#28a745'};">第一步: 選擇對象</span>
            </div>
            """, unsafe_allow_html=True)
            
            if contact_names:
                options = ["選擇"] + contact_names
                saved_contact = st.session_state.get('selected_contact_saved', None)
                default_idx = options.index(saved_contact) if saved_contact and saved_contact in options else 0
                
                selected = st.selectbox("對象", options, index=default_idx, key="contact_select_h", label_visibility="collapsed")
                
                if selected != "選擇":
                    st.session_state.selected_contact_saved = selected
                    st.markdown(f'<p style="font-size: 22px; color: #443C3C;">已選擇：{selected}</p>', unsafe_allow_html=True)
                    step1_done = True
                else:
                    st.session_state.selected_contact_saved = None
                    step1_done = False
            else:
                st.markdown("""<div style="background: #fff2cc; border: none; border-radius: 8px; padding: 10px; text-align: center;">
                    <div style="font-size: 20px; font-weight: bold; color: #856404;">⚠️ 請先新增對象</div>
                </div>""", unsafe_allow_html=True)
        
        # ===== 第二步：機密內容 =====
        with col2:
            st.markdown(f"""
            <div style="text-align: center; padding: 10px; border-bottom: {'4px solid #B8C8D8' if not step1_done else ('4px solid #28a745' if step2_done else '4px solid #4A6B8A')}; margin-bottom: 15px;">
                <span style="font-size: 28px; font-weight: bold; color: {'#B8C8D8' if not step1_done else ('#28a745' if step2_done else '#4A6B8A')};">第二步: 機密內容</span>
            </div>
            """, unsafe_allow_html=True)
            
            if step1_done:
                saved_type = st.session_state.get('embed_secret_type_saved', '文字')
                type_idx = 0 if saved_type == "文字" else 1
                embed_secret_type = st.radio("類型", ["文字", "圖片"], index=type_idx, key="embed_type_h", horizontal=True, label_visibility="collapsed")
                
                if embed_secret_type == "文字":
                    saved_text = st.session_state.get('embed_text_saved', '')
                    embed_text_raw = st.text_area("輸入機密", value=saved_text, placeholder="輸入機密訊息...", height=100, key="embed_text_h", label_visibility="collapsed")
                    if embed_text_raw and embed_text_raw.strip():
                        embed_text = embed_text_raw.strip()
                        secret_bits_needed = len(text_to_binary(embed_text))
                        st.session_state.secret_bits_saved = secret_bits_needed
                        st.session_state.embed_text_saved = embed_text
                        st.session_state.embed_secret_type_saved = "文字"
                        st.markdown(f'<p style="font-size: 20px; color: #28a745;">✅ {secret_bits_needed:,} bits</p>', unsafe_allow_html=True)
                        step2_done = True
                    else:
                        st.session_state.secret_bits_saved = 0
                        step2_done = False
                else:
                    embed_img_file = st.file_uploader("上傳圖片", type=["jpg", "jpeg", "png"], key="embed_img_h", label_visibility="collapsed")
                    if embed_img_file:
                        embed_img_file.seek(0)
                        secret_img = Image.open(embed_img_file)
                        secret_bits_needed, _ = calculate_required_bits_for_image(secret_img)
                        st.session_state.secret_bits_saved = secret_bits_needed
                        st.session_state.embed_secret_type_saved = "圖片"
                        embed_img_file.seek(0)
                        st.session_state.embed_secret_image_data = embed_img_file.read()
                        st.session_state.embed_secret_image_name = embed_img_file.name
                        st.image(secret_img, width=120)
                        st.markdown(f'<p style="font-size: 20px; color: #28a745;">✅ {secret_bits_needed:,} bits</p>', unsafe_allow_html=True)
                        step2_done = True
                    elif st.session_state.get('embed_secret_image_data'):
                        secret_img = Image.open(BytesIO(st.session_state.embed_secret_image_data))
                        st.image(secret_img, width=120)
                        st.markdown(f'<p style="font-size: 20px; color: #28a745;">✅ {st.session_state.get("secret_bits_saved", 0):,} bits</p>', unsafe_allow_html=True)
                        step2_done = True
                    else:
                        st.session_state.secret_bits_saved = 0
                        step2_done = False
            else:
                st.markdown('<p style="font-size: 24px; color: #999; text-align: center;">請先完成第一步</p>', unsafe_allow_html=True)
        
        # ===== 第三步：載體圖像 =====
        with col3:
            st.markdown(f"""
            <div style="text-align: center; padding: 10px; border-bottom: {'4px solid #B8C8D8' if not step2_done else '4px solid #4A6B8A'}; margin-bottom: 15px;">
                <span style="font-size: 28px; font-weight: bold; color: {'#B8C8D8' if not step2_done else '#4A6B8A'};">第三步: 載體圖像</span>
            </div>
            """, unsafe_allow_html=True)
            
            if step2_done:
                secret_bits_needed = st.session_state.get('secret_bits_saved', 0)
                selected_contact = st.session_state.get('selected_contact_saved', '選擇')
                
                style_list = list(STYLE_CATEGORIES.keys())
                auto_style = contacts.get(selected_contact, None)
                default_style_index = style_list.index(auto_style) if auto_style and auto_style != "選擇" and auto_style in style_list else 0
                
                selected_style = st.selectbox("風格", style_list, index=default_style_index, key="embed_style_h")
                
                style_name = STYLE_CATEGORIES.get(selected_style, "建築")
                images = IMAGE_LIBRARY.get(style_name, [])
                
                if images:
                    image_options = [f"{i+1}. {images[i]['name']}" for i in range(len(images))]
                    img_idx = st.selectbox("圖片", range(len(images)), format_func=lambda i: image_options[i], key="embed_img_select_h")
                    
                    available_sizes = [s for s in AVAILABLE_SIZES if calculate_image_capacity(s) >= secret_bits_needed]
                    if not available_sizes:
                        available_sizes = [AVAILABLE_SIZES[-1]]
                    recommended_size = available_sizes[0]
                    
                    size_options = [f"{s}×{s} ⭐" if s == recommended_size else f"{s}×{s}" for s in available_sizes]
                    size_idx = st.selectbox("尺寸", range(len(available_sizes)), format_func=lambda i: size_options[i], key="embed_size_h")
                    selected_size = available_sizes[size_idx]
                    
                    selected_image = images[img_idx]
                    preview_size = 150
                    img_display, _ = download_image_by_id(selected_image["id"], preview_size)
                    st.image(img_display, width=150)
                    
                    capacity = calculate_image_capacity(selected_size)
                    usage = secret_bits_needed / capacity * 100
                    color = "#ffa726" if usage > 90 else "#28a745"
                    st.markdown(f'<p style="font-size: 18px; color: {color};">{usage:.1f}% 使用</p>', unsafe_allow_html=True)
                    
                    st.session_state.embed_image_id = selected_image["id"]
                    st.session_state.embed_image_size = selected_size
                    st.session_state.embed_image_name = selected_image["name"]
                    embed_image_choice = f"{style_name}-{img_idx+1}-{selected_size}"
            else:
                st.markdown('<p style="font-size: 24px; color: #999; text-align: center;">請先完成第二步</p>', unsafe_allow_html=True)
        
        # ===== 開始嵌入按鈕 =====
        st.markdown("<br>", unsafe_allow_html=True)
        
        all_done = step1_done and step2_done and st.session_state.get('embed_image_id')
        
        if all_done:
            embed_btn = st.button("開始嵌入", type="primary", key="embed_btn_horizontal")
            
            components.html("""
            <script>
            function fixButtons() {
                const buttons = window.parent.document.querySelectorAll('button');
                for (let btn of buttons) { 
                    if (btn.innerText === '開始嵌入') {
                        let container = btn.closest('.stButton') || btn.parentElement.parentElement.parentElement;
                        if (container) {
                            container.style.cssText = 'position:fixed!important;bottom:50px!important;right:30px!important;left:auto!important;width:auto!important;z-index:1000!important;';
                        }
                    }
                }
            }
            fixButtons();
            setTimeout(fixButtons, 100);
            </script>
            """, height=0)
            
            if embed_btn:
                processing_placeholder = st.empty()
                processing_placeholder.markdown("""
                <div style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 9999; display: flex; justify-content: center; align-items: center;">
                    <div style="background: white; padding: 40px 60px; border-radius: 16px; text-align: center;">
                        <div style="font-size: 28px; font-weight: bold; color: #5D6D7E; margin-bottom: 20px;">🔄 嵌入中...</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                try:
                    start = time.time()
                    image_id = st.session_state.get('embed_image_id')
                    image_size = st.session_state.get('embed_image_size')
                    _, img_process = download_image_by_id(image_id, image_size)
                    capacity = calculate_image_capacity(image_size)
                    
                    embed_secret_type = st.session_state.get('embed_secret_type_saved', '文字')
                    embed_text = st.session_state.get('embed_text_saved', None)
                    
                    if embed_secret_type == "文字" and embed_text:
                        secret_content = embed_text
                        secret_type_flag = 'text'
                        secret_desc = f'文字: "{embed_text}"'
                        secret_filename = None
                    elif embed_secret_type == "圖片":
                        secret_img_data = st.session_state.get('embed_secret_image_data')
                        if secret_img_data:
                            secret_content = Image.open(BytesIO(secret_img_data))
                            secret_type_flag = 'image'
                            secret_desc = f"圖片: {secret_content.size[0]}×{secret_content.size[1]} px"
                            secret_filename = st.session_state.get('embed_secret_image_name', 'image.png')
                    
                    z_bits, used_capacity, info = embed_secret(img_process, secret_content, secret_type=secret_type_flag)
                    processing_placeholder.empty()
                    
                    st.session_state.embed_result = {
                        'success': True, 'elapsed_time': time.time()-start,
                        'embed_image_choice': embed_image_choice, 'secret_desc': secret_desc,
                        'embed_secret_type': embed_secret_type, 'z_bits': z_bits,
                        'image_name': st.session_state.get('embed_image_name', ''),
                        'image_size': image_size, 'secret_filename': secret_filename,
                        'secret_bits': info['bits'], 'capacity': capacity,
                        'usage_percent': info['bits']*100/capacity
                    }
                    for key in ['selected_contact_saved', 'secret_bits_saved', 'embed_text_saved', 'embed_secret_type_saved', 'embed_secret_image_data', 'embed_secret_image_name']:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.session_state.embed_page = 'result'
                    st.rerun()
                except Exception as e:
                    processing_placeholder.empty()
                    st.markdown(f'<div class="error-box">❌ 嵌入失敗! {e}</div>', unsafe_allow_html=True)

else:
    # ==================== 提取模式 ====================
    
    if 'extract_page' not in st.session_state:
        st.session_state.extract_page = 'input'
    
    # 結果頁
    if st.session_state.extract_page == 'result' and st.session_state.extract_result and st.session_state.extract_result.get('success'):
        st.markdown('<style>.main { overflow: auto !important; }</style>', unsafe_allow_html=True)
        
        r = st.session_state.extract_result
        
        st.markdown('<div class="page-title-extract" style="text-align: center; margin-bottom: 30px;">提取結果</div>', unsafe_allow_html=True)
        
        spacer_left, c1, c2, spacer_right = st.columns([1, 2, 2, 1])
        with c1:
            st.markdown(f'<div class="success-box" style="font-size: 24px;">提取成功! ({r["elapsed_time"]:.2f} 秒)</div>', unsafe_allow_html=True)
            
            if r['type'] == 'text':
                st.markdown('<p style="font-size: 28px; font-weight: bold; margin-top: 15px;">機密文字:</p>', unsafe_allow_html=True)
                st.markdown(f'<p style="font-size: 20px; color: #443C3C; white-space: pre-wrap;">{r["content"]}</p>', unsafe_allow_html=True)
            else:
                st.markdown('<p style="font-size: 28px; font-weight: bold; margin-top: 15px;">機密圖片:</p>', unsafe_allow_html=True)
                st.image(Image.open(BytesIO(r['image_data'])), width=200)
                st.download_button("下載圖片", r['image_data'], "recovered.png", "image/png", key="dl_rec")
        
        with c2:
            st.markdown('<p style="font-size: 28px; font-weight: bold;">驗證結果</p>', unsafe_allow_html=True)
            if r['type'] == 'text':
                verify_input = st.text_area("輸入原始機密", key="verify_text_input", height=50, placeholder="貼上嵌入時的原始機密內容...")
                if st.button("驗證", key="verify_btn"):
                    if verify_input:
                        if verify_input == r['content']:
                            st.markdown('<p style="font-size: 22px; font-weight: bold; color: #2E7D32;">✅ 完全一致！</p>', unsafe_allow_html=True)
                        else:
                            st.markdown('<p style="font-size: 22px; font-weight: bold; color: #C62828;">❌ 不一致！</p>', unsafe_allow_html=True)
            else:
                verify_img = st.file_uploader("上傳原始機密圖片", type=["png", "jpg", "jpeg"], key="verify_img_upload")
                if verify_img:
                    orig_img = Image.open(verify_img)
                    extracted_img = Image.open(BytesIO(r['image_data']))
                    
                    col_orig, col_ext = st.columns(2)
                    with col_orig:
                        st.markdown('<p style="font-size: 20px; font-weight: bold;">原始圖片</p>', unsafe_allow_html=True)
                        st.image(orig_img, width=150)
                    with col_ext:
                        st.markdown('<p style="font-size: 20px; font-weight: bold;">提取結果</p>', unsafe_allow_html=True)
                        st.image(extracted_img, width=150)
                    
                    orig_arr = np.array(orig_img.convert('RGB'))
                    ext_arr = np.array(extracted_img.convert('RGB'))
                    
                    if orig_arr.shape == ext_arr.shape:
                        mse = np.mean((orig_arr.astype(int) - ext_arr.astype(int)) ** 2)
                        if mse == 0:
                            st.markdown(f'<p style="color: #2E7D32;">MSE: {mse:.4f} - ✅ 完全一致！</p>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<p style="color: #F57C00;">MSE: {mse:.4f}</p>', unsafe_allow_html=True)
        
        if st.button("返回首頁", key="back_to_home_from_extract"):
            st.session_state.extract_page = 'input'
            st.session_state.extract_result = None
            st.session_state.current_mode = None
            st.rerun()
    
    # 輸入頁
    else:
        st.session_state.extract_page = 'input'
        st.markdown('<div id="sidebar-toggle-label">對象管理</div>', unsafe_allow_html=True)
        
        components.html("""
<script>
(function() {
    const doc = window.parent.document;
    function closeSidebar() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        const label = doc.getElementById('sidebar-toggle-label');
        if (sidebar) sidebar.classList.remove('sidebar-open');
        if (label) label.style.display = 'block';
    }
    function openSidebar() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        const label = doc.getElementById('sidebar-toggle-label');
        if (sidebar) sidebar.classList.add('sidebar-open');
        if (label) label.style.display = 'none';
    }
    function setup() {
        const label = doc.getElementById('sidebar-toggle-label');
        if (label && !label.hasAttribute('data-bound')) {
            label.setAttribute('data-bound', 'true');
            label.addEventListener('click', openSidebar);
        }
        const closeBtn = doc.getElementById('sidebar-close-btn');
        if (closeBtn) closeBtn.onclick = closeSidebar;
    }
    setup();
    setTimeout(setup, 100);
    new MutationObserver(setup).observe(doc.body, { childList: true, subtree: true });
})();
</script>
""", height=0)
        
        st.markdown('<div class="page-title-extract" style="text-align: center; margin-bottom: 20px; margin-top: 1rem;">提取機密</div>', unsafe_allow_html=True)
        
        extract_z_text, extract_img_num, extract_img_size = None, None, None
        
        contacts = st.session_state.contacts
        contact_names = list(contacts.keys())
        
        if 'extract_step' not in st.session_state:
            st.session_state.extract_step = 1
        
        current_step = st.session_state.extract_step
        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; margin-bottom: 20px; max-width: 1200px; margin-left: auto; margin-right: auto;">
            <div style="flex: 1; text-align: center; padding: 15px 10px; border-bottom: {'4px solid #7D5A6B' if current_step == 1 else '2px solid #D8C0C8'}; color: {'#7D5A6B' if current_step == 1 else '#A08090'}; font-size: clamp(20px, 2.5vw, 30px); font-weight: 700;">第一步: 選擇對象</div>
            <div style="flex: 1; text-align: center; padding: 15px 10px; border-bottom: {'4px solid #7D5A6B' if current_step == 2 else '2px solid #D8C0C8'}; color: {'#7D5A6B' if current_step == 2 else '#A08090'}; font-size: clamp(20px, 2.5vw, 30px); font-weight: 700;">第二步: 上傳 Z碼圖</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        show_next_btn = False
        next_step = 1
        style_name = None
        
        if st.session_state.extract_step == 1:
            st.markdown('<p style="font-size: 30px; font-weight: bold; margin-bottom: 10px; color: #443C3C;">選擇對象</p>', unsafe_allow_html=True)
            if contact_names:
                options = ["選擇"] + contact_names
                saved_contact = st.session_state.get('extract_contact_saved', None)
                default_idx = options.index(saved_contact) if saved_contact and saved_contact in contact_names else 0
                
                selected_contact = st.selectbox("對象", options, index=default_idx, key="extract_contact_select", label_visibility="collapsed")
                
                if selected_contact != "選擇":
                    st.session_state.extract_contact_saved = selected_contact
                    auto_style = contacts[selected_contact]
                    
                    style_list = list(STYLE_CATEGORIES.keys())
                    default_style_index = style_list.index(auto_style) if auto_style and auto_style in style_list else 0
                    
                    selected_style = st.selectbox("風格", style_list, index=default_style_index, key="extract_style_select")
                    style_name = STYLE_CATEGORIES.get(selected_style, "建築")
                    st.session_state.extract_style_saved = selected_style
                    
                    st.markdown(f'<p style="font-size: 26px; color: #31333F;">✅ 已選擇：{selected_contact}（{selected_style}）</p>', unsafe_allow_html=True)
                    show_next_btn = True
                    next_step = 2
            else:
                st.markdown("""<div style="background: #fff2cc; border: none; border-radius: 12px; padding: 15px; text-align: center;"><div style="font-size: 16px; font-weight: bold; color: #856404;">⚠️ 請先新增對象</div></div>""", unsafe_allow_html=True)
        
        elif st.session_state.extract_step == 2:
            saved_contact = st.session_state.get('extract_contact_saved', None)
            saved_style = st.session_state.get('extract_style_saved', None)
            
            if saved_contact and saved_contact in contact_names:
                style_name = STYLE_CATEGORIES.get(saved_style, "建築")
                st.markdown(f'<p style="font-size: 24px; color: #31333F;">對象：{saved_contact}（{saved_style}）</p>', unsafe_allow_html=True)
                
                st.markdown('<p style="font-size: 26px; font-weight: bold; margin-bottom: 10px;">上傳 Z碼圖</p>', unsafe_allow_html=True)
                extract_file = st.file_uploader("上傳 QR Code 或 Z碼圖", type=["png", "jpg", "jpeg"], key="extract_z_upload", label_visibility="collapsed")
                
                if extract_file:
                    uploaded_img = Image.open(extract_file)
                    detected = False
                    success_msg = ""
                    
                    try:
                        decode_qr = load_pyzbar()
                        decoded = decode_qr(uploaded_img)
                        if decoded:
                            qr_content = decoded[0].data.decode('utf-8')
                            if '|' in qr_content:
                                header, z_text = qr_content.split('|', 1)
                                parts = header.split('-')
                                if len(parts) == 2:
                                    extract_img_num = int(parts[0])
                                    extract_img_size = int(parts[1])
                                    extract_z_text = z_text
                                    images = IMAGE_LIBRARY.get(style_name, [])
                                    img_name = images[extract_img_num - 1]['name'] if extract_img_num <= len(images) else str(extract_img_num)
                                    success_msg = f"QR Code：圖片 {extract_img_num}（{img_name}），尺寸 {extract_img_size}×{extract_img_size}"
                                    detected = True
                    except:
                        pass
                    
                    if not detected:
                        try:
                            z_bits, img_num, img_size = decode_image_to_z_with_header(uploaded_img)
                            extract_img_num = img_num
                            extract_img_size = img_size
                            extract_z_text = ''.join(str(b) for b in z_bits)
                            images = IMAGE_LIBRARY.get(style_name, [])
                            img_name = images[extract_img_num - 1]['name'] if extract_img_num <= len(images) else str(extract_img_num)
                            success_msg = f"Z碼圖：圖片 {extract_img_num}（{img_name}），尺寸 {extract_img_size}×{extract_img_size}"
                            detected = True
                        except:
                            pass
                    
                    col_left, col_img, col_info, col_right = st.columns([1.2, 0.6, 2, 0.5])
                    with col_img:
                        st.image(uploaded_img, width=200)
                    with col_info:
                        if detected:
                            st.markdown(f'<div style="display: flex; align-items: center; min-height: 180px;"><div style="font-size: 22px; color: #443C3C; margin-left: 50px;">{success_msg}</div></div>', unsafe_allow_html=True)
                        else:
                            st.markdown('<div style="display: flex; align-items: center; min-height: 180px;"><div style="font-size: 22px; color: #C62828; margin-left: 50px;">無法識別</div></div>', unsafe_allow_html=True)
        
        if st.session_state.extract_step >= 2:
            if st.button("返回", key="extract_back_step_btn"):
                st.session_state.extract_step -= 1
                st.rerun()
        
        if show_next_btn and st.session_state.extract_step < 2:
            if st.button("下一步", type="primary", key="extract_next_btn"):
                st.session_state.extract_step = next_step
                st.rerun()
        
        if st.session_state.extract_step == 2 and extract_z_text and extract_img_num and extract_img_size:
            extract_btn = st.button("開始提取", type="primary", key="extract_start_btn")
            
            if extract_btn:
                processing_placeholder = st.empty()
                processing_placeholder.markdown("""
                <div style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 9999; display: flex; justify-content: center; align-items: center;">
                    <div style="background: white; padding: 40px 60px; border-radius: 16px; text-align: center;">
                        <div style="font-size: 28px; font-weight: bold; color: #5D6D7E;">🔄 提取中...</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                try:
                    start = time.time()
                    clean = ''.join(c for c in extract_z_text.strip() if c in '01')
                    Z = [int(b) for b in clean] if clean else None
                    
                    if Z:
                        images = IMAGE_LIBRARY.get(style_name, [])
                        img_idx = extract_img_num - 1
                        
                        if img_idx < len(images):
                            selected_image = images[img_idx]
                            _, img_process = download_image_by_id(selected_image["id"], extract_img_size)
                            
                            secret, secret_type, info = detect_and_extract(img_process, Z)
                            processing_placeholder.empty()
                            
                            if secret_type == 'text':
                                st.session_state.extract_result = {'success': True, 'type': 'text', 'elapsed_time': time.time()-start, 'content': secret}
                            else:
                                buf = BytesIO()
                                secret.save(buf, format='PNG')
                                st.session_state.extract_result = {'success': True, 'type': 'image', 'elapsed_time': time.time()-start, 'image_data': buf.getvalue()}
                            
                            for key in ['extract_contact_saved', 'extract_style_saved']:
                                if key in st.session_state:
                                    del st.session_state[key]
                            st.session_state.extract_step = 1
                            st.session_state.extract_page = 'result'
                            st.rerun()
                except Exception as e:
                    processing_placeholder.empty()
                    st.markdown(f'<div class="error-box">❌ 提取失敗! {e}</div>', unsafe_allow_html=True)
        
        components.html("""
        <script>
        function fixButtons() {
            const buttons = window.parent.document.querySelectorAll('button');
            for (let btn of buttons) { 
                if (btn.innerText.includes('下一步') || btn.innerText.includes('開始提取')) {
                    let container = btn.closest('.stButton') || btn.parentElement.parentElement.parentElement;
                    if (container) {
                        container.style.cssText = 'position:fixed!important;bottom:50px!important;right:30px!important;left:auto!important;width:auto!important;z-index:1000!important;';
                    }
                }
                if (btn.innerText.includes('返回') && !btn.innerText.includes('首頁')) {
                    let container = btn.closest('.stButton') || btn.parentElement.parentElement.parentElement;
                    if (container) {
                        container.style.cssText = 'position:fixed!important;bottom:50px!important;left:30px!important;right:auto!important;width:auto!important;z-index:1000!important;';
                    }
                }
            }
        }
        fixButtons();
        setTimeout(fixButtons, 100);
        setTimeout(fixButtons, 300);
        </script>
        """, height=0)
