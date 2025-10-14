/**
 * API Client Module
 * Handles all HTTP requests and API communication
 * Centralizes error handling and response processing
 */

class APIClient {
    constructor(errorHandler = null, validator = null) {
        this.errorHandler = errorHandler;
        this.validator = validator;
        this.baseURL = '';
        this.defaultHeaders = {
            'Content-Type': 'application/json'
        };
        
        // Get CSRF token
        const csrfToken = document.querySelector('meta[name="csrf-token"]');
        if (csrfToken) {
            this.defaultHeaders['X-CSRFToken'] = csrfToken.getAttribute('content');
        }
        
        // Request timeout (30 seconds)
        this.timeout = 30000;
    }

    /**
     * Generic request handler with enhanced error handling
     */
    async request(url, options = {}) {
        try {
            const config = {
                headers: { ...this.defaultHeaders, ...options.headers },
                ...options
            };

            // Create timeout promise
            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => reject(new Error('Request timeout')), this.timeout);
            });

            // Make the request with timeout
            const response = await Promise.race([
                fetch(url, config),
                timeoutPromise
            ]);
            
            if (!response.ok) {
                const apiError = await APIError.fromResponse(response);
                
                // Use error handler if available
                if (this.errorHandler) {
                    this.errorHandler.handleError(apiError);
                }
                
                throw apiError;
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const data = await response.json();
                
                // Check for API-level errors
                if (data.error) {
                    const apiError = new APIError(data.error, response.status, response);
                    apiError.errorData = data;
                    
                    if (this.errorHandler) {
                        this.errorHandler.handleError(apiError);
                    }
                    
                    throw apiError;
                }
                
                return data;
            }
            
            return response;
        } catch (error) {
            if (error instanceof APIError) {
                throw error;
            }
            
            // Handle network errors
            const networkError = APIError.fromNetworkError(error);
            
            if (this.errorHandler) {
                this.errorHandler.handleError(networkError);
            }
            
            throw networkError;
        }
    }

    /**
     * Validate data before sending request
     */
    validateData(data, schemaName) {
        if (this.validator && schemaName) {
            try {
                return this.validator.validate(data, schemaName);
            } catch (validationError) {
                if (this.errorHandler) {
                    this.errorHandler.handleError(validationError);
                }
                throw validationError;
            }
        }
        return data;
    }

    // Conversation API methods
    async getConversations() {
        return this.request('/conversations');
    }

    async createConversation(data) {
        return this.request('/conversations', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async deleteConversation(conversationId) {
        return this.request(`/conversations/${conversationId}`, {
            method: 'DELETE'
        });
    }

    async updateConversation(conversationId, data) {
        return this.request(`/conversations/${conversationId}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    // Chat API methods
    async sendChatMessage(data) {
        const validatedData = this.validateData(data, 'chatMessage');
        return this.request('/chat', {
            method: 'POST',
            body: JSON.stringify(validatedData)
        });
    }

    // Project API methods
    async getProjects() {
        return this.request('/projects');
    }

    async createProject(data) {
        const validatedData = this.validateData(data, 'project');
        return this.request('/projects', {
            method: 'POST',
            body: JSON.stringify(validatedData)
        });
    }

    async deleteProject(projectId, deleteConversations = false) {
        const url = `/projects/${projectId}?delete_conversations=${deleteConversations}`;
        return this.request(url, {
            method: 'DELETE'
        });
    }

    async updateProject(projectId, data) {
        return this.request(`/projects/${projectId}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async getProjectTemplate(projectId) {
        return this.request(`/projects/${projectId}/template`);
    }

    async updateProjectTemplate(projectId, data) {
        return this.request(`/projects/${projectId}/template`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    // Context API methods
    async getContextItems() {
        return this.request('/api/context');
    }

    async createContextItem(data) {
        return this.request('/api/context', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    // Model management API methods
    async getModelSettings() {
        return this.request('/api/model-settings');
    }

    async saveModelSettings(data) {
        return this.request('/api/model-settings', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async checkModelAccess(model) {
        return this.request('/api/check-model-access', {
            method: 'POST',
            body: JSON.stringify({ model })
        });
    }

    // User preferences API methods
    async getUserPreferences() {
        return this.request('/api/preferences');
    }

    async saveUserPreferences(data) {
        return this.request('/api/preferences', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    // Search API methods
    async searchConversations(query, options = {}) {
        const params = new URLSearchParams({
            q: query,
            ...options
        });
        return this.request(`/api/search/conversations?${params}`);
    }

    // Analytics API methods
    async getHomeStats() {
        return this.request('/api/stats/home');
    }

    // Follow-up questions API
    async generateFollowUpQuestions(data) {
        return this.request('/api/generate-followup-questions', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
}

/**
 * Custom API Error class for better error handling
 */
class APIError extends Error {
    constructor(message, status = 0, data = null) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.data = data;
    }

    isNetworkError() {
        return this.status === 0;
    }

    isServerError() {
        return this.status >= 500;
    }

    isClientError() {
        return this.status >= 400 && this.status < 500;
    }
}

// Export for use in other modules
window.APIClient = APIClient;
window.APIError = APIError;
