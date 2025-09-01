// Authentication helpers migrated from inline scripts
window.checkAuthStatus = async function checkAuthStatus() {
    try {
        const response = await fetch('/auth/status');
        const data = await response.json();
        if (data.auth_enabled) {
            const logoutBtn = document.getElementById('logout-btn');
            if (logoutBtn) logoutBtn.style.display = 'block';
        }
        if (data.free_access && !data.authenticated) {
            window.showUsageIndicator?.(data.free_access);
        }
        return data;
    } catch (error) {
        console.error('Failed to check auth status:', error);
        return { authenticated: false, auth_enabled: false };
    }
};

window.showUsageIndicator = function showUsageIndicator(freeAccess) {
    const existingIndicator = document.getElementById('usage-indicator');
    if (existingIndicator) existingIndicator.remove();
    const indicator = document.createElement('div');
    indicator.id = 'usage-indicator';
    indicator.className = 'usage-indicator';

    const remaining = freeAccess.queries_remaining;
    const total = freeAccess.limit;
    const used = freeAccess.queries_used;

    if (remaining <= 0) {
        indicator.className += ' danger';
        const hours = Math.floor(freeAccess.hours_until_reset || 0);
        const minutes = Math.floor(((freeAccess.hours_until_reset || 0) % 1) * 60);
        const resetText = hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
        indicator.innerHTML = `
            <div><strong>Free queries exhausted</strong></div>
            <div>Used: ${used}/${total}</div>
            <div><small>Resets in ${resetText}</small></div>
            <div><small>Login for unlimited access</small></div>
        `;
    } else if (remaining <= 3) {
        indicator.className += ' warning';
        indicator.innerHTML = `
            <div><strong>${remaining} free queries left</strong></div>
            <div>Used: ${used}/${total}</div>
        `;
    } else {
        indicator.innerHTML = `
            <div><strong>${remaining} free queries remaining</strong></div>
            <div>Used: ${used}/${total}</div>
        `;
    }

    document.body.appendChild(indicator);
};

window.logout = async function logout() {
    try {
        const response = await fetch('/auth/logout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        if (response.ok) {
            window.location.href = '/login';
        } else {
            console.error('Logout failed:', await response.text());
        }
    } catch (error) {
        console.error('Logout failed:', error);
        window.location.href = '/login';
    }
};


