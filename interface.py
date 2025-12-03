
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
import json

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

CONTACTS_FILE = "contacts.json"

def load_contacts():
    try:
        if os.path.exists(CONTACTS_FILE):
            with open(CONTACTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_contacts(contacts):
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
    for size in AVAILABLE_SIZES:
        capacity = calculate_image_capacity(size)
        if capacity >= secret_bits:
            return size
    return AVAILABLE_SIZES[-1]

def get_image_url(pexels_id, size):
    return f"https://images.pexels.com/photos/{pexels_id}/pexels-photo-{pexels_id}.jpeg?auto=compress&cs=tinysrgb&w={size}&h={size}&fit=crop"

@st.cache_data(ttl=86400, show_spinner=False)
def download_image_cached(pexels_id, size):
    url = f"https://images.pexels.com/photos/{pexels_id}/pexels-photo-{pexels_id}.jpeg?auto=compress&cs=tinysrgb&w={size}&h={size}&fit=crop"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.content
    except:
        pass
    return None

def download_image_by_id(pexels_id, size):
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
def calculate_remaining_capacity(capacity_bits, used_bits):
    remaining_bits = capacity_bits - used_bits
    if remaining_bits <= 0:
        return 0, 0
    return remaining_bits // 24, remaining_bits // 8

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
    elif original_mode not in ['RGB', 'RGBA']:
        has_alpha = False
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

# ==================== Z碼圖編碼/解碼 =====================
def encode_z_as_image_auto(z_bits):
    length = len(z_bits)
    length_bits = [int(b) for b in format(length, '032b')]
    full_bits = length_bits + z_bits
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

def encode_z_as_image_with_header(z_bits, img_num, img_size):
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
    if image.mode != 'L':
        image = image.convert('L')
    pixels = list(image.getdata())
    all_bits = []
    for pixel in pixels:
        bits = [int(b) for b in format(pixel, '08b')]
        all_bits.extend(bits)
    if len(all_bits) < 64:
        raise ValueError("Z碼圖片格式錯誤：太小")
    z_length = int(''.join(map(str, all_bits[:32])), 2)
    img_num = int(''.join(map(str, all_bits[32:48])), 2)
    img_size = int(''.join(map(str, all_bits[48:64])), 2)
    if z_length <= 0 or z_length > len(all_bits) - 64:
        raise ValueError(f"Z碼長度無效：{z_length}")
    z_bits = all_bits[64:64 + z_length]
    return z_bits, img_num, img_size

def decode_image_to_z_auto(image):
    if image.mode != 'L':
        image = image.convert('L')
    pixels = list(image.getdata())
    all_bits = []
    for pixel in pixels:
        bits = [int(b) for b in format(pixel, '08b')]
        all_bits.extend(bits)
    if len(all_bits) < 32:
        raise ValueError("Z碼圖片格式錯誤：太小")
    length_bits = all_bits[:32]
    actual_length = int(''.join(map(str, length_bits)), 2)
    if actual_length <= 0 or actual_length > len(all_bits) - 32:
        raise ValueError(f"Z碼長度無效：{actual_length}")
    z_bits = all_bits[32:32 + actual_length]
    return z_bits, actual_length

# ==================== Streamlit 頁面配置 ====================
st.set_page_config(page_title="🔐 高效能無載體之機密編碼技術", page_icon="🔐", layout="wide", initial_sidebar_state="collapsed")

# ==================== 強化 CSS 與 JS（覆蓋動態元素） ====================
# 這段 CSS/JS 使用更強的選擇器、!important 與 MutationObserver 來移除右下角浮動元素並確保上方間距生效
st.markdown("""
<style>
/* 強制上方內距，讓標題與卡片往下（提高優先權） */
.block-container, .main, .css-1d391kg, .css-1outpf7 {
    padding-top: 5rem !important;
}

/* 限制主區域最大寬度 */
[data-testid="stMain"] > div, .block-container {
    max-width: 1400px !important;
    margin: 0 auto !important;
}

/* 卡片高度與間距調整，減少下方空白 */
.anim-card {
    min-height: clamp(140px, 16vw, 200px) !important;
    margin-bottom: clamp(8px, 1vw, 12px) !important;
    padding: clamp(16px, 2vw, 26px) !important;
}

/* 更強力隱藏右下角常見浮動元素（通用） */
div[style*="position: fixed"][style*="right"], 
div[style*="position: fixed"][style*="bottom"], 
div[style*="position: fixed"][style*="z-index"], 
a[href*="streamlit"], 
a[class*="stBadge"], 
button[class*="stBadge"], 
div[class*="floating"], 
div[class*="badge"], 
div[class*="share"], 
div[class*="floating-action"] {
    display: none !important;
    visibility: hidden !important;
    pointer-events: none !important;
    opacity: 0 !important;
    height: 0 !important;
    width: 0 !important;
}

/* 針對 footer、header、menu 再次隱藏 */
header, footer, #MainMenu, .stToolbar, [data-testid="stHeader"], [data-testid="stToolbar"] {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    width: 0 !important;
}

/* 保險：隱藏任何固定定位且位於右下象限的元素 */
body * {
    transition: none !important;
}
</style>

<script>
// 使用 MutationObserver 移除動態插入的浮動元素（例如右下角徽章或分享按鈕）
(function() {
    function removeFloating() {
        try {
            // 常見選擇器集合
            const selectors = [
                'div[style*="position: fixed"][style*="right"]',
                'div[style*="position: fixed"][style*="bottom"]',
                'a[href*="streamlit"]',
                'a[class*="stBadge"]',
                'div[class*="floating"]',
                'div[class*="badge"]',
                'div[class*="share"]',
                'div[class*="floating-action"]',
                'button[class*="stBadge"]',
                'iframe'
            ];
            selectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => {
                    // 進一步檢查位置（右下角）
                    const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
                    if (!rect || (rect.right > window.innerWidth - 50 && rect.bottom > window.innerHeight - 50) || true) {
                        el.style.display = 'none';
                        el.style.visibility = 'hidden';
                        el.style.pointerEvents = 'none';
                        el.style.opacity = '0';
                        el.style.height = '0';
                        el.style.width = '0';
                    }
                });
            });
        } catch (e) {
            // ignore
        }
    }

    // 初次移除
    removeFloating();

    // 監聽 DOM 變化，持續移除
    const observer = new MutationObserver(function(mutations) {
        removeFloating();
    });
    observer.observe(document.documentElement || document.body, { childList: true, subtree: true, attributes: true });

    // 也在視窗大小改變時再移除一次
    window.addEventListener('resize', removeFloating);
    // 最後保險：在頁面載入後 1s、2s、3s 再次執行
    setTimeout(removeFloating, 500);
    setTimeout(removeFloating, 1500);
    setTimeout(removeFloating, 3000);
})();
</script>
""", unsafe_allow_html=True)

# ==================== 簡單的 UI 範例（首頁） ====================
def show_home():
    st.markdown('<div class="welcome-container">', unsafe_allow_html=True)
    st.markdown(f'<div class="welcome-title">🔐 高效能無載體之機密編碼技術</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="welcome-subtitle">嵌入與提取機密資訊的高效流程示意</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown('<div class="anim-card anim-card-embed">', unsafe_allow_html=True)
        st.markdown('<div class="anim-flow">', unsafe_allow_html=True)
        st.markdown('<div class="anim-icon anim-icon-secret">📦</div><div class="anim-icon anim-icon-arrow">➡️</div><div class="anim-icon anim-icon-result">🖼️</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="anim-title">嵌入機密</div>', unsafe_allow_html=True)
        st.markdown('<div class="anim-desc">將機密編碼為 Z 碼並嵌入載體圖像</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="anim-card anim-card-extract">', unsafe_allow_html=True)
        st.markdown('<div class="anim-flow">', unsafe_allow_html=True)
        st.markdown('<div class="anim-icon anim-icon-source">🖼️</div><div class="anim-icon anim-icon-arrow">➡️</div><div class="anim-icon anim-icon-result">📦</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="anim-title">提取機密</div>', unsafe_allow_html=True)
        st.markdown('<div class="anim-desc">從載體圖像中偵測並還原 Z 碼</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="text-align:center; margin-top:12px; color:#333; font-weight:600;">組員：鄭凱馨、劉佳典、王于婕</div>', unsafe_allow_html=True)

def main():
    show_home()
    st.markdown("---")
    st.markdown("**操作說明**")
    st.write("請重新整理頁面以套用最新樣式。若仍有右下角元素，請告訴我該元素的畫面截圖或顯示文字，我會針對該元素做精準隱藏。")

if __name__ == "__main__":
    main()
