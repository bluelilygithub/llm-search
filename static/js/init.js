// Initialization migrated from inline script
(function initOnDOMContentLoaded() {
    document.addEventListener('DOMContentLoaded', async () => {
        try {
            window.userManuallyChangedModel = false;

            const authStatus = await (window.checkAuthStatus?.() || {});
            if (authStatus.authenticated) {
                const wl = document.getElementById('whitelist-tab');
                if (wl) wl.style.display = 'inline-block';
                const settingsBtn = document.getElementById('sidebar-settings-btn');
                if (settingsBtn) settingsBtn.style.display = 'flex';
            }

            // Load model settings and user preferences
            let modelSettings = {};
            let userPreferences = {};
            try {
                const [modelResponse, prefsResponse] = await Promise.all([
                    fetch('/api/model-settings'),
                    fetch('/api/preferences')
                ]);
                if (modelResponse.ok) {
                    modelSettings = await modelResponse.json();
                    window.modelSettings = modelSettings;
                }
                if (prefsResponse.ok) {
                    userPreferences = await prefsResponse.json();
                    window.userPreferences = userPreferences;
                }
            } catch (e) {
                console.error('Failed to load model settings or preferences', e);
            }

            // Update dropdowns if helpers exist
            if (typeof window.updateModelDropdown === 'function') {
                window.updateModelDropdown();
            }
            if (document.getElementById('preferences-section')?.classList.contains('active') &&
                typeof window.populateDefaultModelSelect === 'function') {
                window.populateDefaultModelSelect();
            }
        } catch (e) {
            console.error('Initialization error', e);
        }
    });
})();


