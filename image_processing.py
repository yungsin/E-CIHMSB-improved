
# 建立 image_processing.py → 圖片處理模組

import numpy as np

def calculate_hierarchical_averages(block_8x8):
  """
  功能:
    計算一個 8×8 區塊的多層次平均值（三層結構）

  參數:
    block_8x8: 8×8 的 numpy array

  返回:
    averages_21: 21 個平均值的列表
      - 前 16 個: 第一層 (16 個 2×2 區塊的平均值)
      - 中 4 個: 第二層 (4 個分組的平均值)
      - 最後 1 個: 第三層 (1 個總平均值)

  原理:
    第一層: 將 8×8 圖片切成 16 個 2×2 區塊，計算每個區塊平均值
    第二層: 將第一層的 16 個平均值排成 4×4，分成 4 組 (每組 2×2)，計算每組平均值
    第三層: 將第二層的 4 個平均值計算總平均
  """
  block_8x8 = np.array(block_8x8)

  # ========== 第一層: 16 個 2×2 區塊 ==========
  layer1_averages = []

  # 8×8 切成 4×4 = 16 個 2×2 區塊
  for i in range(4):  # 4 行
    for j in range(4):  # 4 列
      # 計算 2×2 區塊的範圍
      start_row = i * 2
      end_row = start_row + 2
      start_col = j * 2
      end_col = start_col + 2

      # 提取 2×2 區塊
      block_2x2 = block_8x8[start_row:end_row, start_col:end_col]

      # 計算平均值
      avg = int(np.mean(block_2x2))
      layer1_averages.append(avg)

  # ========== 第二層: 4 個分組 (對第一層的 16 個平均值重新分組) ==========
  # 將第一層的 16 個值重新組織成 4×4 矩陣
  layer1_matrix = np.array(layer1_averages).reshape(4, 4)

  layer2_averages = []

  # 將 4×4 矩陣分成 4 個 2×2 區塊
  for i in range(2):  # 2 行
    for j in range(2):  # 2 列
      # 從 layer1_matrix 中取出 2×2 區塊
      start_row = i * 2
      end_row = start_row + 2
      start_col = j * 2
      end_col = start_col + 2

      # 提取 2×2 區塊
      group_values = layer1_matrix[start_row:end_row, start_col:end_col]

      # 計算平均值
      avg = int(np.mean(group_values))
      layer2_averages.append(avg)

  # ========== 第三層: 1 個 8×8 整體 (對第二層的 4 個平均值計算總平均) ==========
  layer3_average = int(np.mean(layer2_averages))

  # ========== 合併三層結果 ==========
  averages_21 = layer1_averages + layer2_averages + [layer3_average]

  return averages_21

def process_image_multilayer(image):
  """
  功能:
    處理整張圖片，計算所有 8×8 區塊的多層次平均值

  參數:
    image: numpy array，灰階圖片（H×W）或彩色圖片（H×W×3）

  返回:
    all_averages: 所有 8×8 區塊的平均值列表
                  結構: [[區塊1 的 21 個平均值], [區塊2 的 21 個平均值], ...]
    num_units: 8×8 區塊的數量

  範例:
    512×512 圖片:
    - 8×8 區塊數量: (512÷8)×(512÷8) = 64×64 = 4096 個
    - 每個區塊: 21 個平均值
    - 總共: 4096×21 = 86,016 個平均值
  """
  image = np.array(image)

  # 判斷圖片類型，若為彩色則轉成灰階
  if len(image.shape) == 3:  # 彩色圖片
    # 使用標準灰階轉換公式
    # 綠色權重最高 (0.587)，紅色次之 (0.299)，藍色最低 (0.114)
    image = (0.299 * image[:, :, 0] + 0.587 * image[:, :, 1] + 0.114 * image[:, :, 2]).astype(np.uint8)

  height, width = image.shape

  # 檢查圖片大小是否為 8 的倍數
  if height % 8 != 0 or width % 8 != 0:
    raise ValueError(f"圖片大小必須是 8 的倍數！當前大小: {width}×{height}")

  # 計算有多少個 8×8 區塊
  num_rows = height // 8
  num_cols = width // 8
  num_units = num_rows * num_cols

  all_averages = []

  # 遍歷每個 8×8 區塊
  for i in range(num_rows):
    for j in range(num_cols):
      # 提取 8×8 區塊
      start_row = i * 8
      end_row = start_row + 8
      start_col = j * 8
      end_col = start_col + 8

      block_8x8 = image[start_row:end_row, start_col:end_col]

      # 計算這個 8×8 區塊的 21 個平均值
      averages_21 = calculate_hierarchical_averages(block_8x8)

      all_averages.append(averages_21)

  return all_averages, num_units
