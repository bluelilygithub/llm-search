/**
 * Main Application Class
 * Orchestrates all modules and manages global application state
 * Simplified and modular architecture for better maintainability
 */

class KnowledgeBaseApp {
    constructor() {
        // Core modules
        this.apiClient = null;
        this.uiController = null;
        this.chatManager = null;
        this.projectManager = null;
        
        // Application state
        this.isInitialized = false;
        this.selectedModel = 'gpt-3.5-turbo';
        
        // Initialize the application
        this.initialize();
    }

    /**
     * Initialize the application and all modules
     */
    async initialize() {
        try {
            console.log('Initializing Knowledge Base App...');
            
            // Initialize core modules
            this.initializeModules();
            
            // Setup global event listeners
            this.setupGlobalEventListeners();
            
            // Load initial data
            await this.loadInitialData();
            
            // Mark as initialized
            this.isInitialized = true;
            
            console.log('Knowledge Base App initialized successfully');
            
        } catch (error) {
            console.error('Failed to initialize application:', error);
            this.handleInitializationError(error);
        }
    }

    /**
     * Initialize all modules in correct order
     */
    initializeModules() {
        // Initialize API client first
        this.apiClient = new APIClient();
        
        // Initialize UI controller
        this.uiController = new UIController();
        
        // Initialize managers with dependencies
        this.chatManager = new ChatManager(this.apiClient, this.uiController);
        this.projectManager = new ProjectManager(this.apiClient, this.uiController);
        
        // Make modules globally available for backward compatibility
        window.apiClient = this.apiClient;
        window.uiController = this.uiController;
        window.chatManager = this.chatManager;
        window.projectManager = this.projectManager;
        
        console.log('All modules initialized');
    }

    /**
     * Setup global event listeners
     */
    setupGlobalEventListeners() {
        // Handle unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled promise rejection:', event.reason);
            this.handleError(event.reason);
        });

        // Handle JavaScript errors
        window.addEventListener('error', (event) => {
            console.error('JavaScript error:', event.error);
            this.handleError(event.error);
        });

        // Handle page visibility changes
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.handlePageVisible();
            }
        });
    }

    /**
     * Load initial application data
     */
    async loadInitialData() {
        try {
            // Load projects in background
            this.projectManager.loadProjects();
            
            // Load user preferences
            await this.loadUserPreferences();
            
            // Load model settings
            await this.chatManager.loadModelSettings();
            
        } catch (error) {
            console.error('Error loading initial data:', error);
        }
    }

    /**
     * Load user preferences
     */
    async loadUserPreferences() {
        try {
            const preferences = await this.apiClient.getUserPreferences();
            
            if (preferences.defaultModel) {
                this.selectedModel = preferences.defaultModel;
                this.chatManager.selectedModel = preferences.defaultModel;
            }
            
        } catch (error) {
            console.error('Error loading user preferences:', error);
        }
    }

    /**
     * Handle page becoming visible (user returns to tab)
     */
    handlePageVisible() {
        // Refresh data if needed
        if (this.isInitialized) {
            // Could refresh conversations, projects, etc.
        }
    }

    /**
     * Handle application errors
     */
    handleError(error) {
        let message = 'An unexpected error occurred';
        
        if (error instanceof APIError) {
            if (error.isNetworkError()) {
                message = 'Network connection error. Please check your internet connection.';
            } else if (error.status === 401) {
                message = 'Authentication required. Please log in.';
            } else if (error.status === 403) {
                message = 'Access denied. You may not have permission for this action.';
            } else if (error.status === 429) {
                message = 'Rate limit exceeded. Please wait a moment before trying again.';
            } else {
                message = error.message || 'Server error occurred';
            }
        } else if (error.message) {
            message = error.message;
        }
        
        this.uiController.showNotification(message, 'error');
    }

    /**
     * Handle initialization errors
     */
    handleInitializationError(error) {
        document.body.innerHTML = `
            <div class="error-container">
                <div class="error-content">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h2>Application Failed to Load</h2>
                    <p>There was an error initializing the application.</p>
                    <p class="error-details">${error.message}</p>
                    <button onclick="window.location.reload()" class="retry-btn">
                        <i class="fas fa-refresh"></i>
                        Retry
                    </button>
                </div>
            </div>
        `;
    }

    // ===== PUBLIC API METHODS =====
    // These methods maintain backward compatibility with existing code

    /**
     * Start a new conversation
     */
    async startNewConversation() {
        return this.chatManager.startNewConversation();
    }

    /**
     * Start a new conversation in a project
     */
    async startNewConversationInProject(projectId) {
        this.projectManager.setCurrentProject(
            this.projectManager.getProject(projectId)
        );
        return this.chatManager.startNewConversation(projectId);
    }

    /**
     * Load a conversation
     */
    async loadConversation(conversationId) {
        return this.chatManager.loadConversation(conversationId);
    }

    /**
     * Show conversations view
     */
    showConversationsView() {
        this.uiController.showView('conversations');
    }

    /**
     * Show projects view
     */
    showProjectsView() {
        this.projectManager.showProjectsView();
        this.uiController.showView('projects');
    }

    /**
     * Show home view
     */
    showHomeView() {
        this.uiController.showView('home');
    }

    /**
     * Open a project
     */
    openProject(projectId) {
        this.projectManager.showProjectDetailView(projectId);
    }

    /**
     * Create a new project
     */
    async createProject(projectData) {
        return this.projectManager.createProject(projectData);
    }

    /**
     * Delete a project
     */
    async deleteProject(projectId) {
        return this.projectManager.deleteProject(projectId);
    }

    /**
     * Edit a project
     */
    async editProject(projectId, currentName) {
        return this.projectManager.showEditProjectModal(projectId);
    }

    /**
     * Send a message
     */
    async sendMessage() {
        return this.chatManager.sendMessage();
    }

    /**
     * Delete a conversation
     */
    async deleteConversation(conversationId) {
        return this.chatManager.deleteConversation(conversationId);
    }

    /**
     * Show loading state
     */
    showLoading(message) {
        this.uiController.showLoading(message);
    }

    /**
     * Hide loading state
     */
    hideLoading() {
        this.uiController.hideLoading();
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        return this.uiController.showNotification(message, type);
    }

    /**
     * Get current project
     */
    get currentProject() {
        return this.projectManager.currentProject;
    }

    /**
     * Set current project
     */
    set currentProject(project) {
        this.projectManager.setCurrentProject(project);
    }

    /**
     * Get current view project
     */
    get currentViewProject() {
        return this.projectManager.currentViewProject;
    }

    /**
     * Set current view project
     */
    set currentViewProject(project) {
        this.projectManager.currentViewProject = project;
    }

    /**
     * Get current conversation ID
     */
    get currentConversationId() {
        return this.chatManager.currentConversationId;
    }

    /**
     * Set current conversation ID
     */
    set currentConversationId(id) {
        this.chatManager.currentConversationId = id;
    }
}

// Initialize the application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new KnowledgeBaseApp();
});

// Backward compatibility functions
function startNewChat() {
    if (window.app?.startNewConversation) {
        window.app.startNewConversation();
    }
}

function updateModel() {
    window.userManuallyChangedModel = true;
    if (window.app?.chatManager) {
        const modelSelector = document.getElementById('model-selector');
        if (modelSelector) {
            window.app.chatManager.selectedModel = modelSelector.value;
            window.app.chatManager.saveModelPreference();
        }
    }
}

// Export for debugging and testing
window.KnowledgeBaseApp = KnowledgeBaseApp;
