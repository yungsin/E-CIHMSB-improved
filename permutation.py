
# 建立 permutation.py → 密鑰 Q 生成模組

import numpy as np

def generate_Q_from_block(block, q_length=7):
  """
  功能:
    從 8×8 區塊的第一行前 q_length 個像素生成排列密鑰 Q
  
  參數:
    block:numpy array，8×8 灰階區塊 或 8×8×3 彩色區塊
    q_length:Q 的長度，預設 7
  
  返回:
    Q:排列順序列表 (1-based 索引)
  
  原理:
    假設區塊第一行前 7 個是 [44, 61, 72, 58, 70, 79, 66]
    1. 找出數值由小到大的位置: 44(位置0) < 58(位置3) < 61(位置1) < ...
    2. 這個順序就是我們的 Q: [1, 4, 2, 7, 5, 3, 6] (轉成 1-based)
  """
  # 取出圖片
  block = np.array(block)

  # 判斷圖片類型並取第一行
  if len(block.shape) == 3:  # 彩色區塊
    # 使用標準灰階轉換公式
    # 綠色權重最高 (0.587)，紅色次之 (0.299)，藍色最低 (0.114)
    first_row = (0.299 * block[0, :, 0] + 0.587 * block[0, :, 1] + 0.114 * block[0, :, 2]).astype(np.uint8)
  else:  # 灰階區塊
    first_row = block[0, :]

  # 只取前 q_length 個像素
  first_row = first_row[:q_length]

  # 排序後得到每個數值在排序中的位置 (0-based) 
  sorted_indices = np.argsort(first_row)  # 取得按數值小到大排序後的原始位置

  # 轉換成 1-based 索引
  Q = (sorted_indices + 1).tolist()

  return Q

def apply_permutation(values, Q):
  """
  功能:
    使用 Q 重新排列一組值
  
  參數:
    values:要排列的值列表 (長度應等於 len(Q))
    Q:排列順序 (1-based 索引)
  
  返回:
    reordered:重新排列後的值列表
  
  舉例:
    values = [109, 101, 135, 65, 74, 137, 121]
    Q = [7, 1, 3, 5, 6, 2, 4]
    → reordered = [121, 109, 135, 74, 137, 101, 65]
  """
  if len(values) != len(Q):
    raise ValueError(f"值的數量 ({len(values)}) 必須等於 Q 的長度 ({len(Q)})")

  # 將 Q 轉換成 0-based 索引
  Q_zero_based = [q - 1 for q in Q]

  # 按 Q 的順序重新排列
  reordered = [values[i] for i in Q_zero_based]

  return reordered

def apply_Q_three_rounds(averages_21, Q):
  """
  功能:
    將 21 個平均值分成 3 輪，每輪使用相同的 Q 進行排列
  
  參數:
    averages_21:21 個平均值的列表
    Q:排列順序 (長度為 7 的列表)
  
  返回:
    reordered_all:重新排列後的 21 個平均值
  """
  if len(averages_21) != 21:
    raise ValueError(f"必須提供 21 個平均值，但收到 {len(averages_21)} 個")

  if len(Q) != 7:
    raise ValueError(f"Q 的長度必須是 7，但收到 {len(Q)} 個")

  # 分成3輪
  round1 = apply_permutation(averages_21[0:7], Q)
  round2 = apply_permutation(averages_21[7:14], Q)
  round3 = apply_permutation(averages_21[14:21], Q)

  # 合併結果
  reordered_all = round1 + round2 + round3

  return reordered_all
