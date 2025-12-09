# embed.py → 嵌入模組（支援文字和圖片，含對象密鑰）

import numpy as np

from config import Q_LENGTH, TOTAL_AVERAGES_PER_UNIT, BLOCK_SIZE, calculate_capacity
from permutation import generate_Q_from_block, apply_Q_three_rounds
from image_processing import calculate_hierarchical_averages
from binary_operations import get_msbs
from mapping import map_to_z
from secret_encoding import text_to_binary, image_to_binary


def shuffle_bits(bits, key):
    """
    功能:
        用密鑰打亂位元順序
    
    參數:
        bits: 位元列表
        key: 密鑰字串
    
    返回:
        打亂後的位元列表
    
    原理:
        用 key 的 hash 值作為 seed，生成固定的打亂順序
        同樣的 key 永遠產生同樣的打亂順序
    """
    if not key or len(bits) == 0:
        return bits
    
    seed = hash(key) % 2147483647
    np.random.seed(seed)
    order = np.random.permutation(len(bits))
    
    return [bits[i] for i in order]


def embed_secret(cover_image, secret, secret_type='text', contact_key=None):
    """
    功能:
        將機密內容嵌入無載體圖片，產生 Z 碼
    
    參數:
        cover_image: numpy array，灰階圖片 (H×W) 或彩色圖片 (H×W×3)
        secret: 機密內容（字串或 PIL Image）
        secret_type: 'text' 或 'image'
        contact_key: 對象專屬密鑰（字串），用於加密
    
    返回:
        z_bits: Z 碼位元列表
        capacity: 圖片的總容量
        info: 額外資訊（機密內容的相關資訊）
    
    流程:
        1. 圖片預處理（彩色轉灰階、檢查尺寸）
        2. 計算容量並檢查
        3. 用 contact_key 打亂機密位元順序（新增！）
        4. 對每個 8×8 區塊進行嵌入
    
    格式:
        [1 bit 類型標記] + [機密內容]
        類型標記: 0 = 文字, 1 = 圖片
    
    安全機制:
        - Q 密鑰：保護每個區塊的「值」
        - Seed 打亂：保護機密的「位置」
        - 雙重保護：載體或對象錯誤都會變成完全馬賽克
    """
    cover_image = np.array(cover_image)
    
    # ========== 步驟 1：圖片預處理 ==========
    # 1.1 若為彩色圖片，轉成灰階
    if len(cover_image.shape) == 3:
        cover_image = (
            0.299 * cover_image[:, :, 0] + 
            0.587 * cover_image[:, :, 1] + 
            0.114 * cover_image[:, :, 2]
        ).astype(np.uint8)
    
    height, width = cover_image.shape
    
    # 1.2 檢查圖片大小是否為 8 的倍數
    if height % 8 != 0 or width % 8 != 0:
        raise ValueError(f"圖片大小必須是 8 的倍數！當前大小: {width}×{height}")
    
    # ========== 步驟 2：計算容量並檢查 ==========
    # 2.1 計算 8×8 區塊數量
    num_rows = height // BLOCK_SIZE
    num_cols = width // BLOCK_SIZE
    num_units = num_rows * num_cols
    
    # 2.2 計算容量
    capacity = num_units * TOTAL_AVERAGES_PER_UNIT
    
    # 2.3 將機密內容轉成二進位（加入類型標記）
    if secret_type == 'text':
        type_marker = [0]  # 0 = 文字
        content_bits = text_to_binary(secret)
        info = {'type': 'text', 'length': len(secret), 'bits': len(content_bits) + 1}
    else:
        type_marker = [1]  # 1 = 圖片
        content_bits, orig_size, mode = image_to_binary(secret, capacity - 1)  # 預留 1 bit 給類型標記
        info = {'type': 'image', 'size': orig_size, 'mode': mode, 'bits': len(content_bits) + 1}
    
    # 2.4 組合完整的 secret_bits
    secret_bits = type_marker + content_bits
    
    # 2.5 檢查容量是否足夠
    if len(secret_bits) > capacity:
        raise ValueError(
            f"機密內容太大！需要 {len(secret_bits)} bits，但容量只有 {capacity} bits"
        )
    
    # ========== 步驟 3：用 contact_key 打亂機密位元順序（新增！）==========
    # 這樣即使載體或對象錯誤，提取出來的位置也會全亂
    secret_bits = shuffle_bits(secret_bits, contact_key)
    
    # ========== 步驟 4：對每個 8×8 區塊進行嵌入 ==========
    z_bits = []
    secret_bit_index = 0
    finished = False
    
    for i in range(num_rows):
        if finished:
            break
        
        for j in range(num_cols):
            # 檢查是否所有 secret_bits 已處理完
            if secret_bit_index >= len(secret_bits):
                finished = True
                break
            
            # 4.1 提取這個 8×8 區塊
            start_row = i * BLOCK_SIZE
            end_row = start_row + BLOCK_SIZE
            start_col = j * BLOCK_SIZE
            end_col = start_col + BLOCK_SIZE
            block = cover_image[start_row:end_row, start_col:end_col]
            
            # 4.2 生成這個區塊專屬的排列密鑰 Q（加入 contact_key）
            Q = generate_Q_from_block(block, Q_LENGTH, contact_key=contact_key)
            
            # 4.3 計算 21 個多層次平均值
            averages_21 = calculate_hierarchical_averages(block)
            
            # 4.4 用 Q 重新排列 21 個平均值
            reordered_averages = apply_Q_three_rounds(averages_21, Q)
            
            # 4.5 提取排列後的 21 個 MSB
            msbs = get_msbs(reordered_averages)
            
            # 4.6 映射產生 Z 碼
            for k in range(TOTAL_AVERAGES_PER_UNIT):
                if secret_bit_index >= len(secret_bits):
                    finished = True
                    break
                
                secret_bit = secret_bits[secret_bit_index]
                msb = msbs[k]
                z_bit = map_to_z(secret_bit, msb)
                z_bits.append(z_bit)
                
                secret_bit_index += 1
    
    return z_bits, capacity, info
