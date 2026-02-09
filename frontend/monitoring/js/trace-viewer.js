// Trace viewer module

import * as api from './api.js';

let currentTrace = null;

// Load trace for a conversation
export async function loadTrace(conversationId) {
    try {
        // Get trace visualization (Mermaid)
        const vizData = await api.getTraceVisualization(conversationId, 'mermaid');

        // Update header info
        updateTraceHeader(vizData);

        // Render Mermaid flowchart
        renderFlowchart(vizData.mermaid);

        // Get and render spans
        const spansData = await api.getSpans(conversationId);
        renderSpansTable(spansData.spans);

        currentTrace = vizData;
    } catch (error) {
        console.error('Failed to load trace:', error);
        showError('无法加载追踪数据');
    }
}

// Update trace header information
function updateTraceHeader(traceData) {
    const rootSpan = traceData.trace?.root_span || traceData.root_span;

    document.getElementById('trace-conversation-id').textContent =
        traceData.conversation_id || 'Unknown';

    document.getElementById('trace-session-id').textContent =
        `Session: ${traceData.session_id || rootSpan?.attributes?.session_id || '-'}`;

    const duration = rootSpan?.duration_ms || traceData.total_duration_ms;
    document.getElementById('trace-duration').textContent =
        `Duration: ${formatDuration(duration)}`;

    const status = rootSpan?.status || 'unknown';
    const statusElement = document.getElementById('trace-status');
    statusElement.textContent = `Status: ${status}`;
    statusElement.className = status === 'success' ? 'text-success' :
                           status === 'error' ? 'text-error' : 'text-muted';
}

// Render Mermaid flowchart
function renderFlowchart(mermaidCode) {
    const container = document.getElementById('flowchart');
    container.textContent = mermaidCode;

    // Initialize Mermaid
    mermaid.init(undefined, container);
}

// Render spans table
function renderSpansTable(spans) {
    const tbody = document.getElementById('spans-tbody');

    if (!spans || spans.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-muted">暂无数据</td></tr>';
        return;
    }

    tbody.innerHTML = spans.map(span => {
        const typeClass = span.span_type || 'unknown';
        const statusIcon = span.status === 'success' ? '✓' :
                          span.status === 'error' ? '✗' : '○';

        return `
            <tr>
                <td><span class="span-badge ${typeClass}">${span.span_type}</span></td>
                <td>${span.name}</td>
                <td>${formatDuration(span.duration_ms)}</td>
                <td><span class="span-status ${span.status}"></span>${statusIcon}</td>
                <td>
                    <button class="btn-icon" onclick="showSpanDetails('${span.span_id}')" title="查看详情">
                        ℹ️
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// Show span details (could be expanded to show modal)
function showSpanDetails(spanId) {
    const span = currentTrace?.trace?.root_span;
    if (!span) return;

    // Find span in hierarchy
    const findSpan = (s, id) => {
        if (s.span_id === id) return s;
        for (const child of s.children || []) {
            const found = findSpan(child, id);
            if (found) return found;
        }
        return null;
    };

    const targetSpan = findSpan(span, spanId);
    if (!targetSpan) return;

    // Show alert with details (could be replaced with modal)
    const details = {
        'Span ID': targetSpan.span_id,
        'Name': targetSpan.name,
        'Type': targetSpan.span_type,
        'Duration': `${targetSpan.duration_ms?.toFixed(2)}ms`,
        'Status': targetSpan.status,
        'Events': targetSpan.events?.length || 0,
        'Attributes': JSON.stringify(targetSpan.attributes, null, 2)
    };

    alert(JSON.stringify(details, null, 2));
}

// Export trace
export async function exportTrace(format) {
    const conversationId = document.getElementById('trace-conversation-id').textContent;
    if (!conversationId || conversationId === 'Unknown') return;

    try {
        let content, filename, mimeType;

        if (format === 'json') {
            const trace = await api.getTrace(conversationId);
            content = JSON.stringify(trace, null, 2);
            filename = `trace_${conversationId}.json`;
            mimeType = 'application/json';
        } else if (format === 'mermaid') {
            const viz = await api.getTraceVisualization(conversationId, 'mermaid');
            content = viz.mermaid;
            filename = `trace_${conversationId}.mmd`;
            mimeType = 'text/plain';
        }

        // Create download link
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Failed to export trace:', error);
        alert('导出失败');
    }
}

// Format duration
function formatDuration(ms) {
    if (!ms) return '-';
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
}

// Show error message
function showError(message) {
    document.getElementById('trace-empty').style.display = 'flex';
    document.getElementById('trace-details').style.display = 'none';
    document.getElementById('trace-empty').querySelector('h3').textContent = message;
}

// Make exportTrace available globally
window.exportTrace = exportTrace;
window.showSpanDetails = showSpanDetails;
