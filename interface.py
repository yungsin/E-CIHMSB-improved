
import streamlit as st
import streamlit.components.v1 as components
import numpy as np
from PIL import Image, ImageDraw
import requests
from io import BytesIO
import os
import math
import time
import random
import base64
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
def generate_pattern_image(size, pattern_type):
    img = Image.new('RGB', (size, size), 'white')
    draw = ImageDraw.Draw(img)
    if pattern_type == 'gradient_blue':
        return generate_gradient_image(size, (30, 60, 114), (42, 157, 143), 'horizontal')
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
import os
if 'embed_result' not in st.session_state:
    st.session_state.embed_result = None
if 'extract_result' not in st.session_state:
    st.session_state.extract_result = None
# ==================== 對象管理 ====================
import json
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
# 可用尺寸列表
AVAILABLE_SIZES = [64, 128, 256, 512, 1024, 2048, 4096]
# 圖片庫：風格 -> 圖片列表（每張圖片記錄 picsum id）
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
    return AVAILABLE_SIZES[-1] # 最大尺寸
def get_image_url(pexels_id, size):
    """取得 Pexels 指定尺寸的圖片 URL"""
    return f"https://images.pexels.com/photos/{pexels_id}/pexels-photo-{pexels_id}.jpeg?auto=compress&cs=tinysrgb&w={size}&h={size}&fit=crop"
@st.cache_data(ttl=86400, show_spinner=False) # 快取 24 小時
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
    # 使用持久化快取
    image_data = download_image_cached(pexels_id, size)
   
    if image_data:
        img = Image.open(BytesIO(image_data)).convert('RGB')
        # 確保是正方形
        if img.size[0] != size or img.size[1] != size:
            img = img.resize((size, size), Image.LANCZOS)
        img_gray = img.convert('L') # 灰階版本供處理用
        return img, img_gray
   
    # 失敗時生成預設圖片
    img = generate_gradient_image(size, (100, 150, 200), (150, 200, 250))
    return img, img.convert('L')
# ==================== 輔助函數 ====================
def calculate_remaining_capacity(capacity_bits, used_bits):
    remaining_bits = capacity_bits - used_bits
    if remaining_bits <= 0:
        return 0, 0
    return remaining_bits // 24, remaining_bits // 8
def calculate_image_capacity(size):
    return (size * size) // 64 * 21
def calculate_required_bits_for_image(image, target_capacity=None):
    original_size, original_mode = image.size, image.mode
   
    # 模擬 image_to_binary_full 的轉換行為
    is_color = original_mode not in ['L', '1', 'LA']
   
    if not is_color:
        has_alpha = False
    elif original_mode == 'P':
        # P 模式：實際轉換後檢查是否有 alpha
        temp_img = image.convert('RGBA')
        # 檢查是否真的有透明像素
        if temp_img.mode == 'RGBA':
            alpha_channel = temp_img.split()[-1]
            has_alpha = alpha_channel.getextrema()[0] < 255 # 有任何透明像素
        else:
            has_alpha = False
    elif original_mode in ['RGBA', 'PA']:
        has_alpha = True
    elif original_mode not in ['RGB', 'RGBA']:
        has_alpha = False # 會被轉成 RGB
    else:
        has_alpha = False
   
    if is_color:
        header_bits = 66 # 彩色圖片都是 66（原始尺寸32 + 2 + 縮放後尺寸32）
        bits_per_pixel = 32 if has_alpha else 24
    else:
        header_bits, bits_per_pixel = 66, 8 # 灰階也改成 66 bits header（縮放尺寸改用 16 bits）
   
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
def get_size_from_name(image_name):
    return PUBLIC_IMAGES.get(image_name, (512, None))[0]
@st.cache_data(ttl=3600)
def download_public_image_v2(image_name):
    try:
        size, url = PUBLIC_IMAGES[image_name]
        if url.startswith("resize:"):
            actual_url = url.split(":", 2)[2]
            response = requests.get(actual_url, timeout=10)
            image = Image.open(BytesIO(response.content))
            return image.convert('RGB'), image.resize((size, size), Image.Resampling.LANCZOS).convert('L')
        else:
            response = requests.get(url, timeout=10)
            image = Image.open(BytesIO(response.content))
            if image.size != (size, size):
                image = image.resize((size, size), Image.Resampling.LANCZOS)
            return image.convert('RGB'), image.convert('L')
    except Exception as e:
        size = PUBLIC_IMAGES.get(image_name, (512, None))[0]
        return Image.new('RGB', (size, size), (128, 128, 128)), Image.new('L', (size, size), 128)
# ==================== Z碼圖編碼/解碼（正確版：8 bits = 1 pixel）====================
def encode_z_as_image_auto(z_bits):
    """
    Z碼圖編碼：8 bits = 1 pixel
    格式：32 bits (長度) + Z碼內容 + 補齊到 8 的倍數
    """
    # 加入長度 header (32 bits)
    length = len(z_bits)
    length_bits = [int(b) for b in format(length, '032b')]
    full_bits = length_bits + z_bits
   
    # 補齊到 8 的倍數
    if len(full_bits) % 8 != 0:
        padding = 8 - (len(full_bits) % 8)
        full_bits = full_bits + [0] * padding
   
    # 每 8 bits 轉成一個像素值 (0-255)
    pixels = []
    for i in range(0, len(full_bits), 8):
        byte = full_bits[i:i+8]
        pixel_value = int(''.join(map(str, byte)), 2)
        pixels.append(pixel_value)
   
    # 計算圖片尺寸 (盡量接近正方形)
    num_pixels = len(pixels)
    width = int(math.sqrt(num_pixels))
    height = math.ceil(num_pixels / width)
   
    # 補齊像素
    while len(pixels) < width * height:
        pixels.append(0)
   
    # 建立灰階圖片
    image = Image.new('L', (width, height))
    image.putdata(pixels[:width * height])
   
    return image, length
def encode_z_as_image_with_header(z_bits, img_num, img_size):
    """
    Z碼圖編碼（含編號和尺寸）：8 bits = 1 pixel
    格式：32 bits (Z長度) + 16 bits (編號) + 16 bits (尺寸) + Z碼 + 補齊到 8 的倍數
    """
    # 加入 header: 32 bits (Z長度) + 16 bits (編號) + 16 bits (尺寸) = 64 bits
    length = len(z_bits)
    header_bits = [int(b) for b in format(length, '032b')]
    header_bits += [int(b) for b in format(img_num, '016b')]
    header_bits += [int(b) for b in format(img_size, '016b')]
    full_bits = header_bits + z_bits
   
    # 補齊到 8 的倍數
    if len(full_bits) % 8 != 0:
        padding = 8 - (len(full_bits) % 8)
        full_bits = full_bits + [0] * padding
   
    # 每 8 bits 轉成一個像素值 (0-255)
    pixels = []
    for i in range(0, len(full_bits), 8):
        byte = full_bits[i:i+8]
        pixel_value = int(''.join(map(str, byte)), 2)
        pixels.append(pixel_value)
   
    # 計算圖片尺寸 (盡量接近正方形)
    num_pixels = len(pixels)
    width = int(math.sqrt(num_pixels))
    height = math.ceil(num_pixels / width)
   
    # 補齊像素
    while len(pixels) < width * height:
        pixels.append(0)
   
    # 建立灰階圖片
    image = Image.new('L', (width, height))
    image.putdata(pixels[:width * height])
   
    return image, length
def decode_image_to_z_with_header(image):
    """
    Z碼圖解碼（含編號和尺寸）：1 pixel = 8 bits
    格式：32 bits (Z長度) + 16 bits (編號) + 16 bits (尺寸) + Z碼
    """
    # 轉成灰階
    if image.mode != 'L':
        image = image.convert('L')
   
    # 取得所有像素
    pixels = list(image.getdata())
   
    # 每個像素轉成 8 bits
    all_bits = []
    for pixel in pixels:
        bits = [int(b) for b in format(pixel, '08b')]
        all_bits.extend(bits)
   
    # 檢查長度（至少需要 64 bits header）
    if len(all_bits) < 64:
        raise ValueError("Z碼圖片格式錯誤：太小")
   
    # 讀取 header
    z_length = int(''.join(map(str, all_bits[:32])), 2)
    img_num = int(''.join(map(str, all_bits[32:48])), 2)
    img_size = int(''.join(map(str, all_bits[48:64])), 2)
   
    # 驗證長度
    if z_length <= 0 or z_length > len(all_bits) - 64:
        raise ValueError(f"Z碼長度無效：{z_length}")
   
    # 提取 Z碼
    z_bits = all_bits[64:64 + z_length]
   
    return z_bits, img_num, img_size
def decode_image_to_z_auto(image):
    """
    Z碼圖解碼：1 pixel = 8 bits
    格式：32 bits (長度) + Z碼內容
    """
    # 轉成灰階
    if image.mode != 'L':
        image = image.convert('L')
   
    # 取得所有像素
    pixels = list(image.getdata())
   
    # 每個像素轉成 8 bits
    all_bits = []
    for pixel in pixels:
        bits = [int(b) for b in format(pixel, '08b')]
        all_bits.extend(bits)
   
    # 檢查長度
    if len(all_bits) < 32:
        raise ValueError("Z碼圖片格式錯誤：太小")
   
    # 讀取長度 header
    length_bits = all_bits[:32]
    actual_length = int(''.join(map(str, length_bits)), 2)
   
    # 驗證長度
    if actual_length <= 0 or actual_length > len(all_bits) - 32:
        raise ValueError(f"Z碼長度無效：{actual_length}")
   
    # 提取 Z碼
    z_bits = all_bits[32:32 + actual_length]
   
    return z_bits, actual_length
# ==================== Streamlit 頁面配置 ====================
st.set_page_config(page_title="🔐 高效能無載體之機密編碼技術", page_icon="🔐", layout="wide", initial_sidebar_state="collapsed")
# ==================== CSS 樣式（響應式設計）====================
st.markdown("""
<style>
/* 背景圖片 - 復古紙張紋理 */
.stApp {
    background-image: url('https://i.pinimg.com/1200x/03/c9/99/03c999e78415b51ad02b3d4e92942bcd.jpg');
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    background-attachment: fixed;
}
/* 隱藏 Streamlit 預設元素 */
header[data-testid="stHeader"],
#MainMenu, footer, .stDeployButton, div[data-testid="stToolbar"] {
    display: none !important;
    visibility: hidden !important;
}
.block-container { padding-top: 1rem !important; }
/* ==================== 響應式設計核心 ==================== */
/* 限制最大寬度，讓內容不會在大螢幕上拉太開 */
[data-testid="stMain"] > div {
    max-width: 1400px !important;
    margin: 0 auto !important;
}
.block-container {
    max-width: 1400px !important;
    margin: 0 auto !important;
    padding-left: clamp(1rem, 3vw, 3rem) !important;
    padding-right: clamp(1rem, 3vw, 3rem) !important;
}
/* 完全隱藏 Streamlit 所有側邊欄控制按鈕 */
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
    top: 8px;
    left: 0;
    background: #4A6B8A;
    color: white;
    writing-mode: vertical-rl;
    padding: clamp(12px, 1.5vw, 16px) clamp(6px, 0.8vw, 8px);
    border-radius: 0 8px 8px 0;
    font-size: clamp(18px, 2vw, 24px);
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
/* 確保主內容區不受側邊欄影響 */
[data-testid="stMain"] {
    margin-left: 0 !important;
    width: 100% !important;
}
/* 側邊欄樣式：固定定位，不影響主內容 */
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
    background: #f5f5f0 !important;
    box-shadow: 4px 0 15px rgba(0,0,0,0.2) !important;
}
[data-testid="stSidebar"].sidebar-open {
    transform: translateX(0) !important;
}
/* 側邊欄標題字體放大 */
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
    font-size: 38px !important;
    font-weight: bold !important;
}
[data-testid="stSidebar"] strong,
[data-testid="stSidebar"] b,
[data-testid="stSidebar"] p strong,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong {
    font-size: 24px !important;
}
/* 下拉式選單（Expander）字體放大 */
[data-testid="stSidebar"] [data-testid="stExpander"] summary,
[data-testid="stSidebar"] [data-testid="stExpander"] summary span,
[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] details summary span {
    font-size: 24px !important;
}
[data-testid="stSidebar"] .stExpander,
[data-testid="stSidebar"] details {
    font-size: 22px !important;
}
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] select,
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stTextInput label {
    font-size: 18px !important;
}
[data-testid="stSidebar"] button {
    font-size: 18px !important;
}
/* 隱藏側邊欄頂部的 < 收合按鈕 */
[data-testid="stSidebar"] [data-testid="stBaseButton-header"],
[data-testid="stSidebar"] button[kind="header"],
[data-testid="stSidebar"] > div:first-child > button,
[data-testid="stSidebarContent"] > div:first-child button {
    display: none !important;
}
/* ==================== 首頁按鈕隱藏（CSS 備用）==================== */
.home-page-btn + div {
    position: fixed !important;
    top: -9999px !important;
    left: -9999px !important;
    opacity: 0 !important;
}
/* ==================== 全屏選擇頁面樣式（響應式）==================== */
.welcome-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 10vh; /* Increased from 2vh for better spacing */
    text-align: center;
    margin-bottom: 1rem;
    margin-top: 4rem; /* Push title and cards down as requested */
}
.welcome-title {
    font-size: clamp(36px, 4vw, 60px);
    font-weight: bold;
    margin-bottom: 2rem;
    letter-spacing: clamp(0.15em, 2vw, 0.3em);
    padding-left: clamp(0.15em, 2vw, 0.3em);
    white-space: nowrap;
    background: linear-gradient(135deg, #4A6B8A 0%, #7D5A6B 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.welcome-subtitle {
    font-size: 1rem;
    color: #5D5D5D;
    margin-bottom: 3rem;
}
/* ==================== 動畫卡片樣式（響應式）==================== */
.anim-card {
    width: 90%;
    max-width: 450px;
    min-height: clamp(220px, 25vw, 280px);
    padding: clamp(25px, 3vw, 35px) clamp(20px, 2.5vw, 30px) clamp(15px, 2vw, 20px) clamp(15px, 2vw, 20px);
    border-radius: 20px;
    text-align: center;
    cursor: pointer;
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    position: relative;
    overflow: visible;
    margin: 0 auto;
    margin-bottom: 0 !important; /* Remove extra bottom margin on cards */
    box-shadow: 8px 8px 0px 0px rgba(60, 80, 100, 0.4);
}
.anim-card:hover {
    transform: translateY(-8px) scale(1.02);
    box-shadow: 12px 12px 0px 0px rgba(60, 80, 100, 0.5);
}
.anim-card-embed {
    background: linear-gradient(145deg, #7BA3C4 0%, #5C8AAD 100%);
}
.anim-card-extract {
    background: linear-gradient(145deg, #C4A0AB 0%, #A67B85 100%);
}
/* 動畫圖示流程（響應式）*/
.anim-flow {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: clamp(10px, 1.5vw, 18px);
    margin-bottom: clamp(20px, 2.5vw, 30px);
    font-size: clamp(40px, 5vw, 58px);
    height: clamp(70px, 9vw, 100px);
}
.anim-flow img {
    width: clamp(60px, 8vw, 95px) !important;
    height: clamp(60px, 8vw, 95px) !important;
}
.anim-flow img.anim-icon-arrow {
    width: clamp(50px, 6vw, 75px) !important;
    height: clamp(50px, 6vw, 75px) !important;
}
.anim-icon {
    transition: all 0.3s ease;
}
/* 嵌入動畫效果 */
.anim-card-embed .anim-icon-secret {
    animation: embedPulse 2s ease-in-out infinite;
}
.anim-card-embed .anim-icon-arrow {
    animation: arrowBounce 1.5s ease-in-out infinite;
}
.anim-card-embed .anim-icon-result {
    animation: resultGlow 2s ease-in-out infinite;
}
@keyframes embedPulse {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.15); opacity: 0.8; }
}
@keyframes arrowBounce {
    0%, 100% { transform: translateX(0); }
    50% { transform: translateX(8px); }
}
@keyframes resultGlow {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.1); }
}
/* 提取動畫效果 */
.anim-card-extract .anim-icon-source {
    animation: sourcePulse 2s ease-in-out infinite;
}
.anim-card-extract .anim-icon-arrow {
    animation: arrowBounce 1.5s ease-in-out infinite;
}
.anim-card-extract .anim-icon-result {
    animation: extractReveal 2s ease-in-out infinite;
}
@keyframes sourcePulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.1); }
}
@keyframes extractReveal {
    0%, 100% { transform: scale(1) rotate(0deg); opacity: 1; }
    50% { transform: scale(1.2) rotate(5deg); opacity: 0.9; }
}
/* 卡片文字（響應式）*/
.anim-title {
    font-size: clamp(36px, 4vw, 52px);
    font-weight: bold;
    color: #FFFFFF;
    margin-bottom: clamp(12px, 1.5vw, 20px);
    text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
}
.anim-desc {
    font-size: clamp(28px, 3.5vw, 42px);
    color: rgba(255,255,255,0.9);
    line-height: 1.7;
    margin-bottom: 0;
}
.anim-flow-text {
    font-size: 13px;
    color: rgba(255,255,255,0.75);
    font-family: monospace;
    background: rgba(255,255,255,0.15);
    padding: 6px 14px;
    border-radius: 15px;
    display: inline-block;
    margin-top: 8px;
}
/* ==================== 功能頁面樣式（響應式）==================== */
.page-title-embed {
    font-size: clamp(2rem, 4vw, 3rem);
    font-weight: bold;
    background: linear-gradient(135deg, #4A6B8A 0%, #5C8AAD 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.page-title-extract {
    font-size: clamp(2rem, 4vw, 3rem);
    font-weight: bold;
    background: linear-gradient(135deg, #7D5A6B 0%, #A67B85 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
/* 成功/錯誤框（響應式）*/
.success-box {
    background: linear-gradient(135deg, #4A6B8A 0%, #5C8AAD 100%);
    color: white;
    padding: clamp(15px, 2vw, 20px) clamp(20px, 2.5vw, 30px);
    border-radius: 10px;
    margin: 10px 0;
    display: inline-block;
    font-size: clamp(22px, 2.5vw, 28px);
    min-width: min(350px, 90%);
}
.info-box {
    background: linear-gradient(135deg, #4A6B8A 0%, #5C8AAD 100%);
    color: white;
    padding: clamp(15px, 2vw, 20px) clamp(20px, 2.5vw, 30px);
    border-radius: 10px;
    margin: 10px 0;
    display: inline-block;
    font-size: clamp(20px, 2.2vw, 26px);
    line-height: 1.9;
    min-width: min(350px, 90%);
}
.info-tip-box {
    background: linear-gradient(135deg, #5C8AAD 0%, #7BA3C4 100%);
    color: white;
    padding: clamp(15px, 2vw, 20px) clamp(20px, 2.5vw, 30px);
    border-radius: 10px;
    margin: 10px 0;
    display: inline-block;
    font-size: clamp(20px, 2.2vw, 26px);
    min-width: min(350px, 90%);
}
.error-box {
    background: linear-gradient(135deg, #8B5A5A 0%, #A67B7B 100%);
    color: white;
    padding: clamp(15px, 2vw, 20px) clamp(20px, 2.5vw, 30px);
    border-radius: 10px;
    margin: 10px 0;
    display: inline-block;
    font-size: clamp(20px, 2.2vw, 26px);
    min-width: min(350px, 90%);
}
/* 下載按鈕字體 */
.stDownloadButton button span,
.stDownloadButton button p {
    font-size: 18px !important;
    font-weight: bold !important;
}
/* 結果頁置中容器 */
.result-center-wrapper {
    display: flex;
    justify-content: center;
    align-items: flex-start;
    gap: clamp(30px, 5vw, 60px);
    margin: 20px auto;
    max-width: 900px;
}
.result-left-box, .result-right-box {
    flex: 0 0 auto;
}
/* 功能頁面全域字體放大加粗 - 只針對主區域（響應式）*/
[data-testid="stMain"] .stMarkdown,
[data-testid="stMain"] .stText,
[data-testid="stMain"] .stTextArea,
[data-testid="stMain"] .stRadio,
[data-testid="stMain"] .stFileUploader {
    font-size: clamp(24px, 2.8vw, 32px) !important;
    font-weight: bold !important;
}
[data-testid="stMain"] .stMarkdown p,
[data-testid="stMain"] .stText p {
    font-size: clamp(22px, 2.6vw, 30px) !important;
    font-weight: bold !important;
}
/* 側邊欄保持正常大小 */
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .stText,
[data-testid="stSidebar"] .stSelectbox,
[data-testid="stSidebar"] .stTextInput {
    font-size: 16px !important;
    font-weight: normal !important;
}
[data-testid="stSidebar"] h3 {
    font-size: 1.3rem !important;
}
[data-testid="stSidebar"] .stMarkdown p {
    font-size: 14px !important;
    font-weight: normal !important;
}
h3 {
    font-size: clamp(1.6rem, 3vw, 2.2rem) !important;
    font-weight: bold !important;
}
/* ==================== 通用按鈕樣式 ==================== */
.stButton button span,
.stButton button p,
[data-testid="stButton"] button span,
[data-testid="stButton"] button p,
[data-testid="baseButton-primary"] span,
[data-testid="baseButton-secondary"] span,
[data-testid="baseButton-primary"] p,
[data-testid="baseButton-secondary"] p,
button[kind="primary"] span,
button[kind="secondary"] span,
button[kind="primary"] p,
button[kind="secondary"] p {
    font-size: 18px !important;
    font-weight: bold !important;
}
/* 主頁面的主要操作按鈕 */
[data-testid="stMain"] .stButton button[kind="primary"],
[data-testid="stMain"] [data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
}
[data-testid="stMain"] .stButton button[kind="secondary"],
[data-testid="stMain"] [data-testid="baseButton-secondary"] {
    background: white !important;
    color: #333 !important;
    border: 2px solid #ccc !important;
    border-radius: 8px !important;
}
/* 首頁 Tab 按鈕特別樣式 */
.home-page-btn .stButton button,
.home-page-btn .stButton button span,
.home-page-btn .stButton button p,
.home-page-btn + div .stButton button,
.home-page-btn + div .stButton button span,
.home-page-btn + div .stButton button p {
    background: transparent !important;
    background-color: transparent !important;
    color: #4A6B8A !important;
    border: none !important;
    border-bottom: 4px solid #4A6B8A !important;
    border-radius: 0 !important;
    font-weight: 700 !important;
    font-size: 18px !important;
}
/* 側邊欄的按鈕 */
[data-testid="stSidebar"] .stButton button span,
[data-testid="stSidebar"] .stButton button p {
    font-size: 16px !important;
    font-weight: bold !important;
}
[data-testid="stSidebar"] .stButton button[kind="primary"] {
    background: linear-gradient(135deg, #4A6B8A 0%, #5C8AAD 100%) !important;
    color: white !important;
    border: none !important;
    border-bottom: none !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] .stButton button[kind="secondary"] {
    background: #E8E0E3 !important;
    color: #7D5A6B !important;
    border: 1px solid #C4A0AB !important;
    border-bottom: 1px solid #C4A0AB !important;
    border-radius: 8px !important;
}
.stCaption {
    font-size: clamp(18px, 2vw, 24px) !important;
    font-weight: bold !important;
}
/* 放大 selectbox, radio, text_area 字體（響應式）*/
.stSelectbox label, .stRadio label, .stTextArea label, .stFileUploader label {
    font-size: clamp(18px, 2vw, 24px) !important;
    font-weight: bold !important;
}
.stSelectbox label p, .stRadio label p, .stTextArea label p, .stFileUploader label p {
    font-size: clamp(18px, 2vw, 24px) !important;
    font-weight: bold !important;
}
[data-testid="stWidgetLabel"] {
    font-size: clamp(18px, 2vw, 24px) !important;
    font-weight: bold !important;
}
[data-testid="stWidgetLabel"] p {
    font-size: clamp(18px, 2vw, 24px) !important;
    font-weight: bold !important;
}
.stRadio [role="radiogroup"] label {
    font-size: clamp(22px, 2.5vw, 28px) !important;
    font-weight: bold !important;
}
.stTextArea textarea {
    font-size: clamp(24px, 2.6vw, 30px) !important;
    font-weight: normal !important;
}
/* ===== 「已選擇」說明文字顏色 ===== */
.stCaption, [data-testid="stCaptionContainer"] {
    color: #443C3C !important;
    font-size: clamp(18px, 2vw, 22px) !important;
}
/* 圖片 caption 放大 */
[data-testid="stImage"] + div,
[data-testid="caption"],
figcaption,
[data-testid="stImage"] figcaption,
[data-testid="stImage"] ~ div,
.stImage figcaption,
.stImage + div {
    font-size: clamp(18px, 2vw, 22px) !important;
    color: #443C3C !important;
}
[data-testid="stImage"] div[data-testid="stMarkdownContainer"] p,
[data-testid="stImage"] p {
    font-size: clamp(18px, 2vw, 22px) !important;
    color: #443C3C !important;
}
/* ===== 刪除按鈕 - 紅色 ===== */
[data-testid="stSidebar"] .stButton button:contains("刪除") {
    background: linear-gradient(135deg, #e57373 0%, #ef5350 100%) !important;
}
/* ===== 主區域 Selectbox 樣式 - 放大框和字（響應式）===== */
[data-testid="stMain"] .stSelectbox > div > div {
    background-color: white !important;
    border-radius: 8px !important;
    font-size: clamp(18px, 2vw, 24px) !important;
    font-weight: bold !important;
    min-height: 50px !important;
    padding: 8px 12px !important;
}
[data-testid="stMain"] .stSelectbox [data-baseweb="select"] span,
[data-testid="stMain"] .stSelectbox [data-baseweb="select"] div,
[data-testid="stMain"] .stSelectbox input,
[data-testid="stMain"] .stSelectbox [data-baseweb="select"] {
    font-size: clamp(18px, 2vw, 24px) !important;
    font-weight: bold !important;
}
/* ===== 側邊欄 Selectbox 樣式 - 保持原樣 ===== */
[data-testid="stSidebar"] .stSelectbox > div > div {
    background-color: white !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    font-weight: normal !important;
}
[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] span,
[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] div {
    font-size: 14px !important;
    font-weight: normal !important;
}
/* 下拉選單列表 */
[data-baseweb="popover"] {
    background-color: white !important;
}
[data-baseweb="popover"] ul {
    background-color: white !important;
}
[data-baseweb="popover"] li {
    background-color: white !important;
    font-size: clamp(18px, 2vw, 22px) !important;
}
[data-baseweb="popover"] li:hover {
    background-color: #f0f0f0 !important;
}
/* 側邊欄 selectbox 樣式 */
section[data-testid="stSidebar"] [data-baseweb="select"] input {
    font-size: 20px !important;
    caret-color: transparent !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    font-size: 20px !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] span {
    font-size: 20px !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] div {
    font-size: 20px !important;
}
section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] {
    font-size: 20px !important;
}
section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] div {
    font-size: 20px !important;
}
section[data-testid="stSidebar"] [data-testid="stSelectbox"] div {
    font-size: 20px !important;
}
/* 主頁面 selectbox 樣式（響應式）*/
[data-testid="stMain"] [data-baseweb="select"] input {
    font-size: clamp(18px, 2vw, 22px) !important;
    caret-color: transparent !important;
}
[data-testid="stMain"] [data-baseweb="select"] div {
    font-size: clamp(18px, 2vw, 22px) !important;
}
[data-testid="stMain"] .stSelectbox div {
    font-size: clamp(18px, 2vw, 22px) !important;
}
.stRadio [role="radiogroup"] label {
    font-size: clamp(22px, 2.5vw, 28px) !important;
}
.stRadio [role="radiogroup"] label p {
    font-size: clamp(22px, 2.5vw, 28px) !important;
}
.stRadio [role="radiogroup"] label span {
    font-size: clamp(22px, 2.5vw, 28px) !important;
}
.stRadio [data-testid="stMarkdownContainer"] p {
    font-size: clamp(22px, 2.5vw, 28px) !important;
}
[data-testid="stRadio"] label {
    font-size: clamp(22px, 2.5vw, 28px) !important;
}
[data-testid="stRadio"] label p {
    font-size: clamp(22px, 2.5vw, 28px) !important;
}
.stTextArea textarea {
    font-size: clamp(24px, 2.6vw, 30px) !important;
}
/* 放大成功/資訊訊息（響應式）*/
div[data-testid="stAlert"] {
    font-size: clamp(20px, 2.2vw, 26px) !important;
}
div[data-testid="stAlert"] p {
    font-size: clamp(20px, 2.2vw, 26px) !important;
}
/* 縮小上傳框 */
.stFileUploader section {
    padding: 10px !important;
}
.stFileUploader section > div:first-child {
    padding: 15px !important;
}
/* 放大上傳文件名 */
.stFileUploader [data-testid="stFileUploaderFile"] span {
    font-size: 18px !important;
}
.stFileUploader small {
    font-size: 16px !important;
}
/* 減少間距讓頁面更緊湊 */
.block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 2rem !important; /* Reduced bottom padding */
}
/* 嵌入/提取頁面內容往上移 */
.embed-extract-page .block-container {
    margin-top: -4rem !important;
}
.stMarkdown hr {
    margin: 0.5rem 0 !important;
}
.stSelectbox, .stTextArea, .stFileUploader, .stRadio {
    margin-bottom: 0.3rem !important;
}
div[data-testid="stVerticalBlock"] > div {
    gap: 0.3rem !important;
}
/* ==================== 固定在右下角的按鈕樣式 ==================== */
#next-step-fixed span,
#next-step-fixed p {
    font-size: 18px !important;
    font-weight: bold !important;
}
#next-step-fixed {
    position: fixed !important;
    bottom: clamp(5px, 1vw, 15px) !important;
    right: clamp(15px, 3vw, 30px) !important;
    z-index: 1000 !important;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    cursor: pointer !important;
    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4) !important;
    transition: all 0.2s !important;
}
#next-step-fixed:hover:not(:disabled) {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5) !important;
}
#next-step-fixed:disabled {
    background: #ccc !important;
    color: #888 !important;
    cursor: not-allowed !important;
    box-shadow: none !important;
}
/* ==================== 固定在左下角的返回按鈕樣式 ==================== */
#back-step-fixed span,
#back-step-fixed p {
    font-size: 18px !important;
    font-weight: bold !important;
}
#back-step-fixed {
    position: fixed !important;
    bottom: clamp(5px, 1vw, 15px) !important;
    left: clamp(15px, 3vw, 30px) !important;
    z-index: 1000 !important;
    background: white !important;
    color: #333 !important;
    border: 2px solid #ccc !important;
    border-radius: 8px !important;
    cursor: pointer !important;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1) !important;
    transition: all 0.2s !important;
}
#back-step-fixed:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15) !important;
    background: #f5f5f5 !important;
}
/* ==================== 步驟指示器（響應式）==================== */
.step-indicator {
    font-size: clamp(18px, 2vw, 24px) !important;
    font-weight: 700 !important;
    padding: clamp(10px, 1.5vw, 15px) clamp(8px, 1vw, 10px) !important;
}
/* ==================== 響應式 Media Queries ==================== */
/* 超大螢幕 (> 1920px) */
@media (min-width: 1920px) {
    [data-testid="stMain"] > div {
        max-width: 1600px !important;
    }
    .block-container {
        max-width: 1600px !important;
    }
}
/* 大螢幕 (1440px - 1920px) */
@media (min-width: 1440px) and (max-width: 1919px) {
    [data-testid="stMain"] > div {
        max-width: 1400px !important;
    }
}
/* 中等螢幕 (1200px - 1440px) */
@media (min-width: 1200px) and (max-width: 1439px) {
    [data-testid="stMain"] > div {
        max-width: 1200px !important;
    }
}
/* 小螢幕 (< 1200px) */
@media (max-width: 1199px) {
    [data-testid="stMain"] > div {
        max-width: 100% !important;
        padding: 0 1rem !important;
    }
   
    .anim-card {
        max-width: 380px !important;
        min-height: 220px !important;
        padding: 25px 20px 15px 15px !important;
    }
   
    #next-step-fixed,
    #back-step-fixed {
        bottom: 10px !important;
    }
    #next-step-fixed {
        right: 15px !important;
    }
    #back-step-fixed {
        left: 15px !important;
    }
}
/* 平板 (768px - 1199px) */
@media (max-width: 1199px) and (min-width: 768px) {
    .welcome-title {
        white-space: normal !important;
        line-height: 1.3 !important;
    }
}
/* 手機 (< 768px) */
@media (max-width: 767px) {
    .welcome-title {
        white-space: normal !important;
        line-height: 1.3 !important;
        letter-spacing: 0.1em !important;
        padding-left: 0.1em !important;
    }
   
    .anim-card {
        max-width: 320px !important;
        min-height: 200px !important;
    }
   
    #sidebar-toggle-label {
        padding: 10px 6px !important;
        font-size: 16px !important;
    }
}
/* 首頁底部組員文字（響應式）*/
.member-text {
    font-size: clamp(28px, 3.5vw, 40px) !important;
    position: fixed;
    bottom: 1rem; /* Move up slightly to reduce overall bottom space */
    left: 0;
    right: 0;
    text-align: center;
    color: #5D5D5D;
    font-weight: 500;
    z-index: 10;
}
/* Reduce space below cards by tightening column gaps and paddings */
div.row-widget.stHorizontal > div {
    gap: 1rem !important; /* Smaller gap between columns */
}
/* More aggressive hiding for any bottom-right elements (Streamlit balloons, toasts, or debug icons) */
div[data-testid="stStatusWidget"], 
div[data-testid="stToast"], 
div.stAlert, 
.stSpinner, 
.stException, 
.stBalloon, 
div.element-container iframe, 
div[title="Streamlit app"], 
button[kind="primary"][style*="bottom"], 
div[style*="bottom: 0; right: 0;"] {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
    width: 0 !important;
    height: 0 !important;
}

/* Hide any red/purple dots or squares specifically */
div[style*="background: red"], 
div[style*="background: purple"], 
circle[fill="purple"], 
rect[fill="red"] {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)
# ==================== 初始化狀態 ====================
if 'current_mode' not in st.session_state:
    st.session_state.current_mode = None # None = 全屏選擇頁
# ==================== 側邊欄 - 對象管理（只在嵌入/提取頁面顯示）====================
if st.session_state.current_mode is not None:
    with st.sidebar:
        # 關閉按鈕
        st.markdown("""
        <style>
        /* 側邊欄 expander 文字放大 */
        section[data-testid="stSidebar"] details summary span p {
            font-size: 22px !important;
        }
        section[data-testid="stSidebar"] details summary {
            font-size: 22px !important;
        }
        /* 已建立對象標題 */
        #built-contacts-title {
            font-size: 28px !important;
            font-weight: bold !important;
            margin-bottom: 10px !important;
        }
        /* 側邊欄 selectbox 字體放大 */
        section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] div[class] {
            font-size: 20px !important;
        }
        section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] [class*="valueContainer"] {
            font-size: 20px !important;
        }
        section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] [class*="singleValue"] {
            font-size: 20px !important;
        }
        section[data-testid="stSidebar"] [class*="st-emotion-cache"] {
            font-size: 20px !important;
        }
        </style>
        <div id="sidebar-close-btn" style="position: absolute; top: 5px; right: 10px;
            width: 30px; height: 30px; background: #e0e0e0; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            cursor: pointer; font-size: 18px; color: #666; z-index: 9999;
            transition: all 0.2s;">✕</div>
        """, unsafe_allow_html=True)
       
        st.markdown('<h3 style="font-size: 36px; margin-bottom: 15px;">對象管理</h3>', unsafe_allow_html=True)
       
        contacts = st.session_state.contacts
       
        # 新增對象
        add_expanded = st.session_state.get('add_expander_open', False)
        with st.expander("➕ 新增對象", expanded=add_expanded):
            add_counter = st.session_state.get('add_contact_counter', 0)
            new_name = st.text_input("名稱", key=f"sidebar_new_name_{add_counter}", placeholder="例如：小明、老媽、閨蜜")
            style_options = ["選擇"] + list(STYLE_CATEGORIES.keys())
            new_style = st.selectbox("綁定風格", style_options, key=f"sidebar_new_style_{add_counter}")
           
            can_add = new_name and new_name.strip() and new_style != "選擇"
            if st.button("新增", key="sidebar_add_btn", use_container_width=True, disabled=not can_add, type="primary" if can_add else "secondary"):
                st.session_state.contacts[new_name.strip()] = new_style
                save_contacts(st.session_state.contacts)
                st.toast(f"✅ 已新增「{new_name.strip()}」")
                st.session_state.add_contact_counter = add_counter + 1
                st.session_state.add_expander_open = False
                st.rerun()
       
        st.markdown("---")
        st.markdown('<div id="built-contacts-title">已建立的對象：</div>', unsafe_allow_html=True)
        if contacts:
            for name, style in contacts.items():
                if style:
                    style_display = STYLE_CATEGORIES.get(style, style)
                    display_text = f"{name}（{style_display}）"
                else:
                    display_text = f"{name}（未綁定）"
               
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
                   
                    if st.button("刪除", key=f"del_{name}", use_container_width=True, type="primary"):
                        del st.session_state.contacts[name]
                        save_contacts(st.session_state.contacts)
                        st.rerun()
        else:
            st.markdown('<p style="font-size: 12px; color: #999;">尚無對象，請先新增</p>', unsafe_allow_html=True)
# ==================== 主要邏輯 ====================
if st.session_state.current_mode is None:
    # ==================== 全屏選擇頁面 + 動畫卡片 ====================
   
    st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"], .main, [data-testid="stMain"] {
        overflow: hidden !important;
        max-height: 100vh !important;
    }
    .block-container {
        padding-bottom: 0 !important;
        max-height: 100vh !important;
        overflow: hidden !important;
    }
    </style>
    """, unsafe_allow_html=True)
   
    st.markdown("""
    <div class="welcome-container">
        <div class="welcome-title">高效能無載體之機密編碼技術</div>
    </div>
    <div style="position: fixed; bottom: 5px; left: 0; right: 0; text-align: center; color: #5D5D5D; font-size: clamp(28px, 3.5vw, 40px); font-weight: 500; z-index: 10;" class="member-text">
        組員：鄭凱譽、劉佳典、王于婕
    </div>
    """, unsafe_allow_html=True)
   
    icon_secret = get_icon_base64("secret-message")
    icon_image = get_icon_base64("public-image")
    icon_arrow = get_icon_base64("arrow")
    icon_zcode = get_icon_base64("z-code")
   
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
   
    col_spacer1, col_embed, col_spacer_mid, col_extract, col_spacer2 = st.columns([0.35, 2, 0.15, 2, 0.4], gap="large")
   
    with col_embed:
        st.markdown(f"""
        <div class="anim-card anim-card-embed" id="embed-card">
            <div class="anim-flow">
                <img src="{icon_secret}" class="anim-icon anim-icon-secret">
                <span class="anim-icon">+</span>
                <img src="{icon_image}" class="anim-icon">
                <img src="{icon_arrow}" class="anim-icon anim-icon-arrow">
                <img src="{icon_zcode}" class="anim-icon anim-icon-result">
            </div>
            <div class="anim-title">嵌入機密</div>
            <div class="anim-desc">圖像編碼<br>機密隱於Z碼中</div>
        </div>
        <div class="home-page-btn">
        """, unsafe_allow_html=True)
        if st.button("開始嵌入", key="btn_embed", use_container_width=True):
            st.session_state.current_mode = 'embed'
            st.session_state.prev_embed_image_select = None
            st.session_state.prev_contact = None
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
   
    with col_extract:
        st.markdown(f"""
        <div class="anim-card anim-card-extract" id="extract-card">
            <div class="anim-flow">
                <img src="{icon_zcode}" class="anim-icon anim-icon-source">
                <span class="anim-icon">+</span>
                <img src="{icon_image}" class="anim-icon">
                <img src="{icon_arrow}" class="anim-icon anim-icon-arrow">
                <img src="{icon_secret}" class="anim-icon anim-icon-result">
            </div>
            <div class="anim-title">提取機密</div>
            <div class="anim-desc">Z碼解碼<br>機密現於圖像間</div>
        </div>
        <div class="home-page-btn">
        """, unsafe_allow_html=True)
        if st.button("開始提取", key="btn_extract", use_container_width=True):
            st.session_state.current_mode = 'extract'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
   
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
    setTimeout(hideHomeButtons, 0);
    setTimeout(hideHomeButtons, 10);
    setTimeout(hideHomeButtons, 50);
    setTimeout(hideHomeButtons, 100);
   
    function bindCardClicks() {
        const embedCard = doc.getElementById('embed-card');
        const extractCard = doc.getElementById('extract-card');
       
        if (embedCard && !embedCard.hasAttribute('data-bound')) {
            embedCard.setAttribute('data-bound', 'true');
            embedCard.style.cursor = 'pointer';
            embedCard.addEventListener('click', () => {
                const buttons = doc.querySelectorAll('button');
                buttons.forEach(btn => {
                    if ((btn.innerText || btn.textContent).includes('開始嵌入')) {
                        btn.click();
                    }
                });
            });
        }
       
        if (extractCard && !extractCard.hasAttribute('data-bound')) {
            extractCard.setAttribute('data-bound', 'true');
            extractCard.style.cursor = 'pointer';
            extractCard.addEventListener('click', () => {
                const buttons = doc.querySelectorAll('button');
                buttons.forEach(btn => {
                    if ((btn.innerText || btn.textContent).includes('開始提取')) {
                        btn.click();
                    }
                });
            });
        }
    }
   
    setTimeout(bindCardClicks, 100);
   
    const observer = new MutationObserver(() => {
        hideHomeButtons();
        bindCardClicks();
    });
    observer.observe(doc.body, { childList: true, subtree: true });
    </script>
    """, height=0)
elif st.session_state.current_mode == 'embed':
    # ==================== 嵌入模式頁面 ====================
   
    if 'embed_page' not in st.session_state:
        st.session_state.embed_page = 'input'
   
    # ========== 結果頁 ==========
    if st.session_state.embed_page == 'result' and st.session_state.embed_result and st.session_state.embed_result.get('success'):
        # 允許頁面滾動
        st.markdown("""
        <style>
        .main { overflow: auto !important; }
        section.main > div { overflow: auto !important; }
        </style>
        """, unsafe_allow_html=True)
       
        r = st.session_state.embed_result
       
        st.markdown('<div class="page-title-embed" style="text-align: center; margin-bottom: 30px;">嵌入結果</div>', unsafe_allow_html=True)
       
        spacer_left, col_left, col_gap, col_right, spacer_right = st.columns([0.5, 2, 0.5, 2, 0.5])
       
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
           
            st.markdown(f'<div class="info-box"><strong>嵌入資訊</strong><br><br>無載體圖像編號：<strong>{img_num}</strong>（{img_name}）<br>無載體圖像尺寸：{img_size}×{img_size}<br>機密內容：<br>{secret_display}<br>容量：{secret_bits:,} / {capacity:,} bits ({usage_percent:.1f}%)</div>', unsafe_allow_html=True)
       
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
                   
                    st.markdown('<p style="font-size: clamp(26px, 3vw, 34px); font-weight: bold;">Z碼圖</p>', unsafe_allow_html=True)
                    st.image(qr_bytes, width=250)
                    st.download_button("下載 Z碼圖", qr_bytes, "z_code.png", "image/png", key="dl_z_qr")
                    st.markdown('<p style="font-size: clamp(24px, 2.6vw, 30px); color: #443C3C;">傳送 Z碼圖給對方</p>', unsafe_allow_html=True)
                except:
                    st.warning("⚠️ 機密內容較長，改用 Z碼圖片")
                    img_num_int = int(img_num)
                    img_size_int = int(img_size)
                    z_img, _ = encode_z_as_image_with_header(r['z_bits'], img_num_int, img_size_int)
                   
                    st.markdown('<p style="font-size: clamp(26px, 3vw, 34px); font-weight: bold;">Z碼圖片</p>', unsafe_allow_html=True)
                    st.image(z_img, width=250)
                   
                    buf = BytesIO()
                    z_img.save(buf, format='PNG')
                    st.download_button("下載圖片", buf.getvalue(), "z_code.png", "image/png", key="dl_z_img_fallback")
                    st.markdown('<p style="font-size: clamp(24px, 2.6vw, 30px); color: #443C3C;">傳送 Z碼圖給對方</p>', unsafe_allow_html=True)
            else:
                img_num = int(r["embed_image_choice"].split("-")[1])
                img_size = int(r["embed_image_choice"].split("-")[2])
                z_img, _ = encode_z_as_image_with_header(r['z_bits'], img_num, img_size)
               
                st.markdown('<p style="font-size: clamp(26px, 3vw, 34px); font-weight: bold;">Z碼圖片</p>', unsafe_allow_html=True)
                st.image(z_img, width=250)
                buf = BytesIO()
                z_img.save(buf, format='PNG')
                st.download_button("下載圖片", buf.getvalue(), "z_code.png", "image/png", key="dl_z_img")
                st.markdown('<p style="font-size: clamp(24px, 2.6vw, 30px); color: #443C3C;">傳送 Z碼圖給對方</p>', unsafe_allow_html=True)
       
        st.markdown("""
        <style>
        #btn-back-home span, #btn-back-home p { font-size: 18px !important; font-weight: bold !important; }
        #btn-back-home { position: fixed !important; bottom: clamp(5px, 1vw, 15px) !important; right: clamp(15px, 3vw, 30px) !important; z-index: 1000 !important; background: white !important; color: #333 !important; border: 2px solid #ccc !important; border-radius: 8px !important; cursor: pointer !important; }
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
        const fixButtons = () => {
            const buttons = window.parent.document.querySelectorAll('button');
            for (let btn of buttons) {
                if (btn.innerText === '返回首頁') btn.id = 'btn-back-home';
            }
        };
        fixButtons();
        const observer = new MutationObserver(fixButtons);
        observer.observe(window.parent.document.body, { childList: true, subtree: true });
        </script>
        """, height=0)
   
    # ========== 輸入頁 ==========
    else:
        st.session_state.embed_page = 'input'
       
        # 顯示自訂標籤
        st.markdown('<div id="sidebar-toggle-label">對象管理</div>', unsafe_allow_html=True)
       
        # JavaScript：點擊標籤展開，點擊 X 關閉
        components.html("""
<script>
(function() {
    const doc = window.parent.document;
   
    function fixSidebarSelectbox() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        if (sidebar) {
            if (!doc.getElementById('sidebar-selectbox-style')) {
                const style = doc.createElement('style');
                style.id = 'sidebar-selectbox-style';
                style.textContent = `
                    section[data-testid="stSidebar"] .stSelectbox div { font-size: 20px !important; }
                    section[data-testid="stSidebar"] [data-baseweb="select"] input { font-size: 20px !important; caret-color: transparent !important; }
                `;
                doc.head.appendChild(style);
            }
            const allElements = sidebar.querySelectorAll('.stSelectbox *');
            allElements.forEach(el => { el.style.fontSize = '20px'; });
            const inputs = sidebar.querySelectorAll('[data-baseweb="select"] input');
            inputs.forEach(input => {
                input.setAttribute('readonly', 'true');
                input.style.fontSize = '20px';
                input.style.caretColor = 'transparent';
                input.style.cursor = 'pointer';
            });
        }
        const mainInputs = doc.querySelectorAll('[data-testid="stMain"] [data-baseweb="select"] input');
        mainInputs.forEach(input => {
            input.setAttribute('readonly', 'true');
            input.style.fontSize = '22px';
            input.style.caretColor = 'transparent';
            input.style.cursor = 'pointer';
        });
        const mainDivs = doc.querySelectorAll('[data-testid="stMain"] .stSelectbox div');
        mainDivs.forEach(div => { div.style.fontSize = '22px'; });
    }
   
    function hideStreamlitCollapseBtn() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        if (sidebar) {
            const btns = sidebar.querySelectorAll('button');
            btns.forEach(btn => {
                if (btn.id !== 'sidebar-close-btn' && !btn.closest('.stExpander')) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.top < 100 && rect.right > sidebar.getBoundingClientRect().right - 60) {
                        btn.style.display = 'none';
                    }
                }
            });
        }
        fixSidebarSelectbox();
    }
   
    function closeSidebar() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        const label = doc.getElementById('sidebar-toggle-label');
        if (sidebar) { sidebar.classList.remove('sidebar-open'); }
        if (label) label.style.display = 'block';
    }
   
    function openSidebar() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        const label = doc.getElementById('sidebar-toggle-label');
        if (sidebar) { sidebar.classList.add('sidebar-open'); hideStreamlitCollapseBtn(); }
        if (label) label.style.display = 'none';
    }
   
    function setupToggle() {
        const label = doc.getElementById('sidebar-toggle-label');
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        if (sidebar && sidebar.classList.contains('sidebar-open')) {
            if (label) label.style.display = 'none';
        }
        if (label && !label.hasAttribute('data-sidebar-bindx')) {
            label.setAttribute('data-sidebar-bindx', 'true');
            label.addEventListener('click', openSidebar);
        }
        const closeBtn = doc.getElementById('sidebar-close-btn');
        if (closeBtn) { closeBtn.onclick = closeSidebar; }
        hideStreamlitCollapseBtn();
    }
   
    function fixAllSelectboxes() {
        if (!doc.getElementById('global-selectbox-style')) {
            const style = doc.createElement('style');
            style.id = 'global-selectbox-style';
            style.textContent = `
                .stSelectbox div { font-size: 22px !important; }
                [data-baseweb="select"] input { font-size: 22px !important; caret-color: transparent !important; }
                [data-baseweb="select"] > div { min-height: 50px !important; display: flex !important; align-items: center !important; }
                [data-baseweb="popover"] li { font-size: 22px !important; }
                .stRadio [role="radiogroup"] label { font-size: 28px !important; }
                .stRadio label { font-size: 28px !important; }
                .stRadio label p { font-size: 28px !important; }
                [data-testid="stRadio"] label p { font-size: 28px !important; }
                [data-testid="stImage"] figcaption { font-size: 22px !important; }
                [data-testid="stImage"] + div { font-size: 22px !important; }
                .element-container figcaption { font-size: 22px !important; }
            `;
            doc.head.appendChild(style);
        }
        const mainInputs = doc.querySelectorAll('[data-baseweb="select"] input');
        mainInputs.forEach(input => {
            input.setAttribute('readonly', 'true');
            input.style.setProperty('font-size', '22px', 'important');
            input.style.setProperty('caret-color', 'transparent', 'important');
            input.style.cursor = 'pointer';
        });
        const allSelectDivs = doc.querySelectorAll('.stSelectbox div');
        allSelectDivs.forEach(div => { div.style.setProperty('font-size', '22px', 'important'); });
        const radioLabels = doc.querySelectorAll('.stRadio label, [data-testid="stRadio"] label');
        radioLabels.forEach(label => {
            label.style.setProperty('font-size', '28px', 'important');
            const p = label.querySelector('p');
            if (p) p.style.setProperty('font-size', '28px', 'important');
            const span = label.querySelector('span');
            if (span) span.style.setProperty('font-size', '28px', 'important');
        });
        const captions = doc.querySelectorAll('[data-testid="stImage"] + div, figcaption, .stCaption');
        captions.forEach(cap => { cap.style.setProperty('font-size', '22px', 'important'); });
        const figcaptions = doc.querySelectorAll('figcaption');
        figcaptions.forEach(fig => {
            fig.style.setProperty('font-size', '22px', 'important');
            fig.style.setProperty('color', '#443C3C', 'important');
        });
        const labels = doc.querySelectorAll('[data-testid="stWidgetLabel"] p');
        labels.forEach(label => {
            label.style.setProperty('font-size', '24px', 'important');
            label.style.setProperty('font-weight', 'bold', 'important');
        });
        const imgContainers = doc.querySelectorAll('[data-testid="stImage"]');
        imgContainers.forEach(container => {
            const texts = container.querySelectorAll('div, span, p');
            texts.forEach(t => {
                if (t.innerText && t.innerText.trim()) {
                    t.style.setProperty('font-size', '22px', 'important');
                    t.style.setProperty('color', '#443C3C', 'important');
                }
            });
        });
    }
   
    setupToggle();
    fixAllSelectboxes();
    setTimeout(() => { setupToggle(); fixAllSelectboxes(); }, 100);
    setTimeout(() => { setupToggle(); fixAllSelectboxes(); }, 500);
    setTimeout(() => { setupToggle(); fixAllSelectboxes(); }, 1000);
    new MutationObserver(() => { setupToggle(); fixAllSelectboxes(); }).observe(doc.body, { childList: true, subtree: true });
})();
</script>
""", height=0)
       
        st.markdown('<div class="page-title-embed" style="text-align: center; margin-bottom: 20px; margin-top: -4rem;">嵌入機密</div>', unsafe_allow_html=True)
       
        embed_text, embed_image, secret_bits_needed = None, None, 0
        embed_image_choice, img_display, img_process, selected_size = None, None, None, None
       
        contacts = st.session_state.contacts
        contact_names = list(contacts.keys())
       
        if 'embed_step' not in st.session_state:
            st.session_state.embed_step = 1
       
        current_step = st.session_state.embed_step
        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
            <div class="step-indicator" style="flex: 1; text-align: center; border-bottom: {'4px solid #4A6B8A' if current_step == 1 else '2px solid #B8C8D8'}; color: {'#4A6B8A' if current_step == 1 else '#7A8A9A'};">第一步: 選擇對象</div>
            <div class="step-indicator" style="flex: 1; text-align: center; border-bottom: {'4px solid #4A6B8A' if current_step == 2 else '2px solid #B8C8D8'}; color: {'#4A6B8A' if current_step == 2 else '#7A8A9A'};">第二步: 機密內容</div>
            <div class="step-indicator" style="flex: 1; text-align: center; border-bottom: {'4px solid #4A6B8A' if current_step == 3 else '2px solid #B8C8D8'}; color: {'#4A6B8A' if current_step == 3 else '#7A8A9A'};">第三步: 無載體圖像</div>
        </div>
        """, unsafe_allow_html=True)
       
        st.markdown("---")
       
        show_next_btn = False
        next_step = 1
       
        if st.session_state.embed_step == 1:
            st.markdown('<p style="font-size: clamp(24px, 2.6vw, 30px); font-weight: bold; margin-bottom: 10px;">選擇對象</p>', unsafe_allow_html=True)
            if contact_names:
                options = ["選擇"] + contact_names
                saved_contact = st.session_state.get('selected_contact_saved', None)
                default_idx = options.index(saved_contact) if saved_contact and saved_contact in contact_names else 0
               
                selected_contact = st.selectbox("對象", options, index=default_idx, key="contact_select", label_visibility="collapsed")
               
                if selected_contact != "選擇":
                    prev_contact = st.session_state.get('prev_contact', None)
                    if prev_contact != selected_contact:
                        st.session_state.prev_embed_image_select = None
                    st.session_state.prev_contact = selected_contact
                    st.session_state.selected_contact_saved = selected_contact
                    st.markdown(f'<p style="font-size: clamp(20px, 2.2vw, 26px); color: #31333F;">✅ 已選擇：{selected_contact}</p>', unsafe_allow_html=True)
                    show_next_btn = True
                    next_step = 2
            else:
                st.markdown("""<div style="background: linear-gradient(135deg, #fff3cd 0%, #ffe69c 100%); border: 2px solid #ffc107; border-radius: 12px; padding: 15px; text-align: center; margin: 10px 0;"><div style="font-size: 16px; font-weight: bold; color: #856404;">⚠️ 請先新增對象（點擊左上角「對象管理」按鈕）</div></div>""", unsafe_allow_html=True)
       
        elif st.session_state.embed_step == 2:
            st.markdown("""<style>.main { overflow: hidden !important; } section.main > div { overflow: hidden !important; }</style>""", unsafe_allow_html=True)
           
            selected_contact = st.session_state.get('selected_contact_saved', '選擇')
            saved_type = st.session_state.get('embed_secret_type_saved', '文字')
            type_idx = 0 if saved_type == "文字" else 1
            st.markdown('<p style="font-size: clamp(20px, 2.2vw, 26px); font-weight: bold; margin-bottom: 5px;">內容類型</p>', unsafe_allow_html=True)
            embed_secret_type = st.radio("內容類型", ["文字", "圖片"], index=type_idx, key="embed_type", horizontal=True, label_visibility="collapsed")
           
            if embed_secret_type == "文字" and saved_type == "圖片":
                st.session_state.embed_secret_image_data = None
                st.session_state.embed_secret_image_name = None
                st.session_state.secret_bits_saved = 0
                st.session_state.embed_secret_type_saved = "文字"
            elif embed_secret_type == "圖片" and saved_type == "文字":
                st.session_state.embed_text_saved = ''
                st.session_state.secret_bits_saved = 0
                st.session_state.embed_secret_type_saved = "圖片"
           
            if embed_secret_type == "文字":
                saved_text = st.session_state.get('embed_text_saved', '')
                embed_text_raw = st.text_area("輸入機密訊息", value=saved_text, placeholder="輸入機密訊息...", height=100, key="embed_text_input", label_visibility="collapsed")
                if embed_text_raw:
                    embed_text = embed_text_raw.strip()
                    secret_bits_needed = len(text_to_binary(embed_text))
                    chinese = sum(1 for c in embed_text if '\u4e00' <= c <= '\u9fff')
                    st.markdown(f'<p style="font-size: clamp(18px, 2vw, 24px); color: #443C3C;"><b>機密文字:</b> {chinese} 中文 + {len(embed_text) - chinese} 英文/符號 | {secret_bits_needed:,} bits</p>', unsafe_allow_html=True)
                    st.session_state.secret_bits_saved = secret_bits_needed
                    st.session_state.embed_text_saved = embed_text
                    st.session_state.embed_secret_type_saved = "文字"
                    show_next_btn = True
                    next_step = 3
            else:
                saved_image_data = st.session_state.get('embed_secret_image_data')
                embed_image = st.file_uploader("上傳機密圖片", type=["jpg", "jpeg", "png"], key="embed_image_upload", label_visibility="collapsed")
               
                if embed_image:
                    embed_image.seek(0)
                    secret_img = Image.open(embed_image)
                    secret_bits_needed, _ = calculate_required_bits_for_image(secret_img)
                    filename = embed_image.name.rsplit('.', 1)[0]
                   
                    st.markdown('<div style="margin-top: 5px;"></div>', unsafe_allow_html=True)
                    col_left, col_img, col_info, col_right = st.columns([1.2, 0.6, 2, 0.5])
                    with col_img:
                        st.image(secret_img, width=150)
                    with col_info:
                        st.markdown(f'<div style="display: flex; align-items: center; min-height: 120px;"><div style="font-size: clamp(18px, 2vw, 22px); color: #443C3C; margin-left: 50px;"><b>機密圖像:</b> {filename} ({secret_img.size[0]}×{secret_img.size[1]} px) | {secret_bits_needed:,} bits</div></div>', unsafe_allow_html=True)
                   
                    st.session_state.secret_bits_saved = secret_bits_needed
                    st.session_state.embed_secret_type_saved = "圖片"
                    embed_image.seek(0)
                    st.session_state.embed_secret_image_data = embed_image.read()
                    st.session_state.embed_secret_image_name = embed_image.name
                    show_next_btn = True
                    next_step = 3
                elif saved_image_data:
                    secret_img = Image.open(BytesIO(saved_image_data))
                    secret_bits_needed = st.session_state.get('secret_bits_saved', 0)
                    saved_name = st.session_state.get('embed_secret_image_name', 'image')
                    filename = saved_name.rsplit('.', 1)[0]
                   
                    st.markdown('<div style="margin-top: 5px;"></div>', unsafe_allow_html=True)
                    col_left, col_img, col_info, col_right = st.columns([1.2, 0.6, 2, 0.5])
                    with col_img:
                        st.image(secret_img, width=150)
                    with col_info:
                        st.markdown(f'<div style="display: flex; align-items: center; min-height: 120px;"><div style="font-size: clamp(18px, 2vw, 22px); color: #443C3C; margin-left: 50px;"><b>機密圖像:</b> {filename} ({secret_img.size[0]}×{secret_img.size[1]} px) | {secret_bits_needed:,} bits</div></div>', unsafe_allow_html=True)
                   
                    show_next_btn = True
                    next_step = 3
       
        elif st.session_state.embed_step == 3:
            st.markdown("""<style>.main { overflow: hidden !important; } section.main > div { overflow: hidden !important; }</style>""", unsafe_allow_html=True)
           
            selected_contact = st.session_state.get('selected_contact_saved', '選擇')
            secret_bits_needed = st.session_state.get('secret_bits_saved', 0)
            embed_secret_type = st.session_state.get('embed_secret_type_saved', '文字')
            embed_text = st.session_state.get('embed_text_saved', None)
           
            if secret_bits_needed > 0 and selected_contact != "選擇":
                style_list = list(STYLE_CATEGORIES.keys())
                auto_style = contacts[selected_contact]
                default_style_index = style_list.index(auto_style) if auto_style and auto_style != "選擇" and auto_style in style_list else 0
               
                available_sizes = [s for s in AVAILABLE_SIZES if calculate_image_capacity(s) >= secret_bits_needed]
                if not available_sizes:
                    available_sizes = [AVAILABLE_SIZES[-1]]
                recommended_size = available_sizes[0]
               
                col_style, col_img, col_size = st.columns([1.5, 2, 2.5])
                with col_style:
                    selected_style = st.selectbox("風格", style_list, index=default_style_index, key="embed_style_select")
               
                style_name = STYLE_CATEGORIES.get(selected_style, "建築")
                images = IMAGE_LIBRARY.get(style_name, [])
               
                if images:
                    with col_img:
                        image_options = [f"{i+1}. {images[i]['name']}" for i in range(len(images))]
                        img_idx = st.selectbox("圖片", range(len(images)), format_func=lambda i: image_options[i], key="embed_image_select")
                    with col_size:
                        size_options = [f"{s}×{s} ⭐推薦" if s == recommended_size else f"{s}×{s}" for s in available_sizes]
                        size_idx = st.selectbox("尺寸", range(len(available_sizes)), format_func=lambda i: size_options[i], key="embed_size_select")
                        selected_size = available_sizes[size_idx]
                   
                    selected_image = images[img_idx]
                    preview_size = 256
                    img_display, _ = download_image_by_id(selected_image["id"], preview_size)
                   
                    capacity = calculate_image_capacity(selected_size)
                    usage = secret_bits_needed / capacity * 100
                   
                    st.markdown('<div style="margin-top: 5px;"></div>', unsafe_allow_html=True)
                    col_left, col_img, col_info, col_right = st.columns([1.2, 0.6, 2, 0.5])
                    with col_img:
                        st.image(img_display, caption=f"{style_name} - {selected_image['name']}", width=200)
                    with col_info:
                        if usage > 90:
                            st.markdown(f'<div style="display: flex; align-items: center; min-height: 180px;"><div style="color: #ffa726; font-size: clamp(18px, 2vw, 22px); margin-left: 50px;">機密容量 {secret_bits_needed:,} bits / 圖像容量 {capacity:,} bits ({usage:.1f}%)</div></div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div style="display: flex; align-items: center; min-height: 180px;"><div style="font-size: clamp(18px, 2vw, 22px); color: #443C3C; margin-left: 50px;">機密容量 {secret_bits_needed:,} bits / 圖像容量 {capacity:,} bits ({usage:.1f}%)</div></div>', unsafe_allow_html=True)
                   
                    code = f"{style_name}-{img_idx+1}-{selected_size}"
                    embed_image_choice = code
                   
                    st.session_state.embed_image_id = selected_image["id"]
                    st.session_state.embed_image_size = selected_size
                    st.session_state.embed_image_name = selected_image["name"]
                else:
                    st.warning(f"⚠️ 「{selected_style}」沒有可用圖片")
               
                if embed_image_choice:
                    embed_btn = st.button("開始嵌入", type="primary", key="embed_btn_step3")
                   
                    components.html("""
                    <script>
                    const findAndFixEmbedButton = () => {
                        const buttons = window.parent.document.querySelectorAll('button');
                        for (let btn of buttons) { if (btn.innerText === '開始嵌入') { btn.id = 'next-step-fixed'; break; } }
                    };
                    findAndFixEmbedButton();
                    const observer = new MutationObserver(findAndFixEmbedButton);
                    observer.observe(window.parent.document.body, { childList: true, subtree: true });
                    </script>
                    """, height=0)
                   
                    if embed_btn:
                        processing_placeholder = st.empty()
                        processing_placeholder.markdown("""
                        <div style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 9999; display: flex; justify-content: center; align-items: center;">
                            <div style="background: white; padding: 40px 60px; border-radius: 16px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.3);">
                                <div style="font-size: 28px; font-weight: bold; color: #5D6D7E; margin-bottom: 20px;">🔄 嵌入中...</div>
                                <div style="font-size: 18px; color: #888;">請稍候，正在處理您的機密資料</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                       
                        try:
                            start = time.time()
                            image_id = st.session_state.get('embed_image_id')
                            image_size = st.session_state.get('embed_image_size')
                            _, img_process = download_image_by_id(image_id, image_size)
                            capacity = calculate_image_capacity(image_size)
                           
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
                                'code': embed_image_choice,
                                'image_name': st.session_state.get('embed_image_name', ''),
                                'image_size': image_size,
                                'secret_filename': secret_filename,
                                'secret_bits': info['bits'],
                                'capacity': capacity,
                                'usage_percent': info['bits']*100/capacity
                            }
                            for key in ['selected_contact_saved', 'secret_bits_saved', 'embed_text_saved', 'embed_secret_type_saved', 'embed_secret_image_data', 'embed_secret_image_name']:
                                if key in st.session_state:
                                    del st.session_state[key]
                            st.session_state.embed_page = 'result'
                            st.session_state.embed_step = 1
                            st.rerun()
                        except Exception as e:
                            processing_placeholder.empty()
                            st.markdown(f'<div class="error-box">❌ 嵌入失敗! {e}</div>', unsafe_allow_html=True)
            else:
                if secret_bits_needed == 0 and selected_contact == "選擇":
                    st.info("請先完成步驟 1 和 2")
                elif secret_bits_needed == 0:
                    st.info("請先完成步驟 2（機密內容）")
                else:
                    st.info("請先完成步驟 1（選擇對象）")
       
        if st.session_state.embed_step >= 2:
            if st.button("返回", key="back_step_btn"):
                st.session_state.embed_step = st.session_state.embed_step - 1
                st.rerun()
       
        if st.session_state.embed_step < 3:
            if st.button("下一步", type="primary", key="next_step_btn", disabled=not show_next_btn):
                if show_next_btn:
                    st.session_state.embed_step = next_step
                    st.rerun()
       
        if st.session_state.embed_step < 3 or st.session_state.embed_step >= 2:
            components.html("""
            <script>
            const findAndFixButton = () => {
                const buttons = window.parent.document.querySelectorAll('button');
                for (let btn of buttons) {
                    if (btn.innerText === '下一步') { btn.id = 'next-step-fixed'; }
                    if (btn.innerText === '返回') { btn.id = 'back-step-fixed'; }
                }
            };
            findAndFixButton();
            const observer = new MutationObserver(findAndFixButton);
            observer.observe(window.parent.document.body, { childList: true, subtree: true });
            </script>
            """, height=0)
else:
    # ==================== 提取模式頁面 ====================
   
    if 'extract_page' not in st.session_state:
        st.session_state.extract_page = 'input'
   
    if st.session_state.extract_page == 'result' and st.session_state.extract_result and st.session_state.extract_result.get('success'):
        st.markdown("""<style>.main { overflow: auto !important; } section.main > div { overflow: auto !important; }</style>""", unsafe_allow_html=True)
       
        r = st.session_state.extract_result
       
        st.markdown('<div class="page-title-extract" style="text-align: center; margin-bottom: 30px;">提取結果</div>', unsafe_allow_html=True)
       
        spacer_left, c1, c2, spacer_right = st.columns([1, 2, 2, 1])
        with c1:
            st.markdown(f'<div class="success-box" style="padding: 12px 20px; min-width: min(200px, 90%); font-size: clamp(18px, 2vw, 24px);">提取成功! ({r["elapsed_time"]:.2f} 秒)</div>', unsafe_allow_html=True)
           
            if r['type'] == 'text':
                st.markdown('<p style="font-size: clamp(22px, 2.5vw, 28px); font-weight: bold; margin-top: 15px;">機密文字:</p>', unsafe_allow_html=True)
                st.markdown(f'<p style="font-size: clamp(16px, 1.8vw, 20px); color: #443C3C; white-space: pre-wrap;">{r["content"]}</p>', unsafe_allow_html=True)
            else:
                st.markdown('<p style="font-size: clamp(22px, 2.5vw, 28px); font-weight: bold; margin-top: 15px;">機密圖片:</p>', unsafe_allow_html=True)
                st.image(Image.open(BytesIO(r['image_data'])), width=200)
                st.download_button("下載圖片", r['image_data'], "recovered.png", "image/png", key="dl_rec")
       
        with c2:
            st.markdown('<p style="font-size: clamp(22px, 2.5vw, 28px); font-weight: bold;">驗證結果</p>', unsafe_allow_html=True)
            if r['type'] == 'text':
                verify_input = st.text_area("輸入原始機密", key="verify_text_input", height=50, placeholder="貼上嵌入時的原始機密內容...")
                if st.button("驗證", key="verify_btn"):
                    if verify_input:
                        col_orig, col_ext = st.columns(2)
                        with col_orig:
                            st.markdown('<p style="font-size: clamp(16px, 1.8vw, 20px); font-weight: bold; margin-bottom: 0;">原始機密：</p>', unsafe_allow_html=True)
                            st.markdown(f'<p style="font-size: clamp(14px, 1.6vw, 18px); color: #443C3C; white-space: pre-wrap; margin: 5px 0;">{verify_input}</p>', unsafe_allow_html=True)
                            st.markdown(f'<p style="font-size: clamp(14px, 1.6vw, 18px); color: #443C3C; margin: 0;">{len(verify_input)} 字元</p>', unsafe_allow_html=True)
                        with col_ext:
                            st.markdown('<p style="font-size: clamp(16px, 1.8vw, 20px); font-weight: bold; margin-bottom: 0;">提取結果：</p>', unsafe_allow_html=True)
                            st.markdown(f'<p style="font-size: clamp(14px, 1.6vw, 18px); color: #443C3C; white-space: pre-wrap; margin: 5px 0;">{r["content"]}</p>', unsafe_allow_html=True)
                            st.markdown(f'<p style="font-size: clamp(14px, 1.6vw, 18px); color: #443C3C; margin: 0;">{len(r["content"])} 字元</p>', unsafe_allow_html=True)
                       
                        if verify_input == r['content']:
                            st.markdown('<p style="font-size: clamp(18px, 2vw, 22px); font-weight: bold; color: #2E7D32; margin-top: 10px;">完全一致！</p>', unsafe_allow_html=True)
                        else:
                            st.markdown('<p style="font-size: clamp(18px, 2vw, 22px); font-weight: bold; color: #C62828; margin-top: 10px;">不一致！</p>', unsafe_allow_html=True)
                    else:
                        st.warning("請輸入原始機密")
            else:
                verify_img = st.file_uploader("上傳原始機密圖片", type=["png", "jpg", "jpeg"], key="verify_img_upload")
                if verify_img:
                    orig_img = Image.open(verify_img)
                    extracted_img = Image.open(BytesIO(r['image_data']))
                   
                    def get_actual_mode(img):
                        if img.mode == 'L':
                            return '灰階'
                        elif img.mode in ['RGB', 'RGBA']:
                            arr = np.array(img.convert('RGB'))
                            if np.array_equal(arr[:,:,0], arr[:,:,1]) and np.array_equal(arr[:,:,1], arr[:,:,2]):
                                return '灰階'
                            return '彩色'
                        return img.mode
                   
                    orig_mode = get_actual_mode(orig_img)
                    ext_mode = get_actual_mode(extracted_img)
                   
                    col_orig, col_gap, col_ext = st.columns([1, 0.8, 1])
                    with col_orig:
                        st.markdown('<p style="font-size: clamp(18px, 2vw, 24px); font-weight: bold;">原始圖片：</p>', unsafe_allow_html=True)
                        st.image(orig_img, width=180)
                        st.markdown(f'<p style="font-size: clamp(16px, 1.8vw, 22px); color: #443C3C; white-space: nowrap;">尺寸：{orig_img.size[0]}×{orig_img.size[1]} | 模式：{orig_mode}</p>', unsafe_allow_html=True)
                    with col_ext:
                        st.markdown('<p style="font-size: clamp(18px, 2vw, 24px); font-weight: bold;">提取結果：</p>', unsafe_allow_html=True)
                        st.image(extracted_img, width=180)
                        st.markdown(f'<p style="font-size: clamp(16px, 1.8vw, 22px); color: #443C3C; white-space: nowrap;">尺寸：{extracted_img.size[0]}×{extracted_img.size[1]} | 模式：{ext_mode}</p>', unsafe_allow_html=True)
                   
                    orig_arr = np.array(orig_img.convert('RGB'))
                    ext_arr = np.array(extracted_img.convert('RGB'))
                   
                    if orig_arr.shape == ext_arr.shape:
                        diff = np.abs(orig_arr.astype(int) - ext_arr.astype(int))
                        mse = np.mean(diff ** 2)
                        if mse == 0:
                            st.markdown(f'<p style="font-size: clamp(18px, 2vw, 24px); color: #443C3C;">MSE: {mse:.4f} &nbsp;&nbsp; <b style="color: #2E7D32;">完全一致！</b></p>', unsafe_allow_html=True)
                        elif mse < 100:
                            st.markdown(f'<p style="font-size: clamp(18px, 2vw, 24px); color: #443C3C;">MSE: {mse:.4f} &nbsp;&nbsp; <b style="color: #F57C00;">接近一致</b></p>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<p style="font-size: clamp(18px, 2vw, 24px); color: #443C3C;">MSE: {mse:.4f} &nbsp;&nbsp; <b style="color: #C62828;">不一致</b></p>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<p style="font-size: clamp(18px, 2vw, 24px); color: #1976D2;">尺寸不同：原始 {orig_img.size} vs 提取 {extracted_img.size}</p>', unsafe_allow_html=True)
       
        st.markdown("""
        <style>
        #btn-back-home-extract span, #btn-back-home-extract p { font-size: 18px !important; font-weight: bold !important; }
        #btn-back-home-extract { position: fixed !important; bottom: clamp(5px, 1vw, 15px) !important; right: clamp(15px, 3vw, 30px) !important; z-index: 1000 !important; background: white !important; color: #333 !important; border: 2px solid #ccc !important; border-radius: 8px !important; cursor: pointer !important; }
        #btn-verify span, #btn-verify p { font-size: 18px !important; font-weight: bold !important; }
        #btn-verify { background: linear-gradient(135deg, #7D5A6B 0%, #A67B85 100%) !important; color: white !important; border: none !important; border-radius: 8px !important; }
        </style>
        """, unsafe_allow_html=True)
       
        if st.button("返回首頁", key="back_to_home_from_extract"):
            st.session_state.extract_page = 'input'
            st.session_state.extract_result = None
            st.session_state.current_mode = None
            st.rerun()
       
        components.html("""
        <script>
        const fixExtractButtons = () => {
            const buttons = window.parent.document.querySelectorAll('button');
            for (let btn of buttons) {
                if (btn.innerText === '返回首頁') btn.id = 'btn-back-home-extract';
                if (btn.innerText === '驗證') btn.id = 'btn-verify';
            }
        };
        fixExtractButtons();
        const observer = new MutationObserver(fixExtractButtons);
        observer.observe(window.parent.document.body, { childList: true, subtree: true });
        </script>
        """, height=0)
   
    else:
        st.session_state.extract_page = 'input'
       
        st.markdown('<div id="sidebar-toggle-label">對象管理</div>', unsafe_allow_html=True)
       
        components.html("""
<script>
(function() {
    const doc = window.parent.document;
   
    function fixSidebarSelectbox() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        if (sidebar) {
            if (!doc.getElementById('sidebar-selectbox-style')) {
                const style = doc.createElement('style');
                style.id = 'sidebar-selectbox-style';
                style.textContent = `
                    section[data-testid="stSidebar"] .stSelectbox div { font-size: 20px !important; }
                    section[data-testid="stSidebar"] [data-baseweb="select"] input { font-size: 20px !important; caret-color: transparent !important; }
                `;
                doc.head.appendChild(style);
            }
            const allElements = sidebar.querySelectorAll('.stSelectbox *');
            allElements.forEach(el => { el.style.fontSize = '20px'; });
            const inputs = sidebar.querySelectorAll('[data-baseweb="select"] input');
            inputs.forEach(input => {
                input.setAttribute('readonly', 'true');
                input.style.fontSize = '20px';
                input.style.caretColor = 'transparent';
                input.style.cursor = 'pointer';
            });
        }
        const mainInputs = doc.querySelectorAll('[data-testid="stMain"] [data-baseweb="select"] input');
        mainInputs.forEach(input => {
            input.setAttribute('readonly', 'true');
            input.style.fontSize = '22px';
            input.style.caretColor = 'transparent';
            input.style.cursor = 'pointer';
        });
        const mainDivs = doc.querySelectorAll('[data-testid="stMain"] .stSelectbox div');
        mainDivs.forEach(div => { div.style.fontSize = '22px'; });
    }
   
    function hideStreamlitCollapseBtn() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        if (sidebar) {
            const btns = sidebar.querySelectorAll('button');
            btns.forEach(btn => {
                if (btn.id !== 'sidebar-close-btn' && !btn.closest('.stExpander')) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.top < 100 && rect.right > sidebar.getBoundingClientRect().right - 60) {
                        btn.style.display = 'none';
                    }
                }
            });
        }
        fixSidebarSelectbox();
    }
   
    function closeSidebar() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        const label = doc.getElementById('sidebar-toggle-label');
        if (sidebar) { sidebar.classList.remove('sidebar-open'); }
        if (label) label.style.display = 'block';
    }
   
    function openSidebar() {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        const label = doc.getElementById('sidebar-toggle-label');
        if (sidebar) { sidebar.classList.add('sidebar-open'); hideStreamlitCollapseBtn(); }
        if (label) label.style.display = 'none';
    }
   
    function setupToggle() {
        const label = doc.getElementById('sidebar-toggle-label');
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        if (sidebar && sidebar.classList.contains('sidebar-open')) {
            if (label) label.style.display = 'none';
        }
        if (label && !label.hasAttribute('data-sidebar-bindx')) {
            label.setAttribute('data-sidebar-bindx', 'true');
            label.addEventListener('click', openSidebar);
        }
        const closeBtn = doc.getElementById('sidebar-close-btn');
        if (closeBtn) { closeBtn.onclick = closeSidebar; }
        hideStreamlitCollapseBtn();
    }
   
    function fixAllSelectboxes() {
        if (!doc.getElementById('global-selectbox-style')) {
            const style = doc.createElement('style');
            style.id = 'global-selectbox-style';
            style.textContent = `
                .stSelectbox div { font-size: 22px !important; }
                [data-baseweb="select"] input { font-size: 22px !important; caret-color: transparent !important; }
                [data-baseweb="select"] > div { min-height: 50px !important; display: flex !important; align-items: center !important; }
                [data-baseweb="popover"] li { font-size: 22px !important; }
                .stRadio [role="radiogroup"] label { font-size: 28px !important; }
                .stRadio label { font-size: 28px !important; }
                .stRadio label p { font-size: 28px !important; }
                [data-testid="stRadio"] label p { font-size: 28px !important; }
                [data-testid="stImage"] figcaption { font-size: 22px !important; }
                [data-testid="stImage"] + div { font-size: 22px !important; }
                .element-container figcaption { font-size: 22px !important; }
            `;
            doc.head.appendChild(style);
        }
        const mainInputs = doc.querySelectorAll('[data-baseweb="select"] input');
        mainInputs.forEach(input => {
            input.setAttribute('readonly', 'true');
            input.style.setProperty('font-size', '22px', 'important');
            input.style.setProperty('caret-color', 'transparent', 'important');
            input.style.cursor = 'pointer';
        });
        const allSelectDivs = doc.querySelectorAll('.stSelectbox div');
        allSelectDivs.forEach(div => { div.style.setProperty('font-size', '22px', 'important'); });
        const radioLabels = doc.querySelectorAll('.stRadio label, [data-testid="stRadio"] label');
        radioLabels.forEach(label => {
            label.style.setProperty('font-size', '28px', 'important');
            const p = label.querySelector('p');
            if (p) p.style.setProperty('font-size', '28px', 'important');
            const span = label.querySelector('span');
            if (span) span.style.setProperty('font-size', '28px', 'important');
        });
        const captions = doc.querySelectorAll('[data-testid="stImage"] + div, figcaption, .stCaption');
        captions.forEach(cap => { cap.style.setProperty('font-size', '22px', 'important'); });
        const figcaptions = doc.querySelectorAll('figcaption');
        figcaptions.forEach(fig => {
            fig.style.setProperty('font-size', '22px', 'important');
            fig.style.setProperty('color', '#443C3C', 'important');
        });
        const labels = doc.querySelectorAll('[data-testid="stWidgetLabel"] p');
        labels.forEach(label => {
            label.style.setProperty('font-size', '24px', 'important');
            label.style.setProperty('font-weight', 'bold', 'important');
        });
        const imgContainers = doc.querySelectorAll('[data-testid="stImage"]');
        imgContainers.forEach(container => {
            const texts = container.querySelectorAll('div, span, p');
            texts.forEach(t => {
                if (t.innerText && t.innerText.trim()) {
                    t.style.setProperty('font-size', '22px', 'important');
                    t.style.setProperty('color', '#443C3C', 'important');
                }
            });
        });
    }
   
    setupToggle();
    fixAllSelectboxes();
    setTimeout(() => { setupToggle(); fixAllSelectboxes(); }, 100);
    setTimeout(() => { setupToggle(); fixAllSelectboxes(); }, 500);
    setTimeout(() => { setupToggle(); fixAllSelectboxes(); }, 1000);
    new MutationObserver(() => { setupToggle(); fixAllSelectboxes(); }).observe(doc.body, { childList: true, subtree: true });
})();
</script>
""", height=0)
       
        st.markdown('<div class="page-title-extract" style="text-align: center; margin-bottom: 20px; margin-top: -4rem;">提取機密</div>', unsafe_allow_html=True)
       
        extract_z_text = None
        extract_img_num = None
        extract_img_size = None
       
        contacts = st.session_state.contacts
        contact_names = list(contacts.keys())
       
        if 'extract_step' not in st.session_state:
            st.session_state.extract_step = 1
       
        current_step = st.session_state.extract_step
        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
            <div class="step-indicator" style="flex: 1; text-align: center; border-bottom: {'4px solid #7D5A6B' if current_step == 1 else '2px solid #D8C0C8'}; color: {'#7D5A6B' if current_step == 1 else '#A08090'};">第一步: 選擇對象</div>
            <div class="step-indicator" style="flex: 1; text-align: center; border-bottom: {'4px solid #7D5A6B' if current_step == 2 else '2px solid #D8C0C8'}; color: {'#7D5A6B' if current_step == 2 else '#A08090'};">第二步: 上傳 Z碼圖</div>
        </div>
        """, unsafe_allow_html=True)
       
        st.markdown("---")
       
        show_next_btn = False
        next_step = 1
        style_name = None
        selected_contact = None
       
        if st.session_state.extract_step == 1:
            st.markdown('<p style="font-size: clamp(24px, 2.6vw, 30px); font-weight: bold; margin-bottom: 10px;">選擇對象</p>', unsafe_allow_html=True)
            if contact_names:
                options = ["選擇"] + contact_names
                saved_contact = st.session_state.get('extract_contact_saved', None)
                default_idx = options.index(saved_contact) if saved_contact and saved_contact in contact_names else 0
               
                selected_contact = st.selectbox("對象", options, index=default_idx, key="extract_contact_select", label_visibility="collapsed")
               
                if selected_contact != "選擇":
                    st.session_state.extract_contact_saved = selected_contact
                    auto_style = contacts[selected_contact]
                   
                    style_list = list(STYLE_CATEGORIES.keys())
                    default_style_index = style_list.index(auto_style) if auto_style and auto_style != "選擇" and auto_style in style_list else 0
                   
                    selected_style = st.selectbox("風格", style_list, index=default_style_index, key="extract_style_select")
                    style_name = STYLE_CATEGORIES.get(selected_style, "建築")
                    st.session_state.extract_style_saved = selected_style
                   
                    st.markdown(f'<p style="font-size: clamp(20px, 2.2vw, 26px); color: #31333F;">✅ 已選擇：{selected_contact}（{selected_style}）</p>', unsafe_allow_html=True)
                    show_next_btn = True
                    next_step = 2
            else:
                st.markdown("""<div style="background: linear-gradient(135deg, #fff3cd 0%, #ffe69c 100%); border: 2px solid #ffc107; border-radius: 12px; padding: 15px; text-align: center; margin: 10px 0;"><div style="font-size: 16px; font-weight: bold; color: #856404;">⚠️ 請先新增對象（點擊左上角「對象管理」按鈕）</div></div>""", unsafe_allow_html=True)
       
        elif st.session_state.extract_step == 2:
            st.markdown("""<style>.main { overflow: hidden !important; } section.main > div { overflow: hidden !important; }</style>""", unsafe_allow_html=True)
           
            saved_contact = st.session_state.get('extract_contact_saved', None)
            saved_style = st.session_state.get('extract_style_saved', None)
           
            if saved_contact and saved_contact in contact_names:
                selected_contact = saved_contact
                style_name = STYLE_CATEGORIES.get(saved_style, "建築")
                st.markdown(f'<p style="font-size: clamp(18px, 2vw, 24px); color: #31333F;">對象：{selected_contact}（{saved_style}）</p>', unsafe_allow_html=True)
               
                st.markdown('<p style="font-size: clamp(20px, 2.2vw, 26px); font-weight: bold; margin-bottom: 10px;">上傳 Z碼圖</p>', unsafe_allow_html=True)
                extract_file = st.file_uploader("上傳 QR Code 或 Z碼圖片", type=["png", "jpg", "jpeg"], key="extract_z_upload", label_visibility="collapsed")
               
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
                                    if style_name:
                                        images = IMAGE_LIBRARY.get(style_name, [])
                                        if extract_img_num <= len(images):
                                            img_name = images[extract_img_num - 1]['name']
                                            success_msg = f"QR Code 讀取內容：圖片 {extract_img_num}（{img_name}），尺寸 {extract_img_size}×{extract_img_size}"
                                        else:
                                            success_msg = f"QR Code 讀取內容：圖片 {extract_img_num}，尺寸 {extract_img_size}×{extract_img_size}"
                                    else:
                                        success_msg = f"QR Code 讀取內容：圖片 {extract_img_num}，尺寸 {extract_img_size}×{extract_img_size}"
                                    detected = True
                    except:
                        pass
                   
                    if not detected:
                        try:
                            z_bits, img_num, img_size = decode_image_to_z_with_header(uploaded_img)
                            extract_img_num = img_num
                            extract_img_size = img_size
                            extract_z_text = ''.join(str(b) for b in z_bits)
                            if style_name:
                                images = IMAGE_LIBRARY.get(style_name, [])
                                if extract_img_num <= len(images):
                                    img_name = images[extract_img_num - 1]['name']
                                    success_msg = f"Z碼圖讀取內容：圖片 {extract_img_num}（{img_name}），尺寸 {extract_img_size}×{extract_img_size}"
                                else:
                                    success_msg = f"Z碼圖讀取內容：圖片 {extract_img_num}，尺寸 {extract_img_size}×{extract_img_size}"
                            else:
                                success_msg = f"Z碼圖讀取內容：圖片 {extract_img_num}，尺寸 {extract_img_size}×{extract_img_size}"
                            detected = True
                        except:
                            pass
                   
                    st.markdown('<div style="margin-top: -10px;"></div>', unsafe_allow_html=True)
                    col_left, col_img, col_info, col_right = st.columns([1.2, 0.6, 2, 0.5])
                    with col_img:
                        st.image(uploaded_img, width=200)
                    with col_info:
                        if detected:
                            st.markdown(f'<div style="display: flex; align-items: center; min-height: 180px;"><div style="font-size: clamp(18px, 2vw, 22px); color: #443C3C; margin-left: 50px;">{success_msg.replace("<br>", " ")}</div></div>', unsafe_allow_html=True)
                        else:
                            st.markdown('<div style="display: flex; align-items: center; min-height: 180px;"><div style="font-size: clamp(18px, 2vw, 22px); color: #C62828; margin-left: 50px;">無法識別，請確認上傳的是 QR Code 或 Z碼圖片</div></div>', unsafe_allow_html=True)
            else:
                st.info("請先完成步驟 1（選擇對象）")
       
        if st.session_state.extract_step >= 2:
            if st.button("返回", key="extract_back_step_btn"):
                st.session_state.extract_step = st.session_state.extract_step - 1
                st.rerun()
       
        if show_next_btn and st.session_state.extract_step < 2:
            if st.button("下一步", type="primary", key="extract_next_btn"):
                st.session_state.extract_step = next_step
                st.rerun()
       
        if st.session_state.extract_step < 2 or st.session_state.extract_step >= 2:
            components.html("""
            <script>
            const findAndFixButton = () => {
                const buttons = window.parent.document.querySelectorAll('button');
                for (let btn of buttons) {
                    if (btn.innerText === '下一步') { btn.id = 'next-step-fixed'; }
                    if (btn.innerText === '返回') { btn.id = 'back-step-fixed'; }
                }
            };
            findAndFixButton();
            const observer = new MutationObserver(findAndFixButton);
            observer.observe(window.parent.document.body, { childList: true, subtree: true });
            </script>
            """, height=0)
       
        if st.session_state.extract_step == 2 and extract_z_text and extract_img_num and extract_img_size:
            extract_btn = st.button("開始提取", type="primary", key="extract_start_btn")
           
            components.html("""
            <script>
            const fixExtractBtn = () => {
                const buttons = window.parent.document.querySelectorAll('button');
                for (const btn of buttons) { if (btn.innerText === '開始提取') btn.id = 'next-step-fixed'; }
            };
            fixExtractBtn();
            const observer = new MutationObserver(fixExtractBtn);
            observer.observe(window.parent.document.body, { childList: true, subtree: true });
            </script>
            """, height=0)
           
            if extract_btn:
                processing_placeholder = st.empty()
                processing_placeholder.markdown("""
                <div style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 9999; display: flex; justify-content: center; align-items: center;">
                    <div style="background: white; padding: 40px 60px; border-radius: 16px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.3);">
                        <div style="font-size: 28px; font-weight: bold; color: #5D6D7E; margin-bottom: 20px;">🔄 提取中...</div>
                        <div style="font-size: 18px; color: #888;">請稍候，正在解析您的機密資料</div>
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
                                st.session_state.extract_result = {'success': True, 'type': 'image', 'elapsed_time': time.time()-start, 'image_data': buf.getvalue(), 'orig_size': info['size'], 'color_mode': secret.mode}
                           
                            for key in ['extract_contact_saved', 'extract_style_saved']:
                                if key in st.session_state:
                                    del st.session_state[key]
                            st.session_state.extract_step = 1
                            st.session_state.extract_page = 'result'
                            st.rerun()
                        else:
                            processing_placeholder.empty()
                            st.error(f"❌ 找不到圖片編號 {extract_img_num}")
                except Exception as e:
                    processing_placeholder.empty()
                    st.markdown(f'<div class="error-box">❌ 提取失敗! {e}</div>', unsafe_allow_html=True)
