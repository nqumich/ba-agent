# 异动检测分析 Skill

## 描述

检测数据中的异常波动并分析可能原因。支持统计方法（3-sigma）、历史对比（同比/环比）、AI智能识别。

## 使用场景

- "今天GMV有什么异常？"
- "检测最近7天的异常波动"
- "GMV突然下降是什么原因？"

## 入口函数

`detect(data, method='statistical', threshold=2.0)`

## 参数

- `data`: 包含时间序列数据的DataFrame，必须有date列和value列
- `method`: 检测方法，可选 'statistical' (3-sigma), 'historical' (同比/环比), 'ai' (AI智能识别)
- `threshold`: 异常阈值，统计检测的标准差倍数，默认2.0

## 返回值

返回异动检测结果列表，每个异动包含：
- date: 异常日期
- value: 异常值
- type: 异常类型 (上升/下降)
- severity: 异常程度 (低/中/高)
- reason: 可能原因分析

## 依赖

- pandas>=2.0.0
- numpy>=1.24.0
- scipy>=1.10.0
- anthropic>=0.39.0

## 配置

```yaml
methods:
  - statistical  # 基于3-sigma的统计检测
  - historical   # 同比/环比历史对比
  - ai          # 使用Claude AI智能识别
threshold: 2.0        # 统计检测的标准差倍数
min_data_points: 7    # 最小数据点数
```
