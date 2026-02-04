---
name: attribution
display_name: "归因分析"
description: "分析指标变化的归因因素，包括维度下钻、事件归因、外部因素分析。"
version: "1.0.0"
category: "Analysis"
author: "BA-Agent Team"
entrypoint: "skills/attribution/main.py"
function: "analyze"
requirements:
  - "pandas>=2.0.0"
  - "numpy>=1.24.0"
  - "anthropic>=0.39.0"
config:
  dimensions:
    - region      # 地区维度分析
    - category    # 品类维度分析
    - channel     # 渠道维度分析
    - user_type   # 用户分群分析
  attribution_methods:
    - contribution  # 贡献度分析
    - correlation   # 相关性分析
    - sequence      # 序列分析
  external_factors:
    - holiday      # 节假日因素
    - weather      # 天气因素
    - competitor   # 竞品动作
tags:
  - "attribution"
  - "analysis"
  - "dimension"
  - "factors"
examples:
  - "为什么GMV增长了？"
  - "分析本周GMV下降的原因"
  - "华东地区GMV增长的主要驱动因素是什么？"
---

# 归因分析 Skill

## 描述

分析指标变化的归因因素，包括维度下钻、事件归因、外部因素分析。

## 使用场景

- "为什么GMV增长了？"
- "分析本周GMV下降的原因"
- "华东地区GMV增长的主要驱动因素是什么？"

## 入口函数

`analyze(data, target_dimension, attribution_method='contribution')`

## 参数

- `data`: 包含维度和指标数据的DataFrame
- `target_dimension`: 目标分析维度 (region/category/channel/user_type)
- `attribution_method`: 归因方法，可选 'contribution' (贡献度), 'correlation' (相关性), 'sequence' (序列)

## 返回值

返回归因分析结果，包含：
- primary_factors: 主要影响因素列表
- contribution_scores: 各维度贡献度分数
- insights: 归因洞察分析
- recommendations: 建议措施
