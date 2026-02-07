// BA-Agent Monitoring Dashboard - Main Application

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

// Initialize application
async function initApp() {
    // Check authentication
    const authToken = localStorage.getItem('auth_token');
    if (!authToken) {
        // Redirect to login page
        window.location.href = '/';
        return;
    }

    // Initialize Mermaid
    mermaid.initialize({
        startOnLoad: false,
        theme: 'dark',
        securityLevel: 'loose',
        themeVariables: {
            primaryColor: '#3b82f6',
            primaryTextColor: '#f1f5f9',
            primaryBorderColor: '#475569',
            lineColor: '#64748b',
            secondaryColor: '#334155',
            tertiaryColor: '#1e293b',
            background: '#1e293b',
            mainBkg: '#334155',
            nodeBorder: '#475569',
            clusterBk: '#334155',
        }
    });

    // Display user info
    displayUserInfo();

    // Initialize conversation list
    const conversationListModule = await import('./conversation-list.js');
    await conversationListModule.initConversationList();
}

// Display user information
function displayUserInfo() {
    // Try to get user info from localStorage
    const userInfo = localStorage.getItem('user_info');
    if (userInfo) {
        try {
            const user = JSON.parse(userInfo);
            document.getElementById('user-display').textContent =
                `${user.username || user.email || 'User'} (${user.role || 'user'})`;
        } catch (e) {
            document.getElementById('user-display').textContent = 'User';
        }
    } else {
        document.getElementById('user-display').textContent = 'User';
    }
}

// Logout function
async function logout() {
    try {
        // Call logout API
        await fetch('/api/v1/auth/logout', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
            }
        });
    } catch (error) {
        console.error('Logout API call failed:', error);
    }

    // Clear local storage
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_info');

    // Redirect to main page
    window.location.href = '/';
}

// Make functions globally available
window.logout = logout;
window.refreshConversations = () => {
    import('./conversation-list.js').then(module => {
        module.refreshConversations();
    });
};
window.selectConversation = (conversationId) => {
    import('./conversation-list.js').then(module => {
        module.selectConversation(conversationId);
    });
};
window.filterConversations = () => {
    import('./conversation-list.js').then(module => {
        module.applyFilters();
    });
};

// Handle keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + R to refresh
    if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
        e.preventDefault();
        window.refreshConversations();
    }
});
