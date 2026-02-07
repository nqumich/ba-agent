// Metrics dashboard module

import * as api from './api.js';

let charts = {};

// Load metrics for a conversation
export async function loadMetrics(conversationId) {
    try {
        // Get performance summary
        const perfSummary = await api.getPerformanceSummary(conversationId);

        // Update summary cards
        updateSummaryCards(perfSummary);

        // Render charts
        renderTokenChart(perfSummary);
        renderDurationChart(perfSummary);
        renderToolsChart(perfSummary);

    } catch (error) {
        console.error('Failed to load metrics:', error);
        showMetricsError();
    }
}

// Update summary cards
function updateSummaryCards(perf) {
    document.getElementById('metric-duration').textContent =
        formatNumber(perf.total_duration_ms.toFixed(0));

    document.getElementById('metric-tokens').textContent =
        formatNumber(perf.total_tokens);

    document.getElementById('metric-cost').textContent =
        perf.estimated_cost_usd.toFixed(4);

    document.getElementById('metric-tools').textContent =
        perf.tool_calls_count.toString();
}

// Render token distribution chart
function renderTokenChart(perf) {
    const container = document.getElementById('token-chart');

    if (charts.token) {
        charts.token.dispose();
    }

    charts.token = echarts.init(container);

    const option = {
        tooltip: {
            trigger: 'item',
            formatter: '{b}: {c} ({d}%)'
        },
        series: [{
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            label: {
                show: false,
                position: 'center'
            },
            emphasis: {
                label: {
                    show: true,
                    fontSize: 14,
                    fontWeight: 'bold'
                }
            },
            labelLine: {
                show: false
            },
            data: [
                {
                    value: perf.total_tokens || 0,
                    name: 'Total Tokens',
                    itemStyle: { color: '#3b82f6' }
                }
            ]
        }],
        backgroundColor: 'transparent'
    };

    charts.token.setOption(option);
}

// Render duration breakdown chart
function renderDurationChart(perf) {
    const container = document.getElementById('duration-chart');

    if (charts.duration) {
        charts.duration.dispose();
    }

    charts.duration = echarts.init(container);

    const option = {
        tooltip: {
            trigger: 'item',
            formatter: '{b}: {c}ms ({d}%)'
        },
        series: [{
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            label: {
                show: false,
                position: 'center'
            },
            emphasis: {
                label: {
                    show: true,
                    fontSize: 14,
                    fontWeight: 'bold'
                }
            },
            labelLine: {
                show: false
            },
            data: [
                {
                    value: perf.llm_duration_ms,
                    name: 'LLM',
                    itemStyle: { color: '#8b5cf6' }
                },
                {
                    value: perf.tool_duration_ms,
                    name: 'Tools',
                    itemStyle: { color: '#06b6d4' }
                },
                {
                    value: perf.other_duration_ms,
                    name: 'Other',
                    itemStyle: { color: '#64748b' }
                }
            ].filter(d => d.value > 0)
        }],
        backgroundColor: 'transparent'
    };

    charts.duration.setOption(option);
}

// Render tools statistics chart
function renderToolsChart(perf) {
    const container = document.getElementById('tools-chart');

    if (charts.tools) {
        charts.tools.dispose();
    }

    charts.tools = echarts.init(container);

    // For now, just show a simple gauge for tool calls
    const option = {
        series: [{
            type: 'gauge',
            startAngle: 180,
            endAngle: 0,
            min: 0,
            max: Math.max(perf.tool_calls_count, 10),
            splitNumber: 5,
            axisLine: {
                lineStyle: {
                    width: 8,
                    color: [
                        [0.25, '#10b981'],
                        [0.5, '#3b82f6'],
                        [0.75, '#f59e0b'],
                        [1, '#ef4444']
                    ]
                }
            },
            pointer: {
                icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
                length: 12,
                width: 20,
                offsetCenter: [0, '-60%'],
                itemStyle: { color: 'auto' }
            },
            axisTick: { length: 12, lineStyle: { color: 'auto', width: 2 } },
            splitLine: { length: 20, lineStyle: { color: 'auto', width: 5 } },
            axisLabel: { color: '#464646', fontSize: 10, distance: -60 },
            title: {
                offsetCenter: [0, '-20%'],
                fontSize: 20
            },
            detail: {
                fontSize: 30,
                offsetCenter: [0, '0%'],
                valueAnimation: true,
                formatter: function (value) { return Math.round(value); },
                color: 'auto'
            },
            data: [{ value: perf.tool_calls_count, name: 'Tools' }]
        }],
        backgroundColor: 'transparent'
    };

    charts.tools.setOption(option);
}

// Format number with commas
function formatNumber(num) {
    if (!num) return '0';
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// Show error state
function showMetricsError() {
    document.getElementById('metric-duration').textContent = '-';
    document.getElementById('metric-tokens').textContent = '-';
    document.getElementById('metric-cost').textContent = '-';
    document.getElementById('metric-tools').textContent = '-';
}

// Resize charts on window resize
window.addEventListener('resize', () => {
    Object.values(charts).forEach(chart => chart.resize());
});
