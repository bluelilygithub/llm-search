// UI helpers migrated from inline scripts
window.toggleSidebar = function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const logoText = document.getElementById('logo-text');
    const toggleIcon = document.getElementById('toggle-icon');
    const sidebarMainActions = document.getElementById('sidebar-main-actions');
    const sidebarContent = document.getElementById('sidebar-content');
    const sidebarCollapsedContent = document.getElementById('sidebar-collapsed-content');
    const sidebarFooter = document.getElementById('sidebar-footer');

    if (!sidebar) return;
    sidebar.classList.toggle('collapsed');

    if (sidebar.classList.contains('collapsed')) {
        if (logoText) logoText.style.display = 'none';
        if (toggleIcon) toggleIcon.innerHTML = '<path d="m24,128a8,8,0,0,1,8-8h132.69l-58.35-58.34a8,8,0,0,1,11.32-11.32l72,72a8,8,0,0,1,0,11.32l-72,72a8,8,0,0,1-11.32-11.32l58.35-58.34h-132.69a8,8,0,0,1-8-8zm192-88a8,8,0,0,0,8-8v-176a8,8,0,0,0-16,0v176a8,8,0,0,0,8,8z"></path>';
        if (sidebarMainActions) sidebarMainActions.style.display = 'none';
        if (sidebarContent) sidebarContent.style.display = 'none';
        if (sidebarCollapsedContent) sidebarCollapsedContent.style.display = 'block';
        if (sidebarFooter) {
            const settingsLabel = sidebarFooter.querySelector('.settings-label');
            if (settingsLabel) settingsLabel.style.display = 'none';
        }
    } else {
        if (logoText) logoText.style.display = 'block';
        if (toggleIcon) toggleIcon.innerHTML = '<path d="M232,128a8,8,0,0,1-8,8H91.31l58.35,58.34a8,8,0,0,1-11.32,11.32l-72-72a8,8,0,0,1,0-11.32l72-72a8,8,0,0,1,11.32,11.32L91.31,120H224A8,8,0,0,1,232,128ZM40,32a8,8,0,0,0-8,8V216a8,8,0,0,0,16,0V40A8,8,0,0,0,40,32Z"></path>';
        if (sidebarMainActions) sidebarMainActions.style.display = 'block';
        if (sidebarContent) sidebarContent.style.display = 'block';
        if (sidebarCollapsedContent) sidebarCollapsedContent.style.display = 'none';
        if (sidebarFooter) {
            const settingsLabel = sidebarFooter.querySelector('.settings-label');
            if (settingsLabel) settingsLabel.style.display = 'inline';
        }
    }
};

window.toggleSection = function toggleSection(sectionName) {
    if (sectionName === 'recent' && window.app) {
        window.app.showConversationsView?.();
        return;
    }
    if (sectionName === 'projects' && window.app) {
        window.app.showProjectsView?.();
        return;
    }
    const content = document.getElementById(sectionName + '-content');
    const toggle = document.getElementById(sectionName + '-toggle');
    if (content && toggle) {
        if (content.classList.contains('expanded')) {
            content.classList.remove('expanded');
            toggle.className = 'fas fa-plus';
        } else {
            content.classList.add('expanded');
            toggle.className = 'fas fa-minus';
        }
    }
};

window.selectNoProject = function selectNoProject() {
    if (window.app) {
        // Clear current project selection
        window.app.currentProject = null;
        window.app.currentViewProject = null;
        
        // Update UI to show "No Project" as selected
        window.app.updateProjectSelectionUI(null);
        
        // Refresh conversations to show all (no project filter)
        window.app.loadConversations();
        
        // Update new conversation title
        window.app.updateNewConversationTitle();
        
        // Show chat view
        window.app.showChatView();
    }
};

window.startNewChat = function startNewChat() {
    if (window.app?.startNewConversation) {
        window.app.startNewConversation();
    }
};

window.updateModel = function updateModel() {
    window.userManuallyChangedModel = true;
    if (window.app?.updateModel) {
        window.app.updateModel();
    }
};


