// API wrapper for monitoring endpoints

const MONITORING_API_BASE = '/api/v1/monitoring';

// Get auth token from localStorage
function getAuthToken() {
    return localStorage.getItem('auth_token');
}

// Make authenticated API request
async function monitoringApiRequest(endpoint, options = {}) {
    const token = getAuthToken();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${MONITORING_API_BASE}${endpoint}`, {
        ...options,
        headers
    });

    if (!response.ok) {
        throw new Error(`API request failed: ${response.status} ${response.statusText}`);
    }

    return response.json();
}

// Get list of conversations with traces
export async function getConversations(filters = {}) {
    const params = new URLSearchParams();
    if (filters.sessionId) params.append('session_id', filters.sessionId);
    if (filters.limit) params.append('limit', filters.limit);

    const queryString = params.toString();
    return monitoringApiRequest(`/conversations${queryString ? `?${queryString}` : ''}`);
}

// Get trace for a specific conversation
export async function getTrace(conversationId) {
    return monitoringApiRequest(`/traces/${conversationId}`);
}

// Get Mermaid visualization for a trace
export async function getTraceVisualization(conversationId, format = 'mermaid') {
    const params = new URLSearchParams({ format });
    return monitoringApiRequest(`/traces/${conversationId}/visualize?${params.toString()}`);
}

// Get metrics
export async function getMetrics(filters = {}) {
    const params = new URLSearchParams();
    if (filters.conversationId) params.append('conversation_id', filters.conversationId);
    if (filters.sessionId) params.append('session_id', filters.sessionId);
    if (filters.startTime) params.append('start_time', filters.startTime);
    if (filters.endTime) params.append('end_time', filters.endTime);

    const queryString = params.toString();
    return monitoringApiRequest(`/metrics${queryString ? `?${queryString}` : ''}`);
}

// Get performance summary for a conversation
export async function getPerformanceSummary(conversationId) {
    return monitoringApiRequest(`/performance/${conversationId}`);
}

// Get all spans for a conversation
export async function getSpans(conversationId) {
    return monitoringApiRequest(`/spans/${conversationId}`);
}

// Get recent activity
export async function getRecentActivity(hours = 24) {
    return monitoringApiRequest(`/recent?hours=${hours}`);
}

// Export format
export default {
    getConversations,
    getTrace,
    getTraceVisualization,
    getMetrics,
    getPerformanceSummary,
    getSpans,
    getRecentActivity,
};
