# 数据可视化 Skill

## 描述

根据数据自动生成合适的可视化图表。

## 使用场景

- "把最近30天的GMV趋势用图表展示"
- "生成各地区GMV占比的饼图"
- "展示用户增长的折线图"

## 入口函数

`create_chart(data, chart_type='auto', config=None)`

## 参数

- `data`: 要可视化的数据
- `chart_type`: 图表类型 (auto/line/bar/pie/heatmap/map/table)
- `config`: 图表配置 (标题、颜色、尺寸等)

## 返回值

返回图表配置，包含：
- chart_type: 图表类型
- data: 图表数据
- layout: 图表布局配置
- file_path: 图片文件路径 (如果导出)
- interactive_html: 交互式HTML (Plotly)

## 依赖

- plotly>=5.24.0
- matplotlib>=3.7.0
- kaleido>=0.2.1
- anthropic>=0.39.0

## 配置

```yaml
chart_types:
  line:
    best_for: 时间序列、趋势展示
    max_data_points: 1000
  bar:
    best_for: 数据对比、排名展示
    max_categories: 20
  pie:
    best_for: 占比分析、部分展示
    max_categories: 10
  heatmap:
    best_for: 多维数据展示
  map:
    best_for: 地域分布展示
  table:
    best_for: 详细数据展示
auto_select: true  # 自动选择最适合的图表类型
```
