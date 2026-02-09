// Conversation list management

import * as api from './api.js';

let conversations = [];
let filteredConversations = [];
let selectedConversationId = null;

// Initialize conversation list
export async function initConversationList() {
    await loadConversations();
    setupFilters();
}

// Load conversations from API
async function loadConversations() {
    const listElement = document.getElementById('conversation-list');
    listElement.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const data = await api.getConversations({ limit: 100 });
        conversations = data;
        applyFilters();
    } catch (error) {
        console.error('Failed to load conversations:', error);
        listElement.innerHTML = '<div class="text-error">加载失败</div>';
    }
}

// Refresh conversations
export async function refreshConversations() {
    await loadConversations();
}

// Setup filter event listeners
function setupFilters() {
    // Time filter
    document.getElementById('time-filter').addEventListener('change', applyFilters);

    // Status filter
    document.getElementById('status-filter').addEventListener('change', applyFilters);

    // Search input
    document.getElementById('search-input').addEventListener('keyup', applyFilters);
}

// Apply filters to conversation list
function applyFilters() {
    const timeFilter = document.getElementById('time-filter').value;
    const statusFilter = document.getElementById('status-filter').value;
    const searchQuery = document.getElementById('search-input').value.toLowerCase();

    const now = Date.now() / 1000;
    const timeThresholds = {
        today: now - 24 * 3600,
        week: now - 7 * 24 * 3600,
        month: now - 30 * 24 * 3600,
        all: 0
    };

    filteredConversations = conversations.filter(conv => {
        // Time filter
        if (timeFilter !== 'all' && conv.start_time < timeThresholds[timeFilter]) {
            return false;
        }

        // Status filter (would need status from trace data)
        // For now, we'll just check if duration exists
        if (statusFilter === 'error' && conv.total_duration_ms > 0) {
            return false; // Assume all with duration are success for now
        }

        // Search filter
        if (searchQuery && !conv.conversation_id.toLowerCase().includes(searchQuery)) {
            return false;
        }

        return true;
    });

    renderConversationList();
}

// Render conversation list
function renderConversationList() {
    const listElement = document.getElementById('conversation-list');

    if (filteredConversations.length === 0) {
        listElement.innerHTML = '<div class="text-muted" style="text-align: center; padding: 20px;">没有找到匹配的对话</div>';
        return;
    }

    listElement.innerHTML = filteredConversations.map(conv => {
        const isSelected = conv.conversation_id === selectedConversationId;
        const status = conv.total_duration_ms > 0 ? 'success' : 'error';
        const duration = formatDuration(conv.total_duration_ms);
        const time = formatTimestamp(conv.start_time);

        return `
            <div class="conversation-item ${isSelected ? 'active' : ''}"
                 onclick="selectConversation('${conv.conversation_id}')">
                <div class="conversation-item-header">
                    <span class="conversation-id" title="${conv.conversation_id}">${conv.conversation_id}</span>
                    <span class="conversation-status ${status}">${status}</span>
                </div>
                <div class="conversation-meta">
                    <span>${duration}</span>
                    <span>${conv.total_tokens} tokens</span>
                    <span>${conv.tool_calls} tools</span>
                </div>
            </div>
        `;
    }).join('');
}

// Select a conversation
export async function selectConversation(conversationId) {
    selectedConversationId = conversationId;

    // Update active state in list
    renderConversationList();

    // Load trace details
    await loadTraceDetails(conversationId);
}

// Load trace details for a conversation
async function loadTraceDetails(conversationId) {
    // Show loading state
    document.getElementById('trace-empty').style.display = 'none';
    document.getElementById('trace-details').style.display = 'block';

    // Load trace data
    const traceModule = await import('./trace-viewer.js');
    await traceModule.loadTrace(conversationId);

    // Load metrics
    const metricsModule = await import('./metrics-dashboard.js');
    await metricsModule.loadMetrics(conversationId);
}

// Format duration in ms to human readable
function formatDuration(ms) {
    if (!ms) return '-';
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
}

// Format timestamp to readable date
function formatTimestamp(ts) {
    const date = new Date(ts * 1000);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return '刚刚';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`;

    return date.toLocaleDateString('zh-CN');
}

// Export selected conversation ID
export function getSelectedConversationId() {
    return selectedConversationId;
}
