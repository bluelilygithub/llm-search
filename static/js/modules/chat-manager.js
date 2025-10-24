/**
 * Chat Manager Module
 * Handles all chat-related functionality including conversations, messages, and AI interactions
 * Manages chat state and provides clean API for chat operations
 */

class ChatManager {
    constructor(apiClient, uiController) {
        this.apiClient = apiClient;
        this.uiController = uiController;
        
        // Chat state
        this.currentConversationId = null;
        this.selectedModel = 'gpt-3.5-turbo';
        this.isTyping = false;
        this.messageHistory = new Map(); // Cache for conversation messages
        
        this.initializeChatManager();
    }

    /**
     * Initialize chat manager
     */
    initializeChatManager() {
        this.loadModelSettings();
        this.setupChatEventListeners();
    }

    /**
     * Setup chat-specific event listeners
     */
    setupChatEventListeners() {
        // Message input enter key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey && e.target.id === 'message-input') {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Model selector change
        document.addEventListener('change', (e) => {
            if (e.target.id === 'model-selector') {
                this.selectedModel = e.target.value;
                this.saveModelPreference();
            }
        });
    }

    /**
     * Start a new conversation
     */
    async startNewConversation(projectId = null) {
        try {
            this.currentConversationId = null;
            this.messageHistory.clear();
            
            // Show chat view
            this.uiController.showView('chat');
            
            // Clear chat messages
            this.clearChatMessages();
            
            // Show empty state
            this.showEmptyState(projectId);
            
            // Focus input
            this.uiController.focusMessageInput();
            
        } catch (error) {
            console.error('Error starting new conversation:', error);
            this.uiController.showNotification('Failed to start new conversation', 'error');
        }
    }

    /**
     * Load an existing conversation
     */
    async loadConversation(conversationId) {
        try {
            this.uiController.showLoading('Loading conversation...');
            
            this.currentConversationId = conversationId;
            
            // Get conversation messages
            const messages = await this.apiClient.request(`/conversations/${conversationId}/messages`);
            
            // Cache messages
            this.messageHistory.set(conversationId, messages);
            
            // Show chat view
            this.uiController.showView('chat');
            
            // Render messages
            this.renderMessages(messages);
            
            // Scroll to bottom
            this.uiController.scrollToBottom();
            
        } catch (error) {
            console.error('Error loading conversation:', error);
            this.uiController.showNotification('Failed to load conversation', 'error');
        } finally {
            this.uiController.hideLoading();
        }
    }

    /**
     * Send a message
     */
    async sendMessage() {
        const messageInput = this.uiController.getElement('message-input');
        if (!messageInput) return;

        const message = messageInput.value.trim();
        if (!message) return;

        try {
            // Disable input and show typing
            this.setTypingState(true);
            this.uiController.clearMessageInput();

            // Create conversation if needed
            if (!this.currentConversationId) {
                await this.createNewConversation(message);
            }

            // Add user message to UI
            this.addMessageToChat({
                role: 'user',
                content: message,
                timestamp: new Date().toISOString()
            }, true);

            // Save user message to backend
            await this.saveMessage('user', message);

            // Get AI response
            const response = await this.getAIResponse(message);
            
            // Add AI message to UI
            this.addMessageToChat({
                role: 'assistant',
                content: response.response,
                timestamp: response.timestamp,
                model: response.model
            }, true);

            // Save AI message to backend
            await this.saveMessage('assistant', response.response);

            // Scroll to bottom
            this.uiController.scrollToBottom();

        } catch (error) {
            console.error('Error sending message:', error);
            this.handleSendMessageError(error);
        } finally {
            this.setTypingState(false);
            this.uiController.focusMessageInput();
        }
    }

    /**
     * Get AI response
     */
    async getAIResponse(message) {
        const requestData = {
            message: message,
            model: this.selectedModel,
            conversation_id: this.currentConversationId
        };

        // Add project context if available
        const projectId = window.app?.currentProject?.id || window.app?.currentViewProject?.id;
        if (projectId && !this.currentConversationId) {
            requestData.project_id = projectId;
        }

        return await this.apiClient.sendChatMessage(requestData);
    }

    /**
     * Create new conversation
     */
    async createNewConversation(firstMessage) {
        const title = firstMessage.length > 50 ? 
            firstMessage.substring(0, 50) + '...' : firstMessage;
        
        const conversationData = {
            title: title,
            llm_model: this.selectedModel,
            tags: []
        };

        // Add project context if available
        const projectId = window.app?.currentProject?.id || window.app?.currentViewProject?.id;
        if (projectId) {
            conversationData.project_id = projectId;
        }

        const conversation = await this.apiClient.createConversation(conversationData);
        this.currentConversationId = conversation.id;
        
        // Update sidebar
        if (window.app?.loadConversations) {
            window.app.loadConversations();
        }

        return conversation;
    }

    /**
     * Save message to backend
     */
    async saveMessage(role, content) {
        if (!this.currentConversationId) return;

        return await this.apiClient.request(`/conversations/${this.currentConversationId}/messages`, {
            method: 'POST',
            body: JSON.stringify({ role, content })
        });
    }

    /**
     * Add message to chat UI
     */
    addMessageToChat(message, isNewMessage = false) {
        const chatMessages = this.uiController.getElement('chat-messages');
        if (!chatMessages) return;

        // Remove empty state if it exists
        const emptyState = chatMessages.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.role}`;
        
        let timeString = this.formatTime(message.timestamp);
        if (message.role === 'assistant' && message.model) {
            timeString += ` (${message.model})`;
        }

        messageDiv.innerHTML = `
            <div class="message-content">
                ${this.formatMessageContent(message.content)}
                <div class="message-time">${timeString}</div>
            </div>
        `;

        chatMessages.appendChild(messageDiv);

        // Generate follow-up questions for new assistant messages
        if (message.role === 'assistant' && isNewMessage) {
            this.addFollowUpQuestions(messageDiv, message.content);
        }

        // Update cached messages
        if (this.currentConversationId) {
            const cached = this.messageHistory.get(this.currentConversationId) || [];
            cached.push(message);
            this.messageHistory.set(this.currentConversationId, cached);
        }
    }

    /**
     * Render messages in chat
     */
    renderMessages(messages) {
        const chatMessages = this.uiController.getElement('chat-messages');
        if (!chatMessages) return;

        chatMessages.innerHTML = '';

        messages.forEach(message => {
            this.addMessageToChat(message, false);
        });
    }

    /**
     * Add follow-up questions
     */
    async addFollowUpQuestions(messageDiv, aiResponse) {
        try {
            // Show loading indicator
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'follow-up-loading';
            loadingDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating follow-up questions...';
            messageDiv.appendChild(loadingDiv);

            // Generate questions
            const response = await this.apiClient.generateFollowUpQuestions({
                latest_response: aiResponse,
                model: this.selectedModel
            });

            // Remove loading indicator
            loadingDiv.remove();

            if (response.questions && response.questions.length > 0) {
                const followUpDiv = document.createElement('div');
                followUpDiv.className = 'follow-up-questions';
                
                const questionsHTML = response.questions.map(question => 
                    `<button class="follow-up-btn" onclick="window.chatManager.askFollowUpQuestion('${this.escapeHtml(question)}')">${question}</button>`
                ).join('');

                followUpDiv.innerHTML = `
                    <div class="follow-up-title">
                        <i class="fas fa-lightbulb"></i>
                        Follow-up questions:
                    </div>
                    <div class="follow-up-buttons">
                        ${questionsHTML}
                    </div>
                `;

                messageDiv.appendChild(followUpDiv);
            }
        } catch (error) {
            console.error('Error generating follow-up questions:', error);
            // Remove loading indicator if it exists
            const loadingDiv = messageDiv.querySelector('.follow-up-loading');
            if (loadingDiv) {
                loadingDiv.remove();
            }
        }
    }

    /**
     * Ask a follow-up question
     */
    askFollowUpQuestion(question) {
        console.log('Follow-up question:', question);
        
        // Check if this is a diagram request
        if (question.toLowerCase().includes('illustrate') || 
            question.toLowerCase().includes('diagram') || 
            question.toLowerCase().includes('graphic')) {
            console.log('Detected diagram request');
            this.generateAndDisplayDiagram();
            return;
        }
        
        const messageInput = this.uiController.getElement('message-input');
        if (messageInput) {
            messageInput.value = question;
            this.sendMessage();
        }
    }

    /**
     * Generate and display a diagram for math problems
     */
    async generateAndDisplayDiagram() {
        try {
            console.log('Starting diagram generation');
            const chatArea = this.uiController.getElement('chat-messages');
            if (!chatArea) {
                alert('Chat area not found');
                return;
            }
            
            const messages = chatArea.querySelectorAll('.message');
            if (messages.length === 0) {
                alert('No AI response found');
                return;
            }
            
            const lastMessage = messages[messages.length - 1];
            const responseText = lastMessage.querySelector('.message-content')?.textContent || '';
            
            if (!responseText) {
                alert('Could not extract response');
                return;
            }
            
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'diagram-loading';
            loadingDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating diagram...';
            chatArea.appendChild(loadingDiv);
            
            const response = await fetch('/api/generate-diagram', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    response: responseText,
                    problem: this.lastUserMessage || '',
                    model: 'stable-image-ultra'
                })
            });
            
            loadingDiv.remove();
            
            if (response.ok) {
                const data = await response.json();
                const diagramDiv = document.createElement('div');
                diagramDiv.className = 'generated-diagram';
                diagramDiv.innerHTML = `
                    <div class="diagram-container">
                        <div class="diagram-title">
                            <i class="fas fa-image"></i>
                            Professional Diagram
                        </div>
                        <img src="${data.image_url}" alt="Generated diagram" class="diagram-image" />
                        <div class="diagram-info">
                            <small>Generated with Stability AI</small>
                        </div>
                    </div>
                `;
                chatArea.appendChild(diagramDiv);
                chatArea.scrollTop = chatArea.scrollHeight;
            } else {
                const error = await response.json();
                alert('Failed to generate diagram: ' + (error.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Diagram error:', error);
            alert('Error: ' + error.message);
        }
    }

    /**
     * Format message content (handle markdown, code, etc.)
     */
    formatMessageContent(content) {
        // Basic formatting - can be enhanced with markdown parser
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }

    /**
     * Format timestamp
     */
    formatTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    /**
     * Escape HTML for safe insertion
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Set typing state
     */
    setTypingState(isTyping) {
        this.isTyping = isTyping;
        
        const messageInput = this.uiController.getElement('message-input');
        const sendButton = document.querySelector('.send-button');
        
        if (messageInput) {
            messageInput.disabled = isTyping;
        }
        
        if (sendButton) {
            sendButton.disabled = isTyping;
            if (isTyping) {
                sendButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            } else {
                sendButton.innerHTML = '<i class="fas fa-paper-plane"></i>';
            }
        }
    }

    /**
     * Clear chat messages
     */
    clearChatMessages() {
        const chatMessages = this.uiController.getElement('chat-messages');
        if (chatMessages) {
            chatMessages.innerHTML = '';
        }
    }

    /**
     * Show empty state
     */
    showEmptyState(projectId = null) {
        const chatMessages = this.uiController.getElement('chat-messages');
        if (!chatMessages) return;

        let title = 'New Conversation';
        let description = 'Start a conversation or search your knowledge base.';

        if (projectId && window.app?.currentViewProject) {
            title = `New Conversation - ${window.app.currentViewProject.name}`;
            description = `Start a conversation within the ${window.app.currentViewProject.name} project.`;
        }

        chatMessages.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <i class="fas fa-comments"></i>
                </div>
                <h2 class="empty-state-title">${title}</h2>
                <p class="empty-state-description">${description}</p>
            </div>
        `;
    }

    /**
     * Handle send message error
     */
    handleSendMessageError(error) {
        let message = 'Failed to send message. Please try again.';
        
        if (error instanceof window.APIError) {
            if (error.isNetworkError()) {
                message = 'Network error. Please check your connection.';
            } else if (error.status === 429) {
                message = 'Rate limit exceeded. Please wait a moment.';
            } else if (error.status === 401) {
                message = 'Authentication required. Please log in.';
            }
        }

        this.uiController.showNotification(message, 'error');
    }

    /**
     * Load model settings
     */
    async loadModelSettings() {
        try {
            const settings = await this.apiClient.getModelSettings();
            this.updateModelSelector(settings);
        } catch (error) {
            console.error('Error loading model settings:', error);
        }
    }

    /**
     * Update model selector
     */
    updateModelSelector(settings) {
        const modelSelector = this.uiController.getElement('model-selector');
        if (!modelSelector) return;

        // Clear existing options
        modelSelector.innerHTML = '';

        // Add enabled models
        Object.entries(settings).forEach(([model, config]) => {
            if (config.enabled) {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                modelSelector.appendChild(option);
            }
        });

        // Set selected model
        if (modelSelector.querySelector(`option[value="${this.selectedModel}"]`)) {
            modelSelector.value = this.selectedModel;
        } else {
            // Fallback to first available model
            const firstOption = modelSelector.querySelector('option');
            if (firstOption) {
                this.selectedModel = firstOption.value;
                modelSelector.value = this.selectedModel;
            }
        }
    }

    /**
     * Save model preference
     */
    async saveModelPreference() {
        try {
            await this.apiClient.saveUserPreferences({
                defaultModel: this.selectedModel
            });
        } catch (error) {
            console.error('Error saving model preference:', error);
        }
    }

    /**
     * Delete conversation
     */
    async deleteConversation(conversationId) {
        try {
            await this.apiClient.deleteConversation(conversationId);
            
            // Clear current conversation if it was deleted
            if (this.currentConversationId === conversationId) {
                this.startNewConversation();
            }
            
            // Remove from cache
            this.messageHistory.delete(conversationId);
            
            // Update sidebar
            if (window.app?.loadConversations) {
                window.app.loadConversations();
            }
            
            this.uiController.showNotification('Conversation deleted', 'success');
            
        } catch (error) {
            console.error('Error deleting conversation:', error);
            this.uiController.showNotification('Failed to delete conversation', 'error');
        }
    }
}

// Export for global use
window.ChatManager = ChatManager;
