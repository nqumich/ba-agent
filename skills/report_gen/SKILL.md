# 报告生成 Skill

## 描述

自动生成业务分析报告，支持日报、周报、月报。

## 使用场景

- "帮我生成本周的业务周报"
- "生成GMV月度分析报告"
- "自动生成每日业务简报"

## 入口函数

`generate(report_type, data, format='markdown', template=None)`

## 参数

- `report_type`: 报告类型 (daily/weekly/monthly)
- `data`: 业务数据
- `format`: 输出格式 (pdf/docx/xlsx/markdown)
- `template`: 自定义模板 (可选)

## 返回值

返回生成的报告，包含：
- title: 报告标题
- period: 报告周期
- sections: 报告章节内容
- metrics: 核心指标汇总
- charts: 图表配置
- file_path: 报告文件路径

## 依赖

- python-docx>=1.1.0
- reportlab>=4.0.0
- matplotlib>=3.7.0
- anthropic>=0.39.0

## 配置

```yaml
templates:
  daily:
    sections:
      - 核心指标概览
      - 关键异动提醒
      - 今日重点关注
      - 明日建议
  weekly:
    sections:
      - 本周经营概况
      - 核心指标趋势
      - 异动分析
      - 下周策略建议
  monthly:
    sections:
      - 月度经营总结
      - 关键指标分析
      - 异动复盘
      - 下月规划
formats:
  - pdf:     PDF格式报告
  - docx:    Word格式报告
  - xlsx:    Excel格式报告（含图表）
  - markdown: Markdown格式报告
```
