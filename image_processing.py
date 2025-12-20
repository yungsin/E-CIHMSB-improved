# 建立 image_processing.py → 圖像處理模組
# 多層次平均值計算、圖像預處理

import numpy as np

from config import BLOCK_SIZE

# ==================== 圖像預處理 ====================
def convert_to_grayscale(image):
    """
    功能:
        將彩色圖像轉成灰階（若已是灰階則不處理）
    
    參數:
        image: numpy array，灰階 (H×W) 或彩色 (H×W×3)
    
    返回:
        gray_image: numpy array，灰階圖像 (H×W)
    
    原理:
        使用標準權重: Gray = 0.299×R + 0.587×G + 0.114×B
    """
    image = np.array(image)
    
    if len(image.shape) == 3:  # 彩色圖像
        gray_image = (
            0.299 * image[:, :, 0] +  # R × 0.299
            0.587 * image[:, :, 1] +  # G × 0.587
            0.114 * image[:, :, 2]    # B × 0.114
        ).astype(np.uint8)
        return gray_image
    
    return image  # 已是灰階，直接返回

def validate_image_size(image):
    """
    功能:
        檢查圖像尺寸是否為 8 的倍數
    
    參數:
        image: numpy array，圖像
    
    返回:
        height, width: 圖像的高度和寬度
    
    例外:
        若尺寸不是 8 的倍數，拋出 ValueError
    """
    height, width = image.shape[:2]
    
    if height % BLOCK_SIZE != 0 or width % BLOCK_SIZE != 0:
        raise ValueError(f"圖像大小必須是 {BLOCK_SIZE} 的倍數！當前大小: {width}×{height}")
    
    return height, width

# ==================== 多層次平均值計算 ====================
def calculate_hierarchical_averages(block_8x8):
    """
    功能:
        計算一個 8×8 區塊的多層次平均值（三層結構）
    
    參數:
        block_8x8: 8×8 的 numpy array
    
    返回:
        averages_21: 21 個平均值的列表
            - 前 16 個: 第一層（16 個 2×2 區塊的平均值）
            - 中 4 個: 第二層（4 個分組的平均值）
            - 最後 1 個: 第三層（1 個總平均值）
    
    原理:
        第一層: 將 8×8 區塊切成 16 個 2×2 子區塊，計算每個子區塊平均值
        第二層: 將第一層的 16 個平均值排成 4×4，分成 4 組（每組 2×2），計算每組平均值
        第三層: 將第二層的 4 個平均值計算總平均
    """
    block_8x8 = np.array(block_8x8)
    
    # ========== 第一層: 16 個 2×2 區塊 ==========
    # 把 8×8 reshape 成 (4, 2, 4, 2)，對 axis 1 和 3 取平均
    reshaped = block_8x8.reshape(4, 2, 4, 2)
    layer1 = reshaped.mean(axis=(1, 3))  # 結果: 4×4
    layer1_averages = layer1.flatten().astype(int).tolist()
    
    # ========== 第二層: 4 個分組（對第一層的 16 個平均值重新分組）==========
    # 把 4×4 reshape 成 (2, 2, 2, 2)，對 axis 1 和 3 取平均
    layer1_2x2 = layer1.reshape(2, 2, 2, 2)
    layer2 = layer1_2x2.mean(axis=(1, 3))  # 結果: 2×2
    layer2_averages = layer2.flatten().astype(int).tolist()
    
    # ========== 第三層: 1 個總平均（對第二層的 4 個平均值計算平均）==========
    layer3_average = int(layer2.mean())
    
    # ========== 合併三層結果 ==========
    averages_21 = layer1_averages + layer2_averages + [layer3_average]
    
    return averages_21
