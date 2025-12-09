# extract.py → 提取模組（支援文字和圖片，含對象密鑰）

import numpy as np

from config import Q_LENGTH, TOTAL_AVERAGES_PER_UNIT, BLOCK_SIZE
from permutation import generate_Q_from_block, apply_Q_three_rounds
from image_processing import calculate_hierarchical_averages
from binary_operations import get_msbs
from mapping import map_from_z
from secret_encoding import binary_to_text, binary_to_image


def unshuffle_bits(bits, key):
    """
    功能:
        用密鑰還原位元順序（shuffle_bits 的逆操作）
    
    參數:
        bits: 打亂後的位元列表
        key: 密鑰字串（必須和嵌入時用的相同）
    
    返回:
        還原順序後的位元列表
    
    原理:
        用相同的 key 生成相同的打亂順序
        然後用 argsort 找到還原順序
    """
    if not key or len(bits) == 0:
        return bits
    
    seed = hash(key) % 2147483647
    np.random.seed(seed)
    order = np.random.permutation(len(bits))
    restore_order = np.argsort(order)
    
    return [bits[i] for i in restore_order]


def extract_secret(cover_image, z_bits, secret_type='text', contact_key=None):
    """
    功能:
        從 Z 碼和無載體圖片提取機密內容
    
    參數:
        cover_image: numpy array，灰階圖片 (H×W) 或彩色圖片 (H×W×3)
        z_bits: Z 碼位元列表
        secret_type: 'text' 或 'image'
        contact_key: 對象專屬密鑰（字串），用於解密
    
    返回:
        secret: 還原的機密內容（字串或 PIL Image）
        info: 額外資訊
    
    格式:
        [1 bit 類型標記] + [打亂後的機密內容]
        類型標記不參與打亂
    """
    cover_image = np.array(cover_image)
    
    # ========== 步驟 1：圖片預處理 ==========
    if len(cover_image.shape) == 3:
        cover_image = (
            0.299 * cover_image[:, :, 0] + 
            0.587 * cover_image[:, :, 1] + 
            0.114 * cover_image[:, :, 2]
        ).astype(np.uint8)
    
    height, width = cover_image.shape
    
    if height % 8 != 0 or width % 8 != 0:
        raise ValueError(f"圖片大小必須是 8 的倍數！當前大小: {width}×{height}")
    
    # ========== 步驟 2：計算 8×8 區塊數量 ==========
    num_rows = height // BLOCK_SIZE
    num_cols = width // BLOCK_SIZE
    
    # ========== 步驟 3：對每個 8×8 區塊進行提取 ==========
    extracted_bits = []
    z_bit_index = 0
    finished = False
    
    for i in range(num_rows):
        if finished:
            break
        
        for j in range(num_cols):
            if z_bit_index >= len(z_bits):
                finished = True
                break
            
            start_row = i * BLOCK_SIZE
            end_row = start_row + BLOCK_SIZE
            start_col = j * BLOCK_SIZE
            end_col = start_col + BLOCK_SIZE
            block = cover_image[start_row:end_row, start_col:end_col]
            
            Q = generate_Q_from_block(block, Q_LENGTH, contact_key=contact_key)
            averages_21 = calculate_hierarchical_averages(block)
            reordered_averages = apply_Q_three_rounds(averages_21, Q)
            msbs = get_msbs(reordered_averages)
            
            for k in range(TOTAL_AVERAGES_PER_UNIT):
                if z_bit_index >= len(z_bits):
                    finished = True
                    break
                
                z_bit = z_bits[z_bit_index]
                msb = msbs[k]
                secret_bit = map_from_z(z_bit, msb)
                extracted_bits.append(secret_bit)
                
                z_bit_index += 1
    
    # ========== 步驟 4：分離類型標記和內容 ==========
    if len(extracted_bits) < 1:
        raise ValueError("提取的位元數不足，無法讀取類型標記")
    
    type_marker = extracted_bits[0]  # 類型標記不參與打亂
    shuffled_content = extracted_bits[1:]  # 剩餘的是打亂後的內容
    
    # ========== 步驟 5：只對內容進行還原 ==========
    content_bits = unshuffle_bits(shuffled_content, contact_key)
    
    # ========== 步驟 6：解碼內容 ==========
    if secret_type == 'text':
        secret = binary_to_text(content_bits)
        info = {
            'type': 'text', 
            'length': len(secret),
            'type_marker': type_marker,
            'total_bits': len(extracted_bits),
            'content_bits': len(content_bits)
        }
    else:
        secret, orig_size, is_color = binary_to_image(content_bits)
        info = {
            'type': 'image', 
            'size': orig_size, 
            'is_color': is_color,
            'type_marker': type_marker,
            'total_bits': len(extracted_bits),
            'content_bits': len(content_bits)
        }
    
    return secret, info


def detect_and_extract(cover_image, z_bits, contact_key=None):
    """
    功能:
        自動偵測機密類型並提取
    
    參數:
        cover_image: 無載體圖片
        z_bits: Z 碼
        contact_key: 對象專屬密鑰（字串），用於解密
    
    返回:
        secret: 機密內容
        secret_type: 'text' 或 'image'
        info: 額外資訊
    
    流程:
        1. 先提取所有 bits
        2. 讀取第 1 bit 類型標記（不參與打亂）
        3. 對剩餘內容用 contact_key 還原順序
        4. 根據類型標記解碼
    """
    cover_image = np.array(cover_image)
    
    if len(cover_image.shape) == 3:
        cover_image = (
            0.299 * cover_image[:, :, 0] + 
            0.587 * cover_image[:, :, 1] + 
            0.114 * cover_image[:, :, 2]
        ).astype(np.uint8)
    
    height, width = cover_image.shape
    num_rows = height // BLOCK_SIZE
    num_cols = width // BLOCK_SIZE
    
    extracted_bits = []
    z_bit_index = 0
    finished = False
    
    for i in range(num_rows):
        if finished:
            break
        for j in range(num_cols):
            if z_bit_index >= len(z_bits):
                finished = True
                break
            
            block = cover_image[i*BLOCK_SIZE:(i+1)*BLOCK_SIZE, j*BLOCK_SIZE:(j+1)*BLOCK_SIZE]
            Q = generate_Q_from_block(block, Q_LENGTH, contact_key=contact_key)
            averages_21 = calculate_hierarchical_averages(block)
            reordered = apply_Q_three_rounds(averages_21, Q)
            msbs = get_msbs(reordered)
            
            for k in range(TOTAL_AVERAGES_PER_UNIT):
                if z_bit_index >= len(z_bits):
                    finished = True
                    break
                extracted_bits.append(map_from_z(z_bits[z_bit_index], msbs[k]))
                z_bit_index += 1
    
    # 檢查是否有足夠的 bits
    if len(extracted_bits) < 1:
        raise ValueError("Z 碼太短，無法提取類型標記")
    
    # ========== 分離類型標記和內容 ==========
    type_marker = extracted_bits[0]  # 類型標記不參與打亂
    shuffled_content = extracted_bits[1:]  # 打亂後的內容
    
    # ========== 只對內容進行還原 ==========
    content_bits = unshuffle_bits(shuffled_content, contact_key)
    
    # ========== 根據類型標記解碼 ==========
    if type_marker == 0:
        # 文字類型
        try:
            text = binary_to_text(content_bits)
            return text, 'text', {
                'type': 'text', 
                'length': len(text),
                'type_marker': type_marker,
                'total_bits': len(extracted_bits),
                'content_bits': len(content_bits)
            }
        except Exception as e:
            raise ValueError(f"文字解碼失敗: {e}")
    else:
        # 圖片類型
        try:
            img, orig_size, is_color = binary_to_image(content_bits)
            if img is not None:
                return img, 'image', {
                    'type': 'image', 
                    'size': orig_size, 
                    'is_color': is_color,
                    'type_marker': type_marker,
                    'total_bits': len(extracted_bits),
                    'content_bits': len(content_bits)
                }
            else:
                raise ValueError("圖片解碼返回 None")
        except Exception as e:
            raise ValueError(f"圖片解碼失敗: {e}")
