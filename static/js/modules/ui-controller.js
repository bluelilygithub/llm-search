/**
 * UI Controller Module
 * Manages UI state, view transitions, and user interface interactions
 * Centralizes UI logic and provides clean separation of concerns
 */

class UIController {
    constructor() {
        this.currentView = 'home';
        this.isLoading = false;
        this.notifications = [];
        
        // UI element cache
        this.elements = new Map();
        
        this.initializeUI();
    }

    /**
     * Initialize UI components and event listeners
     */
    initializeUI() {
        // Cache frequently used elements
        this.cacheElements();
        
        // Setup global event listeners
        this.setupEventListeners();
        
        // Initialize view state
        this.showView('home');
    }

    /**
     * Cache DOM elements for performance
     */
    cacheElements() {
        const elementIds = [
            'main-content',
            'sidebar',
            'chat-messages',
            'conversation-search',
            'conversations-list',
            'projects-list',
            'model-selector',
            'message-input'
        ];

        elementIds.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                this.elements.set(id, element);
            }
        });
    }

    /**
     * Get cached element or query DOM
     */
    getElement(id) {
        if (this.elements.has(id)) {
            return this.elements.get(id);
        }
        
        const element = document.getElementById(id);
        if (element) {
            this.elements.set(id, element);
        }
        return element;
    }

    /**
     * Setup global event listeners
     */
    setupEventListeners() {
        // Handle escape key for modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeActiveModal();
            }
        });

        // Handle window resize
        window.addEventListener('resize', () => {
            this.handleResize();
        });

        // Handle clicks outside modals
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-backdrop')) {
                this.closeActiveModal();
            }
        });
    }

    /**
     * Show a specific view
     */
    showView(viewName, data = null) {
        if (this.currentView === viewName) {
            return;
        }

        this.hideAllViews();
        this.currentView = viewName;

        switch (viewName) {
            case 'home':
                this.showHomeView(data);
                break;
            case 'chat':
                this.showChatView(data);
                break;
            case 'conversations':
                this.showConversationsView(data);
                break;
            case 'projects':
                this.showProjectsView(data);
                break;
            case 'project-detail':
                this.showProjectDetailView(data);
                break;
            default:
                console.warn(`Unknown view: ${viewName}`);
                this.showHomeView();
        }

        this.updateNavigation(viewName);
    }

    /**
     * Hide all views
     */
    hideAllViews() {
        const mainContent = this.getElement('main-content');
        if (mainContent) {
            // Remove all main-view elements
            const existingViews = mainContent.querySelectorAll('.main-view');
            existingViews.forEach(view => view.remove());
            
            // Hide chat container if exists
            const chatContainer = mainContent.querySelector('.chat-messages-container');
            if (chatContainer) {
                chatContainer.style.display = 'none';
            }
        }
    }

    /**
     * Show home view
     */
    showHomeView(data) {
        const mainContent = this.getElement('main-content');
        if (!mainContent) return;

        const homeHTML = `
            <div class="main-view">
                <nav class="breadcrumb">
                    <span class="breadcrumb-item active">
                        <i class="fas fa-home"></i>
                        Home
                    </span>
                </nav>
                
                <div class="view-header">
                    <div class="view-title">
                        <i class="fas fa-home"></i>
                        <h2>Welcome to Your Knowledge Base</h2>
                    </div>
                    <div class="view-actions">
                        <button class="view-action-btn" onclick="window.app.startNewConversation()">
                            <i class="fas fa-plus"></i>
                            New Chat
                        </button>
                    </div>
                </div>
                
                <div class="home-content">
                    <div class="home-stats">
                        <div class="stat-card">
                            <i class="fas fa-comments"></i>
                            <div class="stat-info">
                                <span class="stat-number" id="total-conversations">-</span>
                                <span class="stat-label">Conversations</span>
                            </div>
                        </div>
                        <div class="stat-card">
                            <i class="fas fa-folder"></i>
                            <div class="stat-info">
                                <span class="stat-number" id="total-projects">-</span>
                                <span class="stat-label">Projects</span>
                            </div>
                        </div>
                        <div class="stat-card">
                            <i class="fas fa-file-alt"></i>
                            <div class="stat-info">
                                <span class="stat-number" id="total-context-items">-</span>
                                <span class="stat-label">Context Items</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="home-actions">
                        <div class="action-card" onclick="window.app.startNewConversation()">
                            <i class="fas fa-comments"></i>
                            <h3>Start New Chat</h3>
                            <p>Begin a new conversation with AI</p>
                        </div>
                        <div class="action-card" onclick="window.uiController.showView('conversations')">
                            <i class="fas fa-clock"></i>
                            <h3>Recent Conversations</h3>
                            <p>Browse your conversation history</p>
                        </div>
                        <div class="action-card" onclick="window.uiController.showView('projects')">
                            <i class="fas fa-folder-open"></i>
                            <h3>Manage Projects</h3>
                            <p>Organize conversations into projects</p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        mainContent.innerHTML = homeHTML;
    }

    /**
     * Show loading state
     */
    showLoading(message = 'Loading...') {
        this.isLoading = true;
        
        // Show loading indicator
        const loadingHTML = `
            <div class="loading-overlay">
                <div class="loading-spinner">
                    <i class="fas fa-spinner fa-spin"></i>
                    <p>${message}</p>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', loadingHTML);
    }

    /**
     * Hide loading state
     */
    hideLoading() {
        this.isLoading = false;
        
        const loadingOverlay = document.querySelector('.loading-overlay');
        if (loadingOverlay) {
            loadingOverlay.remove();
        }
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info', duration = 5000) {
        const notification = {
            id: Date.now(),
            message,
            type, // 'success', 'error', 'warning', 'info'
            duration
        };

        this.notifications.push(notification);
        this.renderNotification(notification);

        // Auto-remove after duration
        if (duration > 0) {
            setTimeout(() => {
                this.removeNotification(notification.id);
            }, duration);
        }

        return notification.id;
    }

    /**
     * Render notification in UI
     */
    renderNotification(notification) {
        let container = document.querySelector('.notifications-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'notifications-container';
            document.body.appendChild(container);
        }

        const notificationHTML = `
            <div class="notification notification-${notification.type}" data-id="${notification.id}">
                <div class="notification-content">
                    <i class="fas fa-${this.getNotificationIcon(notification.type)}"></i>
                    <span>${notification.message}</span>
                </div>
                <button class="notification-close" onclick="window.uiController.removeNotification(${notification.id})">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;

        container.insertAdjacentHTML('afterbegin', notificationHTML);
    }

    /**
     * Get icon for notification type
     */
    getNotificationIcon(type) {
        const icons = {
            success: 'check-circle',
            error: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        };
        return icons[type] || 'info-circle';
    }

    /**
     * Remove notification
     */
    removeNotification(notificationId) {
        this.notifications = this.notifications.filter(n => n.id !== notificationId);
        
        const notificationEl = document.querySelector(`[data-id="${notificationId}"]`);
        if (notificationEl) {
            notificationEl.classList.add('fade-out');
            setTimeout(() => {
                notificationEl.remove();
            }, 300);
        }
    }

    /**
     * Update navigation state
     */
    updateNavigation(activeView) {
        // Update sidebar active states
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            item.classList.remove('active');
            if (item.dataset.view === activeView) {
                item.classList.add('active');
            }
        });
    }

    /**
     * Close active modal
     */
    closeActiveModal() {
        const activeModal = document.querySelector('.modal.show');
        if (activeModal) {
            activeModal.classList.remove('show');
            const backdrop = document.querySelector('.modal-backdrop');
            if (backdrop) {
                backdrop.remove();
            }
        }
    }

    /**
     * Handle window resize
     */
    handleResize() {
        // Adjust UI elements based on screen size
        const sidebar = this.getElement('sidebar');
        if (sidebar && window.innerWidth < 768) {
            sidebar.classList.add('mobile');
        } else if (sidebar) {
            sidebar.classList.remove('mobile');
        }
    }

    /**
     * Scroll to bottom of chat
     */
    scrollToBottom() {
        const chatMessages = this.getElement('chat-messages');
        if (chatMessages) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    /**
     * Focus message input
     */
    focusMessageInput() {
        const messageInput = this.getElement('message-input');
        if (messageInput) {
            messageInput.focus();
        }
    }

    /**
     * Clear message input
     */
    clearMessageInput() {
        const messageInput = this.getElement('message-input');
        if (messageInput) {
            messageInput.value = '';
        }
    }
}

// Export for global use
window.UIController = UIController;
