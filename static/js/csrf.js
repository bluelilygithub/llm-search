// CSRF token setup and fetch override
(function setupCsrfFetchOverride() {
    try {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (!meta) return;
        window.csrfToken = meta.getAttribute('content');

        const originalFetch = window.fetch;
        window.fetch = function(url, options = {}) {
            try {
                const isStringUrl = typeof url === 'string';
                const isSameOrigin = isStringUrl ? (url.startsWith('/') || url.startsWith(window.location.origin)) : true;
                const method = (options.method || 'GET').toUpperCase();
                if (isSameOrigin && method !== 'GET') {
                    options.headers = options.headers || {};
                    if (typeof options.headers === 'object' && !Array.isArray(options.headers)) {
                        options.headers['X-CSRFToken'] = window.csrfToken;
                    }
                    if (options.headers['Content-Type'] === 'application/json' && options.body) {
                        try {
                            const bodyData = JSON.parse(options.body);
                            bodyData.csrf_token = window.csrfToken;
                            options.body = JSON.stringify(bodyData);
                        } catch (_) {}
                    }
                }
            } catch (_) {}
            return originalFetch.call(this, url, options);
        };
    } catch (e) {
        console.error('Failed to set up CSRF fetch override', e);
    }
})();


