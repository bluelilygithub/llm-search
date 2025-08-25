class KnowledgeBaseApp {
    constructor() {
        this.currentConversationId = null;
        this.selectedModel = 'gpt-4';
        this.uploadedFiles = [];
        this.urlReferences = [];
        this.isRecording = false;
        this.mediaRecorder = null;
        this.currentProject = null; // Added for project management
        this.projects = []; // Initialize projects array
        
        // Setup global error handling
        this.setupGlobalErrorHandling();
        
        this.init();
    }

    init() {
        this.loadProjects(); // Load projects on app initialization
        this.loadConversations();
        this.setupEventListeners();
        this.autoResizeTextarea();
        // No longer showing model instructions automatically
    }

    setupGlobalErrorHandling() {
        // Handle uncaught JavaScript errors
        window.addEventListener('error', (event) => {
            this.handleError('JavaScript Error', event.error || event.message);
        });

        // Handle unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            this.handleError('Promise Rejection', event.reason);
        });
    }

    handleError(type, error, context = '') {
        console.error(`${type}:`, error);
        
        // Show user-friendly error message
        this.showErrorNotification(`${type}: ${this.getErrorMessage(error)}`, context);
        
        // Log to server if needed (optional)
        this.logErrorToServer(type, error, context);
    }

    getErrorMessage(error) {
        if (typeof error === 'string') return error;
        if (error?.message) return error.message;
        if (error?.toString) return error.toString();
        return 'An unexpected error occurred';
    }

    showErrorNotification(message, context = '') {
        // Create error notification element
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-notification';
        errorDiv.innerHTML = `
            <div class="error-content">
                <i class="fas fa-exclamation-triangle"></i>
                <span>${message}</span>
                <button class="close-error" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;
        
        // Add to page
        document.body.appendChild(errorDiv);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentElement) {
                errorDiv.remove();
            }
        }, 5000);
    }

    showMessage(message, type = 'info') {
        const notification = document.createElement('div');
        let className, icon;
        
        switch(type) {
            case 'success':
                className = 'success-notification';
                icon = 'fas fa-check-circle';
                break;
            case 'warning':
                className = 'warning-notification';
                icon = 'fas fa-exclamation-triangle';
                break;
            case 'info':
            default:
                className = 'info-notification';
                icon = 'fas fa-info-circle';
                break;
        }
        
        notification.className = className;
        notification.innerHTML = `
            <div class="error-content">
                <i class="${icon}"></i>
                <span>${message}</span>
                <button class="close-error" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 4 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 4000);
    }

    async logErrorToServer(type, error, context) {
        try {
            await fetch('/api/log-error', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type,
                    message: this.getErrorMessage(error),
                    context,
                    url: window.location.href,
                    userAgent: navigator.userAgent,
                    timestamp: new Date().toISOString()
                })
            });
        } catch (e) {
            // Don't throw if error logging fails
            console.warn('Failed to log error to server:', e);
        }
    }

    setupEventListeners() {
        // Auto-resize textarea
        const messageInput = document.getElementById('message-input');
        messageInput.addEventListener('input', this.autoResizeTextarea);
        
        // File upload drag and drop
        this.setupFileUpload();
        
        // Voice input setup
        this.setupVoiceInput();
    }

    autoResizeTextarea() {
        const textarea = document.getElementById('message-input');
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    }

    // --- Project Management ---
    async loadProjects() {
        try {
            const response = await fetch('/projects');
            const projects = await response.json();
            this.projects = projects; // Store projects for later use
            this.renderProjects(projects);
        } catch (error) {
            console.error('Failed to load projects:', error);
        }
    }

    renderProjects(projects) {
        const container = document.getElementById('project-list');
        if (!container) {
            console.error('Project list container not found');
            return;
        }
        
        container.innerHTML = '';

        // Add "All Projects" option
        const allItem = document.createElement('div');
        allItem.className = 'project-item';
        allItem.onclick = () => this.selectProject(null);
        if (!this.currentProject) {
            allItem.classList.add('active');
        }

        allItem.innerHTML = `
            <div class="project-main">
                <div class="project-icon">
                    <i class="fas fa-folder"></i>
                </div>
                <div class="project-info">
                    <div class="project-name">All Projects</div>
                    <div class="project-count">View all conversations</div>
                </div>
            </div>
        `;
        container.appendChild(allItem);

        // Add individual projects
        projects.forEach(project => {
            const item = document.createElement('div');
            item.className = 'project-item';
            item.onclick = () => this.selectProject(project);
            
            if (this.currentProject && this.currentProject.id === project.id) {
                item.classList.add('active');
            }

            // Count conversations for this project (you may need to add this to backend)
            const conversationCount = project.conversation_count || 0;

            item.innerHTML = `
                <div class="project-main">
                    <div class="project-icon">
                        <i class="fas fa-folder-open"></i>
                    </div>
                    <div class="project-info">
                        <div class="project-name">${project.name}</div>
                        <div class="project-count">${conversationCount} conversations</div>
                    </div>
                </div>
                <div class="project-actions">
                    <button class="project-action-btn" onclick="event.stopPropagation(); window.app.editProject('${project.id}', '${project.name.replace(/'/g, "\\'")}')" title="Edit Project">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="project-action-btn" onclick="event.stopPropagation(); window.app.deleteProject('${project.id}')" title="Delete Project">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
            
            container.appendChild(item);
        });
    }

    showNewProjectPrompt() { /* no-op, replaced by inline input */ }

    // Methods called from the new HTML structure
    startNewConversation() {
        this.currentConversationId = null;
        document.getElementById('chat-messages').innerHTML = `
            <div class="empty-state" id="empty-state">
                <div class="empty-state-icon">
                    <i class="fas fa-comments"></i>
                </div>
                <h2 class="empty-state-title" id="new-conversation-title">New Conversation</h2>
                <p class="empty-state-description">Start a conversation or search your knowledge base.</p>
            </div>
        `;
        this.updateNewConversationTitle();
    }

    createNewProject(name) {
        if (!name.trim()) return;
        this.createProject(name.trim());
    }

    editConversationTitle(conversationId, currentTitle) {
        const newTitle = prompt('Edit conversation title:', currentTitle);
        if (newTitle && newTitle !== currentTitle) {
            this.updateConversationTitle(conversationId, newTitle);
        }
    }

    async updateConversationTitle(conversationId, newTitle) {
        try {
            const response = await fetch(`/conversations/${conversationId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    title: newTitle
                })
            });

            if (response.ok) {
                this.loadConversations();
            } else {
                console.error('Failed to update conversation title');
            }
        } catch (error) {
            console.error('Error updating conversation title:', error);
        }
    }

    deleteConversation(conversationId) {
        if (confirm('Are you sure you want to delete this conversation?')) {
            this.deleteConversationById(conversationId);
        }
    }

    async deleteConversationById(conversationId) {
        try {
            const response = await fetch(`/conversations/${conversationId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                if (this.currentConversationId === conversationId) {
                    this.startNewConversation();
                }
                this.loadConversations();
            } else {
                console.error('Failed to delete conversation');
            }
        } catch (error) {
            console.error('Error deleting conversation:', error);
        }
    }

    editProject(projectId, currentName) {
        const newName = prompt('Edit project name:', currentName);
        if (newName && newName !== currentName) {
            this.renameProject({ id: projectId }, newName);
        }
    }

    async deleteProject(projectId) {
        if (confirm('Are you sure you want to delete this project?')) {
            try {
                const response = await fetch(`/projects/${projectId}`, {
                    method: 'DELETE'
                });

                if (response.ok) {
                    if (this.currentProject && this.currentProject.id === projectId) {
                        this.currentProject = null;
                    }
                    this.loadProjects();
                    this.loadConversations();
                } else {
                    const errorData = await response.json();
                    console.error('Failed to delete project:', errorData.error);
                    alert(`Failed to delete project: ${errorData.error || 'Unknown error'}`);
                }
            } catch (error) {
                console.error('Error deleting project:', error);
                alert('Failed to delete project. Please try again.');
            }
        }
    }

    async createProject(name) {
        if (!name) return;
        try {
            const response = await fetch('/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });
            if (!response.ok) throw new Error('Failed to create project');
            this.addingProject = false;
            await this.loadProjects();
            console.log('Created project:', name);
        } catch (error) {
            console.error('Failed to create project:', error);
        }
    }


    async renameProject(project, newName) {
        if (!newName) return;
        try {
            const response = await fetch(`/projects/${project.id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newName })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                console.error('Failed to rename project:', errorData.error);
                alert(`Failed to rename project: ${errorData.error || 'Unknown error'}`);
                return;
            }
            
            this.renamingProject = null;
            await this.loadProjects();
            console.log('Renamed project:', newName);
        } catch (error) {
            console.error('Failed to rename project:', error);
            alert('Failed to rename project. Please try again.');
        }
    }

    selectProject(project) {
        // Only trigger if changing project
        const isNewProject = !this.currentProject || !project || this.currentProject.id !== project.id;
        this.currentProject = project;
        this.loadProjects();
        this.loadConversations();
        if (isNewProject) {
            this.currentConversationId = null;
            document.getElementById('chat-messages').innerHTML = `
                <div class="welcome-message">
                    <h3 id="new-conversation-title">New Conversation</h3>
                    <p>Start a conversation or search your knowledge base.</p>
                </div>
            `;
            this.updateNewConversationTitle();
            document.getElementById('message-input').value = '';
            this.autoResizeTextarea();
        }
    }

    updateNewConversationTitle() {
        const titleElement = document.getElementById('new-conversation-title');
        if (!titleElement) return;
        
        if (this.currentProject && this.currentProject.name) {
            titleElement.textContent = `New Conversation - ${this.currentProject.name}`;
        } else {
            titleElement.textContent = 'New Conversation - All Conversations';
        }
    }

    // --- Conversation Filtering by Project ---
    async loadConversations() {
        try {
            let url = '/conversations';
            if (this.currentProject && this.currentProject.id) {
                url += `?project_id=${this.currentProject.id}`;
            }
            const response = await fetch(url);
            const conversations = await response.json();
            console.log('Current project:', this.currentProject);
            console.log('Fetched conversations:', conversations);
            // Filter on frontend as a fallback (in case backend returns all)
            let filtered = conversations;
            if (this.currentProject && this.currentProject.id) {
                filtered = conversations.filter(conv => conv.project_id === this.currentProject.id);
                console.log('Filtered conversations:', filtered);
            }
            this.renderConversations(filtered);
        } catch (error) {
            console.error('Failed to load conversations:', error);
        }
    }

    renderConversations(conversations) {
        console.log('DEBUG: renderConversations called with:', conversations);
        const container = document.getElementById('conversations-list');
        container.innerHTML = '';

        conversations.forEach(conv => {
            console.log(`DEBUG: Rendering conversation "${conv.title}" with tags:`, conv.tags);
            const item = document.createElement('div');
            item.className = 'conversation-item';
            item.onclick = () => this.loadConversation(conv.id);
            
            const tags = (conv.tags || []).map(tag => 
                `<span class="tag">
                    ${tag}
                    <button class="tag-remove-btn" onclick="event.stopPropagation(); window.app.removeTagFromConversation('${conv.id}', '${tag.replace(/'/g, "\\'")}')" title="Remove tag">
                        <i class="fas fa-times"></i>
                    </button>
                </span>`
            ).join('');
            console.log(`DEBUG: Generated tags HTML for "${conv.title}":`, tags);
            
            item.innerHTML = `
                <div class="conversation-content">
                    <div class="conversation-title">${conv.title}</div>
                    <div class="conversation-meta">
                        <span>${conv.llm_model}</span>
                        <span>•</span>
                        <span>${this.formatDate(conv.updated_at)}</span>
                    </div>
                    <div class="conversation-tags">${tags}</div>
                </div>
                <div class="conversation-actions">
                    <button class="conversation-action-btn" onclick="event.stopPropagation(); window.app.editConversationTitle(${conv.id}, '${conv.title.replace(/'/g, '\\\'')}')" title="Edit">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="conversation-action-btn" onclick="event.stopPropagation(); window.app.deleteConversation(${conv.id})" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
            
            container.appendChild(item);
        });
    }

    async loadConversation(conversationId) {
        try {
            this.currentConversationId = conversationId;
            
            // Update active conversation in sidebar
            document.querySelectorAll('.conversation-item').forEach(item => {
                item.classList.remove('active');
            });
            // Only try to add active class if event exists (from sidebar click)
            if (typeof event !== 'undefined' && event.currentTarget) {
                event.currentTarget.classList.add('active');
            }

            const response = await fetch(`/conversations/${conversationId}/messages`);
            
            if (!response.ok) {
                throw new Error(`Failed to fetch conversation: ${response.status} ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Safety checks for API response
            if (!data || !data.messages) {
                console.warn('Invalid API response:', data);
                this.renderMessages([]);
                return;
            }
            
            this.renderMessages(data.messages);
            
            if (data.conversation && data.conversation.llm_model) {
                this.selectedModel = data.conversation.llm_model;
                document.getElementById('llm-model').value = this.selectedModel;
            }
            
            // Update chat header with project and conversation context
            this.updateChatHeader(data.conversation);
            
            // No longer showing model instructions automatically
            
        } catch (error) {
            console.error('Failed to load conversation:', error);
        }
    }

    updateChatHeader(conversation) {
        const chatHeader = document.getElementById('chat-header');
        const projectName = document.getElementById('project-name');
        const conversationTitle = document.getElementById('conversation-title');
        
        if (!chatHeader || !projectName || !conversationTitle) {
            return;
        }
        
        // Check if we're in a project context and have project info
        if (this.currentViewProject || (conversation && conversation.project_id && this.projects)) {
            let project = this.currentViewProject;
            
            // If we don't have currentViewProject, try to find it from conversation's project_id
            if (!project && conversation.project_id && this.projects) {
                project = this.projects.find(p => p.id === conversation.project_id);
            }
            
            if (project) {
                // Show header with project context
                projectName.textContent = project.name;
                conversationTitle.textContent = conversation.title;
                chatHeader.style.display = 'block';
                return;
            }
        }
        
        // Hide header if no project context
        chatHeader.style.display = 'none';
    }

    goBackToProject() {
        if (this.currentViewProject) {
            this.showProjectConversationsView(this.currentViewProject);
        }
    }

    renderMessages(messages) {
        const container = document.getElementById('chat-messages');
        container.innerHTML = '';

        // Safety check: ensure messages is an array
        if (!messages || !Array.isArray(messages)) {
            console.warn('Messages is not an array or is undefined:', messages);
            return;
        }

        messages.forEach(message => {
            this.addMessageToChat(message);
        });

        this.scrollToBottom();
    }

    addMessageToChat(message) {
        const container = document.getElementById('chat-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.role} new`;
        
        // If assistant, include model in time
        let timeString = this.formatTime(message.timestamp);
        if (message.role === 'assistant' && this.selectedModel) {
            timeString += ` (${this.selectedModel})`;
        }
        messageDiv.innerHTML = `
            <div class="message-content">
                ${this.formatMessageContent(message.content)}
                <div class="message-time">${timeString}</div>
            </div>
        `;
        
        container.appendChild(messageDiv);
        this.scrollToBottom();
    }

    formatMessageContent(content) {
        // Simple markdown-like formatting
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width: 100%; height: auto; border-radius: 8px; margin: 10px 0;">')
            .replace(/\n/g, '<br>');
    }

    async sendMessage() {
        const input = document.getElementById('message-input');
        const sendBtn = document.getElementById('send-btn');
        const content = input.value.trim();
        
        if (!content) return;
        
        // Disable input and send button during API call
        input.disabled = true;
        sendBtn.disabled = true;
        sendBtn.textContent = 'Sending...';

        // Add user message immediately
        const userMessage = {
            role: 'user',
            content: content,
            timestamp: new Date().toISOString()
        };
        
        this.addMessageToChat(userMessage);
        input.value = '';
        this.autoResizeTextarea();

        // Show typing indicator
        this.showTypingIndicator();

        try {
            // Create new conversation if needed
            if (!this.currentConversationId) {
                await this.createNewConversation(content);
            }

            // Save user message
            await this.saveMessage('user', content);

            // Get AI response (placeholder for now)
            const aiResponse = await this.getAIResponse(content);
            
            // Save AI message
            await this.saveMessage('assistant', aiResponse);

            // Add AI message to chat
            this.hideTypingIndicator();
            const aiMessage = {
                role: 'assistant',
                content: aiResponse,
                timestamp: new Date().toISOString()
            };
            this.addMessageToChat(aiMessage);

        } catch (error) {
            this.hideTypingIndicator();
            console.error('Failed to send message:', error);
            // Show the actual error message instead of generic message
            this.showError(error.message || 'Failed to send message. Please try again.');
        } finally {
            // Re-enable input and send button
            input.disabled = false;
            sendBtn.disabled = false;
            sendBtn.textContent = 'Send';
        }
    }

    async createNewConversation(firstMessage) {
        const title = firstMessage.length > 50 ? 
            firstMessage.substring(0, 50) + '...' : firstMessage;
        const body = {
            title: title,
            llm_model: this.selectedModel,
            tags: []
        };
        if (this.currentProject && this.currentProject.id) {
            body.project_id = this.currentProject.id;
        }
        const response = await fetch('/conversations', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(body)
        });
        const conversation = await response.json();
        this.currentConversationId = conversation.id;
        this.loadConversations(); // Refresh sidebar
    }

    async saveMessage(role, content) {
        if (!this.currentConversationId) return;

        await fetch(`/conversations/${this.currentConversationId}/messages`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                role: role,
                content: content
            })
        });
    }

    async getAIResponse(userMessage) {
        try {
            // Check if we have a Stability AI model and an uploaded image
            const stabilityModels = [
                'stable-image-ultra',
                'stable-image-core', 
                'stable-image-sd3',
                'stable-audio-2'
            ];
            
            const isStabilityModel = stabilityModels.includes(this.selectedModel);
            const hasUploadedImage = this.currentStabilityImage && isStabilityModel && this.selectedModel.includes('stable-image');
            
            if (hasUploadedImage) {
                // For image editing with uploaded image, use FormData
                return await this.handleStabilityImageEditing(userMessage);
            } else {
                // Regular chat API call
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        message: userMessage,
                        model: this.selectedModel,
                        conversation_id: this.currentConversationId
                    })
                });

                const data = await response.json();
                
                // Check for API errors (backend returns 500 with error details)
                if (!response.ok || data.error) {
                    throw new Error(data.error || `HTTP error! status: ${response.status}`);
                }
                
                // Update free access indicator if present
                if (data.free_access) {
                    this.updateUsageIndicator(data.free_access);
                }
                
                return data.response;
            }
            
        } catch (error) {
            console.error('LLM API error:', error);
            throw error; // Preserve the original error message
        }
    }

    async handleStabilityImageEditing(userMessage) {
        // Create FormData to send both image and editing instructions
        const formData = new FormData();
        formData.append('image', this.currentStabilityImage);
        formData.append('prompt', userMessage);
        formData.append('model', this.selectedModel);
        formData.append('conversation_id', this.currentConversationId || '');
        
        try {
            const response = await fetch('/stability-edit-image', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (!response.ok || data.error) {
                throw new Error(data.error || 'Image editing failed');
            }
            
            // Clear the uploaded image after successful editing
            this.currentStabilityImage = null;
            
            // Show a message that the image was processed
            this.showImageEditingComplete();
            
            return data.response;
            
        } catch (error) {
            console.error('Stability image editing error:', error);
            throw error;
        }
    }

    showImageEditingComplete() {
        const container = document.getElementById('chat-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system';
        messageDiv.innerHTML = `
            <div class="message-content">
                <div style="color: #28a745; font-weight: 500;">
                    <i class="fas fa-check-circle"></i> Image editing request processed
                </div>
            </div>
        `;
        container.appendChild(messageDiv);
        this.scrollToBottom();
    }

    showTypingIndicator() {
        const container = document.getElementById('chat-messages');
        const indicator = document.createElement('div');
        indicator.className = 'message assistant';
        indicator.id = 'typing-indicator';
        indicator.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        container.appendChild(indicator);
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    }

    startNewChat() {
        this.currentConversationId = null;
        document.getElementById('chat-messages').innerHTML = `
            <div class="welcome-message">
                <h3 id="new-conversation-title">New Conversation</h3>
                <p>Start a conversation or search your knowledge base.</p>
            </div>
        `;
        this.updateNewConversationTitle();
        
        // Clear active conversation
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.remove('active');
        });
        
        // Clear input
        document.getElementById('message-input').value = '';
        this.autoResizeTextarea();
    }

    updateModel() {
        this.selectedModel = document.getElementById('llm-model').value;
        // No longer showing model instructions automatically
    }

    showModelInstructions() {
        // Remove any existing model instructions (cleanup only)
        const existingInstructions = document.getElementById('model-instructions');
        if (existingInstructions) {
            existingInstructions.remove();
        }

        // Check if selected model is a Stability AI model
        const stabilityModels = [
            'stable-image-ultra',
            'stable-image-core', 
            'stable-image-sd3',
            'stable-audio-2'
        ];

        // Show/hide image upload button based on model type
        this.toggleImageUploadForStability(stabilityModels.includes(this.selectedModel));

        // Instructions will only be shown when an image is uploaded, not on model selection
        // No longer automatically showing instructions here
    }

    toggleImageUploadForStability(isStabilityModel) {
        let imageUploadBtn = document.getElementById('image-upload-btn');
        const regularFileBtn = document.querySelector('button[onclick="triggerFileUpload()"]');
        
        if (isStabilityModel) {
            // Show image upload button for Stability models
            if (!imageUploadBtn) {
                const newImageBtn = document.createElement('button');
                newImageBtn.id = 'image-upload-btn';
                newImageBtn.className = 'input-btn-inline stability-upload';
                newImageBtn.onclick = () => this.triggerImageUpload();
                newImageBtn.title = 'Upload Image for Editing';
                newImageBtn.innerHTML = '<i class="fas fa-image"></i>';
                
                // Insert after the regular file upload button
                const inputControlsLeft = document.querySelector('.input-controls-left');
                if (inputControlsLeft) {
                    inputControlsLeft.appendChild(newImageBtn);
                    imageUploadBtn = newImageBtn; // Update reference
                } else {
                    console.error('Could not find .input-controls-left element');
                    return;
                }
            }
            
            // Now safely set display
            if (imageUploadBtn) {
                imageUploadBtn.style.display = 'block';
            }
            
            // Hide regular file upload to avoid confusion
            if (regularFileBtn) {
                regularFileBtn.style.display = 'none';
            }
        } else {
            // Hide image upload button for non-Stability models
            if (imageUploadBtn) {
                imageUploadBtn.style.display = 'none';
            }
            
            // Show regular file upload button
            if (regularFileBtn) {
                regularFileBtn.style.display = 'block';
            }
        }
    }

    triggerImageUpload() {
        // Create a dedicated image file input for Stability
        let imageInput = document.getElementById('stability-image-input');
        if (!imageInput) {
            imageInput = document.createElement('input');
            imageInput.type = 'file';
            imageInput.id = 'stability-image-input';
            imageInput.accept = 'image/*';
            imageInput.style.display = 'none';
            imageInput.onchange = (event) => this.handleStabilityImageUpload(event);
            document.body.appendChild(imageInput);
        }
        imageInput.click();
    }

    async handleStabilityImageUpload(event) {
        const files = Array.from(event.target.files);
        if (!files.length) return;

        const file = files[0];
        
        // Validate it's an image
        if (!file.type.startsWith('image/')) {
            this.showError('Please select an image file (JPG, PNG, GIF, etc.)');
            return;
        }

        // Show the uploaded image in chat and prepare for editing options
        await this.showImageForEditing(file);
        
        // Clear the file input for next upload
        event.target.value = '';
    }

    async showImageForEditing(imageFile) {
        const container = document.getElementById('chat-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user new stability-image-upload';
        
        // Create image preview
        const imageUrl = URL.createObjectURL(imageFile);
        
        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="stability-image-container">
                    <img src="${imageUrl}" alt="Uploaded for editing" class="stability-uploaded-image">
                    <div class="image-editing-info">
                        <i class="fas fa-image"></i>
                        <strong>Image uploaded for Stability AI editing</strong>
                        <div class="image-details">
                            <span>${imageFile.name}</span>
                            <span>(${this.formatFileSize(imageFile.size)})</span>
                        </div>
                    </div>
                </div>
                <div class="editing-instructions">
                    Now describe what you want to do with this image:
                    <div class="editing-examples">
                        • "Remove the background"
                        • "Erase the person on the left"  
                        • "Change the sky to sunset colors"
                        • "Extend this image to the right"
                    </div>
                </div>
            </div>
        `;
        
        container.appendChild(messageDiv);
        this.scrollToBottom();
        
        // Store the image file for potential use
        this.currentStabilityImage = imageFile;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }


    // Search functionality
    async searchKnowledgeBase() {
        document.getElementById('search-modal').style.display = 'flex';
        document.getElementById('kb-search-input').focus();
    }

    async performKnowledgeBaseSearch() {
        const query = document.getElementById('kb-search-input').value.trim();
        if (!query) return;

        // Placeholder search - will implement semantic search
        const results = [
            {
                title: "Previous conversation about AI",
                snippet: "We discussed the benefits of using AI for content creation...",
                conversation_id: "123",
                timestamp: "2024-01-15"
            }
        ];

        this.renderSearchResults(results);
    }

    renderSearchResults(results) {
        const container = document.getElementById('search-results-container');
        container.innerHTML = '';

        results.forEach(result => {
            const item = document.createElement('div');
            item.className = 'search-result-item';
            item.onclick = () => {
                this.loadConversation(result.conversation_id);
                this.closeSearchModal();
            };
            
            item.innerHTML = `
                <div class="search-result-title">${result.title}</div>
                <div class="search-result-snippet">${result.snippet}</div>
                <div class="search-result-meta">
                    <span>${result.timestamp}</span>
                </div>
            `;
            
            container.appendChild(item);
        });
    }

    closeSearchModal() {
        document.getElementById('search-modal').style.display = 'none';
        document.getElementById('kb-search-input').value = '';
        document.getElementById('search-results-container').innerHTML = '';
    }

    // Tagging functionality
    async tagConversation() {
        if (!this.currentConversationId) {
            this.showError('Please select a conversation to tag');
            return;
        }
        
        // Load current conversation tags and existing tags
        await this.loadTagsForModal();
        document.getElementById('tag-modal').style.display = 'flex';
        document.getElementById('tag-input').focus();
    }

    async loadTagsForModal() {
        try {
            // Load current conversation tags
            const currentResponse = await fetch(`/api/conversations/${this.currentConversationId}/tags`);
            const currentTags = await currentResponse.json();
            this.displayCurrentTags(currentTags.tags || []);
            
            // Load all existing tags for suggestions
            const allResponse = await fetch('/api/tags');
            const allTagsData = await allResponse.json();
            this.displaySuggestedTags(allTagsData.tags || []);
        } catch (error) {
            console.error('Failed to load tags:', error);
            this.displayCurrentTags([]);
            this.displaySuggestedTags([]);
        }
    }

    displayCurrentTags(tags) {
        const container = document.getElementById('conversation-current-tags');
        if (tags.length === 0) {
            container.innerHTML = '<span class="no-tags">No tags yet</span>';
        } else {
            container.innerHTML = tags.map(tag => 
                `<span class="tag">${tag} <span class="remove-tag" onclick="window.app.removeTagFromCurrent('${tag}')">&times;</span></span>`
            ).join('');
        }
    }

    displaySuggestedTags(tags) {
        const container = document.getElementById('existing-tags');
        if (tags.length === 0) {
            container.innerHTML = '<span style="color: #999; font-style: italic;">No tags from other conversations yet</span>';
        } else {
            // Show unique tags only
            const uniqueTags = [...new Set(tags)];
            container.innerHTML = uniqueTags.slice(0, 20).map(tag => 
                `<span class="tag" onclick="window.app.addTagFromSuggested('${tag}')">${tag}</span>`
            ).join('');
        }
    }

    addTagFromSuggested(tag) {
        const input = document.getElementById('tag-input');
        const currentValue = input.value.trim();
        
        // Check if tag already exists in input
        const currentTags = currentValue.split(',').map(t => t.trim()).filter(t => t);
        if (!currentTags.includes(tag)) {
            if (currentValue) {
                input.value = currentValue + ', ' + tag;
            } else {
                input.value = tag;
            }
        }
        
        // Visual feedback
        const suggestionElement = event.target;
        suggestionElement.classList.add('selected');
        setTimeout(() => suggestionElement.classList.remove('selected'), 500);
    }

    removeTagFromCurrent(tag) {
        // Remove tag immediately from current conversation
        this.removeSingleTag(tag);
    }

    async removeTagFromConversation(conversationId, tag) {
        try {
            const response = await fetch(`/api/conversations/${conversationId}/tags`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ tag: tag })
            });
            
            if (response.ok) {
                console.log(`Successfully removed tag "${tag}" from conversation ${conversationId}`);
                
                // Optimistically update UI immediately
                const tagElement = document.querySelector(`[onclick*="${conversationId}"][onclick*="${tag}"]`)?.closest('.tag');
                if (tagElement) {
                    tagElement.remove();
                }
                
                // Refresh the conversation list after a small delay to ensure database consistency
                setTimeout(() => {
                    this.loadConversations();
                }, 100);
            } else {
                const errorData = await response.json();
                console.error('Failed to remove tag:', errorData);
                alert(`Failed to remove tag: ${errorData.error || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Error removing tag from conversation:', error);
            alert('Failed to remove tag: Network error');
        }
    }

    async removeSingleTag(tag) {
        try {
            const response = await fetch(`/api/conversations/${this.currentConversationId}/tags`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ tag: tag })
            });
            
            if (response.ok) {
                this.showMessage('Tag removed successfully', 'success');
                await this.loadTagsForModal(); // Refresh the modal
                this.loadConversations(); // Refresh conversation list
            } else {
                throw new Error('Failed to remove tag');
            }
        } catch (error) {
            console.error('Error removing tag:', error);
            this.showError('Failed to remove tag');
        }
    }

    handleTagInput(event) {
        if (event.key === 'Enter') {
            this.saveTags();
        }
    }

    async saveTags() {
        const tagInput = document.getElementById('tag-input').value;
        const tags = tagInput.split(',').map(tag => tag.trim()).filter(tag => tag);
        console.log(`DEBUG: Saving tags:`, tags, `for conversation:`, this.currentConversationId);
        
        if (tags.length === 0) {
            this.showError('Please enter at least one tag');
            return;
        }
        
        try {
            const response = await fetch(`/api/conversations/${this.currentConversationId}/tags`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ tags: tags })
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log(`DEBUG: Tags saved successfully:`, result);
                this.showMessage(`Added ${tags.length} tag(s) successfully`, 'success');
                this.closeTagModal();
                this.loadConversations(); // Refresh to show new tags
            } else {
                const errorData = await response.json();
                console.error(`DEBUG: Failed to save tags:`, errorData);
                throw new Error(errorData.error || 'Failed to save tags');
            }
        } catch (error) {
            console.error('Error saving tags:', error);
            this.showError('Failed to save tags: ' + error.message);
        }
    }

    closeTagModal() {
        document.getElementById('tag-modal').style.display = 'none';
        document.getElementById('tag-input').value = '';
    }

    // Export functionality
    async exportConversation() {
        if (!this.currentConversationId) {
            this.showError('Please select a conversation to export');
            return;
        }

        try {
            const response = await fetch(`/conversations/${this.currentConversationId}/messages`);
            const data = await response.json();
            
            const markdown = this.generateMarkdown(data);
            this.downloadMarkdown(markdown, data.conversation.title);
            
        } catch (error) {
            console.error('Export failed:', error);
            this.showError('Failed to export conversation');
        }
    }

    generateMarkdown(data) {
        let markdown = `# ${data.conversation.title}\n\n`;
        markdown += `**Model:** ${data.conversation.llm_model}\n`;
        markdown += `**Date:** ${this.formatDate(data.messages[0]?.timestamp)}\n\n`;
        markdown += `---\n\n`;

        data.messages.forEach(message => {
            const role = message.role === 'user' ? 'You' : 'Assistant';
            markdown += `## ${role}\n\n${message.content}\n\n`;
        });

        return markdown;
    }

    downloadMarkdown(content, filename) {
        const blob = new Blob([content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${filename.replace(/[^a-z0-9]/gi, '_')}.md`;
        a.click();
        URL.revokeObjectURL(url);
    }

    // File upload functionality
    setupFileUpload() {
        const fileInput = document.getElementById('file-input');
        const chatContainer = document.getElementById('chat-messages');
        
        // Drag and drop
        chatContainer.addEventListener('dragover', (e) => {
            e.preventDefault();
            chatContainer.classList.add('dragover');
        });
        
        chatContainer.addEventListener('dragleave', () => {
            chatContainer.classList.remove('dragover');
        });
        
        chatContainer.addEventListener('drop', (e) => {
            e.preventDefault();
            chatContainer.classList.remove('dragover');
            this.handleFileUpload({ target: { files: e.dataTransfer.files } });
        });
    }

    triggerFileUpload() {
        document.getElementById('file-input').click();
    }

    async handleFileUpload(event) {
        const files = Array.from(event.target.files);
        if (!this.currentConversationId) {
            this.showError('Please start or select a conversation before uploading files.');
            return;
        }
        if (!files.length) return;
        const formData = new FormData();
        files.forEach(file => formData.append('files', file));
        try {
            const response = await fetch(`/conversations/${this.currentConversationId}/attachments`, {
                method: 'POST',
                body: formData
            });
            if (!response.ok) throw new Error('Failed to upload files');
            const data = await response.json();
            if (data.attachments) {
                data.attachments.forEach(att => {
                    this.addAttachmentToChat(att);
                });
            }
        } catch (error) {
            this.showError('File upload failed.');
            console.error('File upload error:', error);
        }
    }

    addAttachmentToChat(attachment) {
        const container = document.getElementById('chat-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user new';
        // Extract just the filename for the /uploads route
        const filename = attachment.filename;
        messageDiv.innerHTML = `
            <div class="message-content">
                <a href="/uploads/${encodeURIComponent(filename)}" target="_blank">${filename}</a>
                <div class="message-time">${this.formatTime(attachment.created_at)}</div>
            </div>
        `;
        container.appendChild(messageDiv);
        this.scrollToBottom();
    }

    // Voice input functionality (Web Speech API only)
    setupVoiceInput() {
        // No setup needed for Web Speech API
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            console.warn('Speech recognition is not supported in this browser');
        }
    }

    async startVoiceInput() {
        alert('Mic button pressed!');
        console.log('Class startVoiceInput called');
        // Use Web Speech API for speech-to-text
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            this.showError('Speech recognition is not supported in this browser.');
            console.log('Speech recognition not supported in this browser.');
            return;
        }
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        recognition.lang = 'en-US';
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;
            
            const voiceBtn = document.getElementById('voice-btn');
            voiceBtn.classList.add('recording');
        console.log('Speech recognition started');

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            console.log('Speech recognition result:', transcript);
            const messageInput = document.getElementById('message-input');
            messageInput.value = transcript;
            messageInput.focus();
        };
        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.showError('Speech recognition error: ' + event.error);
        };
        recognition.onend = () => {
            console.log('Speech recognition ended');
                voiceBtn.classList.remove('recording');
        };
        recognition.start();
    }

    // Remove MediaRecorder and backend-based voice input methods
    stopVoiceInput() {}
    async transcribeAudio(audioBlob) {}

    // URL reference functionality
    async addUrlReference() {
        let url = prompt('Enter URL to extract content from:');
        if (!url) return;
        
        // Auto-add https if no protocol specified
        if (!url.match(/^https?:\/\//)) {
            url = 'https://' + url;
        }
        
        if (!this.isValidUrl(url)) {
            this.showError('Invalid URL format. Please check the URL and try again.');
            return;
        }
        
        if (!this.currentConversationId) {
            this.showError('Please start or select a conversation before adding URL content.');
            return;
        }
        
        try {
            const response = await fetch('/extract-url', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                url: url,
                    conversation_id: this.currentConversationId,
                    task_type: 'reference'  // Can be made configurable
                })
            });
            
            const data = await response.json();
            if (data.success) {
                this.showUrlUploadMessage(data.url, data.title, data.preview, data.word_count, data.task_type);
            } else {
                this.showError(data.error || 'Failed to extract URL content.');
            }
        } catch (error) {
            this.showError('Failed to extract URL content.');
            console.error('URL extraction error:', error);
        }
    }

    isValidUrl(string) {
        try {
            new URL(string);
            return true;
        } catch (_) {
            return false;
        }
    }

    extractDomain(url) {
        try {
            return new URL(url).hostname;
        } catch (_) {
            return url;
        }
    }

    renderUrlReferences() {
        // Implementation for showing URL references
        console.log('URL references:', this.urlReferences);
    }

    // Search conversations
    async searchConversations() {
        const query = document.getElementById('conversation-search').value.trim();
        console.log(`DEBUG: searchConversations called with query: "${query}"`);
        
        if (!query) {
            console.log('DEBUG: Empty query, reloading conversations');
            // If empty query, reload normal conversations and clear highlights
            this.loadConversations();
            this.clearSearchHighlights();
            return;
        }
        
        // Use client-side filtering for all tag searches
        // This preserves the tag display and highlighting
        console.log(`DEBUG: Using client-side filtering for query: "${query}"`);
        this.filterConversationsClientSide(query.toLowerCase());
        return;
        
        try {
            // Build search URL with project awareness
            let searchUrl = `/api/search/conversations?query=${encodeURIComponent(query)}`;
            if (this.currentProject && this.currentProject.id) {
                searchUrl += `&project_id=${this.currentProject.id}`;
            }
            
            const response = await fetch(searchUrl);
            const data = await response.json();
            
            if (data.success) {
                this.renderSearchResults(data.conversations, query);
            } else {
                console.error('Search failed:', data.error);
                this.showErrorNotification('Search failed: ' + data.error);
            }
        } catch (error) {
            console.error('Search error:', error);
            this.showErrorNotification('Search failed');
        }
    }
    
    filterConversationsClientSide(query) {
        const items = document.querySelectorAll('.conversation-item');
        console.log(`Filtering ${items.length} conversations for query: "${query}"`);
        
        items.forEach(item => {
            const titleElem = item.querySelector('.conversation-title');
            if (!titleElem) return; // Skip project items
            
            const title = titleElem.textContent.toLowerCase();
            const tagsContainer = item.querySelector('.conversation-tags');
            const tags = (tagsContainer?.textContent || '').toLowerCase();
            
            console.log(`Conversation: "${title}", Tags: "${tags}"`);
            console.log(`Title match: ${title.includes(query)}, Tags match: ${tags.includes(query)}`);
            
            if (title.includes(query) || tags.includes(query)) {
                console.log(`MATCH FOUND: Showing conversation "${title}"`);
                item.style.display = 'block';
                
                // Highlight matching tags
                if (tagsContainer && tags.includes(query)) {
                    const tagElements = tagsContainer.querySelectorAll('.tag');
                    tagElements.forEach(tagElem => {
                        const tagText = tagElem.textContent.toLowerCase();
                        if (tagText.includes(query)) {
                            tagElem.classList.add('tag-match');
                            // Add highlighting within the tag
                            const originalText = tagElem.textContent;
                            const regex = new RegExp(`(${query})`, 'gi');
                            tagElem.innerHTML = originalText.replace(regex, '<mark>$1</mark>');
                        } else {
                            tagElem.classList.remove('tag-match');
                            tagElem.innerHTML = tagElem.textContent; // Remove any existing highlights
                        }
                    });
                }
            } else {
                item.style.display = 'none';
            }
        });
    }
    
    clearSearchHighlights() {
        const tagElements = document.querySelectorAll('.conversation-tags .tag');
        tagElements.forEach(tagElem => {
            tagElem.classList.remove('tag-match');
            // Remove any mark tags but preserve the text content
            tagElem.innerHTML = tagElem.textContent;
        });
    }
    
    renderSearchResults(conversations, query) {
        const container = document.querySelector('.conversations-list');
        
        if (conversations.length === 0) {
            container.innerHTML = `
                <div style="padding: 20px; text-align: center; color: #666; font-style: italic;">
                    No conversations found for "${query}"
                    ${this.currentProject ? ` in ${this.currentProject.name}` : ''}
                </div>
            `;
            return;
        }
        
        container.innerHTML = conversations.map(conv => {
            const isActive = this.currentConversationId === conv.id;
            
            // Highlight matching tags and build tags display
            const tags = conv.tags.length > 0 ? 
                `<div class="conversation-tags">
                    ${conv.tags.map(tag => {
                        const isMatch = tag.toLowerCase().includes(query.toLowerCase());
                        const highlightedTag = isMatch ? tag.replace(new RegExp(`(${query})`, 'gi'), '<mark>$1</mark>') : tag;
                        return `<span class="tag${isMatch ? ' tag-match' : ''}">${highlightedTag}</span>`;
                    }).join('')}
                </div>` : '';
            
            // Show snippets with highlighted query terms
            const snippets = conv.snippets.map(snippet => {
                let content = snippet.content;
                // Highlight search terms (simple highlighting)
                const regex = new RegExp(`(${query})`, 'gi');
                content = content.replace(regex, '<mark>$1</mark>');
                
                return `<div class="search-snippet" style="font-size: 11px; color: #666; margin-top: 4px; line-height: 1.3;">
                    ${snippet.role === 'title' ? '<strong>Title:</strong> ' : 
                      snippet.role === 'user' ? '<strong>You:</strong> ' : '<strong>AI:</strong> '}
                    ${content}
                </div>`;
            }).join('');
            
            return `
                <div class="conversation-item ${isActive ? 'active' : ''}" onclick="window.app.loadConversation('${conv.id}')">
                    <div class="conversation-title">${conv.title}</div>
                    <div class="conversation-meta">
                        <span>${new Date(conv.updated_at).toLocaleDateString()}</span>
                    </div>
                    ${tags}
                    ${snippets}
                </div>
            `;
        }).join('');
    }

    // Input handling
    handleInputKeydown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            this.sendMessage();
        }
    }

    handleInputChange() {
        this.autoResizeTextarea();
        // No type-ahead search suggestions
        // Previously triggered showSearchSuggestions here
            this.hideSearchSuggestions();
    }

    showSearchSuggestions(query) {
        // No-op: type-ahead suggestions removed
    }

    hideSearchSuggestions() {
        document.getElementById('kb-search-results').style.display = 'none';
    }

    // Utility functions
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays} days ago`;
        
        return date.toLocaleDateString();
    }

    formatTime(dateString) {
        return new Date(dateString).toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }

    scrollToBottom() {
        const container = document.getElementById('chat-messages');
        container.scrollTop = container.scrollHeight;
    }

    showError(message) {
        console.error(message);
        
        // Display error as a message in the chat
        const container = document.getElementById('chat-messages');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'message assistant error';
        errorDiv.innerHTML = `
            <div class="message-content">
                <div class="error-message">
                    <i class="fas fa-exclamation-triangle" style="color: #f44336; margin-right: 8px;"></i>
                    <strong>Error:</strong> ${message}
                </div>
            </div>
        `;
        container.appendChild(errorDiv);
        this.scrollToBottom();
    }

    updateUsageIndicator(freeAccess) {
        const existingIndicator = document.getElementById('usage-indicator');
        if (existingIndicator) {
            existingIndicator.remove();
        }

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
    }
}

// --- Add at the top of the file, before class KnowledgeBaseApp ---
KnowledgeBaseApp.prototype.showNewProjectInput = function() {
    this.addingProject = true;
    this.loadProjects();
};

KnowledgeBaseApp.prototype.toggleProjects = function() {
    const section = document.getElementById('projects-section');
    const toggleBtn = document.getElementById('toggle-projects-btn');
    if (section && toggleBtn) {
        section.classList.toggle('collapsed');
        toggleBtn.textContent = section.classList.contains('collapsed') ? '► Projects' : '▼ Projects';
    }
};

KnowledgeBaseApp.prototype.openSettingsModal = async function() {
    const modal = document.getElementById('settings-modal');
    modal.style.display = 'flex';
    try {
        // Call the HTML-based debugging functions instead of API-based ones
        // Get current time range selection
        const timeRange = document.getElementById('dashboard-time-range')?.value || '30';
        
        // Don't call updateDashboardData - it breaks the charts
        
        // Show usage tab by default
        if (typeof showTab === 'function') {
            showTab('usage');
        }
    } catch (e) {
        console.error('Error loading dashboard data:', e);
    }
};

// New dashboard rendering functions
KnowledgeBaseApp.prototype.renderQuickStats = async function() {
    try {
        const response = await fetch('/llm-usage-stats');
        const data = await response.json();
        
        if (data.stats) {
            const activeModels = data.stats.length;
            const totalRequests = data.stats.reduce((sum, r) => sum + r.calls, 0);
            const totalTokens = data.stats.reduce((sum, r) => sum + r.total_tokens, 0);
            
            // Format large numbers
            const formatNumber = (num) => {
                if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
                if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
                return num.toString();
            };
            
            // Update stats
            document.getElementById('stat-active-models').textContent = activeModels;
            document.getElementById('stat-total-requests').textContent = formatNumber(totalRequests);
            document.getElementById('stat-avg-response').textContent = '245ms'; // Mock data for now
            document.getElementById('stat-success-rate').textContent = '99.8%'; // Mock data for now
        }
    } catch (error) {
        console.error('Error loading quick stats:', error);
    }
};

KnowledgeBaseApp.prototype.renderUsageChart = async function() {
    try {
        const response = await fetch('/llm-usage-stats');
        const data = await response.json();
        
        if (data.stats && data.stats.length > 0) {
            const ctx = document.getElementById('llm-usage-chart').getContext('2d');
            if (window.usageChart) window.usageChart.destroy();
            
            window.usageChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.stats.map(r => r.model.replace('gpt-', 'GPT-').replace('claude-', 'Claude-')),
                    datasets: [{
                        label: 'API Calls (K)',
                        data: data.stats.map(r => Math.round(r.calls / 1000)),
                        backgroundColor: '#3b82f6',
                        borderRadius: 4,
                        categoryPercentage: 0.8,
                        barPercentage: 0.9
                    }, {
                        label: 'Tokens (M)',
                        data: data.stats.map(r => Math.round(r.total_tokens / 1000000)),
                        backgroundColor: '#8b5cf6',
                        borderRadius: 4,
                        categoryPercentage: 0.8,
                        barPercentage: 0.9
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                usePointStyle: true,
                                padding: 20
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: '#f3f4f6'
                            },
                            ticks: {
                                color: '#6b7280'
                            }
                        },
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                color: '#6b7280'
                            }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error loading usage chart:', error);
    }
};

KnowledgeBaseApp.prototype.renderActivityTimelineChart = async function() {
    try {
        const response = await fetch('/llm-usage-stats');
        const data = await response.json();
        
        if (data.timeseries && data.timeseries.length > 0) {
            const allDates = [...new Set(data.timeseries.map(r => r.date))].sort();
            const allModels = [...new Set(data.timeseries.map(r => r.model))];
            
            const modelColors = {
                'claude-3.5-sonnet': '#10b981',
                'gpt-4': '#3b82f6',
                'gemini-pro': '#f59e0b',
                'gpt-3.5-turbo': '#8b5cf6'
            };
            
            const datasets = allModels.map((model) => {
                const color = modelColors[model] || '#6b7280';
                return {
                    label: model.replace('gpt-', 'GPT-').replace('claude-', 'Claude-').replace('gemini-', 'Gemini-'),
                    data: allDates.map(date => {
                        const rec = data.timeseries.find(r => r.model === model && r.date === date);
                        return rec ? rec.calls : 0;
                    }),
                    borderColor: color,
                    backgroundColor: color + '20',
                    fill: false,
                    tension: 0.3,
                    pointRadius: 3,
                    pointHoverRadius: 6,
                    borderWidth: 3
                };
            });
            
            const ctx = document.getElementById('activity-timeline-chart').getContext('2d');
            if (window.activityChart) window.activityChart.destroy();
            
            window.activityChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: allDates.map(date => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })),
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                usePointStyle: true,
                                padding: 20
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: '#f3f4f6'
                            },
                            ticks: {
                                color: '#6b7280'
                            }
                        },
                        x: {
                            grid: {
                                color: '#f3f4f6'
                            },
                            ticks: {
                                color: '#6b7280'
                            }
                        }
                    },
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error loading activity timeline chart:', error);
    }
};

KnowledgeBaseApp.prototype.renderModelPerformanceTable = async function() {
    try {
        const response = await fetch('/llm-usage-stats');
        const data = await response.json();
        
        if (data.stats && data.stats.length > 0) {
            const modelInfo = {
                'claude-3.5-sonnet': { provider: 'Anthropic', status: 'active', costPer1k: 0.0015 },
                'claude-3-sonnet': { provider: 'Anthropic', status: 'active', costPer1k: 0.0030 },
                'claude-3-haiku': { provider: 'Anthropic', status: 'active', costPer1k: 0.0003 },
                'gpt-4': { provider: 'OpenAI', status: 'active', costPer1k: 0.0300 },
                'gpt-4-turbo': { provider: 'OpenAI', status: 'active', costPer1k: 0.0100 },
                'gpt-3.5-turbo': { provider: 'OpenAI', status: 'deprecated', costPer1k: 0.0005 },
                'gemini-pro': { provider: 'Google', status: 'limited', costPer1k: 0.0010 }
            };
            
            let tableHtml = `
                <table>
                    <thead>
                        <tr>
                            <th>Model</th>
                            <th>LLM</th>
                            <th>Tokens</th>
                            <th>Cost per K</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            
            data.stats.forEach(row => {
                const info = modelInfo[row.model] || { provider: 'Unknown', status: 'active', costPer1k: 0.001 };
                const statusClass = info.status.toLowerCase();
                const formattedTokens = row.total_tokens >= 1000000 ? 
                    (row.total_tokens / 1000000).toFixed(1) + 'M' : 
                    (row.total_tokens / 1000).toFixed(0) + 'K';
                
                tableHtml += `
                    <tr>
                        <td><strong>${row.model}</strong></td>
                        <td>${info.provider}</td>
                        <td>${formattedTokens}</td>
                        <td>$${info.costPer1k.toFixed(4)}</td>
                        <td><span class="status-badge ${statusClass}">${info.status}</span></td>
                    </tr>
                `;
            });
            
            tableHtml += '</tbody></table>';
            document.getElementById('model-performance-table').innerHTML = tableHtml;
        }
    } catch (error) {
        console.error('Error loading model performance table:', error);
    }
};

KnowledgeBaseApp.prototype.renderActivityLog = async function() {
    try {
        const [errResponse, statsResponse] = await Promise.all([
            fetch('/llm-error-log'),
            fetch('/llm-usage-stats')
        ]);
        
        const errData = await errResponse.json();
        const statsData = await statsResponse.json();
        
        let activities = [];
        
        // Add error logs as warning activities
        if (errData.errors && errData.errors.length > 0) {
            errData.errors.slice(0, 3).forEach(error => {
                activities.push({
                    type: 'warning',
                    icon: 'fas fa-exclamation-triangle',
                    title: `${error.model} API error`,
                    description: error.error_message,
                    time: new Date(error.timestamp).toLocaleString(),
                    badge: 'Warning'
                });
            });
        }
        
        // Add recent successful activities (mock data for demonstration)
        if (statsData.timeseries && statsData.timeseries.length > 0) {
            const recentActivity = statsData.timeseries.slice(-3);
            recentActivity.forEach(activity => {
                activities.push({
                    type: 'success',
                    icon: 'fas fa-check-circle',
                    title: `${activity.model} API request completed`,
                    description: `Successfully processed request with token usage: ${activity.tokens} tokens. Response time: 342ms. Cost: $${activity.cost.toFixed(5)}`,
                    time: new Date(activity.date).toLocaleString(),
                    badge: 'Success'
                });
            });
        }
        
        // Add deployment update (mock)
        activities.push({
            type: 'info',
            icon: 'fas fa-sync-alt',
            title: 'Model deployment updated',
            description: 'GPT-4-Turbo model successfully updated to latest version. Performance improvements: 15% faster response time.',
            time: new Date(Date.now() - 2 * 60 * 60 * 1000).toLocaleString(),
            badge: 'Info'
        });
        
        let logHtml = '';
        activities.slice(0, 5).forEach(activity => {
            logHtml += `
                <div class="activity-item">
                    <div class="activity-icon ${activity.type}">
                        <i class="${activity.icon}"></i>
                    </div>
                    <div class="activity-content">
                        <div class="activity-title">${activity.title}</div>
                        <div class="activity-description">${activity.description}</div>
                        <div class="activity-meta">
                            <span class="activity-badge ${activity.type}">${activity.badge}</span>
                        </div>
                    </div>
                    <div class="activity-time">${activity.time}</div>
                </div>
            `;
        });
        
        if (activities.length === 0) {
            logHtml = '<div class="activity-item"><div class="activity-content">No recent activity</div></div>';
        }
        
        document.getElementById('activity-log').innerHTML = logHtml;
    } catch (error) {
        console.error('Error loading activity log:', error);
    }
};

KnowledgeBaseApp.prototype.renderMonthlyTokenChart = async function() {
    try {
        const response = await fetch('/monthly-token-usage');
        const data = await response.json();
        
        if (data.monthly_stats && data.monthly_stats.length > 0) {
            // Organize data by month and model
            const months = [...new Set(data.monthly_stats.map(r => r.month))].sort();
            const models = [...new Set(data.monthly_stats.map(r => r.model))];
            
            const datasets = models.map((model, i) => {
                const colors = ['#36a2eb', '#ff6384', '#4bc0c0', '#9966ff', '#ff9f40', '#ffcd56', '#c9cbcf'];
                const color = colors[i % colors.length];
                return {
                    label: model,
                    data: months.map(month => {
                        const record = data.monthly_stats.find(r => r.model === model && r.month === month);
                        return record ? record.total_tokens : 0;
                    }),
                    backgroundColor: color + '80', // Add transparency
                    borderColor: color,
                    borderWidth: 2,
                    tension: 0.2
                };
            });
            
            const ctx = document.getElementById('monthly-tokens-chart').getContext('2d');
            if (window.monthlyTokensChart) window.monthlyTokensChart.destroy();
            window.monthlyTokensChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: months,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { 
                            display: true,
                            position: 'top'
                        },
                        title: { 
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Tokens'
                            }
                        }
                    },
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    }
                }
            });
        } else {
            document.getElementById('monthly-tokens-chart').style.display = 'none';
        }
    } catch (error) {
        console.error('Error rendering monthly token chart:', error);
    }
};

KnowledgeBaseApp.prototype.renderSessionTokenChart = async function() {
    try {
        const response = await fetch('/session-token-usage');
        const data = await response.json();
        
        if (data.session_stats && data.session_stats.length > 0) {
            const models = data.session_stats.map(r => r.model);
            const tokens = data.session_stats.map(r => r.total_tokens);
            const colors = ['#36a2eb', '#ff6384', '#4bc0c0', '#9966ff', '#ff9f40', '#ffcd56', '#c9cbcf'];
            
            const ctx = document.getElementById('session-tokens-chart').getContext('2d');
            if (window.sessionTokensChart) window.sessionTokensChart.destroy();
            window.sessionTokensChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: models,
                    datasets: [{
                        data: tokens,
                        backgroundColor: models.map((_, i) => colors[i % colors.length] + '80'),
                        borderColor: models.map((_, i) => colors[i % colors.length]),
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            position: 'right'
                        },
                        title: {
                            display: false
                        }
                    },
                    cutout: '50%'
                }
            });
        } else {
            // Show placeholder text when no data
            const canvas = document.getElementById('session-tokens-chart');
            const parent = canvas.parentElement;
            if (!parent.querySelector('.no-data-message')) {
                const message = document.createElement('div');
                message.className = 'no-data-message';
                message.style.cssText = 'text-align: center; color: #666; padding: 50px; font-style: italic;';
                message.textContent = 'No token usage data for current session';
                parent.appendChild(message);
                canvas.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error rendering session token chart:', error);
    }
};

KnowledgeBaseApp.prototype.closeSettingsModal = function() {
    document.getElementById('settings-modal').style.display = 'none';
};

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new KnowledgeBaseApp();
    document.getElementById('new-project-btn').onclick = function() {
        window.app.showNewProjectInput();
    };
    document.getElementById('new-chat-btn').onclick = function() {
        window.app.startNewChat();
    };
    document.getElementById('settings-btn').onclick = function() {
        window.app.openSettingsModal();
    };
});

// Global functions for HTML onclick handlers
function startNewChat() {
    window.app.startNewChat();
}

function sendMessage() {
    window.app.sendMessage();
}

function updateModel() {
    window.app.updateModel();
}

function searchKnowledgeBase() {
    window.app.searchKnowledgeBase();
}

function exportConversation() {
    window.app.exportConversation();
}

function tagConversation() {
    window.app.tagConversation();
}

function triggerFileUpload() {
    window.app.triggerFileUpload();
}

function startVoiceInput() {
    window.app.startVoiceInput();
}

function addUrlReference() {
    window.app.addUrlReference();
}

function handleFileUpload(event) {
    window.app.handleFileUpload(event);
}

function searchConversations() {
    window.app.searchConversations();
}

// Debounced search function to avoid too many API calls
let searchTimeout;
function debouncedSearchConversations() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        window.app.searchConversations();
    }, 300); // 300ms delay
}

function performKnowledgeBaseSearch() {
    window.app.performKnowledgeBaseSearch();
}

function closeSearchModal() {
    window.app.closeSearchModal();
}

function closeTagModal() {
    window.app.closeTagModal();
}

function handleInputKeydown(event) {
    window.app.handleInputKeydown(event);
}

function handleInputChange() {
    window.app.handleInputChange();
}

function handleTagInput(event) {
    window.app.handleTagInput(event);
}

function saveTags() {
    window.app.saveTags();
}

KnowledgeBaseApp.prototype.handleContextUpload = async function(event) {
    const files = Array.from(event.target.files);
    if (!this.currentConversationId) {
        this.showError('Please start or select a conversation before uploading context.');
        return;
    }
    if (!files.length) return;
    
    // Show uploading message for multiple files
    if (files.length > 1) {
        this.showMessage(`Uploading ${files.length} files...`, 'info');
    }
    
    let successCount = 0;
    let errorCount = 0;
    
    // Process each file individually
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const formData = new FormData();
        formData.append('file', file);
        formData.append('conversation_id', this.currentConversationId);
        
        try {
            const response = await fetch('/upload-context', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (data.success) {
                this.showContextUploadMessage(data.filename, data.preview, data.file_type, data.word_count, data.task_type);
                successCount++;
            } else {
                this.showError(`Failed to upload ${file.name}: ${data.error || 'Upload failed'}`);
                errorCount++;
            }
        } catch (error) {
            console.error(`Context upload error for ${file.name}:`, error);
            this.showError(`Failed to upload ${file.name}: Network error`);
            errorCount++;
        }
        
        // Small delay between uploads to avoid overwhelming the server
        if (i < files.length - 1) {
            await new Promise(resolve => setTimeout(resolve, 200));
        }
    }
    
    // Show summary message for multiple files
    if (files.length > 1) {
        if (successCount > 0 && errorCount === 0) {
            this.showMessage(`Successfully uploaded all ${successCount} files!`, 'success');
        } else if (successCount > 0 && errorCount > 0) {
            this.showMessage(`Uploaded ${successCount} files, ${errorCount} failed`, 'warning');
        } else if (errorCount > 0) {
            this.showError(`Failed to upload all ${errorCount} files`);
        }
    }
    
    // Refresh context panel if it's open
    if (this.contextPanelOpen) {
        await this.loadContextData();
    }
    
    // Clear the file input for next upload
    event.target.value = '';
};

KnowledgeBaseApp.prototype.showContextUploadMessage = function(filename, preview, fileType, wordCount, taskType) {
    const container = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user new';
    
    // Get appropriate icon based on file type
    const getFileIcon = (type) => {
        const icons = {
            'pdf': 'fas fa-file-pdf',
            'word': 'fas fa-file-word', 
            'text': 'fas fa-file-alt',
            'image': 'fas fa-file-image',
            'audio': 'fas fa-file-audio',
            'video': 'fas fa-file-video',
            'file': 'fas fa-file'
        };
        return icons[type] || 'fas fa-file';
    };
    
    const taskLabel = taskType === 'instructions' ? 'Guidelines' : 
                     taskType === 'summary' ? 'Document to summarize' :
                     taskType === 'analysis' ? 'Document to analyze' : 'Document';
    
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="file-upload-info">
                <i class="${getFileIcon(fileType)}" style="color: #4CAF50; margin-right: 8px;"></i>
                <strong>${taskLabel} uploaded:</strong> ${filename}
                ${wordCount ? `<span style="color: #666; font-size: 0.9em;"> (${wordCount} words)</span>` : ''}
            </div>
            <div class="context-preview">${preview.replace(/\n/g, '<br>')}</div>
        </div>
    `;
    container.appendChild(messageDiv);
    this.scrollToBottom();
};

KnowledgeBaseApp.prototype.showUrlUploadMessage = function(url, title, preview, wordCount, taskType) {
    const container = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user new';
    
    const taskLabel = taskType === 'instructions' ? 'Guidelines from URL' : 
                     taskType === 'summary' ? 'URL to summarize' :
                     taskType === 'analysis' ? 'URL to analyze' : 'URL Reference';
    
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="file-upload-info">
                <i class="fas fa-link" style="color: #2196F3; margin-right: 8px;"></i>
                <strong>${taskLabel}:</strong> <a href="${url}" target="_blank">${title}</a>
                ${wordCount ? `<span style="color: #666; font-size: 0.9em;"> (${wordCount} words)</span>` : ''}
            </div>
            <div class="context-preview">${preview.replace(/\n/g, '<br>')}</div>
        </div>
    `;
    container.appendChild(messageDiv);
    this.scrollToBottom();
};

// ==================== CONTEXT MANAGEMENT FUNCTIONS ====================

// Context panel state
KnowledgeBaseApp.prototype.contextPanelOpen = false;
KnowledgeBaseApp.prototype.contextItems = [];
KnowledgeBaseApp.prototype.conversationContext = [];
KnowledgeBaseApp.prototype.contextStats = { total_items: 0, total_tokens: 0 };

// Toggle context panel visibility
function toggleContextPanel() {
    const panel = document.getElementById('context-panel');
    const toggleBtn = document.getElementById('context-toggle-btn');
    
    if (window.app.contextPanelOpen) {
        panel.style.display = 'none';
        toggleBtn.classList.remove('active');
        window.app.contextPanelOpen = false;
    } else {
        panel.style.display = 'flex';
        toggleBtn.classList.add('active');
        window.app.contextPanelOpen = true;
        window.app.loadContextData();
    }
}

// Load all context data
KnowledgeBaseApp.prototype.loadContextData = async function() {
    try {
        // Load user context items
        await this.loadContextItems();
        
        // Load context stats
        await this.loadContextStats();
        
        // Load conversation context if we have a current conversation
        if (this.currentConversationId) {
            await this.loadConversationContext();
        }
        
    } catch (error) {
        console.error('Error loading context data:', error);
        this.showErrorNotification('Failed to load context data');
    }
};

// Load user context items
KnowledgeBaseApp.prototype.loadContextItems = async function() {
    try {
        const response = await fetch('/api/context');
        const data = await response.json();
        
        if (data.success) {
            this.contextItems = data.items;
            this.renderContextItems();
        } else {
            throw new Error(data.error || 'Failed to load context items');
        }
    } catch (error) {
        console.error('Error loading context items:', error);
        document.getElementById('context-items-list').innerHTML = 
            '<div class="empty-context">Failed to load context items</div>';
    }
};

// Load context statistics
KnowledgeBaseApp.prototype.loadContextStats = async function() {
    try {
        const response = await fetch('/api/context/stats');
        const data = await response.json();
        
        if (data.success) {
            this.contextStats = data.stats;
            this.renderContextStats();
        }
    } catch (error) {
        console.error('Error loading context stats:', error);
    }
};

// Load conversation context
KnowledgeBaseApp.prototype.loadConversationContext = async function() {
    if (!this.currentConversationId) return;
    
    try {
        const response = await fetch(`/api/conversation/${this.currentConversationId}/context`);
        const data = await response.json();
        
        if (data.success) {
            this.conversationContext = data.context;
            this.renderConversationContext();
            
            // Show conversation context section
            const section = document.getElementById('context-conversation-section');
            section.style.display = data.context.length > 0 ? 'block' : 'none';
        }
    } catch (error) {
        console.error('Error loading conversation context:', error);
    }
};

// Render context items list
KnowledgeBaseApp.prototype.renderContextItems = function() {
    const container = document.getElementById('context-items-list');
    
    if (this.contextItems.length === 0) {
        container.innerHTML = '<div class="empty-context">No context items found. Add some context to get started!</div>';
        return;
    }
    
    const contextInConversation = new Set(this.conversationContext.map(c => c.item_id));
    
    container.innerHTML = this.contextItems.map(item => `
        <div class="context-item-card ${contextInConversation.has(item.id) ? 'in-conversation' : ''}"
             onclick="window.app.showContextItemDetails('${item.id}')">
            <div class="context-item-header">
                <div class="context-item-name">${item.name}</div>
                <div class="context-item-type">${item.content_type}</div>
            </div>
            ${item.description ? `<div class="context-item-description">${item.description}</div>` : ''}
            <div class="context-item-meta">
                <div class="context-item-tokens">${item.token_count} tokens</div>
                <div class="context-item-actions">
                    ${contextInConversation.has(item.id) 
                        ? `<button class="context-item-action remove" onclick="event.stopPropagation(); window.app.removeContextFromConversation('${item.id}')" title="Remove from conversation">
                             <i class="fas fa-minus-circle"></i>
                           </button>`
                        : `<button class="context-item-action add" onclick="event.stopPropagation(); window.app.addContextToConversation('${item.id}')" title="Add to conversation">
                             <i class="fas fa-plus-circle"></i>
                           </button>`
                    }
                    <button class="context-item-action" onclick="event.stopPropagation(); window.app.editContextItem('${item.id}')" title="Edit">
                        <i class="fas fa-edit"></i>
                    </button>
                </div>
            </div>
        </div>
    `).join('');
};

// Render conversation context
KnowledgeBaseApp.prototype.renderConversationContext = function() {
    const container = document.getElementById('conversation-context-list');
    
    if (this.conversationContext.length === 0) {
        container.innerHTML = '<div class="empty-context">No context items added to this conversation yet.</div>';
        return;
    }
    
    container.innerHTML = this.conversationContext.map(context => `
        <div class="context-item-card in-conversation">
            <div class="context-item-header">
                <div class="context-item-name">${context.name}</div>
                <div class="context-item-type">${context.content_type}</div>
            </div>
            ${context.description ? `<div class="context-item-description">${context.description}</div>` : ''}
            <div class="context-item-meta">
                <div class="context-item-tokens">${context.token_count} tokens</div>
                <div class="context-item-actions">
                    <button class="context-item-action remove" onclick="window.app.removeContextFromConversation('${context.item_id}')" title="Remove from conversation">
                        <i class="fas fa-minus-circle"></i>
                    </button>
                </div>
            </div>
        </div>
    `).join('');
};

// Render context stats
KnowledgeBaseApp.prototype.renderContextStats = function() {
    document.getElementById('total-context-items').textContent = this.contextStats.total_items || 0;
    document.getElementById('total-context-tokens').textContent = this.contextStats.total_tokens || 0;
};

// Render filtered context items (used by search)
KnowledgeBaseApp.prototype.renderFilteredContextItems = function(filteredItems, searchTerm) {
    const container = document.getElementById('context-items-list');
    
    if (filteredItems.length === 0) {
        container.innerHTML = `<div class="empty-context">No context items found for "${searchTerm}"</div>`;
        return;
    }
    
    const contextInConversation = new Set(this.conversationContext.map(c => c.item_id));
    
    // Use same rendering logic but with filtered items
    container.innerHTML = filteredItems.map(item => `
        <div class="context-item-card ${contextInConversation.has(item.id) ? 'in-conversation' : ''}"
             onclick="window.app.showContextItemDetails('${item.id}')">
            <div class="context-item-header">
                <div class="context-item-name">${this.highlightSearchTerm(item.name, searchTerm)}</div>
                <div class="context-item-type">${item.content_type}</div>
            </div>
            ${item.description ? `<div class="context-item-description">${this.highlightSearchTerm(item.description, searchTerm)}</div>` : ''}
            <div class="context-item-meta">
                <div class="context-item-tokens">${item.token_count} tokens</div>
                <div class="context-item-actions">
                    ${contextInConversation.has(item.id) 
                        ? `<button class="context-item-action remove" onclick="event.stopPropagation(); window.app.removeContextFromConversation('${item.id}')" title="Remove from conversation">
                             <i class="fas fa-minus-circle"></i>
                           </button>`
                        : `<button class="context-item-action add" onclick="event.stopPropagation(); window.app.addContextToConversation('${item.id}')" title="Add to conversation">
                             <i class="fas fa-plus-circle"></i>
                           </button>`
                    }
                    <button class="context-item-action" onclick="event.stopPropagation(); window.app.editContextItem('${item.id}')" title="Edit">
                        <i class="fas fa-edit"></i>
                    </button>
                </div>
            </div>
        </div>
    `).join('');
};

// Search through context content using API
KnowledgeBaseApp.prototype.searchContextContentAPI = async function(searchTerm) {
    try {
        const response = await fetch(`/api/context/suggestions?query=${encodeURIComponent(searchTerm)}&limit=10`);
        const data = await response.json();
        
        if (data.success && data.suggestions.length > 0) {
            // Show API search results with content matching
            this.renderContentSearchResults(data.suggestions, searchTerm);
        } else {
            // Show no results message
            document.getElementById('context-items-list').innerHTML = 
                `<div class="empty-context">No context items found for "${searchTerm}"</div>`;
        }
    } catch (error) {
        console.error('Content search error:', error);
        document.getElementById('context-items-list').innerHTML = 
            '<div class="empty-context">Search failed. Please try again.</div>';
    }
};

// Render content search results
KnowledgeBaseApp.prototype.renderContentSearchResults = function(suggestions, searchTerm) {
    const container = document.getElementById('context-items-list');
    const contextInConversation = new Set(this.conversationContext.map(c => c.item_id));
    
    container.innerHTML = suggestions.map(item => `
        <div class="context-item-card ${contextInConversation.has(item.item_id) ? 'in-conversation' : ''}"
             onclick="window.app.showContextItemDetails('${item.item_id}')">
            <div class="context-item-header">
                <div class="context-item-name">${this.highlightSearchTerm(item.name, searchTerm)}</div>
                <div class="context-item-type">${item.content_type}</div>
            </div>
            ${item.description ? `<div class="context-item-description">${this.highlightSearchTerm(item.description, searchTerm)}</div>` : ''}
            <div class="search-relevance" style="font-size: 11px; color: #2563eb; margin: 4px 0;">
                Relevance: ${Math.round(item.relevance_score * 100) / 100} | Used: ${item.usage_count} times
            </div>
            <div class="context-item-meta">
                <div class="context-item-tokens">${item.token_count} tokens</div>
                <div class="context-item-actions">
                    ${contextInConversation.has(item.item_id) 
                        ? `<button class="context-item-action remove" onclick="event.stopPropagation(); window.app.removeContextFromConversation('${item.item_id}')" title="Remove from conversation">
                             <i class="fas fa-minus-circle"></i>
                           </button>`
                        : `<button class="context-item-action add" onclick="event.stopPropagation(); window.app.addContextToConversation('${item.item_id}')" title="Add to conversation">
                             <i class="fas fa-plus-circle"></i>
                           </button>`
                    }
                    <button class="context-item-action" onclick="event.stopPropagation(); window.app.editContextItem('${item.item_id}')" title="Edit">
                        <i class="fas fa-edit"></i>
                    </button>
                </div>
            </div>
        </div>
    `).join('');
};

// Highlight search terms in text
KnowledgeBaseApp.prototype.highlightSearchTerm = function(text, searchTerm) {
    if (!text || !searchTerm) return text || '';
    
    const regex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return text.replace(regex, '<mark style="background: #fff3cd; padding: 1px 2px; border-radius: 2px;">$1</mark>');
};

// Add context item to conversation
KnowledgeBaseApp.prototype.addContextToConversation = async function(contextItemId) {
    if (!this.currentConversationId) {
        this.showErrorNotification('Please start a conversation first');
        return;
    }
    
    try {
        const response = await fetch(`/api/conversation/${this.currentConversationId}/context/${contextItemId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ relevance_score: 1.0 })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Reload context data to update UI
            await this.loadConversationContext();
            this.renderContextItems(); // Re-render to update button states
            
            this.showSuccessNotification('Context added to conversation');
        } else {
            throw new Error(data.error || 'Failed to add context');
        }
    } catch (error) {
        console.error('Error adding context to conversation:', error);
        this.showErrorNotification('Failed to add context to conversation');
    }
};

// Remove context item from conversation
KnowledgeBaseApp.prototype.removeContextFromConversation = async function(contextItemId) {
    if (!this.currentConversationId) return;
    
    try {
        const response = await fetch(`/api/conversation/${this.currentConversationId}/context/${contextItemId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Reload context data to update UI
            await this.loadConversationContext();
            this.renderContextItems(); // Re-render to update button states
            
            this.showSuccessNotification('Context removed from conversation');
        } else {
            throw new Error(data.error || 'Failed to remove context');
        }
    } catch (error) {
        console.error('Error removing context from conversation:', error);
        this.showErrorNotification('Failed to remove context from conversation');
    }
};

// Show context item details (placeholder)
KnowledgeBaseApp.prototype.showContextItemDetails = function(contextItemId) {
    console.log('Show details for context item:', contextItemId);
    // This will be implemented in later increments
};

// Edit context item (placeholder)
KnowledgeBaseApp.prototype.editContextItem = function(contextItemId) {
    console.log('Edit context item:', contextItemId);
    // This will be implemented in later increments
};

// Search context items through content
function searchContextItems() {
    const searchTerm = document.getElementById('context-search').value.trim();
    
    if (!searchTerm) {
        // If empty search, show all items
        window.app.renderContextItems();
        return;
    }
    
    // Filter context items based on search term
    const filteredItems = window.app.contextItems.filter(item => {
        const searchLower = searchTerm.toLowerCase();
        
        // Search through multiple fields
        const name = (item.name || '').toLowerCase();
        const description = (item.description || '').toLowerCase();
        const contentType = (item.content_type || '').toLowerCase();
        const filename = (item.original_filename || '').toLowerCase();
        
        // Basic text matching
        if (name.includes(searchLower) || 
            description.includes(searchLower) || 
            contentType.includes(searchLower) || 
            filename.includes(searchLower)) {
            return true;
        }
        
        return false;
    });
    
    // If no items match basic fields, search through content text
    if (filteredItems.length === 0 && searchTerm.length >= 3) {
        window.app.searchContextContentAPI(searchTerm);
    } else {
        // Render filtered results
        window.app.renderFilteredContextItems(filteredItems, searchTerm);
    }
}

// Refresh context panel
function refreshContextPanel() {
    if (window.app.contextPanelOpen) {
        window.app.loadContextData();
    }
}

// Add new context (placeholder)
function addNewContext() {
    console.log('Add new context - will be implemented in later increments');
    // This will be implemented in later increments
}

// Override loadConversation to update context panel
const originalLoadConversation = KnowledgeBaseApp.prototype.loadConversation;
KnowledgeBaseApp.prototype.loadConversation = function(conversationId) {
    originalLoadConversation.call(this, conversationId);
    
    // Update conversation context if panel is open
    if (this.contextPanelOpen) {
        setTimeout(() => {
            this.loadConversationContext();
        }, 100);
    }
};

// ==================== MAIN CONTENT VIEW METHODS ====================

// Show conversations list view in main content area
KnowledgeBaseApp.prototype.showConversationsView = function() {
    this.currentView = 'conversations';
    const container = document.getElementById('chat-messages');
    
    // Update top bar to hide context toggle
    const contextToggle = document.getElementById('context-toggle-btn');
    if (contextToggle) contextToggle.style.display = 'none';
    
    container.innerHTML = `
        <div class="main-view">
            <nav class="breadcrumb">
                <span class="breadcrumb-item active">
                    <i class="fas fa-clock"></i>
                    All Conversations
                </span>
            </nav>
            
            <div class="view-header">
                <div class="view-title">
                    <i class="fas fa-clock"></i>
                    <h2>Recent Conversations</h2>
                </div>
                <div class="view-actions">
                    <button class="view-action-btn" onclick="window.app.startNewConversation()">
                        <i class="fas fa-plus"></i>
                        New Chat
                    </button>
                </div>
            </div>
            
            <div id="conversations-grid" class="conversations-grid">
                <div class="empty-state-large">
                    <i class="fas fa-spinner fa-spin"></i>
                    <h3>Loading conversations...</h3>
                </div>
            </div>
        </div>
    `;
    
    this.loadConversationsGrid();
};

// Show projects grid view in main content area
KnowledgeBaseApp.prototype.showProjectsView = function() {
    this.currentView = 'projects';
    const container = document.getElementById('chat-messages');
    
    // Update top bar to hide context toggle
    const contextToggle = document.getElementById('context-toggle-btn');
    if (contextToggle) contextToggle.style.display = 'none';
    
    container.innerHTML = `
        <div class="main-view">
            <nav class="breadcrumb">
                <span class="breadcrumb-item active">
                    <i class="fas fa-folder-open"></i>
                    All Projects
                </span>
            </nav>
            
            <div class="view-header">
                <div class="view-title">
                    <i class="fas fa-folder-open"></i>
                    <h2>Projects</h2>
                </div>
                <div class="view-actions">
                    <button class="view-action-btn" onclick="window.app.promptCreateNewProject()">
                        <i class="fas fa-plus"></i>
                        New Project
                    </button>
                </div>
            </div>
            
            <div id="projects-grid" class="projects-grid-view">
                <div class="empty-state-large">
                    <i class="fas fa-spinner fa-spin"></i>
                    <h3>Loading projects...</h3>
                </div>
            </div>
        </div>
    `;
    
    this.loadProjectsGrid();
};

// Show project conversations view
KnowledgeBaseApp.prototype.showProjectConversationsView = function(project) {
    this.currentView = 'project-conversations';
    this.currentViewProject = project;
    const container = document.getElementById('chat-messages');
    
    container.innerHTML = `
        <div class="main-view">
            <nav class="breadcrumb">
                <span class="breadcrumb-item" onclick="window.app.showProjectsView()">
                    <i class="fas fa-folder-open"></i>
                    Projects
                </span>
                <span class="breadcrumb-separator"><i class="fas fa-chevron-right"></i></span>
                <span class="breadcrumb-item active">
                    ${project.name}
                </span>
            </nav>
            
            <div class="view-header">
                <div class="view-title">
                    <i class="fas fa-folder-open"></i>
                    <h2>${project.name}</h2>
                </div>
                <div class="view-actions">
                    <button class="view-action-btn" onclick="window.app.startNewConversationInProject('${project.id}')">
                        <i class="fas fa-plus"></i>
                        New Chat
                    </button>
                    <button class="view-action-btn secondary" onclick="window.app.editProject('${project.id}', '${project.name.replace(/'/g, "\\'")}')">
                        <i class="fas fa-edit"></i>
                        Edit Project
                    </button>
                </div>
            </div>
            
            <div id="project-conversations-grid" class="conversations-grid">
                <div class="empty-state-large">
                    <i class="fas fa-spinner fa-spin"></i>
                    <h3>Loading conversations...</h3>
                </div>
            </div>
        </div>
    `;
    
    this.loadProjectConversationsGrid(project.id);
};

// Load conversations grid data
KnowledgeBaseApp.prototype.loadConversationsGrid = async function() {
    try {
        const response = await fetch('/conversations');
        const conversations = await response.json();
        this.renderConversationsGrid(conversations);
    } catch (error) {
        console.error('Failed to load conversations:', error);
        document.getElementById('conversations-grid').innerHTML = `
            <div class="empty-state-large">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Failed to load conversations</h3>
                <p>Please try again later.</p>
                <button class="view-action-btn" onclick="window.app.loadConversationsGrid()">
                    <i class="fas fa-refresh"></i>
                    Retry
                </button>
            </div>
        `;
    }
};

// Load projects grid data
KnowledgeBaseApp.prototype.loadProjectsGrid = async function() {
    try {
        const response = await fetch('/projects');
        const projects = await response.json();
        this.renderProjectsGrid(projects);
    } catch (error) {
        console.error('Failed to load projects:', error);
        document.getElementById('projects-grid').innerHTML = `
            <div class="empty-state-large">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Failed to load projects</h3>
                <p>Please try again later.</p>
                <button class="view-action-btn" onclick="window.app.loadProjectsGrid()">
                    <i class="fas fa-refresh"></i>
                    Retry
                </button>
            </div>
        `;
    }
};

// Load project conversations grid data
KnowledgeBaseApp.prototype.loadProjectConversationsGrid = async function(projectId) {
    try {
        const response = await fetch(`/conversations?project_id=${projectId}`);
        const conversations = await response.json();
        this.renderConversationsGrid(conversations, 'project-conversations-grid');
    } catch (error) {
        console.error('Failed to load project conversations:', error);
        document.getElementById('project-conversations-grid').innerHTML = `
            <div class="empty-state-large">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Failed to load conversations</h3>
                <p>Please try again later.</p>
                <button class="view-action-btn" onclick="window.app.loadProjectConversationsGrid('${projectId}')">
                    <i class="fas fa-refresh"></i>
                    Retry
                </button>
            </div>
        `;
    }
};

// Render conversations in grid format
KnowledgeBaseApp.prototype.renderConversationsGrid = function(conversations, containerId = 'conversations-grid') {
    const container = document.getElementById(containerId);
    
    if (!conversations.length) {
        container.innerHTML = `
            <div class="empty-state-large">
                <i class="fas fa-comments"></i>
                <h3>No conversations yet</h3>
                <p>Start your first conversation to see it here.</p>
                <button class="view-action-btn" onclick="window.app.startNewConversation()">
                    <i class="fas fa-plus"></i>
                    New Chat
                </button>
            </div>
        `;
        return;
    }
    
    const conversationCards = conversations.map(conv => {
        const tags = (conv.tags || []).map(tag => 
            `<span class="tag">${tag}</span>`
        ).join('');
        
        // Show message count as preview since we don't have message content in the API
        const messageCount = conv.message_count || 0;
        const preview = messageCount > 0 
            ? `${messageCount} message${messageCount !== 1 ? 's' : ''}`
            : 'No messages yet';
            
        return `
            <div class="conversation-card" onclick="window.app.openConversationFromGrid('${conv.id}')">
                <div class="conversation-card-header">
                    <h3 class="conversation-card-title">${conv.title}</h3>
                    <div class="conversation-card-actions">
                        <button class="conversation-card-action" onclick="event.stopPropagation(); window.app.editConversationTitle('${conv.id}', '${conv.title.replace(/'/g, '\\\'')}')" title="Edit">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="conversation-card-action" onclick="event.stopPropagation(); window.app.deleteConversation('${conv.id}')" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
                <div class="conversation-card-meta">
                    <span class="model-badge">${conv.llm_model}</span>
                    <span>•</span>
                    <span>${this.formatDate(conv.updated_at)}</span>
                </div>
                <div class="conversation-card-tags">${tags}</div>
                <div class="conversation-card-preview">${preview}</div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = conversationCards;
};

// Render projects in grid format
KnowledgeBaseApp.prototype.renderProjectsGrid = function(projects) {
    const container = document.getElementById('projects-grid');
    
    if (!projects.length) {
        container.innerHTML = `
            <div class="empty-state-large">
                <i class="fas fa-folder-open"></i>
                <h3>No projects yet</h3>
                <p>Create your first project to organize your conversations.</p>
                <button class="view-action-btn" onclick="window.app.promptCreateNewProject()">
                    <i class="fas fa-plus"></i>
                    New Project
                </button>
            </div>
        `;
        return;
    }
    
    const projectCards = projects.map(project => {
        const conversationCount = project.conversation_count || 0;
        
        return `
            <div class="project-card" onclick="window.app.openProject('${project.id}')">
                <div class="project-card-icon">
                    <i class="fas fa-folder-open"></i>
                </div>
                <h3 class="project-card-title">${project.name}</h3>
                <p class="project-card-count">${conversationCount} conversations</p>
                <div class="project-card-actions">
                    <button class="view-action-btn secondary" onclick="event.stopPropagation(); window.app.editProject('${project.id}', '${project.name.replace(/'/g, "\\'")}')" title="Edit Project">
                        <i class="fas fa-edit"></i>
                        Edit
                    </button>
                    <button class="view-action-btn secondary" onclick="event.stopPropagation(); window.app.deleteProject('${project.id}')" title="Delete Project">
                        <i class="fas fa-trash"></i>
                        Delete
                    </button>
                </div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = projectCards;
};

// Open conversation from grid view
KnowledgeBaseApp.prototype.openConversationFromGrid = function(conversationId) {
    // Preserve project context when opening conversation from project view
    const preserveProjectContext = this.currentViewProject;
    
    // Switch back to chat view and load the conversation
    this.showChatView();
    
    // Restore project context if we came from a project view
    if (preserveProjectContext) {
        this.currentViewProject = preserveProjectContext;
    }
    
    this.loadConversation(conversationId);
};

// Open project from grid view
KnowledgeBaseApp.prototype.openProject = function(projectId) {
    // Find project data
    const project = this.projects.find(p => p.id === projectId);
    if (project) {
        this.showProjectConversationsView(project);
    }
};

// Show normal chat view
KnowledgeBaseApp.prototype.showChatView = function() {
    this.currentView = 'chat';
    const container = document.getElementById('chat-messages');
    
    // Clear project context when switching to normal chat view
    this.currentViewProject = null;
    
    // Hide chat header when not in project context
    const chatHeader = document.getElementById('chat-header');
    if (chatHeader) chatHeader.style.display = 'none';
    
    // Show context toggle again
    const contextToggle = document.getElementById('context-toggle-btn');
    if (contextToggle) contextToggle.style.display = 'block';
    
    // Show empty state or current conversation
    if (!this.currentConversationId) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <i class="fas fa-comments"></i>
                </div>
                <h2 class="empty-state-title">New Conversation</h2>
                <p class="empty-state-description">Start a conversation or search your knowledge base.</p>
            </div>
        `;
    }
    // If there's a current conversation, it will be loaded by the caller
};

// Start new conversation (enhanced to work from any view)
KnowledgeBaseApp.prototype.startNewConversation = function() {
    this.showChatView();
    this.startNewChat();
};

// Start new conversation in specific project
KnowledgeBaseApp.prototype.startNewConversationInProject = function(projectId) {
    this.currentProject = this.projects.find(p => p.id === projectId);
    this.startNewConversation();
};

// Prompt for new project creation
KnowledgeBaseApp.prototype.promptCreateNewProject = function() {
    const name = prompt('Enter project name:');
    if (name && name.trim()) {
        this.createNewProject(name.trim());
    }
};

// Show success notification
KnowledgeBaseApp.prototype.showSuccessNotification = function(message) {
    const notification = document.createElement('div');
    notification.className = 'success-notification';
    notification.innerHTML = `
        <div class="error-content">
            <i class="fas fa-check-circle"></i>
            <span>${message}</span>
            <button class="close-error" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 3000);
};