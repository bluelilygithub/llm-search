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
        this.currentView = 'home'; // Set default view to home
        
        // Setup global error handling
        this.setupGlobalErrorHandling();
        
        // Initialize asynchronously
        this.init().catch(console.error);
    }

    async init() {
        this.loadProjects(); // Load projects on app initialization
        this.loadConversations();
        this.setupEventListeners();
        this.autoResizeTextarea();
        
        // Set "No Project" as active by default
        this.updateProjectSelectionUI(null);
        
        // Show home view by default instead of chat interface
        await this.showHomeView();
        
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
        const projectsList = document.getElementById('projects-list');
        if (!projectsList) return;
        
        // Clear existing projects
        projectsList.innerHTML = '';
        
        // Render each project
        projects.forEach(project => {
            const projectItem = document.createElement('div');
            projectItem.className = 'project-item';
            projectItem.setAttribute('data-project-id', project.id);
            projectItem.onclick = () => this.selectProject(project);
            
            projectItem.innerHTML = `
                <div class="project-content">
                    <div class="project-icon">
                        <i class="fas fa-folder"></i>
                    </div>
                    <div class="project-info">
                        <div class="project-title">${project.name}</div>
                        <div class="project-description">${project.description || 'No description'}</div>
                    </div>
                </div>
            `;
            
            projectsList.appendChild(projectItem);
        });
        
        // Update the active state based on current project
        this.updateProjectSelectionUI(this.currentProject);
    }

    showNewProjectPrompt() { /* no-op, replaced by inline input */ }

    // Methods called from the new HTML structure
    startNewConversation() {
        // Check if we're currently in a project context
        if (this.currentProject && this.currentProject.id) {
            // If we're in a project, start conversation in that project
            this.startNewConversationInProject(this.currentProject.id);
        } else if (this.currentViewProject && this.currentViewProject.id) {
            // If we're viewing a specific project, start conversation in that project
            this.startNewConversationInProject(this.currentViewProject.id);
        } else {
            // No project context, start a general conversation
            // First, ensure we're in chat view
            this.showChatView();
            
            this.currentConversationId = null;
            const chatMessages = document.getElementById('chat-messages');
            if (chatMessages) {
                chatMessages.innerHTML = `
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
            
            // Focus the input field
            const messageInput = document.getElementById('message-input');
            if (messageInput) {
                messageInput.focus();
            }
        }
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
            // Get CSRF token
            const csrfToken = document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || 
                             document.querySelector('input[name=csrf_token]')?.value;
            
            const response = await fetch(`/conversations/${conversationId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    title: newTitle,
                    csrf_token: csrfToken
                })
            });

            if (response.ok) {
                // Refresh both sidebar and main content area
                this.loadConversations();
                
                // If we're currently viewing conversations, refresh the grid
                if (this.currentView === 'conversations') {
                    await this.loadConversationsGrid();
                } else if (this.currentView === 'project-conversations') {
                    // If viewing project conversations, refresh that view
                    await this.loadProjectConversationsGrid(this.currentViewProject.id);
                }
                
                // If we're currently viewing this conversation in chat, update the header
                if (this.currentConversationId === conversationId && this.currentView === 'chat') {
                    const conversationTitle = document.getElementById('conversation-title');
                    if (conversationTitle) {
                        conversationTitle.textContent = newTitle;
                    }
                }
                
                // If we're currently viewing search results, refresh them to show updated titles
                if (this.currentView === 'search-results') {
                    const searchInput = document.getElementById('conversation-search');
                    if (searchInput && searchInput.value.trim()) {
                        // Re-run the search to refresh results
                        this.searchConversations();
                    }
                }
                
                // Show success notification
                this.showSuccessNotification('Conversation title updated successfully!');
            } else {
                const errorData = await response.json();
                console.error('Failed to update conversation title:', errorData.error);
                this.showError(`Failed to update conversation title: ${errorData.error || 'Unknown error'}`);
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
            // Get CSRF token
            const csrfToken = document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || 
                             document.querySelector('input[name=csrf_token]')?.value;
            
            const response = await fetch(`/conversations/${conversationId}`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    csrf_token: csrfToken
                })
            });

            if (response.ok) {
                if (this.currentConversationId === conversationId) {
                    this.startNewConversation();
                }
                
                // Refresh both sidebar and main content area
                this.loadConversations();
                
                // If we're currently viewing conversations, refresh the grid
                if (this.currentView === 'conversations') {
                    await this.loadConversationsGrid();
                } else if (this.currentView === 'project-conversations') {
                    // If viewing project conversations, refresh that view
                    await this.loadProjectConversationsGrid(this.currentViewProject.id);
                }
                
                // If we're currently viewing search results, refresh them
                if (this.currentView === 'search-results') {
                    const searchInput = document.getElementById('conversation-search');
                    if (searchInput && searchInput.value.trim()) {
                        // Re-run the search to refresh results
                        this.searchConversations();
                    }
                }
                
                // Show success notification
                this.showSuccessNotification('Conversation deleted successfully!');
            } else {
                const errorData = await response.json();
                console.error('Failed to delete conversation:', errorData.error);
                this.showError(`Failed to delete conversation: ${errorData.error || 'Unknown error'}`);
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
        try {
            // First, get the count of conversations associated with this project
            const conversationsResponse = await fetch(`/conversations?project_id=${projectId}`);
            const conversations = conversationsResponse.ok ? await conversationsResponse.json() : [];
            const conversationCount = conversations.length;
            
            // Get project name for better UX
            const project = this.projects?.find(p => p.id === projectId);
            const projectName = project?.name || 'this project';
            
            if (conversationCount === 0) {
                // Simple deletion if no conversations
                if (confirm(`Are you sure you want to delete "${projectName}"?\n\nThis project has no conversations.`)) {
                    await this.performProjectDeletion(projectId, false);
                }
            } else {
                // Enhanced deletion flow with conversation handling
                const deleteConversations = confirm(
                    `"${projectName}" has ${conversationCount} conversation${conversationCount > 1 ? 's' : ''} associated with it.\n\n` +
                    `Do you want to DELETE the conversations too?\n\n` +
                    `• Click "OK" to delete the project AND all ${conversationCount} conversation${conversationCount > 1 ? 's' : ''}\n` +
                    `• Click "Cancel" to keep the conversations but remove the project`
                );
                
                if (deleteConversations) {
                    // User wants to delete everything
                    if (confirm(`⚠️ FINAL CONFIRMATION ⚠️\n\nThis will permanently delete:\n• Project: "${projectName}"\n• ${conversationCount} conversation${conversationCount > 1 ? 's' : ''}\n\nThis cannot be undone. Are you sure?`)) {
                        await this.performProjectDeletion(projectId, true);
                    }
                } else {
                    // User wants to keep conversations but delete project
                    if (confirm(`Delete project "${projectName}" but keep the ${conversationCount} conversation${conversationCount > 1 ? 's' : ''}?\n\nThe conversation${conversationCount > 1 ? 's' : ''} will become unassigned and can be found in "All Conversations".`)) {
                        await this.performProjectDeletion(projectId, false);
                    }
                }
            }
            
        } catch (error) {
            console.error('Error during project deletion process:', error);
            alert('Failed to delete project. Please try again.');
        }
    }

    async performProjectDeletion(projectId, deleteConversations) {
        try {
            const url = `/projects/${projectId}${deleteConversations ? '?delete_conversations=true' : ''}`;
            const response = await fetch(url, {
                    method: 'DELETE'
                });

                if (response.ok) {
                    if (this.currentProject && this.currentProject.id === projectId) {
                        this.currentProject = null;
                    }
                    this.loadProjects();
                    this.loadConversations();
                    
                    // If currently viewing projects page, refresh the main content area too
                    if (this.currentView === 'projects') {
                        await this.loadProjectsGrid();
                    }
                    
                    // Show success notification
                const message = deleteConversations 
                    ? 'Project and all associated conversations deleted successfully!'
                    : 'Project deleted successfully! Conversations are now unassigned.';
                this.showSuccessNotification(message);
                
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

    async createProject(name) {
        if (!name) return;
        try {
            const response = await fetch('/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });
            if (!response.ok) throw new Error('Failed to create project');
            const project = await response.json();
            
            this.addingProject = false;
            await this.loadProjects();
            
            // Make the newly created project active immediately
            this.currentProject = project;
            this.currentViewProject = project;
            this.updateProjectSelectionUI(project);
            
            // If currently viewing projects page, refresh the main content area too
            if (this.currentView === 'projects') {
                await this.loadProjectsGrid();
            }
            
            // Show success notification with option to start chatting
            this.showSuccessNotification(`Project "${name}" created successfully! Ready to start chatting.`);
            
            // Automatically switch to chat view to encourage immediate usage
            setTimeout(() => {
                this.showChatView();
                this.startNewChat();
            }, 1000); // Small delay to let user see the success message
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
            
            // If currently viewing projects page, refresh the main content area too
            if (this.currentView === 'projects') {
                await this.loadProjectsGrid();
            }
            
            // Show success notification
            this.showSuccessNotification(`Project renamed to "${newName}" successfully!`);
        } catch (error) {
            console.error('Failed to rename project:', error);
            alert('Failed to rename project. Please try again.');
        }
    }

    selectProject(project) {
        // Only trigger if changing project
        const isNewProject = !this.currentProject || !project || this.currentProject.id !== project.id;
        this.currentProject = project;
        
        // Update the UI to show which project is selected
        this.updateProjectSelectionUI(project);
        
        this.loadProjects();
        this.loadConversations();
        if (isNewProject) {
            this.currentConversationId = null;
            
            // Ensure chat container exists before setting innerHTML
            const chatContainer = document.getElementById('chat-messages');
            if (!chatContainer) {
                console.warn('selectProject: Chat container not found, attempting to restore');
                
                // Preserve project context before restoring
                const preserveProject = this.currentProject;
                const preserveViewProject = this.currentViewProject;
                
                this.showChatView();
                
                // Restore project context after restoring chat view
                if (preserveProject) this.currentProject = preserveProject;
                if (preserveViewProject) this.currentViewProject = preserveViewProject;
                
                const retryContainer = document.getElementById('chat-messages');
                if (!retryContainer) {
                    console.error('selectProject: Still cannot find chat container');
                    return;
                }
                // Use the restored container
                chatContainer = retryContainer;
            }
            
            chatContainer.innerHTML = `
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

    updateProjectSelectionUI(selectedProject) {
        // Remove active class from all project items
        document.querySelectorAll('.project-item').forEach(item => {
            item.classList.remove('active');
        });
        
        // Add active class to selected project or "No Project"
        if (selectedProject) {
            const projectItem = document.querySelector(`[data-project-id="${selectedProject.id}"]`);
            if (projectItem) {
                projectItem.classList.add('active');
            }
        } else {
            // "No Project" is selected
            const noProjectItem = document.getElementById('no-project-item');
            if (noProjectItem) {
                noProjectItem.classList.add('active');
            }
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
            // Filter on frontend as a fallback (in case backend returns all)
            let filtered = conversations;
            if (this.currentProject && this.currentProject.id) {
                filtered = conversations.filter(conv => conv.project_id === this.currentProject.id);
            }
            this.renderConversations(filtered);
        } catch (error) {
            console.error('Failed to load conversations:', error);
        }
    }

    renderConversations(conversations) {
        const container = document.getElementById('conversations-list');
        container.innerHTML = '';

        conversations.forEach(conv => {
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
            
            // Add attachment count to meta info
            const messageCount = conv.message_count || 0;
            const attachmentCount = conv.attachment_count || 0;
            let metaInfo = `${conv.llm_model} • ${this.formatDate(conv.updated_at)}`;
            if (attachmentCount > 0) {
                metaInfo += ` • ${attachmentCount} attachment${attachmentCount !== 1 ? 's' : ''}`;
            }
            
            item.innerHTML = `
                <div class="conversation-content">
                    <div class="conversation-title">${conv.title}</div>
                    <div class="conversation-meta">
                        ${metaInfo}
                    </div>
                    <div class="conversation-tags">${tags}</div>
                </div>
                <div class="conversation-actions">
                    <button class="conversation-action-btn" onclick="event.stopPropagation(); window.app.editConversationTitle('${conv.id}', '${conv.title.replace(/'/g, '\\\'')}')" title="Edit">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="conversation-action-btn" onclick="event.stopPropagation(); window.app.deleteConversation('${conv.id}')" title="Delete">
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
            
            // Ensure we're in chat view with proper layout
            this.showChatView();
            
            // Ensure context button is visible
            this.ensureContextButtonVisible();
            
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
                const llmModelElement = document.getElementById('llm-model');
                if (llmModelElement) {
                    llmModelElement.value = this.selectedModel;
                }
            }
            
            // Update chat header with project and conversation context
            this.updateChatHeader(data.conversation);
            
            // Display uploaded files if any
            if (data.conversation.context_documents && data.conversation.context_documents.length > 0) {
                this.renderContextDocuments(data.conversation.context_documents);
            }
            
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

    goToHome() {
        this.clearProjectContext();
    }

    renderMessages(messages) {
        // Try to find the appropriate container
        let container = document.getElementById('chat-messages');
        
        // If we're in chat view but using main-content, the chat-messages div should exist now
        if (!container && this.currentView === 'chat') {
            container = document.getElementById('chat-messages');
        }
        
        // If still no container, fall back to main-content
        if (!container) {
            container = document.getElementById('main-content');
        }
        
        if (!container) {
            console.error('No suitable container found for rendering messages');
            return;
        }
        
        container.innerHTML = '';

        // Safety check: ensure messages is an array
        if (!messages || !Array.isArray(messages)) {
            console.warn('Messages is not an array or is undefined:', messages);
            return;
        }

        messages.forEach(message => {
            this.addMessageToChat(message, false); // false = existing message, don't generate follow-ups
        });

        this.scrollToBottom();
    }
    addMessageToChat(message, isNewMessage = false) {
        // Try to find the appropriate container
        let container = document.getElementById('chat-messages');
        
        // If we're in chat view but using main-content, the chat-messages div should exist now
        if (!container && this.currentView === 'chat') {
            container = document.getElementById('chat-messages');
        }
        
        // If still no container, fall back to main-content
        if (!container) {
            container = document.getElementById('main-content');
        }
        
        if (!container) {
            console.error('No suitable container found for adding message');
            return;
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.role} new`;
        
        // If assistant, include model in time
        let timeString = this.formatTime(message.timestamp);
        if (message.role === 'assistant' && this.selectedModel) {
            timeString += ` (${this.selectedModel})`;
        }
        
        // Initial message without follow-up questions
        // Add info button for assistant messages (for math curriculum sources)
        const infoButton = message.role === 'assistant' ? 
            `<button class="info-btn" onmouseenter="showInfoTooltip(this)" onmouseleave="hideInfoTooltip(this)">
                <i class="fas fa-info-circle"></i>
                <div class="info-tooltip">
                    <div class="tooltip-header">Curriculum Sources</div>
                    <div class="tooltip-content">
                        <div class="tooltip-link">
                            <strong>NSW Mathematics K-10 Curriculum</strong>
                            <br><a href="https://curriculum.nsw.edu.au/learning-areas/mathematics/mathematics-k-10-2022/overview" target="_blank">curriculum.nsw.edu.au</a>
                        </div>
                        <div class="tooltip-link">
                            <strong>Cluey Learning Year 10 Worksheets</strong>
                            <br><a href="https://go.clueylearning.com.au/maths-worksheets/year-10/" target="_blank">clueylearning.com.au</a>
                        </div>
                        <div class="tooltip-link">
                            <strong>Khan Academy</strong>
                            <br><a href="https://www.khanacademy.org/" target="_blank">khanacademy.org</a>
                        </div>
                    </div>
                </div>
            </button>` : '';
        
        // Add speaker button for assistant messages
        const speakerButton = message.role === 'assistant' ? 
            `<button class="speaker-btn" onclick="window.app.speakMessage(this, '${message.id || Date.now()}')" title="Listen to response">
                <i class="fas fa-volume-up"></i>
            </button>` : '';
        
        messageDiv.innerHTML = `
            <div class="message-content">
                ${this.formatMessageContent(message.content)}
                ${message.rag_used && message.rag_sources ? this.formatRAGSources(message.rag_sources) : ''}
                <div class="message-time">
                    ${timeString}
                    ${infoButton}
                    ${speakerButton}
                </div>
            </div>
        `;
        
        // Store message content for text-to-speech
        if (message.role === 'assistant') {
            messageDiv.dataset.messageText = message.content;
        }
        
        container.appendChild(messageDiv);
        this.scrollToBottom();
        
        // Generate follow-up questions ONLY for NEW assistant messages
        if (message.role === 'assistant' && isNewMessage) {
            this.addFollowUpQuestionsAsync(messageDiv, message.content);
        }
    }

    async addFollowUpQuestionsAsync(messageDiv, aiResponse) {
        try {
            // Show loading indicator for follow-up questions
            const loadingHtml = `
                <div class="follow-up-questions">
                    <div class="follow-up-title">
                        <i class="fas fa-spinner fa-spin"></i>
                        Generating follow-up questions...
                    </div>
                </div>
            `;
            messageDiv.querySelector('.message-content').insertAdjacentHTML('beforeend', loadingHtml);
            
            // Generate the questions
            const followUpQuestions = await this.generateFollowUpQuestions(aiResponse);
            
            // Remove loading indicator
            const loadingDiv = messageDiv.querySelector('.follow-up-questions');
            if (loadingDiv) {
                console.log('Removing loading indicator'); loadingDiv.remove();
            }
            
            // Add the actual follow-up questions
            if (followUpQuestions.length > 0) {
                const followUpHtml = `
                    <div class="follow-up-questions">
                        <div class="follow-up-title">
                            <i class="fas fa-lightbulb"></i>
                            Continue the conversation:
                        </div>
                        <div class="follow-up-buttons">
                            ${followUpQuestions.map(question => 
                                `<button class="follow-up-btn" onclick="window.app.askFollowUpQuestion('${this.escapeHtml(question)}')">
                                    ${question}
                                </button>`
                            ).join('')}
                        </div>
                    </div>
                `;
                messageDiv.querySelector('.message-content').insertAdjacentHTML('beforeend', followUpHtml);
            }
        } catch (error) {
            console.error('Error adding follow-up questions:', error);
            // Remove loading indicator if still present
            const loadingDiv = messageDiv.querySelector('.follow-up-questions');
            if (loadingDiv) {
                console.log('Removing loading indicator'); loadingDiv.remove();
            }
        }
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

    formatRAGSources(sources) {
        if (!sources || sources.length === 0) return '';
        
        const sourcesHtml = sources.map(source => 
            `<div class="rag-source">
                <i class="fas fa-file-alt"></i>
                <span class="source-document">${source.document}</span>
                <span class="source-score">(${(source.score * 100).toFixed(1)}% match)</span>
            </div>`
        ).join('');
        
        return `
            <div class="rag-sources">
                <div class="rag-indicator">
                    <i class="fas fa-database"></i>
                    <span>Knowledge Base Sources:</span>
                </div>
                <div class="rag-source-list">
                    ${sourcesHtml}
                </div>
            </div>
        `;
    }

    generateFollowUpQuestions(aiResponse) {
        // Generate contextually relevant follow-up questions by analyzing the conversation
        // This will be done asynchronously and return a promise
        return this.generateSmartFollowUpQuestions(aiResponse);
    }

    async generateSmartFollowUpQuestions(aiResponse) {
        try {
            // Detect if current project is a math project
            const isMathProject = this.currentProject && (
                (this.currentProject.math_level && this.currentProject.math_level.trim()) || 
                (this.currentProject.math_subject && this.currentProject.math_subject.trim())
            );
            
            console.log('🔍 Follow-up question debugging:');
            console.log('  - Current project:', this.currentProject);
            console.log('  - Math level:', this.currentProject?.math_level);
            console.log('  - Math subject:', this.currentProject?.math_subject);
            console.log('  - Is math project:', isMathProject);
            
            // Send a request to generate follow-up questions based only on the latest response
            const response = await fetch('/api/generate-followup-questions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    latest_response: aiResponse,
                    model: this.selectedModel || 'gpt-3.5-turbo',
                    project_id: this.currentProject?.id || null,
                    conversation_id: this.currentConversationId || null,
                    is_math_project: isMathProject
                })
            });

            if (response.ok) {
                const data = await response.json();
                return data.questions || [];
            } else {
                console.warn('Failed to generate follow-up questions, using fallback');
                return this.getFallbackQuestions(aiResponse);
            }
        } catch (error) {
            console.error('Error generating follow-up questions:', error);
            return this.getFallbackQuestions(aiResponse);
        }
    }

    getFallbackQuestions(aiResponse) {
        // Smarter fallback questions based on response analysis
        const response = aiResponse.toLowerCase();
        
        if (response.includes('step') || response.includes('process') || response.includes('how to')) {
            return [
                "What's the next step I should take?",
                "Can you elaborate on any of these steps?", 
                "What if I run into issues with this process?"
            ];
        } else if (response.includes('example') || response.includes('instance')) {
            return [
                "Can you show me another example?",
                "How would this work in a different scenario?",
                "What are some common variations of this?"
            ];
        } else if (response.includes('code') || response.includes('function') || response.includes('programming')) {
            return [
                "Can you explain how this code works?",
                "How would I modify this for my use case?",
                "What are some best practices to keep in mind?"
            ];
        } else {
            return [
                "Can you explain this further?",
                "What should I consider next?",
                "How does this apply to my situation?"
            ];
        }
    }

    escapeHtml(text) {
        // Escape HTML and quotes for safe use in onclick attributes
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    async askFollowUpQuestion(question) { console.log('Follow-up question:', question);
        
        const messageInput = document.querySelector('#message-input');
        if (messageInput) {
            messageInput.value = question;
            messageInput.focus();
            // Simulate Enter key press to send the message
            const event = new KeyboardEvent('keypress', {
                key: 'Enter',
                code: 'Enter',
                keyCode: 13,
                which: 13,
                bubbles: true
            });
            messageInput.dispatchEvent(event);
        }
    }

    async sendMessage() {
        // Check if we're in a chat context
        let chatContainer = document.getElementById('chat-messages');
        if (!chatContainer) {
            console.warn('Not in chat context, cannot send message');
            console.log('Current view:', this.currentView);
            console.log('Current project context:', this.currentProject);
            console.log('Current view project context:', this.currentViewProject);
            console.log('Chat container not found, attempting to restore chat view');
            
            // Determine the correct project context to preserve
            // Use currentViewProject if currentProject is null but we're in a project context
            const projectToPreserve = this.currentProject || this.currentViewProject;
            console.log('Project context to preserve:', projectToPreserve);
            
            this.showChatView();
            
            // Restore the correct project context after restoring chat view
            if (projectToPreserve) {
                this.currentProject = projectToPreserve;
                this.currentViewProject = projectToPreserve;
                console.log('Restored project context:', this.currentProject);
            }
            
            // Set up the chat view properly for new conversation
            const chatMessages = document.getElementById('chat-messages');
            if (chatMessages) {
                chatMessages.innerHTML = `
                    <div class="welcome-message">
                        <h3 id="new-conversation-title">New Conversation</h3>
                        <p>Start a conversation or search your knowledge base.</p>
                    </div>
                `;
            }
            
            // Update conversation title and header to show project context
            this.updateNewConversationTitle();
            
            // Update the chat header to show project context (breadcrumb)
            const chatHeader = document.getElementById('chat-header');
            if (chatHeader && this.currentProject) {
                chatHeader.style.display = 'block';
                const projectName = document.getElementById('project-name');
                const conversationTitle = document.getElementById('conversation-title');
                if (projectName) projectName.textContent = this.currentProject.name;
                if (conversationTitle) conversationTitle.textContent = 'New Conversation';
            }
            
            // Show the bottom input when automatically restoring chat view
            const bottomInput = document.querySelector('.bottom-input-container');
            if (bottomInput) {
                bottomInput.classList.remove('hidden');
            }
            
            // Try again after restoring
            const retryContainer = document.getElementById('chat-messages');
            if (!retryContainer) {
                console.error('Still cannot find chat container after showChatView');
                return;
            }
            // Use the restored container
            chatContainer = retryContainer;
        }
        
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
        
        // Track the last user message
        this.lastUserMessage = content;
        
        this.addMessageToChat(userMessage, true); // true = new message (though user messages don't get follow-ups anyway)
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
            const aiResponseData = await this.getAIResponse(content);
            
            // Extract response and RAG data
            const aiResponse = aiResponseData.response || aiResponseData;
            const ragUsed = aiResponseData.rag_used || false;
            const ragSources = aiResponseData.rag_sources || [];
            
            // Save AI message
            await this.saveMessage('assistant', aiResponse);

            // Add AI message to chat
            this.hideTypingIndicator();
            const aiMessage = {
                role: 'assistant',
                content: aiResponse,
                timestamp: new Date().toISOString(),
                rag_used: ragUsed,
                rag_sources: ragSources
            };
            this.addMessageToChat(aiMessage, true); // true = new AI message, generate follow-ups

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
        // Check both project contexts to ensure we capture the correct project
        const projectToUse = this.currentProject || this.currentViewProject;
        if (projectToUse && projectToUse.id) {
            body.project_id = projectToUse.id;
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
                const requestBody = {
                    message: userMessage,
                    model: this.selectedModel,
                    conversation_id: this.currentConversationId
                };
                
                // Add project_id if we're in a project context (for new conversations)
                const projectToUse = this.currentProject || this.currentViewProject;
                if (projectToUse && projectToUse.id && !this.currentConversationId) {
                    requestBody.project_id = projectToUse.id;
                }
                
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(requestBody)
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
                
                // Return both response and RAG data
                return {
                    response: data.response,
                    rag_used: data.rag_used || false,
                    rag_sources: data.rag_sources || []
                };
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
        if (!container) {
            console.warn('showImageEditingComplete: Chat container not found, attempting to restore');
            
            // Preserve project context before restoring
            const preserveProject = this.currentProject;
            const preserveViewProject = this.currentViewProject;
            
            this.showChatView();
            
            // Restore project context after restoring chat view
            if (preserveProject) this.currentProject = preserveProject;
            if (preserveViewProject) this.currentViewProject = preserveViewProject;
            
            const retryContainer = document.getElementById('chat-messages');
            if (!retryContainer) {
                console.error('showImageEditingComplete: Still cannot find chat container');
                return;
            }
            // Use the restored container
            container = retryContainer;
        }
        
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
        if (!container) {
            console.warn('Chat container not found, cannot show typing indicator');
            return;
        }
        
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
        
        // If we're currently in home view, ensure we transition to chat view
        if (this.currentView === 'home') {
            this.showChatView();
        }
        
        // Ensure chat container exists before setting innerHTML
        const chatContainer = document.getElementById('chat-messages');
        if (!chatContainer) {
            console.warn('startNewChat: Chat container not found, attempting to restore');
            
            // Preserve project context before restoring
            const preserveProject = this.currentProject;
            const preserveViewProject = this.currentViewProject;
            
            this.showChatView();
            
            // Restore project context after restoring chat view
            if (preserveProject) this.currentProject = preserveProject;
            if (preserveViewProject) this.currentViewProject = preserveViewProject;
            
            const retryContainer = document.getElementById('chat-messages');
            if (!retryContainer) {
                console.error('startNewChat: Still cannot find chat container');
                return;
            }
            // Use the restored container
            chatContainer = retryContainer;
        }
        

        
        chatContainer.innerHTML = `
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
        
        // Preserve current project context if we're in a project view
        if (this.currentViewProject) {
            this.currentProject = this.currentViewProject;
        }
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
        if (!container) {
            console.warn('addAttachmentToChat: Chat container not found, attempting to restore');
            
            // Preserve project context before restoring
            const preserveProject = this.currentProject;
            const preserveViewProject = this.currentViewProject;
            
            this.showChatView();
            
            // Restore project context after restoring chat view
            if (preserveProject) this.currentProject = preserveProject;
            if (preserveViewProject) this.currentViewProject = preserveViewProject;
            
            const retryContainer = document.getElementById('chat-messages');
            if (!retryContainer) {
                console.error('addAttachmentToChat: Still cannot find chat container');
                return;
            }
            // Use the restored container
            container = retryContainer;
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user new';
        
        // Extract just the filename for the /uploads route
        const filename = attachment.filename;
        const fileUrl = `/uploads/${encodeURIComponent(filename)}`;
        
        // Check if it's an image file
        const isImage = this.isImageFile(filename);
        
        let contentHtml = '';
        
        if (isImage) {
            // Display image as small thumbnail
            contentHtml = `
                <div class="message-content">
                    <div class="attachment-image">
                        <img src="${fileUrl}" alt="${filename}" 
                             style="width: 120px; height: 120px; object-fit: cover; border-radius: 8px; cursor: pointer; border: 1px solid var(--gray-200);"
                             onclick="window.open('${fileUrl}', '_blank')"
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
                        <div class="image-error-fallback" style="display: none;">
                            <i class="fas fa-image"></i>
                            <span>Failed to load</span>
                        </div>
                    </div>
                    <div class="attachment-info">
                        <span class="attachment-name">${filename}</span>
                        <a href="${fileUrl}" target="_blank" class="attachment-link">
                            <i class="fas fa-external-link-alt"></i> View full size
                        </a>
                    </div>
                    <div class="message-time">${this.formatTime(attachment.created_at)}</div>
                </div>
            `;
        } else {
            // Display as file attachment
            contentHtml = `
                <div class="message-content">
                    <div class="attachment-file">
                        <div class="attachment-icon">
                            <i class="fas fa-file"></i>
                        </div>
                        <div class="attachment-details">
                            <span class="attachment-name">${filename}</span>
                            <a href="${fileUrl}" target="_blank" class="attachment-link">
                                <i class="fas fa-download"></i> Download
                            </a>
                        </div>
                    </div>
                    <div class="message-time">${this.formatTime(attachment.created_at)}</div>
                </div>
            `;
        }
        
        messageDiv.innerHTML = contentHtml;
        container.appendChild(messageDiv);
        
        // Scroll to bottom with a small delay to ensure content is rendered
        setTimeout(() => {
            this.scrollToBottom();
        }, 100);
    }

    isImageFile(filename) {
        const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.tiff', '.ico'];
        const extension = filename.toLowerCase().substring(filename.lastIndexOf('.'));
        return imageExtensions.includes(extension);
    }

    // Voice input functionality (Web Speech API only)
    setupVoiceInput() {
        // No setup needed for Web Speech API
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            console.warn('Speech recognition is not supported in this browser');
        }
    }

    async startVoiceInput() {
        console.log('Class startVoiceInput called');
        // Use Web Speech API for speech-to-text
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            this.showError('Speech recognition is not supported in this browser.');
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        recognition.lang = (window.app?.userPreferences?.speechLang) || 'en-US';
        recognition.interimResults = true; // capture early audio
        recognition.maxAlternatives = 1;
        recognition.continuous = false;

        const voiceBtn = document.getElementById('voice-btn');
        if (voiceBtn) voiceBtn.classList.add('recording');

        // retry once on no-speech
        this._voiceRetryCount = this._voiceRetryCount || 0;

        recognition.onstart = () => {
            console.log('Speech recognition started');
        };

        recognition.onspeechstart = () => {
            console.log('Speech detected');
        };

        recognition.onresult = (event) => {
            this._voiceRetryCount = 0; // reset on success
            const transcript = event.results[0][0].transcript;
            const messageInput = document.getElementById('message-input');
            if (messageInput) {
                messageInput.value = transcript;
                messageInput.focus();
            }
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            if (event.error === 'no-speech' && this._voiceRetryCount < 1) {
                this._voiceRetryCount += 1;
                console.warn('Retrying speech recognition after no-speech...');
                setTimeout(() => {
                    try { recognition.start(); } catch (e) { console.error('Retry start failed', e); }
                }, 500);
                return;
            }
            this.showError('Speech recognition error: ' + event.error);
        };

        recognition.onend = () => {
            if (voiceBtn) voiceBtn.classList.remove('recording');
            console.log('Speech recognition ended');
        };

        // slight delay so the user can speak after clicking
        setTimeout(() => {
            try { recognition.start(); } catch (e) { console.error('Start failed', e); }
        }, 200);
    }

    // Remove MediaRecorder and backend-based voice input methods
    stopVoiceInput() {}

    // Text-to-Speech functionality
    speakMessage(button, messageId) {
        // Check if browser supports speech synthesis
        if (!('speechSynthesis' in window)) {
            this.showError('Text-to-speech is not supported in this browser.');
            return;
        }

        const messageDiv = button.closest('.message');
        const messageText = messageDiv.dataset.messageText;
        
        if (!messageText) {
            this.showError('No message text found');
            return;
        }

        // If already speaking this message, stop it
        if (this.currentSpeechMessageId === messageId && window.speechSynthesis.speaking) {
            window.speechSynthesis.cancel();
            button.classList.remove('speaking');
            button.innerHTML = '<i class="fas fa-volume-up"></i>';
            this.currentSpeechMessageId = null;
            return;
        }

        // Stop any ongoing speech
        window.speechSynthesis.cancel();

        // Remove speaking class from all buttons
        document.querySelectorAll('.speaker-btn.speaking').forEach(btn => {
            btn.classList.remove('speaking');
            btn.innerHTML = '<i class="fas fa-volume-up"></i>';
        });

        // Create speech utterance
        const utterance = new SpeechSynthesisUtterance(messageText);
        
        // Configure speech settings
        utterance.rate = 1.0;  // Normal speed
        utterance.pitch = 1.0; // Normal pitch
        utterance.volume = 1.0; // Full volume
        
        // Visual feedback when speaking starts
        utterance.onstart = () => {
            button.classList.add('speaking');
            button.innerHTML = '<i class="fas fa-stop"></i>';
            this.currentSpeechMessageId = messageId;
        };
        
        // Reset button when speech ends
        utterance.onend = () => {
            button.classList.remove('speaking');
            button.innerHTML = '<i class="fas fa-volume-up"></i>';
            this.currentSpeechMessageId = null;
        };
        
        // Handle errors
        utterance.onerror = (event) => {
            console.error('Speech synthesis error:', event);
            button.classList.remove('speaking');
            button.innerHTML = '<i class="fas fa-volume-up"></i>';
            this.currentSpeechMessageId = null;
        };

        // Start speaking
        window.speechSynthesis.speak(utterance);
    }

    // Stop all speech
    stopSpeech() {
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
            document.querySelectorAll('.speaker-btn.speaking').forEach(btn => {
                btn.classList.remove('speaking');
                btn.innerHTML = '<i class="fas fa-volume-up"></i>';
            });
            this.currentSpeechMessageId = null;
        }
    }
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
    }

    // Search conversations, projects, and context items
    async searchConversations() {
        const searchField = document.getElementById('conversation-search');
        const query = searchField ? searchField.value.trim() : '';
        
        // SAFETY: If query looks like an email, clear it and abort
        if (query.includes('@')) {
            console.warn('⚠️ Email detected in search field, clearing it');
            if (searchField) searchField.value = '';
            await this.clearSearchResults();
            return;
        }
        
        if (!query) {
            await this.clearSearchResults();
            return;
        }
        
        try {
            // Show loading state
            this.showSearchLoading();
            
            // Perform search across all content types
            const searchResults = await this.performComprehensiveSearch(query);
            
            // Display search results
            this.displaySearchResults(searchResults, query);
            
        } catch (error) {
            console.error('Search error:', error);
            this.showErrorNotification('Search failed: ' + error.message);
            await this.clearSearchResults();
        }
    }
    
    // Perform comprehensive search across conversations, projects, and context items
    async performComprehensiveSearch(query) {
        const results = {
            conversations: [],
            projects: [],
            contextItems: []
        };
        
        try {
            // Search conversations
            const convResponse = await fetch(`/api/search/conversations?query=${encodeURIComponent(query)}`);
            if (convResponse.ok) {
                const convData = await convResponse.json();
                if (convData.success) {
                    results.conversations = convData.conversations || [];
                }
            }
        } catch (error) {
            console.warn('Conversation search failed:', error);
        }
        
        try {
            // Search projects
            const projResponse = await fetch(`/api/search/projects?query=${encodeURIComponent(query)}`);
            if (projResponse.ok) {
                const projData = await projResponse.json();
                if (projData.success) {
                    results.projects = projData.projects || [];
                }
            }
        } catch (error) {
            console.warn('Project search failed:', error);
        }
        
        try {
            // Search context items
            const contextResponse = await fetch(`/api/search/context?query=${encodeURIComponent(query)}`);
            if (contextResponse.ok) {
                const contextData = await contextResponse.json();
                if (contextData.success) {
                    results.contextItems = contextData.context_items || [];
                }
            }
        } catch (error) {
            console.warn('Context search failed:', error);
        }
        
        return results;
    }
    // Display comprehensive search results
    displaySearchResults(results, query) {
        this.currentView = 'search-results';
        const mainContent = document.getElementById('main-content');
        const totalResults = results.conversations.length + results.projects.length + results.contextItems.length;
        
        if (totalResults === 0) {
            // Clear any existing search results or chat containers, preserve top bar
            const existingChatContainer = mainContent.querySelector('.chat-messages-container');
            if (existingChatContainer) {
                existingChatContainer.remove();
            }
            
            const existingSearchContainer = mainContent.querySelector('.search-results-container');
            if (existingSearchContainer) {
                existingSearchContainer.remove();
            }
            
            const searchResultsContainer = document.createElement('div');
            searchResultsContainer.className = 'search-results-container';
            searchResultsContainer.innerHTML = `
                <div class="search-header">
                    <h2>Search Results</h2>
                    <div class="search-summary">No results found for "${query}"</div>
                </div>
                <div class="search-results-empty">
                    <i class="fas fa-search"></i>
                    <p>No conversations, projects, or context items match your search.</p>
                    <button class="btn btn-primary" onclick="window.app.clearSearchResults()">
                        <i class="fas fa-arrow-left"></i> Back to Normal View
                    </button>
                </div>
            `;
            
            // Insert after the top bar
            const topBar = mainContent.querySelector('.top-bar');
            if (topBar) {
                topBar.insertAdjacentElement('afterend', searchResultsContainer);
            } else {
                mainContent.appendChild(searchResultsContainer);
            }
            return;
        }
        
        let resultsHtml = `
            <div class="search-results-container">
                <div class="search-header">
                    <h2>Search Results</h2>
                    <div class="search-summary">
                        Found ${totalResults} result${totalResults !== 1 ? 's' : ''} for "${query}"
                    </div>
                    <button class="btn btn-secondary" onclick="window.app.clearSearchResults()">
                        <i class="fas fa-arrow-left"></i> Back to Normal View
                    </button>
                </div>
        `;
        
        // Display conversations
        if (results.conversations.length > 0) {
            resultsHtml += `
                <div class="search-section">
                    <h3><i class="fas fa-comments"></i> Conversations (${results.conversations.length})</h3>
                    <div class="search-results-list">
                        ${results.conversations.map(conv => this.renderSearchResultConversation(conv, query)).join('')}
                    </div>
                </div>
            `;
        }
        
        // Display projects
        if (results.projects.length > 0) {
            resultsHtml += `
                <div class="search-section">
                    <h3><i class="fas fa-folder"></i> Projects (${results.projects.length})</h3>
                    <div class="search-results-list">
                        ${results.projects.map(proj => this.renderSearchResultProject(proj, query)).join('')}
                    </div>
                </div>
            `;
        }
        
        // Display context items
        if (results.contextItems.length > 0) {
            resultsHtml += `
                <div class="search-section">
                    <h3><i class="fas fa-file-alt"></i> Context Items (${results.contextItems.length})</h3>
                    <div class="search-results-list">
                        ${results.contextItems.map(item => this.renderSearchResultContextItem(item, query)).join('')}
                    </div>
                </div>
            `;
        }
        
        resultsHtml += '</div>';
        
        // Hide the entire content-area (which contains the chat) instead of removing it
        const contentArea = document.getElementById('content-area');
        if (contentArea) {
            contentArea.style.display = 'none';
        }
        
        // Also hide the bottom input area during search
        const bottomInput = mainContent.querySelector('.bottom-input');
        if (bottomInput) {
            bottomInput.style.display = 'none';
        }
        
        // Remove any existing search container
        const existingSearchContainer = mainContent.querySelector('.search-results-container');
        if (existingSearchContainer) {
            existingSearchContainer.remove();
        }
        
        const searchResultsContainer = document.createElement('div');
        searchResultsContainer.className = 'search-results-container';
        searchResultsContainer.innerHTML = resultsHtml;
        
        // Insert after the top bar
        const topBar = mainContent.querySelector('.top-bar');
        if (topBar) {
            topBar.insertAdjacentElement('afterend', searchResultsContainer);
        } else {
            mainContent.appendChild(searchResultsContainer);
        }
    }
    
    // Render individual search result conversation
    renderSearchResultConversation(conv, query) {
        const isActive = this.currentConversationId === conv.id;
        const tags = conv.tags && conv.tags.length > 0 ? 
            `<div class="search-result-tags">
                    ${conv.tags.map(tag => {
                        const isMatch = tag.toLowerCase().includes(query.toLowerCase());
                        const highlightedTag = isMatch ? tag.replace(new RegExp(`(${query})`, 'gi'), '<mark>$1</mark>') : tag;
                        return `<span class="tag${isMatch ? ' tag-match' : ''}">${highlightedTag}</span>`;
                    }).join('')}
                </div>` : '';
            
        return `
            <div class="search-result-item conversation-result ${isActive ? 'active' : ''}" onclick="window.app.openConversationFromSearch('${conv.id}')">
                <div class="search-result-icon">
                    <i class="fas fa-comments"></i>
                </div>
                <div class="search-result-content">
                    <div class="search-result-title">${this.highlightQuery(conv.title, query)}</div>
                    <div class="search-result-meta">
                        <span class="search-result-date">${new Date(conv.updated_at).toLocaleDateString()}</span>
                        ${conv.project_name ? `<span class="search-result-project">in ${conv.project_name}</span>` : ''}
                    </div>
                    ${tags}
                </div>
            </div>
        `;
    }
    
    // Render individual search result project
    renderSearchResultProject(proj, query) {
        return `
            <div class="search-result-item project-result" onclick="window.app.openProject('${proj.id}')">
                <div class="search-result-icon">
                    <i class="fas fa-folder"></i>
                </div>
                <div class="search-result-content">
                    <div class="search-result-title">${this.highlightQuery(proj.name, query)}</div>
                    <div class="search-result-meta">
                        <span class="search-result-date">Created ${new Date(proj.created_at).toLocaleDateString()}</span>
                        <span class="search-result-count">${proj.conversation_count || 0} conversations</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Render individual search result context item
    renderSearchResultContextItem(item, query) {
            return `
            <div class="search-result-item context-result" onclick="window.app.openConversationFromSearch('${item.conversation_id}')">
                <div class="search-result-icon">
                    <i class="fas fa-file-alt"></i>
                    </div>
                <div class="search-result-content">
                    <div class="search-result-title">${this.highlightQuery(item.filename, query)}</div>
                    <div class="search-result-meta">
                        <span class="search-result-type">${item.content_type || 'Document'}</span>
                        ${item.project_name ? `<span class="search-result-project">in ${item.project_name}</span>` : ''}
                    </div>
                    <div class="search-result-preview">${this.highlightQuery(item.content_preview || '', query)}</div>
                </div>
                </div>
            `;
    }
    
    // Highlight search query in text
    highlightQuery(text, query) {
        if (!text || !query) return text;
        const regex = new RegExp(`(${query})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }
    
    // Show search loading state
    showSearchLoading() {
        this.currentView = 'search-results';
        const mainContent = document.getElementById('main-content');
        
        // Hide the entire content-area instead of removing chat container
        const contentArea = document.getElementById('content-area');
        if (contentArea) {
            contentArea.style.display = 'none';
        }
        
        // Hide the bottom input area during search
        const bottomInput = mainContent.querySelector('.bottom-input');
        if (bottomInput) {
            bottomInput.style.display = 'none';
        }
        
        const searchResultsContainer = document.createElement('div');
        searchResultsContainer.className = 'search-results-container';
        searchResultsContainer.innerHTML = `
            <div class="search-header">
                <h2>Search Results</h2>
                <div class="search-summary">Searching...</div>
            </div>
            <div class="search-loading">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Searching conversations, projects, and context items...</p>
            </div>
        `;
        
        // Insert after the top bar
        const topBar = mainContent.querySelector('.top-bar');
        if (topBar) {
            topBar.insertAdjacentElement('afterend', searchResultsContainer);
        } else {
            mainContent.appendChild(searchResultsContainer);
        }
    }
    
    // Open conversation from search results (switches to chat view first)
    async openConversationFromSearch(conversationId) {
        // Set current view to chat BEFORE clearing search
        // This prevents showHomeView() from being called
        this.currentView = 'chat';
        
        // Clear search first
        await this.clearSearchResults();
        
        // Load the conversation directly - it will handle showing the correct view
        this.loadConversation(conversationId);
    }

    // Clear search results and restore normal view
    async clearSearchResults() {
        const searchInput = document.getElementById('conversation-search');
        if (searchInput) {
            searchInput.value = '';
        }
        
        // Ensure we're working with the main-content div for view restoration
        const mainContent = document.getElementById('main-content');
        if (!mainContent) {
            return;
        }
        
        // Restore normal view based on current state
        if (this.currentView === 'chat') {
            this.showChatView();
        } else if (this.currentView === 'conversations') {
            this.showConversationsView();
        } else {
            // Default to home view
            await this.showHomeView();
        }
    }

    // Input handling
    handleInputKeydown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            this.sendMessage();
        }
    }

    // Image paste functionality
    setupImagePaste() {
        const messageInput = document.getElementById('message-input');
        if (!messageInput) {
            console.warn('Message input not found for image paste setup');
            return;
        }

        // Add paste event listener
        messageInput.addEventListener('paste', (event) => {
            this.handleImagePaste(event);
        });

        console.log('✅ Image paste functionality initialized');
    }

    // Keyboard shortcuts functionality
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (event) => {
            this.handleKeyboardShortcut(event);
        });
        
        console.log('✅ Keyboard shortcuts initialized');
    }

    handleKeyboardShortcut(event) {
        // Don't trigger shortcuts when typing in inputs
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
            return;
        }

        const { ctrlKey, key, shiftKey } = event;

        // Ctrl+N - New conversation
        if (ctrlKey && key === 'n') {
            event.preventDefault();
            this.createNewConversation();
            return;
        }

        // Ctrl+/ - Open templates
        if (ctrlKey && key === '/') {
            event.preventDefault();
            this.openTemplatePicker();
            return;
        }

        // Ctrl+K - Focus search
        if (ctrlKey && key === 'k') {
            event.preventDefault();
            const searchInput = document.getElementById('conversation-search');
            if (searchInput) {
                searchInput.focus();
            }
            return;
        }

        // Ctrl+, - Open settings
        if (ctrlKey && key === ',') {
            event.preventDefault();
            this.openSettingsPanel();
            return;
        }

        // Escape - Close modals
        if (key === 'Escape') {
            this.closeAllModals();
            return;
        }

        // Ctrl+S - Export conversation
        if (ctrlKey && key === 's') {
            event.preventDefault();
            this.exportConversation();
            return;
        }

        // Ctrl+Shift+N - New project
        if (ctrlKey && shiftKey && key === 'N') {
            event.preventDefault();
            this.openProjectSetup();
            return;
        }

        // Ctrl+Shift+T - Open templates management
        if (ctrlKey && shiftKey && key === 'T') {
            event.preventDefault();
            this.openSettingsPanel();
            setTimeout(() => {
                this.showSettingsSection('templates');
            }, 100);
            return;
        }

        // Ctrl+? - Show keyboard shortcuts help
        if (ctrlKey && key === '?') {
            event.preventDefault();
            this.showKeyboardShortcutsHelp();
            return;
        }
    }

    closeAllModals() {
        // Close template picker
        const templateModal = document.getElementById('template-modal');
        if (templateModal && templateModal.style.display !== 'none') {
            this.closeTemplatePicker();
        }

        // Close template editor
        const templateEditor = document.getElementById('template-editor-modal');
        if (templateEditor && templateEditor.style.display !== 'none') {
            this.closeTemplateEditor();
        }

        // Close settings panel
        const settingsPanel = document.getElementById('settings-panel');
        if (settingsPanel && settingsPanel.style.display !== 'none') {
            this.closeSettingsPanel();
        }

        // Close other modals
        const modals = document.querySelectorAll('.modal, .template-modal, .settings-panel');
        modals.forEach(modal => {
            if (modal.style.display !== 'none') {
                modal.style.display = 'none';
            }
        });
    }

    showKeyboardShortcutsHelp() {
        const shortcuts = [
            { key: 'Ctrl+N', description: 'New conversation' },
            { key: 'Ctrl+/', description: 'Open templates' },
            { key: 'Ctrl+K', description: 'Focus search' },
            { key: 'Ctrl+,', description: 'Open settings' },
            { key: 'Ctrl+S', description: 'Export conversation' },
            { key: 'Ctrl+Shift+N', description: 'New project' },
            { key: 'Ctrl+Shift+T', description: 'Templates management' },
            { key: 'Ctrl+?', description: 'Show this help' },
            { key: 'Escape', description: 'Close modals' },
            { key: 'Enter', description: 'Send message' },
            { key: 'Shift+Enter', description: 'New line in message' }
        ];

        const helpHtml = `
            <div class="keyboard-shortcuts-help">
                <h3><i class="fas fa-keyboard"></i> Keyboard Shortcuts</h3>
                <div class="shortcuts-list">
                    ${shortcuts.map(shortcut => `
                        <div class="shortcut-item">
                            <kbd>${shortcut.key}</kbd>
                            <span>${shortcut.description}</span>
                        </div>
                    `).join('')}
                </div>
                <div class="shortcuts-footer">
                    <button class="btn-primary" onclick="this.closest('.modal').style.display='none'">
                        <i class="fas fa-times"></i> Close
                    </button>
                </div>
            </div>
        `;

        // Create modal if it doesn't exist
        let modal = document.getElementById('keyboard-shortcuts-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'keyboard-shortcuts-modal';
            modal.className = 'modal';
            modal.style.display = 'none';
            document.body.appendChild(modal);
        }

        modal.innerHTML = helpHtml;
        modal.style.display = 'flex';

        // Close on escape
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                modal.style.display = 'none';
                document.removeEventListener('keydown', handleEscape);
            }
        };
        document.addEventListener('keydown', handleEscape);
    }

    async handleImagePaste(event) {
        const clipboardItems = event.clipboardData?.items;
        if (!clipboardItems) return;

        let imageFound = false;
        
        for (let i = 0; i < clipboardItems.length; i++) {
            const item = clipboardItems[i];
            
            // Check if the pasted item is an image
            if (item.type.indexOf('image') === 0) {
                event.preventDefault(); // Prevent default paste behavior
                imageFound = true;
                
                const file = item.getAsFile();
                if (file) {
                    await this.processPastedImage(file);
                }
                break;
            }
        }
    }

    async processPastedImage(file) {
        const messageContainer = document.querySelector('.message-input-container');
        
        try {
            // Add visual feedback
            if (messageContainer) {
                messageContainer.classList.add('paste-processing');
            }
            
            // Show uploading indicator
            this.showMessage('📷 Processing pasted image...', 'info');
            
            // Validate file size (max 10MB for images)
            const maxSize = 10 * 1024 * 1024; // 10MB
            if (file.size > maxSize) {
                this.showError('Image too large. Maximum size: 10MB');
                return;
            }

            // Validate file type
            if (!file.type.startsWith('image/')) {
                this.showError('Please paste a valid image file');
                return;
            }

            // Check if we have an active conversation
            if (!this.currentConversationId) {
                this.showError('Please start or select a conversation before pasting images');
                return;
            }

            // Create FormData for upload
            const formData = new FormData();
            formData.append('files', file);
            
            // Upload the image
            const response = await fetch(`/conversations/${this.currentConversationId}/attachments`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Failed to upload image');
            }

            const data = await response.json();
            
            if (data.attachments) {
                // Add the image to chat
                data.attachments.forEach(att => {
                    this.addAttachmentToChat(att);
                });
                
                // Show success message
                this.showMessage(`✅ Image "${file.name}" uploaded successfully`, 'success');
            }

        } catch (error) {
            console.error('Image paste error:', error);
            this.showError('Failed to process pasted image: ' + error.message);
        } finally {
            // Remove visual feedback
            if (messageContainer) {
                messageContainer.classList.remove('paste-processing');
            }
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
        // Try to find the appropriate container
        let container = document.querySelector('.chat-messages-container');
        
        // If we're in chat view but using main-content, the chat-messages-container should exist now
        if (!container && this.currentView === 'chat') {
            container = document.querySelector('.chat-messages-container');
        }
        
        // If still no container, fall back to chat-messages
        if (!container) {
            container = document.getElementById('chat-messages');
        }
        
        // Final fallback to content-area
        if (!container) {
            container = document.getElementById('content-area');
        }
        
        if (container) {
            // Use smooth scrolling for better UX
            container.scrollTo({
                top: container.scrollHeight,
                behavior: 'smooth'
            });
        }
    }

    showError(message) {
        console.error(message);
        
        // Display error as a message in the chat
        let container = document.getElementById('chat-messages');
        
        // If we're in chat view but using main-content, the chat-messages div should exist now
        if (!container && this.currentView === 'chat') {
            container = document.getElementById('chat-messages');
        }
        
        // If still no container, fall back to main-content
        if (!container) {
            container = document.getElementById('main-content');
        }
        
        if (!container) {
            console.error('No suitable container found for showing error');
            return;
        }
        
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

    refreshDocumentDisplay() {
        if (!this.currentConversationId) {
            return;
        }
        
        // Fetch the latest conversation data to get updated documents
        fetch(`/conversations/${this.currentConversationId}/messages`)
            .then(response => response.json())
            .then(data => {
                if (data.conversation && data.conversation.context_documents) {
                    this.renderContextDocuments(data.conversation.context_documents);
                }
            })
            .catch(error => {
                console.error('Error refreshing document display:', error);
            });
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
        // Load all dashboard data in parallel
        await Promise.all([
            this.renderQuickStats(),
            this.renderUsageChart(),
            this.renderActivityTimelineChart(),
            this.renderModelPerformanceTable(),
            this.renderActivityLog()
        ]);
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

// Settings Panel Functions (for model toggles)
KnowledgeBaseApp.prototype.openSettingsPanel = function() {
    const panel = document.getElementById('settings-panel');
    if (!panel) {
        console.error('Settings panel element not found');
        return;
    }
    
    // Check if user is admin and add appropriate class
    fetch('/auth/status')
        .then(response => response.json())
        .then(data => {
            const isAdmin = data.authenticated && 
                           (data.user_role === 'super_admin' || data.user_role === 'admin' || data.user_type === 'admin');
            
            if (isAdmin) {
                panel.classList.add('admin-user');
            } else {
                panel.classList.remove('admin-user');
            }
        })
        .catch(error => {
            console.error('Error checking admin status:', error);
            // Default to non-admin if check fails
            panel.classList.remove('admin-user');
        });
    
        panel.classList.add('open');
        // Initialize settings when panel opens
        setTimeout(() => {
            // No longer loading models list in settings panel - use Model Management modal instead
            // this.loadModelsForSettingsPanel();
        // Show Users tab if admin
        window.showUsersTabIfAdmin();
        // Load account info
        window.loadAccountInfo();
        }, 200);
};

// Make openSettingsPanel available globally for onclick handlers
window.openSettingsPanel = function() {
    console.log('✅ window.openSettingsPanel called - function is loaded!');
    if (window.app) {
        window.app.openSettingsPanel();
    } else {
        console.error('❌ App not initialized yet - window.app is undefined');
    }
};

// Open account panel (simplified panel for regular users)
window.openAccountPanel = function() {
    console.log('✅ window.openAccountPanel called');
    const panel = document.getElementById('account-panel');
    console.log('🔍 Account panel element:', panel);
    if (panel) {
        console.log('✅ Account panel found, adding open class');
        panel.classList.add('open');
        console.log('✅ Panel classes after add:', panel.className);
        // Load account info
        setTimeout(() => {
            console.log('🔄 Loading account panel info');
            window.loadAccountPanelInfo();
        }, 100);
    } else {
        console.error('❌ Account panel not found in DOM');
        console.log('🔍 All elements with id containing "account":', document.querySelectorAll('[id*="account"]'));
    }
};

// Close account panel
window.closeAccountPanel = function() {
    const panel = document.getElementById('account-panel');
    if (panel) {
        panel.classList.remove('open');
    }
};

// Load account info into the account panel (simplified version for users)
window.loadAccountPanelInfo = async function() {
    const accountContent = document.getElementById('account-panel-info');
    const updateForm = document.getElementById('account-update-form');
    
    try {
        const response = await fetch('/auth/status');
        const data = await response.json();
        
        if (data.authenticated) {
            const username = data.username || 'User';
            const displayName = data.display_name || username;
            const email = data.email || 'Not provided';
            const firstName = data.first_name || '';
            const lastName = data.last_name || '';
            
            accountContent.innerHTML = `
                <div class="account-card">
                    <div class="account-section">
                        <h4><i class="fas fa-user-circle"></i> Profile Information</h4>
                        <div class="account-details">
                            <div class="detail-row">
                                <span class="detail-label">Display Name:</span>
                                <span class="detail-value"><strong>${displayName}</strong></span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Username:</span>
                                <span class="detail-value">${username}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Email:</span>
                                <span class="detail-value">${email}</span>
                            </div>
                            ${firstName || lastName ? `
                            <div class="detail-row">
                                <span class="detail-label">Name:</span>
                                <span class="detail-value">${firstName} ${lastName}</span>
                            </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
            
            // Show update form and populate it
            if (updateForm) {
                updateForm.style.display = 'block';
                document.getElementById('update-display-name').value = displayName;
            }
        } else {
            accountContent.innerHTML = `
                <div class="account-card">
                    <p style="color: #666;">Not authenticated</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading account info:', error);
        accountContent.innerHTML = `
            <div class="account-card">
                <p style="color: #e74c3c;">Failed to load account information.</p>
            </div>
        `;
    }
};

// Update user profile (display name and password)
window.updateUserProfile = async function() {
    const displayName = document.getElementById('update-display-name').value.trim();
    const currentPassword = document.getElementById('update-current-password').value;
    const newPassword = document.getElementById('update-new-password').value;
    const confirmPassword = document.getElementById('update-confirm-password').value;
    const messageDiv = document.getElementById('update-message');
    
    // Validation
    if (!displayName) {
        messageDiv.style.display = 'block';
        messageDiv.style.color = '#e74c3c';
        messageDiv.innerHTML = '<i class="fas fa-exclamation-circle"></i> Display name is required';
        return;
    }
    
    if (!currentPassword) {
        messageDiv.style.display = 'block';
        messageDiv.style.color = '#e74c3c';
        messageDiv.innerHTML = '<i class="fas fa-exclamation-circle"></i> Current password is required';
        return;
    }
    
    // If changing password, validate new password
    if (newPassword || confirmPassword) {
        if (newPassword !== confirmPassword) {
            messageDiv.style.display = 'block';
            messageDiv.style.color = '#e74c3c';
            messageDiv.innerHTML = '<i class="fas fa-exclamation-circle"></i> New passwords do not match';
            return;
        }
        
        if (newPassword.length < 8) {
            messageDiv.style.display = 'block';
            messageDiv.style.color = '#e74c3c';
            messageDiv.innerHTML = '<i class="fas fa-exclamation-circle"></i> New password must be at least 8 characters';
            return;
        }
    }
    
    try {
        messageDiv.style.display = 'block';
        messageDiv.style.color = '#666';
        messageDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating profile...';
        
        const response = await fetch('/api/users/update-profile', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                display_name: displayName,
                current_password: currentPassword,
                new_password: newPassword || null
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            messageDiv.style.color = '#27ae60';
            messageDiv.innerHTML = '<i class="fas fa-check-circle"></i> Profile updated successfully!';
            
            // Clear password fields
            document.getElementById('update-current-password').value = '';
            document.getElementById('update-new-password').value = '';
            document.getElementById('update-confirm-password').value = '';
            
            // Reload account info after a delay
            setTimeout(() => {
                window.loadAccountPanelInfo();
                messageDiv.style.display = 'none';
            }, 2000);
        } else {
            messageDiv.style.color = '#e74c3c';
            messageDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${data.error || 'Failed to update profile'}`;
        }
    } catch (error) {
        console.error('Error updating profile:', error);
        messageDiv.style.display = 'block';
        messageDiv.style.color = '#e74c3c';
        messageDiv.innerHTML = '<i class="fas fa-exclamation-circle"></i> Error updating profile';
    }
};

// Toggle password visibility
window.togglePasswordVisibility = function(inputId) {
    const input = document.getElementById(inputId);
    const button = input.parentElement.querySelector('.password-toggle, .password-toggle-inline');
    const icon = button.querySelector('i');
    
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
};

// Update welcome messages with user's name
window.updateWelcomeMessages = function(displayName) {
    // Update all welcome headers
    const welcomeHeaders = document.querySelectorAll('h2:contains("Welcome to Your Knowledge Base")');
    welcomeHeaders.forEach(header => {
        if (header.textContent.includes('Welcome to')) {
            header.textContent = `Welcome to ${displayName}'s Knowledge Base`;
        }
    });
    
    // More robust selector
    document.querySelectorAll('h2').forEach(header => {
        if (header.textContent.trim() === 'Welcome to Your Knowledge Base') {
            header.textContent = `Welcome to ${displayName}'s Knowledge Base`;
        }
    });
    
    // Update empty state descriptions
    document.querySelectorAll('.empty-state-description').forEach(desc => {
        if (desc.textContent.includes('Start a conversation')) {
            desc.textContent = `Hi ${displayName}! Start a conversation or search your knowledge base.`;
        }
    });
    
    // Store the display name globally for use in AI responses
    window.userDisplayName = displayName;
};

// Make openSettingsModal globally available for admin users
window.openSettingsModal = function() {
    if (window.app && window.app.openSettingsModal) {
        window.app.openSettingsModal();
    } else {
        console.error('❌ App not initialized yet - window.app is undefined');
    }
};

// Open settings panel for regular users (profile section)
window.openUserSettings = function() {
    if (window.app && window.app.openSettingsPanel) {
        window.app.openSettingsPanel();
        // Ensure profile section is active
        setTimeout(() => {
            showSettingsSection('account');
        }, 100);
    } else {
        console.error('❌ App not initialized yet - window.app is undefined');
    }
};

// Fallback function for editProjectTemplate in case of loading issues
if (typeof window.editProjectTemplate === 'undefined') {
    window.editProjectTemplate = function(projectId) {
        console.log('🔄 Fallback editProjectTemplate called with projectId:', projectId);
        
        // Retry mechanism - wait for showProjectEditModal to become available
        const maxRetries = 10;
        let retryCount = 0;
        
        const tryEditProject = () => {
            retryCount++;
            console.log(`🔄 Retry ${retryCount}/${maxRetries} - Checking for showProjectEditModal...`);
            console.log(`🔄 Script loaded flag:`, window.projectModalScriptLoaded);
            console.log(`🔄 testProjectModal available:`, typeof window.testProjectModal);
            
            if (typeof window.showProjectEditModal === 'function') {
                console.log('✅ showProjectEditModal found, calling it');
                window.showProjectEditModal(projectId);
            } else if (retryCount < maxRetries) {
                console.log(`⏳ showProjectEditModal not ready, retrying in 100ms...`);
                setTimeout(tryEditProject, 100);
            } else {
                console.error('❌ showProjectEditModal not available after retries');
                console.error('❌ Script loading issue detected');
                console.error('❌ Script loaded flag:', window.projectModalScriptLoaded);
                alert('Project editing functionality is not available. Please refresh the page and try again.');
            }
        };
        
        tryEditProject();
    };
    console.log('✅ Fallback editProjectTemplate function defined');
}

console.log('✅ Global window.openSettingsPanel, openAccountPanel, and openSettingsModal registered');

// Function to load dynamic models and API key status
KnowledgeBaseApp.prototype.loadDynamicModels = async function() {
    try {
        // Load all data in parallel
        await Promise.all([
            this.loadApiKeyStatus(),
            this.loadProviders(),
            this.loadCurrentModels()
        ]);
    } catch (error) {
        console.error('Error loading dynamic models:', error);
    }
};

// Load API key status
KnowledgeBaseApp.prototype.loadApiKeyStatus = async function() {
    const container = document.getElementById('api-keys-list');
    if (!container) return;
    
    try {
        container.innerHTML = '<div class="loading-models">Loading API key status...</div>';
        
        const response = await fetch('/api/api-keys/status');
        const apiKeys = await response.json();
        
        let html = '<div class="api-keys-grid">';
        Object.entries(apiKeys).forEach(([keyName, info]) => {
            const status = info.configured ? '✅ Configured' : '❌ Not Found';
            const statusClass = info.configured ? 'configured' : 'not-configured';
            
            html += `
                <div class="api-key-item ${statusClass}">
                    <div class="api-key-name">${keyName}</div>
                    <div class="api-key-provider">${info.provider}</div>
                    <div class="api-key-status">${status}</div>
                    <div class="api-key-models">${info.models_supported}</div>
                </div>
            `;
        });
        html += '</div>';
        
        container.innerHTML = html;
    } catch (error) {
        console.error('Error loading API key status:', error);
        container.innerHTML = '<div class="error">Failed to load API key status</div>';
    }
};

// Load providers for dropdown
KnowledgeBaseApp.prototype.loadProviders = async function() {
    const select = document.getElementById('new-model-provider');
    if (!select) return;
    
    try {
        const response = await fetch('/api/providers');
        const providers = await response.json();
        
        select.innerHTML = '<option value="">Select provider...</option>';
        providers.forEach(provider => {
            select.innerHTML += `
                <option value="${provider.name}" data-api-key="${provider.api_key}">
                    ${provider.name} - ${provider.description}
                </option>
            `;
        });
    } catch (error) {
        console.error('Error loading providers:', error);
    }
};

// Load current models
KnowledgeBaseApp.prototype.loadCurrentModels = async function() {
    const container = document.getElementById('models-list');
    if (!container) return;
    
    try {
        container.innerHTML = '<div class="loading-models">Loading models...</div>';
        
        const response = await fetch('/api/models');
        const models = await response.json();
        
        if (models.length === 0) {
            container.innerHTML = '<div class="no-models">No models configured. Add some models above!</div>';
            return;
        }
        
        let html = '<div class="current-models-grid">';
        models.forEach(model => {
            html += `
                <div class="current-model-item" data-model="${model.name}">
                    <div class="model-info">
                        <div class="model-name">${model.name}</div>
                        <div class="model-provider">${model.provider}</div>
                        <div class="model-description">${model.description}</div>
                    </div>
                    <div class="model-status" id="status-${model.name}">
                        <span class="status-text">Unknown</span>
                    </div>
                    <div class="model-actions">
                        <button class="btn-small btn-secondary" onclick="testSingleModel('${model.name}')" title="Test Access">
                            <i class="fas fa-flask"></i>
                        </button>
                        <button class="btn-small btn-danger" onclick="removeModel('${model.name}')" title="Remove Model">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        
        container.innerHTML = html;
    } catch (error) {
        console.error('Error loading current models:', error);
        container.innerHTML = '<div class="error">Failed to load models</div>';
    }
};
// Function to load models into the settings panel
KnowledgeBaseApp.prototype.loadModelsForSettingsPanel = async function() {
    const modelsList = document.getElementById('models-list');
    if (!modelsList) {
        console.error('Models list container not found');
        return;
    }

    try {
        modelsList.innerHTML = '<div class="loading-models">Loading model configurations...</div>';

        // Load dynamic models and settings in parallel
        const [modelsResponse, settingsResponse] = await Promise.all([
            fetch('/api/models'),
            fetch('/api/model-settings')
        ]);

        const availableModels = await modelsResponse.json();
        const modelSettings = settingsResponse.ok ? await settingsResponse.json() : {};

        console.log('Settings panel - Available models:', availableModels);
        console.log('Settings panel - Model settings:', modelSettings);

        // Group models by provider
        const modelsByProvider = {};
        availableModels.forEach(model => {
            if (!modelsByProvider[model.provider]) {
                modelsByProvider[model.provider] = [];
            }
            modelsByProvider[model.provider].push(model);
        });

        // Generate HTML for models grouped by provider
        let html = '';
        Object.keys(modelsByProvider).forEach(provider => {
            const providerModels = modelsByProvider[provider];
            html += `
                <div class="model-group">
                    <div class="model-group-header">
                        <h4 class="model-group-title">
                            <i class="fas fa-robot"></i>
                            ${provider}
                        </h4>
                        <div class="model-group-actions">
                            <button class="model-group-btn" onclick="toggleGroupModels('${provider.toLowerCase()}', true)">Enable All</button>
                            <button class="model-group-btn" onclick="toggleGroupModels('${provider.toLowerCase()}', false)">Disable All</button>
                        </div>
                    </div>
                    <div class="models-grid">
            `;

            providerModels.forEach(model => {
                const settings = modelSettings[model.name] || { enabled: model.name !== 'gpt-5', status: 'unknown' };
                html += `
                    <div class="model-item">
                        <div class="model-info">
                            <input type="checkbox" class="model-checkbox"
                                   id="model-${model.name}"
                                   ${settings.enabled ? 'checked' : ''}
                                   onchange="toggleModelEnabled('${model.name}')">
                            <div class="model-details">
                                <h5 class="model-name">${model.name}</h5>
                                <p class="model-description">${model.description}</p>
                            </div>
                        </div>
                        <div class="model-status">
                            <div class="model-access-status ${settings.status}">
                                <span class="status-icon ${settings.status}"></span>
                                ${settings.status || 'Unknown'}
                            </div>
                        </div>
                    </div>
                `;
            });

            html += `
                    </div>
                </div>
            `;
        });

        modelsList.innerHTML = html;

    } catch (error) {
        console.error('Failed to load model configurations:', error);
        modelsList.innerHTML = '<div class="loading-models" style="color: red;">Failed to load model configurations</div>';
    }
};

// Method to load models into the main dropdown
KnowledgeBaseApp.prototype.loadMainModelDropdown = async function() {
    const dropdown = document.getElementById('llm-model');
    if (!dropdown) return;
    
    try {
        // Load both dynamic models and settings to show only enabled models
        const [modelsResponse, settingsResponse] = await Promise.all([
            fetch('/api/models'),
            fetch('/api/model-settings')
        ]);
        
        const availableModels = await modelsResponse.json();
        const modelSettings = settingsResponse.ok ? await settingsResponse.json() : {};
        
        console.log('Main dropdown - Available models:', availableModels);
        console.log('Main dropdown - Model settings:', modelSettings);
        
        // Create a combined list of all models (dynamic + legacy from settings)
        const allModels = new Map();
        
        // Add dynamic models first
        // Use model_value (API identifier) as the key, not display name
        availableModels.forEach(model => {
            const modelKey = model.model_value || model.name; // Fallback to name for legacy models
            allModels.set(modelKey, {
                ...model,
                isDynamic: true,
                // Ensure we have both name and model_value
                name: model.name,
                model_value: modelKey
            });
        });
        
        // No longer adding legacy models - all models should be in the dynamic list
        
        // Filter to only enabled models
        const enabledModels = Array.from(allModels.values()).filter(model => {
            // Use model_value (API identifier) to look up settings, not display name
            const modelKey = model.model_value || model.name;
            const settings = modelSettings[modelKey];
            const isEnabled = settings && settings.enabled === true;
            
            // Debug log for each model
            console.log(`Model: ${model.name} (${modelKey}), Settings:`, settings, `Enabled: ${isEnabled}`);
            
            // Explicitly check that enabled is true (not just truthy)
            return isEnabled;
        });
        
        console.log('Enabled models for main dropdown:', enabledModels);
        
        // Group enabled models by provider
        const modelsByProvider = {};
        enabledModels.forEach(model => {
            if (!modelsByProvider[model.provider]) {
                modelsByProvider[model.provider] = [];
            }
            modelsByProvider[model.provider].push(model);
        });
        
        // Build dropdown HTML
        let html = '<option value="">Select a model...</option>';
        
        if (Object.keys(modelsByProvider).length === 0) {
            html = '<option value="">No enabled models - check Settings</option>';
        } else {
            Object.keys(modelsByProvider).sort().forEach(provider => {
                html += `<optgroup label="${provider}">`;
                modelsByProvider[provider].forEach(model => {
                    if (model.type === 'image') return;
                    // Use model_value as the value (API identifier), display name as text
                    const modelValue = model.model_value || model.name;
                    html += `<option value="${modelValue}">${model.name}</option>`;
                });
                html += '</optgroup>';
            });
        }
        
        dropdown.innerHTML = html;
        
        // Try to set default model from preferences
        try {
            const prefsResponse = await fetch('/api/preferences');
            if (prefsResponse.ok) {
                const prefs = await prefsResponse.json();
                // Check if default model exists in enabled models (using model_value/API identifier)
                if (prefs.defaultModel) {
                    const modelExists = enabledModels.some(m => {
                        const modelValue = m.model_value || m.name;
                        return modelValue === prefs.defaultModel;
                    });
                    if (modelExists) {
                        dropdown.value = prefs.defaultModel;
                        console.log('Set default model to:', prefs.defaultModel);
                    }
                }
            }
        } catch (error) {
            console.log('Could not load preferences for default model');
        }
        
        // If no default set, select first enabled model
        if (!dropdown.value && enabledModels.length > 0) {
            const firstModel = enabledModels[0];
            const firstModelValue = firstModel.model_value || firstModel.name;
            dropdown.value = firstModelValue;
            console.log('No default set, using first enabled model:', firstModelValue);
        }
        
        console.log('Main dropdown populated with', enabledModels.length, 'enabled models');
        
    } catch (error) {
        console.error('Error loading main model dropdown:', error);
        dropdown.innerHTML = '<option value="">Error loading models</option>';
    }
};

KnowledgeBaseApp.prototype.closeSettingsPanel = function() {
    const panel = document.getElementById('settings-panel');
    if (panel) {
        panel.classList.remove('open');
    }
};

// Make closeSettingsPanel available globally for onclick handlers
window.closeSettingsPanel = function() {
    if (window.app) {
        window.app.closeSettingsPanel();
    }
};

// Settings section navigation
window.showSettingsSection = function(sectionName) {
    // Hide all sections
    const sections = document.querySelectorAll('.settings-section');
    sections.forEach(section => section.classList.remove('active'));
    
    // Show the selected section
    const targetSection = document.getElementById(sectionName + '-section');
    if (targetSection) {
        targetSection.classList.add('active');
    }
    
    // Update navigation buttons
    const navButtons = document.querySelectorAll('.settings-nav-btn');
    navButtons.forEach(btn => btn.classList.remove('active'));
    
    const activeNavBtn = document.querySelector(`[data-section="${sectionName}"]`);
    if (activeNavBtn) {
        activeNavBtn.classList.add('active');
    }
    
    // Special handling for templates section
    if (sectionName === 'templates' && window.app) {
        window.app.renderTemplatesManagementList();
    }
    
    // Special handling for personas section
    if (sectionName === 'personas') {
        window.app.renderPersonasManagementList();
    }
    
    // Special handling for users section
    if (sectionName === 'users') {
        window.refreshUsersList();
    }
};

// Note: checkAllModelsAccess and saveModelSettings are defined in the HTML template
// and should work directly without global wrappers

// However, the settings modal uses a different template, so we need to define these functions globally
window.checkAllModelsAccess = async function() {
    const checkBtn = document.querySelector('.btn-secondary');
    if (!checkBtn) {
        console.error('Check button not found');
        return;
    }
    
    const originalText = checkBtn.innerHTML;
    
    try {
        // Show loading state
        checkBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking...';
        checkBtn.disabled = true;
        
        console.log('Starting check for all models...');
        
        // Get all model checkboxes to check
        const checkboxes = document.querySelectorAll('.model-checkbox');
        const modelsToCheck = Array.from(checkboxes).map(checkbox => 
            checkbox.id.replace('model-', '')
        );
        
        console.log('Models to check:', modelsToCheck);
        
        let successCount = 0;
        let errorCount = 0;
        const results = [];
        
        // Check each model individually
        for (const modelValue of modelsToCheck) {
            try {
                checkBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Checking ${modelValue}...`;
                
                // Make actual API call to check model access
                const response = await fetch('/api/check-model-access', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ model: modelValue })
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    successCount++;
                    results.push(`✓ ${modelValue}: ${result.status || 'Available'}`);
                    
                    // Update the UI status indicator
                    const modelItem = document.getElementById(`model-${modelValue}`).closest('.model-item');
                    if (modelItem) {
                        const statusElement = modelItem.querySelector('.model-access-status');
                        if (statusElement) {
                            statusElement.className = 'model-access-status available';
                            statusElement.innerHTML = '<span class="status-icon available"></span>Available';
                        }
                    }
                } else {
                    errorCount++;
                    results.push(`✗ ${modelValue}: ${result.error || 'Access denied'}`);
                    
                    // Update the UI status indicator
                    const modelItem = document.getElementById(`model-${modelValue}`).closest('.model-item');
                    if (modelItem) {
                        const statusElement = modelItem.querySelector('.model-access-status');
                        if (statusElement) {
                            statusElement.className = 'model-access-status error';
                            statusElement.innerHTML = '<span class="status-icon error"></span>Error';
                        }
                    }
                }
                
            } catch (error) {
                errorCount++;
                console.error(`Error checking ${modelValue}:`, error);
                results.push(`✗ ${modelValue}: Network error`);
                
                // Update the UI status indicator
                const modelItem = document.getElementById(`model-${modelValue}`).closest('.model-item');
                if (modelItem) {
                    const statusElement = modelItem.querySelector('.model-access-status');
                    if (statusElement) {
                        statusElement.className = 'model-access-status error';
                        statusElement.innerHTML = '<span class="status-icon error"></span>Error';
                    }
                }
            }
            
            // Small delay between checks to avoid rate limiting
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        // Show results summary
        const summary = `Model Access Check Complete!\n\n` +
                       `✓ Available: ${successCount}\n` +
                       `✗ Unavailable: ${errorCount}\n\n` +
                       `Details:\n${results.join('\n')}`;
        
        alert(summary);
        
    } catch (error) {
        console.error('Error checking model access:', error);
        alert('Error checking model access: ' + error.message);
    } finally {
        // Restore button state
        checkBtn.innerHTML = originalText;
        checkBtn.disabled = false;
    }
};

window.saveModelSettings = async function() {
    const saveBtn = document.getElementById('save-model-settings-btn');
    if (!saveBtn) {
        console.error('Save button not found');
        return;
    }
    
    const originalText = saveBtn.innerHTML;
    
    try {
        // Show loading state
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
        saveBtn.disabled = true;
        
        // Get current model settings from checkboxes
        const modelSettings = {};
        const checkboxes = document.querySelectorAll('.model-checkbox');
        checkboxes.forEach(checkbox => {
            const modelValue = checkbox.id.replace('model-', '');
            modelSettings[modelValue] = {
                enabled: checkbox.checked,
                status: 'unknown'
            };
        });
        
        console.log('Saving model settings:', modelSettings);
        
        // Save to server
        const response = await fetch('/api/model-settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(modelSettings)
        });
        
        if (response.ok) {
            alert('Model settings saved successfully!');
        } else {
            const result = await response.json();
            alert(`Failed to save model settings: ${result.error || 'Unknown error'}`);
        }
        
    } catch (error) {
        console.error('Error saving model settings:', error);
        alert('Error saving model settings: ' + error.message);
    } finally {
        // Restore button state
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    }
};

// Note: Model toggle functions (toggleModelEnabled, toggleGroupModels, checkModelAccess) 
// are also defined in the HTML template and should work directly

// Add the missing toggle functions for the settings panel
window.toggleModelEnabled = function(modelValue) {
    const checkbox = document.getElementById(`model-${modelValue}`);
    if (checkbox) {
        console.log(`Model ${modelValue} enabled: ${checkbox.checked}`);
        // Store the setting (you can expand this to save to server)
    }
};

window.toggleGroupModels = function(provider, enabled) {
    // Find all checkboxes for this provider
    const checkboxes = document.querySelectorAll('.model-checkbox');
    checkboxes.forEach(checkbox => {
        const modelValue = checkbox.id.replace('model-', '');
        // Check if this model belongs to the provider
        const modelItem = checkbox.closest('.model-item');
        const modelGroup = modelItem ? modelItem.closest('.model-group') : null;
        const groupTitle = modelGroup ? modelGroup.querySelector('.model-group-title') : null;
        
        if (groupTitle && groupTitle.textContent.trim().toLowerCase().includes(provider.toLowerCase())) {
            checkbox.checked = enabled;
            toggleModelEnabled(modelValue);
        }
    });
};

window.checkModelAccess = async function(modelValue) {
    console.log(`Checking access for model: ${modelValue}`);
    
    try {
        // Find the model item to update its status
        const modelItem = document.getElementById(`model-${modelValue}`).closest('.model-item');
        const statusElement = modelItem ? modelItem.querySelector('.model-access-status') : null;
        
        // Show loading state
        if (statusElement) {
            statusElement.className = 'model-access-status checking';
            statusElement.innerHTML = '<span class="status-icon checking"></span>Checking...';
        }
        
        // Make API call to check model access
        const response = await fetch('/api/check-model-access', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ model: modelValue })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            // Model is available
            if (statusElement) {
                statusElement.className = 'model-access-status available';
                statusElement.innerHTML = '<span class="status-icon available"></span>Available';
            }
            alert(`✓ ${modelValue}: ${result.status || 'Available'}`);
        } else {
            // Model is not available
            if (statusElement) {
                statusElement.className = 'model-access-status error';
                statusElement.innerHTML = '<span class="status-icon error"></span>Error';
            }
            alert(`✗ ${modelValue}: ${result.error || 'Access denied'}`);
        }
        
    } catch (error) {
        console.error(`Error checking ${modelValue}:`, error);
        
        // Update UI to show error
        const modelItem = document.getElementById(`model-${modelValue}`).closest('.model-item');
        const statusElement = modelItem ? modelItem.querySelector('.model-access-status') : null;
        if (statusElement) {
            statusElement.className = 'model-access-status error';
            statusElement.innerHTML = '<span class="status-icon error"></span>Network Error';
        }
        
        alert(`✗ ${modelValue}: Network error - ${error.message}`);
    }
};

// Dynamic Model Management Functions
window.addNewModel = async function() {
    const nameInput = document.getElementById('new-model-name');
    const providerSelect = document.getElementById('new-model-provider');
    const descriptionInput = document.getElementById('new-model-description');
    const addBtn = document.getElementById('add-new-model-btn');
    
    const name = nameInput.value.trim();
    const provider = providerSelect.value;
    const description = descriptionInput.value.trim();
    
    if (!name || !provider) {
        alert('Please enter a model name and select a provider');
        return;
    }
    
    try {
        addBtn.disabled = true;
        addBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
        
        const response = await fetch('/api/models', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                name: name,
                provider: provider,
                description: description
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            // Clear form
            nameInput.value = '';
            providerSelect.value = '';
            descriptionInput.value = '';
            
            // Reload models list
            if (window.app) {
                await window.app.loadCurrentModels();
            }
            
            alert(`✓ Model "${name}" added successfully!`);
        } else {
            alert(`✗ Failed to add model: ${result.error || 'Unknown error'}`);
        }
        
    } catch (error) {
        console.error('Error adding model:', error);
        alert(`✗ Network error: ${error.message}`);
    } finally {
        addBtn.disabled = false;
        addBtn.innerHTML = '<i class="fas fa-plus"></i> Add Model';
    }
};

window.removeModel = async function(modelName) {
    if (!confirm(`Are you sure you want to remove the model "${modelName}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/models/${encodeURIComponent(modelName)}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            // Reload models list
            if (window.app) {
                await window.app.loadCurrentModels();
            }
            
            alert(`✓ Model "${modelName}" removed successfully!`);
        } else {
            alert(`✗ Failed to remove model: ${result.error || 'Unknown error'}`);
        }
        
    } catch (error) {
        console.error('Error removing model:', error);
        alert(`✗ Network error: ${error.message}`);
    }
};

window.testSingleModel = async function(modelName) {
    const statusElement = document.getElementById(`status-${modelName}`);
    
    try {
        if (statusElement) {
            statusElement.innerHTML = '<span class="status-text checking">Testing...</span>';
        }
        
        const response = await fetch('/api/check-model-access', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ model: modelName })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            const status = result.hasAccess ? 'Available' : 'No Access';
            const statusClass = result.hasAccess ? 'available' : 'error';
            
            if (statusElement) {
                statusElement.innerHTML = `<span class="status-text ${statusClass}">${status}</span>`;
            }
            
            const message = result.hasAccess 
                ? `✓ ${modelName}: Available (${result.api_key_name})`
                : `✗ ${modelName}: ${result.status} (${result.api_key_name})`;
            
            alert(message);
        } else {
            if (statusElement) {
                statusElement.innerHTML = '<span class="status-text error">Error</span>';
            }
            alert(`✗ ${modelName}: ${result.error || 'Test failed'}`);
        }
        
    } catch (error) {
        console.error(`Error testing ${modelName}:`, error);
        if (statusElement) {
            statusElement.innerHTML = '<span class="status-text error">Network Error</span>';
        }
        alert(`✗ ${modelName}: Network error - ${error.message}`);
    }
};

window.testNewModel = async function() {
    const nameInput = document.getElementById('new-model-name');
    const providerSelect = document.getElementById('new-model-provider');
    const testBtn = document.getElementById('test-new-model-btn');
    
    const name = nameInput.value.trim();
    const provider = providerSelect.value;
    
    if (!name || !provider) {
        alert('Please enter a model name and select a provider to test');
        return;
    }
    
    try {
        testBtn.disabled = true;
        testBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
        
        const response = await fetch('/api/check-model-access', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ model: name })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            const message = result.hasAccess 
                ? `✓ ${name}: API key available! (${result.api_key_name})`
                : `✗ ${name}: API key not configured (${result.api_key_name})`;
            
            alert(message);
        } else {
            alert(`✗ ${name}: ${result.error || 'Test failed'}`);
        }
        
    } catch (error) {
        console.error(`Error testing ${name}:`, error);
        alert(`✗ ${name}: Network error - ${error.message}`);
    } finally {
        testBtn.disabled = false;
        testBtn.innerHTML = '<i class="fas fa-flask"></i> Test Access';
    }
};

window.refreshModelsList = async function() {
    if (window.app) {
        await window.app.loadDynamicModels();
    }
};

// ==================== PROFILE PREFERENCES ====================
window.app = window.app || {};
window.app.saveProfilePreferences = async function() {
    try {
        const tone = document.getElementById('pref-tone')?.value || '';
        const verbosity = document.getElementById('pref-verbosity')?.value || '';
        const reading = document.getElementById('pref-reading')?.value || '';
        const statusEl = document.getElementById('pref-save-status');
        if (statusEl) statusEl.textContent = 'Saving...';

        const payload = { preferences: { tone, verbosity, reading_level: reading } };
        const res = await fetch('/api/users/update-preferences', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok && data.success) {
            if (statusEl) statusEl.textContent = 'Saved. New responses will reflect your preferences.';
        } else {
            if (statusEl) statusEl.textContent = 'Failed to save preferences: ' + (data.error || res.statusText);
        }
    } catch (e) {
        const statusEl = document.getElementById('pref-save-status');
        if (statusEl) statusEl.textContent = 'Error: ' + e.message;
        console.error('saveProfilePreferences error', e);
    }
};

// Model Management Modal Functions
window.openModelManagement = function() {
    const modal = document.getElementById('model-management-modal');
    const settingsPanel = document.getElementById('settings-panel');
    
    if (modal) {
        // Hide the settings panel completely when model management opens
        if (settingsPanel) {
            settingsPanel.style.opacity = '0';
            settingsPanel.style.pointerEvents = 'none';
            settingsPanel.style.zIndex = '999'; // Lower than modal
        }
        
        modal.style.display = 'flex';
        modal.setAttribute('aria-hidden', 'false');
        modal.style.zIndex = '1000'; // Higher than settings panel
        
        // Add keyboard event listener for ESC key
        const handleKeydown = (e) => {
            if (e.key === 'Escape') {
                closeModelManagement();
                document.removeEventListener('keydown', handleKeydown);
            }
        };
        document.addEventListener('keydown', handleKeydown);
        
        // Aggressive approach to break through the modal mask
        requestAnimationFrame(() => {
            const modalContent = modal.querySelector('.modal-content');
            
            // Simulate click on modal content to break through mask
            if (modalContent) {
                const clickEvent = new MouseEvent('click', {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                    clientX: modalContent.offsetLeft + modalContent.offsetWidth / 2,
                    clientY: modalContent.offsetTop + modalContent.offsetHeight / 2
                });
                modalContent.dispatchEvent(clickEvent);
                
                // Focus the modal content
                modalContent.focus();
            }
            
            // Focus the modal container
            modal.focus();
            
            // Focus the first input after a delay
            setTimeout(() => {
                const firstInput = modal.querySelector('input[type="text"]');
                if (firstInput) {
                    firstInput.focus();
                    firstInput.select(); // Select text if any
                    
                    // Simulate typing to ensure it's active
                    const inputEvent = new Event('input', { bubbles: true });
                    firstInput.dispatchEvent(inputEvent);
                }
            }, 200);
        });
        
        // Load model management data
        loadModelManagementData();
    }
};

window.closeModelManagement = function() {
    const modal = document.getElementById('model-management-modal');
    const settingsPanel = document.getElementById('settings-panel');
    
    if (modal) {
        modal.style.display = 'none';
        modal.setAttribute('aria-hidden', 'true');
        
        // Restore the settings panel
        if (settingsPanel) {
            settingsPanel.style.opacity = '1';
            settingsPanel.style.pointerEvents = 'auto';
            settingsPanel.style.zIndex = '1000'; // Restore original z-index
        }
    }
};
// ==================== USER MANAGEMENT FUNCTIONS ====================
// Show Users tab for admin only
window.showUsersTabIfAdmin = async function() {
    try {
        const response = await fetch('/auth/status');
        const data = await response.json();
        
        console.log('🔍 Auth status data:', data);
        console.log('🔍 user_role:', data.user_role, 'user_type:', data.user_type);
        
        // Show Users tab and settings buttons if admin or super_admin
        const isAdmin = data.authenticated && 
                       (data.user_role === 'super_admin' || data.user_role === 'admin' || data.user_type === 'admin');
        
        console.log('🔍 isAdmin:', isAdmin);
        
        // Show/hide Users tab in settings
        const usersTab = document.getElementById('users-nav-btn');
        if (usersTab) {
            usersTab.style.display = isAdmin ? 'flex' : 'none';
        }
        
        // Show/hide model selector (admin only)
        const modelSelectorContainer = document.getElementById('model-selector-container');
        if (modelSelectorContainer) {
            modelSelectorContainer.style.display = isAdmin ? 'block' : 'none';
        }
        
        // Show/hide Reports button in top bar (admin only)
        const reportsBtn = document.getElementById('admin-reports-btn');
        if (reportsBtn) {
            reportsBtn.style.display = isAdmin ? 'block' : 'none';
        }
        
        // Show/hide Settings button in sidebar footer (admin only)
        const sidebarSettingsBtn = document.getElementById('sidebar-settings-btn');
        if (sidebarSettingsBtn) {
            if (isAdmin) {
                sidebarSettingsBtn.classList.add('show-for-admin');
            } else {
                sidebarSettingsBtn.classList.remove('show-for-admin');
            }
            console.log(`🔧 Settings button in footer: ${isAdmin ? 'VISIBLE (admin)' : 'HIDDEN (user)'}`);
        }
        
        // Show/hide Account button in top bar (all authenticated users)
        const accountBtn = document.getElementById('account-btn');
        if (accountBtn) {
            accountBtn.style.display = data.authenticated ? 'block' : 'none';
        }
        
        // Display username in top bar
        const usernameDisplay = document.getElementById('username-display');
        if (usernameDisplay && data.authenticated) {
            const displayName = data.display_name || data.username || 'User';
            usernameDisplay.textContent = displayName;
            usernameDisplay.style.display = 'inline-block';
            
            // Update welcome messages with the user's name
            window.updateWelcomeMessages(displayName);
            
            // Just store the display name for now
            window.userDisplayName = displayName;
        }
    } catch (error) {
        console.error('Error checking admin status:', error);
    }
};

window.openCreateUserModal = function() {
    console.log('🔵 openCreateUserModal called');
    const modal = document.getElementById('userManagementModal');
    const form = document.getElementById('userForm');
    
    console.log('🔵 Modal element:', modal);
    console.log('🔵 Form element:', form);
    
    if (!modal) {
        console.error('❌ userManagementModal not found!');
        alert('Error: User management modal not found in the page');
        return;
    }
    
    if (!form) {
        console.error('❌ userForm not found!');
        alert('Error: User form not found in the page');
        return;
    }
    
    // Reset form
    form.reset();
    document.getElementById('user-id').value = '';
    document.getElementById('userModalTitle').textContent = 'Create New User';
    document.getElementById('saveUserBtnText').textContent = 'Create User';
    document.getElementById('user-password').required = true;
    
    modal.style.display = 'flex';
    
    // Add click-outside-to-close functionality
    setTimeout(() => {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                window.closeUserModal();
            }
        }, { once: true });
    }, 100);
    
    console.log('✅ Modal opened successfully');
};

window.closeUserModal = function() {
    const modal = document.getElementById('userManagementModal');
    modal.style.display = 'none';
};

window.saveUser = async function(event) {
    event.preventDefault();
    console.log('🟢 saveUser called');
    
    const userId = document.getElementById('user-id').value;
    const username = document.getElementById('user-username').value.trim();
    const email = document.getElementById('user-email').value.trim();
    const password = document.getElementById('user-password').value;
    const confirmPassword = document.getElementById('user-confirm-password').value;
    const firstName = document.getElementById('user-first-name').value.trim();
    const lastName = document.getElementById('user-last-name').value.trim();
    const displayName = document.getElementById('user-display-name').value.trim();
    const role = document.getElementById('user-role').value;
    const status = document.getElementById('user-status').value;
    
    console.log('🟢 Form data:', { userId, username, email, role, status });
    
    // Validation
    if (!userId && password !== confirmPassword) {
        console.error('❌ Passwords do not match');
        alert('Passwords do not match!');
        return;
    }
    
    if (!userId && password.length < 6) {
        console.error('❌ Password too short');
        alert('Password must be at least 6 characters long!');
        return;
    }
    
    try {
        const payload = {
            username,
            email,
            first_name: firstName,
            last_name: lastName,
            display_name: displayName,
            role,
            status
        };
        
        if (password) {
            payload.password = password;
        }
        
        const url = userId ? `/api/users/${userId}` : '/api/users';
        const method = userId ? 'PUT' : 'POST';
        
        console.log('🟢 Sending request:', { url, method, payload });
        
        const response = await fetch(url, {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });
        
        console.log('🟢 Response status:', response.status);
        
        const data = await response.json();
        
        if (data.success || response.ok) {
            alert(userId ? 'User updated successfully!' : 'User created successfully!');
            closeUserModal();
            refreshUsersList();
        } else {
            alert('Error: ' + (data.error || 'Failed to save user'));
        }
    } catch (error) {
        console.error('Error saving user:', error);
        alert('Network error. Please try again.');
    }
};

window.refreshUsersList = async function() {
    console.log('🔄 refreshUsersList called');
    const usersList = document.getElementById('users-list');
    
    if (!usersList) {
        console.error('❌ users-list element not found!');
        return;
    }
    
    try {
        usersList.innerHTML = '<div class="loading-users">Loading users...</div>';
        
        console.log('🔄 Fetching users from /api/users');
        const response = await fetch('/api/users');
        console.log('🔄 Response status:', response.status);
        
        const data = await response.json();
        console.log('🔄 Users data:', data);
        
        if (data.users && data.users.length > 0) {
            usersList.innerHTML = `
                <table class="users-table">
                    <thead>
                        <tr>
                            <th style="width: 40px;"></th>
                            <th style="width: auto;">Username</th>
                            <th style="width: 100px; text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.users.map(user => `
                            <tr>
                                <td style="text-align: center;">
                                    <i class="fas fa-circle status-indicator status-${user.status}" 
                                       title="${user.status === 'active' ? 'Active' : user.status === 'inactive' ? 'Inactive' : 'Suspended'}"></i>
                                </td>
                                <td>
                                    <div><strong>${user.username}</strong></div>
                                    ${user.display_name ? '<div><small style="color: #6b7280;">' + user.display_name + '</small></div>' : ''}
                                    <div><small style="color: #9ca3af;">${user.email || 'No email'}</small></div>
                                    <div><small style="color: #9ca3af;">${user.role}</small></div>
                                </td>
                                <td style="white-space: nowrap; text-align: right;">
                                    <button class="btn-icon" onclick="editUser('${user.id}')" title="Edit user">
                                        <i class="fas fa-edit"></i>
                                    </button>
                                    ${user.username !== 'admin' ? `
                                    <button class="btn-icon btn-danger" onclick="deleteUser('${user.id}', '${user.username}')" title="Delete user">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                    ` : ''}
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        } else {
            usersList.innerHTML = '<p>No users found.</p>';
        }
    } catch (error) {
        console.error('Error loading users:', error);
        usersList.innerHTML = '<p class="error-message">Failed to load users.</p>';
    }
};

window.editUser = async function(userId) {
    try {
        const response = await fetch(`/api/users/${userId}`);
        const data = await response.json();
        
        if (data.user) {
            const user = data.user;
            
            // Populate form
            document.getElementById('user-id').value = user.id;
            document.getElementById('user-username').value = user.username;
            document.getElementById('user-email').value = user.email;
            document.getElementById('user-first-name').value = user.first_name || '';
            document.getElementById('user-last-name').value = user.last_name || '';
            document.getElementById('user-display-name').value = user.display_name || '';
            document.getElementById('user-role').value = user.role;
            document.getElementById('user-status').value = user.status;
            
            // Clear password fields
            document.getElementById('user-password').value = '';
            document.getElementById('user-confirm-password').value = '';
            document.getElementById('user-password').required = false;
            
            // Update modal title
            document.getElementById('userModalTitle').textContent = 'Edit User';
            document.getElementById('saveUserBtnText').textContent = 'Update User';
            
            // Show modal
            document.getElementById('userManagementModal').style.display = 'flex';
        }
    } catch (error) {
        console.error('Error loading user:', error);
        alert('Failed to load user details.');
    }
};

window.deleteUser = async function(userId, username) {
    if (!confirm(`Are you sure you want to delete user "${username}"? This action cannot be undone.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/users/${userId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success || response.ok) {
            alert('User deleted successfully!');
            refreshUsersList();
        } else {
            alert('Error: ' + (data.error || 'Failed to delete user'));
        }
    } catch (error) {
        console.error('Error deleting user:', error);
        alert('Network error. Please try again.');
    }
};

// ==================== ACCOUNT INFORMATION ====================

window.loadAccountInfo = async function() {
    const accountContent = document.getElementById('account-info-content');
    
    try {
        const response = await fetch('/auth/status');
        const data = await response.json();
        
        if (data.authenticated) {
            const userType = data.user_type || 'unknown';
            const userRole = data.user_role || 'N/A';
            const username = data.username || 'Admin';
            const email = data.email || '';
            const firstName = data.first_name || '';
            const lastName = data.last_name || '';
            const displayName = data.display_name || username;
            
            accountContent.innerHTML = `
                <div class="account-card">
                    <div class="account-section">
                        <h4><i class="fas fa-user-circle"></i> Profile Information</h4>
                        <div class="account-details">
                            <div class="detail-row">
                                <span class="detail-label">Display Name:</span>
                                <span class="detail-value"><strong>${displayName}</strong></span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Username:</span>
                                <span class="detail-value">${username}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Email:</span>
                                <span class="detail-value">${email}</span>
                            </div>
                            ${firstName || lastName ? `
                            <div class="detail-row">
                                <span class="detail-label">Full Name:</span>
                                <span class="detail-value">${firstName} ${lastName}</span>
                            </div>
                            ` : ''}
                            <div class="detail-row">
                                <span class="detail-label">Account Type:</span>
                                <span class="detail-value"><span class="role-badge role-${userRole}">${userRole.replace('_', ' ')}</span></span>
                            </div>
                        </div>
                    </div>
                    
                    ${userType === 'admin' ? `
                    <div class="account-section">
                        <h4><i class="fas fa-shield-alt"></i> Administrator Account</h4>
                        <div class="account-details">
                            <p style="color: #666; font-size: 14px;">
                                You are logged in as the system administrator with full access to all features and settings.
                            </p>
                        </div>
                    </div>
                    ` : `
                    <div class="account-section">
                        <h4><i class="fas fa-info-circle"></i> Account Status</h4>
                        <div class="account-details">
                            <div class="detail-row">
                                <span class="detail-label">Status:</span>
                                <span class="detail-value"><span class="status-badge status-active">Active</span></span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Access Level:</span>
                                <span class="detail-value">${getRoleDescription(userRole)}</span>
                            </div>
                        </div>
                    </div>
                    `}
                    
                    <div class="account-section">
                        <h4><i class="fas fa-cog"></i> Actions</h4>
                        <div class="account-actions">
                            <button class="btn-primary" onclick="editProfile()">
                                <i class="fas fa-edit"></i>
                                Edit Profile
                            </button>
                            <button class="btn-secondary" onclick="changePassword()">
                                <i class="fas fa-key"></i>
                                Change Password
                            </button>
                            <button class="btn-danger" onclick="confirmLogout()">
                                <i class="fas fa-sign-out-alt"></i>
                                Sign Out
                            </button>
                        </div>
                    </div>
                </div>
            `;
        } else {
            accountContent.innerHTML = '<p class="error-message">Not authenticated</p>';
        }
    } catch (error) {
        console.error('Error loading account info:', error);
        accountContent.innerHTML = '<p class="error-message">Failed to load account information.</p>';
    }
};

function getRoleDescription(role) {
    const descriptions = {
        'super_admin': 'Full system access with all permissions',
        'admin': 'Can manage users and organization settings',
        'user': 'Standard access to create and manage conversations',
        'viewer': 'Read-only access to view conversations',
        'guest': 'Limited trial access'
    };
    return descriptions[role] || 'Standard user access';
}

// Global variables for profile editing
let currentUserData = null;

window.editProfile = function() {
    // Get current user data
    fetch('/auth/status')
        .then(response => response.json())
        .then(data => {
            if (data.authenticated) {
                currentUserData = data;
                showProfileEditModal(data);
            } else {
                alert('Not authenticated');
            }
        })
        .catch(error => {
            console.error('Error fetching user data:', error);
            alert('Failed to load profile data');
        });
};

window.changePassword = function() {
    // Get current user data
    fetch('/auth/status')
        .then(response => response.json())
        .then(data => {
            if (data.authenticated) {
                currentUserData = data;
                showPasswordChangeModal(data);
            } else {
                alert('Not authenticated');
            }
        })
        .catch(error => {
            console.error('Error fetching user data:', error);
            alert('Failed to load profile data');
        });
};

function showProfileEditModal(userData) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content profile-edit-modal">
            <div class="modal-header">
                <h3><i class="fas fa-edit"></i> Edit Profile</h3>
                <button class="modal-close" onclick="closeProfileModal()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <form id="profile-edit-form">
                    <div class="form-group">
                        <label for="edit-username">Username *</label>
                        <input type="text" id="edit-username" value="${userData.username || ''}" required>
                        <small class="form-text">Your unique username for login</small>
                    </div>
                    
                    <div class="form-group">
                        <label for="edit-email">Email *</label>
                        <input type="email" id="edit-email" value="${userData.email || ''}" required>
                        <small class="form-text">Your email address</small>
                    </div>
                    
                    <div class="form-group">
                        <label for="edit-display-name">Display Name *</label>
                        <input type="text" id="edit-display-name" value="${userData.display_name || ''}" required>
                        <small class="form-text">Name shown in the interface</small>
                    </div>
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label for="edit-first-name">First Name</label>
                            <input type="text" id="edit-first-name" value="${userData.first_name || ''}">
                        </div>
                        <div class="form-group">
                            <label for="edit-last-name">Last Name</label>
                            <input type="text" id="edit-last-name" value="${userData.last_name || ''}">
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label for="edit-current-password">Current Password *</label>
                        <input type="password" id="edit-current-password" required>
                        <small class="form-text">Required to confirm changes</small>
                    </div>
                    
                    <div class="form-group">
                        <label for="edit-new-password">New Password (Optional)</label>
                        <input type="password" id="edit-new-password">
                        <small class="form-text">Leave blank to keep current password</small>
                    </div>
                    
                    <div class="form-group">
                        <label for="edit-confirm-password">Confirm New Password</label>
                        <input type="password" id="edit-confirm-password">
                        <small class="form-text">Must match new password</small>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn-secondary" onclick="closeProfileModal()">Cancel</button>
                <button type="button" class="btn-primary" onclick="saveProfileChanges()">
                    <i class="fas fa-save"></i> Save Changes
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    document.getElementById('edit-username').focus();
}

function showPasswordChangeModal(userData) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content password-change-modal">
            <div class="modal-header">
                <h3><i class="fas fa-key"></i> Change Password</h3>
                <button class="modal-close" onclick="closePasswordModal()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <form id="password-change-form">
                    <div class="form-group">
                        <label for="change-current-password">Current Password *</label>
                        <input type="password" id="change-current-password" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="change-new-password">New Password *</label>
                        <input type="password" id="change-new-password" required>
                        <small class="form-text">Must be at least 8 characters with uppercase, lowercase, number, and special character</small>
                    </div>
                    
                    <div class="form-group">
                        <label for="change-confirm-password">Confirm New Password *</label>
                        <input type="password" id="change-confirm-password" required>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn-secondary" onclick="closePasswordModal()">Cancel</button>
                <button type="button" class="btn-primary" onclick="savePasswordChange()">
                    <i class="fas fa-save"></i> Change Password
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    document.getElementById('change-current-password').focus();
}

window.closeProfileModal = function() {
    const modal = document.querySelector('.profile-edit-modal').closest('.modal-overlay');
    if (modal) {
        modal.remove();
    }
};

window.closePasswordModal = function() {
    const modal = document.querySelector('.password-change-modal').closest('.modal-overlay');
    if (modal) {
        modal.remove();
    }
};

window.saveProfileChanges = function() {
    const form = document.getElementById('profile-edit-form');
    const formData = {
        username: document.getElementById('edit-username').value.trim(),
        email: document.getElementById('edit-email').value.trim(),
        first_name: document.getElementById('edit-first-name').value.trim(),
        last_name: document.getElementById('edit-last-name').value.trim(),
        display_name: document.getElementById('edit-display-name').value.trim(),
        current_password: document.getElementById('edit-current-password').value,
        new_password: document.getElementById('edit-new-password').value || null
    };
    
    // Validation
    if (!formData.username || !formData.email || !formData.display_name || !formData.current_password) {
        alert('Please fill in all required fields');
        return;
    }
    
    if (formData.new_password && formData.new_password !== document.getElementById('edit-confirm-password').value) {
        alert('New password and confirmation do not match');
        return;
    }
    
    // Show loading state
    const saveBtn = document.querySelector('.profile-edit-modal .btn-primary');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    saveBtn.disabled = true;
    
    // Send update request
    fetch('/api/users/update-profile', {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Profile updated successfully!');
            closeProfileModal();
            // Refresh account info
            renderAccountInfo();
            // Update welcome message if needed
            if (window.updateWelcomeMessages) {
                window.updateWelcomeMessages(data.user.display_name);
            }
        } else {
            alert('Error: ' + (data.error || 'Failed to update profile'));
        }
    })
    .catch(error => {
        console.error('Error updating profile:', error);
        alert('Failed to update profile. Please try again.');
    })
    .finally(() => {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    });
};

window.savePasswordChange = function() {
    const formData = {
        current_password: document.getElementById('change-current-password').value,
        new_password: document.getElementById('change-new-password').value,
        confirm_password: document.getElementById('change-confirm-password').value
    };
    
    // Validation
    if (!formData.current_password || !formData.new_password || !formData.confirm_password) {
        alert('Please fill in all fields');
        return;
    }
    
    if (formData.new_password !== formData.confirm_password) {
        alert('New password and confirmation do not match');
        return;
    }
    
    // Show loading state
    const saveBtn = document.querySelector('.password-change-modal .btn-primary');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Changing...';
    saveBtn.disabled = true;
    
    // Send update request
    fetch('/api/users/update-profile', {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            username: currentUserData.username,
            email: currentUserData.email,
            first_name: currentUserData.first_name || '',
            last_name: currentUserData.last_name || '',
            display_name: currentUserData.display_name,
            current_password: formData.current_password,
            new_password: formData.new_password
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Password changed successfully!');
            closePasswordModal();
        } else {
            alert('Error: ' + (data.error || 'Failed to change password'));
        }
    })
    .catch(error => {
        console.error('Error changing password:', error);
        alert('Failed to change password. Please try again.');
    })
    .finally(() => {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    });
};

window.confirmLogout = function() {
    if (confirm('Are you sure you want to sign out?')) {
        logout();
    }
};

async function loadModelManagementData() {
    try {
        await Promise.all([
            loadApiKeysStatus(),
            loadCurrentModelsList()
        ]);
        
        // Ensure API key dropdown is populated after a short delay
        setTimeout(() => {
            const dropdown = document.getElementById('model-api-key');
            if (dropdown && dropdown.options.length <= 1) {
                console.log('Retrying API key dropdown population...');
                // Re-fetch and populate if dropdown is empty
                fetch('/api/api-keys/status')
                    .then(response => response.json())
                    .then(apiKeys => populateApiKeyDropdown(apiKeys))
                    .catch(error => console.error('Error retrying API key dropdown:', error));
            }
        }, 500);
        
    } catch (error) {
        console.error('Error loading model management data:', error);
    }
}

async function loadApiKeysStatus() {
    const container = document.getElementById('api-keys-status');
    if (!container) return;
    
    try {
        container.innerHTML = '<div class="loading">Loading API key status...</div>';
        
        const response = await fetch('/api/api-keys/status');
        const apiKeys = await response.json();
        
        let html = '';
        Object.entries(apiKeys).forEach(([keyName, info]) => {
            const status = info.configured ? '✅ Configured' : '❌ Not Found';
            const statusClass = info.configured ? 'configured' : 'not-configured';
            
            html += `
                <div class="api-key-simple ${statusClass}">
                    <div class="api-key-info">
                        <span class="api-key-name">${keyName}</span>
                        <span class="api-key-provider">(${info.provider})</span>
                    </div>
                    <div class="api-key-status">${status}</div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        
        // Also populate the API key dropdown
        populateApiKeyDropdown(apiKeys);
        
    } catch (error) {
        console.error('Error loading API key status:', error);
        container.innerHTML = '<div class="error">Failed to load API key status</div>';
    }
}

function populateApiKeyDropdown(apiKeys) {
    const dropdown = document.getElementById('model-api-key');
    if (!dropdown) {
        console.log('API key dropdown not found, will retry later');
        return;
    }
    
    console.log('Populating API key dropdown with:', apiKeys);
    
    // Clear existing options except the first one
    dropdown.innerHTML = '<option value="">Auto-detect from provider</option>';
    
    // Add all available API keys
    Object.entries(apiKeys).forEach(([keyName, info]) => {
        const status = info.configured ? '✅' : '❌';
        const option = document.createElement('option');
        option.value = keyName;
        option.textContent = `${keyName} ${status} (${info.provider})`;
        dropdown.appendChild(option);
    });
    
    console.log('API key dropdown populated with', dropdown.options.length, 'options');
}

async function loadCurrentModelsList() {
    const container = document.getElementById('current-models-list');
    if (!container) return;
    
        try {
            container.innerHTML = '<div class="loading">Loading models...</div>';
            
            // Load models, settings, and preferences in parallel
            const [modelsResponse, settingsResponse, prefsResponse] = await Promise.all([
                fetch('/api/models'),
                fetch('/api/model-settings'),
                fetch('/api/preferences')
            ]);
            
            const dynamicModels = await modelsResponse.json();
            const settings = settingsResponse.ok ? await settingsResponse.json() : {};
            const preferences = prefsResponse.ok ? await prefsResponse.json() : {};
            
            console.log('Dynamic models:', dynamicModels);
            console.log('Settings:', settings);
            console.log('Preferences:', preferences);
        
        // Create a combined list of all models (dynamic + legacy from settings)
        const allModels = new Map();
        
        // Add dynamic models first
        dynamicModels.forEach(model => {
            allModels.set(model.name, {
                ...model,
                isDynamic: true
            });
        });
        
        console.log('After adding dynamic models:', Array.from(allModels.keys()));
        
        // No longer adding legacy models - all models should be in the dynamic list
        
        const modelsList = Array.from(allModels.values());
        console.log('Final models list:', modelsList);
        
        if (modelsList.length === 0) {
            container.innerHTML = '<div class="no-models">No models configured. Add some models above!</div>';
            return;
        }
        
               let html = `
                   <div class="model-row header">
                       <div>Model Name</div>
                       <div>Provider</div>
                       <div>API Key</div>
                       <div>Enabled</div>
                       <div>Default</div>
                       <div>Status</div>
                       <div>Actions</div>
                   </div>
               `;
        
        modelsList.forEach(model => {
            // Use model_value (API identifier) to look up settings, not display name
            const modelKey = model.model_value || model.name;
            const modelSettings = settings[modelKey] || { enabled: false };
            const enabledStatus = modelSettings.enabled ? '✅ Yes' : '❌ No';
            const enabledClass = modelSettings.enabled ? 'enabled' : 'disabled';
            const modelType = model.isDynamic ? '' : ' (Legacy)';
            const isDefault = preferences.defaultModel === modelKey;
            
                   html += `
                       <div class="model-row" data-model="${modelKey}">
                           <div class="model-name">
                               ${model.name}${modelType}
                               ${!model.isDynamic ? '<button class="btn-tiny btn-migrate" onclick="migrateModel(\''+modelKey+'\')" title="Migrate to dynamic system"><i class="fas fa-arrow-up"></i></button>' : ''}
                           </div>
                           <div class="model-provider">${model.provider}</div>
                           <div class="model-api-key">${model.api_key || 'Auto-detected'}</div>
                           <div class="model-enabled ${enabledClass}">
                               <label class="toggle-switch" title="Toggle model enabled/disabled">
                                   <input type="checkbox" ${modelSettings.enabled ? 'checked' : ''} 
                                          onchange="toggleModelEnabledInManagement('${modelKey}', this.checked)">
                                   <span class="toggle-slider"></span>
                               </label>
                           </div>
                           <div class="model-default">
                               <label class="radio-container" title="Set as default model">
                                   <input type="radio" name="default-model" value="${modelKey}" 
                                          ${isDefault ? 'checked' : ''} 
                                          ${!modelSettings.enabled ? 'disabled' : ''}
                                          onchange="setDefaultModel('${modelKey}')">
                                   <span class="radio-checkmark"></span>
                               </label>
                           </div>
                           <div class="model-status" id="mgmt-status-${modelKey}">
                               <span class="status-unknown">Unknown</span>
                           </div>
                          <div class="model-actions">
                              <button class="btn-small btn-secondary" onclick="testModelInManagement('${modelKey}')" title="Test Access">
                                  <i class="fas fa-flask"></i>
                              </button>
                              ${model.isDynamic ? '<button class="btn-small btn-secondary btn-edit-model" data-model-name="'+model.name+'" data-model-value="'+(model.model_value||model.name)+'" data-model-provider="'+model.provider+'" data-model-apikey="'+(model.api_key||'')+'" data-model-description="'+(model.description||'')+'" title="Edit Model"><i class="fas fa-edit"></i></button>' : ''}
                              ${model.isDynamic ? '<button class="btn-small btn-danger" onclick="deleteModel(\''+model.name+'\')" title="Remove Model"><i class="fas fa-trash"></i></button>' : ''}
                          </div>
                       </div>
                   `;
        });
        
        container.innerHTML = html;
        
        // Add event listeners for edit buttons
        container.querySelectorAll('.btn-edit-model').forEach(btn => {
            btn.addEventListener('click', function() {
                const modelName = this.dataset.modelName;
                const modelValue = this.dataset.modelValue;
                const provider = this.dataset.modelProvider;
                const apiKey = this.dataset.modelApikey;
                const description = this.dataset.modelDescription;
                editModel(modelName, provider, apiKey, description, modelValue);
            });
        });
        
        // Auto-test all models after loading
        setTimeout(() => {
            modelsList.forEach(model => {
                testModelInManagement(model.name, false); // false = don't show alert
            });
        }, 500);
        
    } catch (error) {
        console.error('Error loading current models:', error);
        container.innerHTML = '<div class="error">Failed to load models</div>';
    }
}

window.addModel = async function() {
    const nameInput = document.getElementById('model-name');
    const valueInput = document.getElementById('model-value');
    const providerSelect = document.getElementById('model-provider');
    const apiKeySelect = document.getElementById('model-api-key');
    const descriptionInput = document.getElementById('model-description');
    const addBtn = document.getElementById('add-model-btn');
    
    const name = nameInput.value.trim();
    const modelValue = valueInput.value.trim();
    const provider = providerSelect.value;
    const apiKey = apiKeySelect.value.trim();
    const description = descriptionInput.value.trim();
    
    if (!name || !provider) {
        alert('Please enter a display name and select a provider');
        return;
    }
    
    if (!modelValue) {
        alert('Please enter the Model Identifier (the actual API model name)');
        return;
    }
    
    try {
        addBtn.disabled = true;
        addBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
        
        const payload = {
            name: name,
            model_value: modelValue,
            provider: provider,
            description: description || `${provider} model`
        };
        
        // Add API key if specified (not empty string)
        if (apiKey) {
            payload.api_key = apiKey;
        }
        
        console.log('Adding model with payload:', payload);
        
        const response = await fetch('/api/models', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });
        
        const result = await response.json();
        console.log('Add model response:', result);
        
        if (response.ok && result.success) {
            // Clear form
            nameInput.value = '';
            valueInput.value = '';
            providerSelect.value = '';
            apiKeySelect.value = '';
            descriptionInput.value = '';
            
            // Auto-enable the new model
            try {
                const settingsResponse = await fetch('/api/model-settings');
                const settings = settingsResponse.ok ? await settingsResponse.json() : {};
                
                // Enable the new model by default
                settings[name] = { enabled: true, status: 'unknown' };
                
                await fetch('/api/model-settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(settings)
                });
            } catch (settingsError) {
                console.log('Could not auto-enable model:', settingsError);
            }
            
            // Reload models list
            await loadCurrentModelsList();
            
            alert(`✓ Model "${name}" added successfully and enabled!`);
        } else {
            alert(`✗ Failed to add model: ${result.error || 'Unknown error'}`);
        }
        
    } catch (error) {
        console.error('Error adding model:', error);
        alert(`✗ Network error: ${error.message}`);
    } finally {
        addBtn.disabled = false;
        addBtn.innerHTML = '<i class="fas fa-plus"></i> Add Model';
    }
};
window.testModelInManagement = async function(modelName, showAlert = true) {
    const statusElement = document.getElementById(`mgmt-status-${modelName}`);
    
    try {
        if (statusElement) {
            statusElement.innerHTML = '<span class="status-testing">Testing...</span>';
        }
        
        console.log(`Testing model access for: ${modelName}`);
        
        const response = await fetch('/api/check-model-access', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ model: modelName })
        });
        
        console.log(`Response status: ${response.status}`);
        console.log(`Response headers:`, response.headers);
        
        // Check if response is actually JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            console.error(`Expected JSON but got: ${contentType}`);
            const textResponse = await response.text();
            console.error(`Response text:`, textResponse.substring(0, 500));
            
            if (statusElement) {
                statusElement.innerHTML = '<span class="status-error">Server Error</span>';
            }
            if (showAlert) {
                alert(`✗ ${modelName}: Server returned HTML instead of JSON. Check console for details.`);
            }
            return;
        }
        
        const result = await response.json();
        console.log(`API response for ${modelName}:`, result);
        
        if (response.ok && result.success) {
            const status = result.hasAccess ? 'Available' : 'No Access';
            const statusClass = result.hasAccess ? 'status-available' : 'status-error';
            
            if (statusElement) {
                statusElement.innerHTML = `<span class="${statusClass}">${status}</span>`;
            }
            
            if (showAlert) {
                const message = result.hasAccess 
                    ? `✓ ${modelName}: Available (${result.api_key_name})`
                    : `✗ ${modelName}: ${result.status} (${result.api_key_name})`;
                
                alert(message);
            }
        } else {
            if (statusElement) {
                statusElement.innerHTML = '<span class="status-error">Error</span>';
            }
            if (showAlert) {
                alert(`✗ ${modelName}: ${result.error || 'Test failed'}`);
            }
        }
        
    } catch (error) {
        console.error(`Error testing ${modelName}:`, error);
        if (statusElement) {
            statusElement.innerHTML = '<span class="status-error">Network Error</span>';
        }
        if (showAlert) {
            alert(`✗ ${modelName}: Network error - ${error.message}`);
        }
    }
};

window.editModel = function(modelName, provider, apiKey, description, modelValue) {
    console.log('editModel called:', modelName, provider, apiKey, description, modelValue);
    
    // Populate the form with existing values
    const nameInput = document.getElementById('model-name');
    const valueInput = document.getElementById('model-value');
    const providerSelect = document.getElementById('model-provider');
    const apiKeySelect = document.getElementById('model-api-key');
    const descInput = document.getElementById('model-description');
    const addBtn = document.getElementById('add-model-btn');
    
    console.log('Form elements:', { nameInput, valueInput, providerSelect, apiKeySelect, descInput, addBtn });
    
    if (!nameInput || !valueInput || !providerSelect || !addBtn) {
        console.error('Form elements not found!');
        alert('Error: Form elements not found. Make sure the Model Management modal is open.');
        return;
    }
    
    nameInput.value = modelName;
    valueInput.value = modelValue || modelName;  // Fallback to modelName if modelValue not provided
    providerSelect.value = provider;
    if (apiKeySelect) apiKeySelect.value = apiKey || '';
    if (descInput) descInput.value = description || '';
    
    // Change the add button to update button
    addBtn.innerHTML = '<i class="fas fa-save"></i> Update Model';
    addBtn.onclick = () => updateModel(modelName);
    
    // Scroll to the form
    const form = document.querySelector('.add-model-form-grid');
    if (form) {
        form.scrollIntoView({ behavior: 'smooth' });
    }
    
    console.log('Edit form populated successfully');
};

window.updateModel = async function(originalName) {
    const nameInput = document.getElementById('model-name');
    const valueInput = document.getElementById('model-value');
    const providerSelect = document.getElementById('model-provider');
    const apiKeySelect = document.getElementById('model-api-key');
    const descInput = document.getElementById('model-description');
    const addBtn = document.getElementById('add-model-btn');
    
    const newName = nameInput.value.trim();
    const modelValue = valueInput.value.trim();
    const provider = providerSelect.value;
    const apiKey = apiKeySelect.value || null;
    const description = descInput.value.trim() || null;
    
    if (!newName || !provider) {
        alert('Please fill in display name and provider');
        return;
    }
    
    if (!modelValue) {
        alert('Please fill in the Model Identifier');
        return;
    }
    
    try {
        addBtn.disabled = true;
        addBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating...';
        
        // Delete old model if name changed
        if (originalName !== newName) {
            await fetch(`/api/models/${encodeURIComponent(originalName)}`, {
                method: 'DELETE'
            });
        }
        
        // Add/update model
        const response = await fetch('/api/models', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: newName,
                model_value: modelValue,
                provider: provider,
                api_key: apiKey,
                description: description
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            // Reset form
            nameInput.value = '';
            valueInput.value = '';
            providerSelect.value = '';
            apiKeySelect.value = '';
            descInput.value = '';
            
            // Reset button
            addBtn.innerHTML = '<i class="fas fa-plus"></i> Add Model';
            addBtn.onclick = addModel;
            
            await loadCurrentModelsList();
            alert(`✓ Model "${newName}" updated successfully!`);
        } else {
            alert(`✗ Failed to update model: ${result.error || 'Unknown error'}`);
        }
        
    } catch (error) {
        console.error('Error updating model:', error);
        alert(`✗ Network error: ${error.message}`);
    } finally {
        addBtn.disabled = false;
    }
};

window.deleteModel = async function(modelName) {
    if (!confirm(`Are you sure you want to remove the model "${modelName}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/models/${encodeURIComponent(modelName)}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            await loadCurrentModelsList();
            alert(`✓ Model "${modelName}" removed successfully!`);
        } else {
            alert(`✗ Failed to remove model: ${result.error || 'Unknown error'}`);
        }
        
    } catch (error) {
        console.error('Error removing model:', error);
        alert(`✗ Network error: ${error.message}`);
    }
};

window.testModelAccess = async function() {
    const nameInput = document.getElementById('model-name');
    const providerSelect = document.getElementById('model-provider');
    const testBtn = document.getElementById('test-model-btn');
    
    const name = nameInput.value.trim();
    const provider = providerSelect.value;
    
    if (!name || !provider) {
        alert('Please enter a model name and select a provider to test');
        return;
    }
    
    try {
        testBtn.disabled = true;
        testBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
        
        const response = await fetch('/api/check-model-access', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ model: name })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            const message = result.hasAccess 
                ? `✓ ${name}: API key available! (${result.api_key_name})`
                : `✗ ${name}: API key not configured (${result.api_key_name})`;
            
            alert(message);
        } else {
            alert(`✗ ${name}: ${result.error || 'Test failed'}`);
        }
        
    } catch (error) {
        console.error(`Error testing ${name}:`, error);
        alert(`✗ ${name}: Network error - ${error.message}`);
    } finally {
        testBtn.disabled = false;
        testBtn.innerHTML = '<i class="fas fa-flask"></i> Test Access';
    }
};

window.refreshModelManagement = async function() {
    await loadModelManagementData();
};

// Function to test all models
window.testAllModels = async function() {
    const testBtn = document.getElementById('test-all-models-btn');
    const modelsList = document.getElementById('current-models-list');
    
    if (!modelsList) {
        alert('Models list not found');
        return;
    }
    
    try {
        testBtn.disabled = true;
        testBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing All Models...';
        
        // Get all model rows
        const modelRows = modelsList.querySelectorAll('[data-model]');
        
        if (modelRows.length === 0) {
            alert('No models found to test');
            testBtn.disabled = false;
            testBtn.innerHTML = '<i class="fas fa-flask"></i> Test All Models';
            return;
        }
        
        let successCount = 0;
        let failCount = 0;
        
        // Test each model
        for (const row of modelRows) {
            const modelName = row.getAttribute('data-model');
            const statusCell = row.querySelector('.model-status');
            
            try {
                // Show testing status
                if (statusCell) {
                    statusCell.innerHTML = '<span class="status-testing">Testing...</span>';
                }
                
                // Test model access
                const response = await fetch('/api/check-model-access', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ model: modelName })
                });
                
                const result = await response.json();
                
                if (response.ok && result.hasAccess) {
                    // Update status to available
                    if (statusCell) {
                        statusCell.innerHTML = '<span class="status-available">✓ Available</span>';
                    }
                    successCount++;
                } else {
                    // Update status to error
                    if (statusCell) {
                        statusCell.innerHTML = '<span class="status-error">✗ Error</span>';
                    }
                    failCount++;
                }
            } catch (error) {
                console.error(`Error testing ${modelName}:`, error);
                if (statusCell) {
                    statusCell.innerHTML = '<span class="status-error">✗ Error</span>';
                }
                failCount++;
            }
            
            // Small delay between requests to avoid rate limiting
            await new Promise(resolve => setTimeout(resolve, 200));
        }
        
        // Show summary
        alert(`Test Complete:\n✓ Available: ${successCount}\n✗ Error: ${failCount}`);
        
    } catch (error) {
        console.error('Error testing models:', error);
        alert(`Error testing models: ${error.message}`);
    } finally {
        testBtn.disabled = false;
        testBtn.innerHTML = '<i class="fas fa-flask"></i> Test All Models';
    }
};

// Function to toggle model enabled status from Model Management
window.toggleModelEnabledInManagement = async function(modelName, newEnabledState) {
    try {
        console.log(`Toggling model ${modelName} to ${newEnabledState ? 'enabled' : 'disabled'}`);
        
        // Load current settings
        const response = await fetch('/api/model-settings');
        const settings = response.ok ? await response.json() : {};
        
        // Update the specific model
        settings[modelName] = settings[modelName] || {};
        settings[modelName].enabled = newEnabledState;
        
        // Save back to server
        const saveResponse = await fetch('/api/model-settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(settings)
        });
        
        if (saveResponse.ok) {
            console.log(`Successfully toggled ${modelName} to ${newEnabledState ? 'enabled' : 'disabled'}`);
            
            // Update the visual state of the row immediately (without full reload)
            const modelRow = document.querySelector(`[data-model="${modelName}"]`);
            if (modelRow) {
                const enabledCell = modelRow.querySelector('.model-enabled');
                if (enabledCell) {
                    enabledCell.className = `model-enabled ${newEnabledState ? 'enabled' : 'disabled'}`;
                }
                
                // Handle default radio button - disable if model is disabled
                const radioButton = modelRow.querySelector('input[type="radio"]');
                if (radioButton) {
                    radioButton.disabled = !newEnabledState;
                    // If disabling a model that was the default, clear the default
                    if (!newEnabledState && radioButton.checked) {
                        radioButton.checked = false;
                        // Clear the default model preference
                        await setDefaultModel(''); // Empty string clears default
                    }
                }
            }
            
            // No longer reloading settings panel models list - removed from UI
            // if (window.app && window.app.loadModelsForSettingsPanel) {
            //     window.app.loadModelsForSettingsPanel();
            // }
            
            // Refresh the main model dropdown
            if (window.app && window.app.loadMainModelDropdown) {
                await window.app.loadMainModelDropdown();
            }
            
        } else {
            console.error('Failed to save model settings');
            alert('Failed to save model settings');
            
            // Revert the checkbox state on error
            const checkbox = document.querySelector(`[data-model="${modelName}"] input[type="checkbox"]`);
            if (checkbox) {
                checkbox.checked = !newEnabledState;
            }
        }
        
    } catch (error) {
        console.error('Error toggling model enabled status:', error);
        alert('Error updating model status: ' + error.message);
        
        // Revert the checkbox state on error
        const checkbox = document.querySelector(`[data-model="${modelName}"] input[type="checkbox"]`);
        if (checkbox) {
            checkbox.checked = !newEnabledState;
        }
    }
};

// Function to set the default model
window.setDefaultModel = async function(modelName) {
    try {
        console.log(`Setting default model to: ${modelName || '(none)'}`);
        
        // Update preferences
        const response = await fetch('/api/preferences', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                defaultModel: modelName || '' // Handle empty string for clearing default
            })
        });
        
        if (response.ok) {
            console.log(`Successfully set default model to: ${modelName || '(none)'}`);
            
            // Refresh the main model dropdown to show the new default
            if (window.app && window.app.loadMainModelDropdown) {
                await window.app.loadMainModelDropdown();
            }
            
            // Show a brief success message only if setting a model (not clearing)
            if (modelName) {
                const statusElement = document.getElementById(`mgmt-status-${modelName}`);
                if (statusElement) {
                    const originalContent = statusElement.innerHTML;
                    statusElement.innerHTML = '<span class="status-success">Default Set!</span>';
                    setTimeout(() => {
                        statusElement.innerHTML = originalContent;
                    }, 2000);
                }
            }
            
        } else {
            const error = await response.json();
            console.error(`Failed to set default model:`, error);
            
            // Only show alert if we were trying to set a model (not clear it)
            if (modelName) {
                alert(`Failed to set default model: ${error.error || 'Unknown error'}`);
                
                // Revert the radio button selection
                const radioButtons = document.querySelectorAll('input[name="default-model"]');
                radioButtons.forEach(radio => {
                    if (radio.value === modelName) {
                        radio.checked = false;
                    }
                });
            }
        }
        
    } catch (error) {
        console.error(`Error setting default model:`, error);
        
        // Only show alert if we were trying to set a model (not clear it)
        if (modelName) {
            alert(`Error setting default model: ${error.message}`);
            
            // Revert the radio button selection
            const radioButtons = document.querySelectorAll('input[name="default-model"]');
            radioButtons.forEach(radio => {
                if (radio.value === modelName) {
                    radio.checked = false;
                }
            });
        }
    }
};

// Populate default model select dropdown in preferences
window.populateDefaultModelSelect = async function() {
    const dropdown = document.getElementById('default-model-select');
    if (!dropdown) {
        console.error('Default model select dropdown not found');
        return;
    }
    
    try {
        // Show loading state
        dropdown.innerHTML = '<option value="">Loading models...</option>';
        
        // Get model settings to find enabled models
        const settingsResponse = await fetch('/api/model-settings');
        if (!settingsResponse.ok) {
            throw new Error('Failed to load model settings');
        }
        
        const modelSettings = await settingsResponse.json();
        
        // Get all available models
        const modelsResponse = await fetch('/api/models');
        if (!modelsResponse.ok) {
            throw new Error('Failed to load models');
        }
        
        const allModels = await modelsResponse.json();
        
        // Filter to only enabled models
        const enabledModels = allModels.filter(model => {
            const settings = modelSettings[model.name];
            return settings && settings.enabled;
        });
        
        // Populate dropdown
        dropdown.innerHTML = '<option value="">-- Select Default Model --</option>';
        enabledModels.forEach(model => {
            const option = document.createElement('option');
            option.value = model.name;
            option.textContent = model.name;
            dropdown.appendChild(option);
        });
        
        // Load current preference and set selected value
        const prefsResponse = await fetch('/api/preferences');
        if (prefsResponse.ok) {
            const prefs = await prefsResponse.json();
            if (prefs.defaultModel) {
                dropdown.value = prefs.defaultModel;
            }
        }
        
        console.log('Default model dropdown populated with', enabledModels.length, 'models');
        
    } catch (error) {
        console.error('Error populating default model select:', error);
        dropdown.innerHTML = '<option value="">Error loading models</option>';
    }
};

// Update default model when dropdown changes
window.updateDefaultModel = async function() {
    const dropdown = document.getElementById('default-model-select');
    if (!dropdown) {
        console.error('Default model select dropdown not found');
        return;
    }
    
    const selectedModel = dropdown.value;
    console.log('Default model changed to:', selectedModel || '(none)');
    
    // Auto-save the preference when changed
    await savePreferences();
};

// Save user preferences
window.savePreferences = async function() {
    const dropdown = document.getElementById('default-model-select');
    if (!dropdown) {
        console.error('Default model select dropdown not found');
        return;
    }
    
    const selectedModel = dropdown.value;
    
    try {
        console.log('Saving preference - default model:', selectedModel || '(none)');
        
        const response = await fetch('/api/preferences', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                defaultModel: selectedModel || ''
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to save preferences');
        }
        
        console.log('Preferences saved successfully');
        alert('Preferences saved successfully!');
        
        // Refresh the main model dropdown if available
        if (window.app && window.app.loadMainModelDropdown) {
            await window.app.loadMainModelDropdown();
        }
        
    } catch (error) {
        console.error('Error saving preferences:', error);
        alert('Error saving preferences: ' + error.message);
    }
};

// ==================== TEMPLATE & PROMPT LIBRARY ====================

// Dynamic template data (loaded from API, fallback to hardcoded)
let TEMPLATE_DATA = {};

// Fallback template data
const TEMPLATE_DATA_FALLBACK = {
    'email-template': {
        name: 'Email Template',
        content: 'Please help me write a professional email about {{topic}}. The email should be {{tone}} and include {{details}}.',
        category: 'writing',
        defaultModel: 'claude-3.5-sonnet',
        icon: 'fas fa-envelope',
        description: 'Professional email writing',
        usageCount: 245,
        isPublic: true
    },
    'code-review': {
        name: 'Code Review',
        content: 'Please review this code for best practices, potential bugs, and improvements:\n\n```\n{{code}}\n```\n\nFocus on: {{focus_areas}}',
        category: 'code',
        defaultModel: 'gpt-4',
        icon: 'fas fa-code',
        description: 'Comprehensive code analysis',
        usageCount: 189,
        isPublic: true
    },
    'meeting-notes': {
        name: 'Meeting Notes',
        content: 'Please help me organize these meeting notes into a structured format:\n\n{{notes}}\n\nInclude: agenda, key decisions, action items, and next steps.',
        category: 'writing',
        defaultModel: 'claude-3.5-sonnet',
        icon: 'fas fa-clipboard',
        description: 'Structured meeting documentation',
        usageCount: 156,
        isPublic: true
    },
    'brainstorming': {
        name: 'Brainstorming',
        content: 'Help me brainstorm creative ideas for {{topic}}. Consider these constraints: {{constraints}}. Generate {{number}} innovative solutions.',
        category: 'creative',
        defaultModel: 'claude-3.5-sonnet',
        icon: 'fas fa-lightbulb',
        description: 'Creative idea generation',
        usageCount: 134,
        isPublic: true
    },
    'research': {
        name: 'Research',
        content: 'Help me research {{topic}}. Please provide:\n1. Key facts and statistics\n2. Current trends\n3. Expert opinions\n4. Potential challenges\n5. Future outlook',
        category: 'research',
        defaultModel: 'gpt-4',
        icon: 'fas fa-search',
        description: 'Academic research assistance',
        usageCount: 98,
        isPublic: true
    },
    'math-problem-solver': {
        name: 'Math Problem Solver',
        content: 'Help me solve this math problem step by step:\n\n{{problem}}\n\nPlease:\n1. Identify what type of problem this is\n2. Show each step clearly\n3. Explain the reasoning\n4. Provide a similar practice problem',
        category: 'mathematics',
        defaultModel: 'gpt-4',
        icon: 'fas fa-calculator',
        description: 'Step-by-step math problem solving',
        usageCount: 0,
        isPublic: true
    },
    'concept-explainer': {
        name: 'Math Concept Explainer',
        content: 'Explain the mathematical concept of {{concept}} to a {{grade_level}} student. Include:\n1. Simple definition\n2. Real-world examples\n3. Visual analogies\n4. Common misconceptions to avoid',
        category: 'mathematics',
        defaultModel: 'claude-3.5-sonnet',
        icon: 'fas fa-lightbulb',
        description: 'Clear mathematical concept explanations',
        usageCount: 0,
        isPublic: true
    },
    'homework-helper': {
        name: 'Math Homework Helper',
        content: 'Help me with my math homework on {{topic}}. The problem is:\n\n{{homework_problem}}\n\nPlease guide me through the solution without giving the answer directly.',
        category: 'mathematics',
        defaultModel: 'gpt-4',
        icon: 'fas fa-book',
        description: 'Guided homework assistance',
        usageCount: 0,
        isPublic: true
    },
    'practice-generator': {
        name: 'Practice Problem Generator',
        content: 'Generate {{number}} practice problems for {{math_topic}} at {{difficulty_level}} level. Include:\n1. The problems\n2. Step-by-step solutions\n3. Answer key',
        category: 'mathematics',
        defaultModel: 'gpt-4',
        icon: 'fas fa-dumbbell',
        description: 'Custom math practice problems',
        usageCount: 0,
        isPublic: true
    },
    'formula-reference': {
        name: 'Formula Reference',
        content: 'Help me understand and apply the formula: {{formula}}\n\nPlease explain:\n1. What each variable represents\n2. When to use this formula\n3. Work through an example\n4. Common mistakes to avoid',
        category: 'mathematics',
        defaultModel: 'claude-3.5-sonnet',
        icon: 'fas fa-square-root-alt',
        description: 'Mathematical formula explanations',
        usageCount: 0,
        isPublic: true
    },
    'word-problem-solver': {
        name: 'Word Problem Solver',
        content: 'Help me solve this word problem:\n\n{{word_problem}}\n\nPlease:\n1. Identify the key information\n2. Determine what we need to find\n3. Choose the appropriate method\n4. Solve step by step\n5. Check the answer makes sense',
        category: 'mathematics',
        defaultModel: 'gpt-4',
        icon: 'fas fa-question-circle',
        description: 'Word problem analysis and solving',
        usageCount: 0,
        isPublic: true
    },
    'blog-post': {
        name: 'Blog Post',
        content: 'Help me write an engaging blog post about {{topic}}. Target audience: {{audience}}. Tone: {{tone}}. Length: {{length}} words.',
        category: 'writing',
        defaultModel: 'claude-3.5-sonnet',
        icon: 'fas fa-blog',
        description: 'Engaging blog content',
        usageCount: 87,
        isPublic: true
    }
};

// Add template loading and management methods
KnowledgeBaseApp.prototype.loadTemplates = async function() {
    try {
        console.log('🔄 Loading templates from API...');
        const response = await fetch('/api/templates');
        if (response.ok) {
            TEMPLATE_DATA = await response.json();
            console.log('✅ Templates loaded from API:', Object.keys(TEMPLATE_DATA).length);
            this.renderTemplateCards();
            this.renderTemplatesManagementList(); // Also update settings list
        } else {
            console.warn('⚠️ API failed, using fallback templates');
            TEMPLATE_DATA = TEMPLATE_DATA_FALLBACK;
            this.renderTemplateCards();
            this.renderTemplatesManagementList(); // Also update settings list
        }
    } catch (error) {
        console.error('❌ Error loading templates:', error);
        console.log('📋 Using fallback templates');
        TEMPLATE_DATA = TEMPLATE_DATA_FALLBACK;
        this.renderTemplateCards();
        this.renderTemplatesManagementList(); // Also update settings list
    }
};

KnowledgeBaseApp.prototype.renderTemplateCards = function() {
    const grid = document.getElementById('template-grid');
    if (!grid) {
        console.warn('⚠️ Template grid not found');
        return;
    }
    
    // Clear existing cards and loading message
    grid.innerHTML = '';
    
    // Render each template
    Object.entries(TEMPLATE_DATA).forEach(([id, template]) => {
        const card = this.createTemplateCard(id, template);
        grid.appendChild(card);
    });
    
    console.log(`✅ Rendered ${Object.keys(TEMPLATE_DATA).length} template cards`);
};
KnowledgeBaseApp.prototype.createTemplateCard = function(id, template) {
    const card = document.createElement('div');
    card.className = 'template-card';
    card.setAttribute('data-category', template.category);
    card.onclick = () => window.app.selectTemplate(id);
    
    const icon = template.icon || 'fas fa-file-alt';
    const usageCount = template.usageCount || 0;
    const defaultModel = template.defaultModel || 'GPT-4';
    
    card.innerHTML = `
        <div class="template-icon">
            <i class="${icon}"></i>
        </div>
        <div class="template-info">
            <h4>${template.name}</h4>
            <p>${template.description || 'Template description'}</p>
            <div class="template-meta">
                <span class="template-model">${defaultModel}</span>
                <span class="template-usage">⭐ ${usageCount} uses</span>
            </div>
        </div>
    `;
    
    return card;
};

// Add template methods to KnowledgeBaseApp prototype
KnowledgeBaseApp.prototype.openTemplatePicker = async function() {
    console.log('✅ Template Picker Opening!');
    console.log('🔍 Checking for modal element...');
    const modal = document.getElementById('template-modal');
    console.log('📦 Modal element:', modal);
    
    if (modal) {
        console.log('✅ Modal found! Current display:', modal.style.display);
        modal.style.display = 'flex';
        console.log('✅ Modal display set to flex. New value:', modal.style.display);
        console.log('📏 Modal computed style:', window.getComputedStyle(modal).display);
        
        // Load/refresh templates when opening picker
        await this.loadTemplates();
        
        setTimeout(() => {
            const searchInput = document.getElementById('template-search');
            if (searchInput) {
                searchInput.focus();
                console.log('✅ Search input focused');
            } else {
                console.warn('⚠️ Template search input not found');
            }
        }, 100);
    } else {
        console.error('❌ Template modal not found in DOM');
        console.log('🔍 All elements with "template" in ID:', 
            Array.from(document.querySelectorAll('[id*="template"]')).map(el => el.id));
    }
};

KnowledgeBaseApp.prototype.closeTemplatePicker = function() {
    const modal = document.getElementById('template-modal');
    if (modal) {
        modal.style.display = 'none';
        const searchInput = document.getElementById('template-search');
        if (searchInput) searchInput.value = '';
        if (this.filterTemplates) {
            this.filterTemplates('all');
        }
    }
};
KnowledgeBaseApp.prototype.selectTemplate = async function(templateId) {
    console.log('📝 Selecting template:', templateId);
    const template = TEMPLATE_DATA[templateId];
    if (!template) {
        console.error('❌ Template not found:', templateId);
        console.log('📋 Available templates:', Object.keys(TEMPLATE_DATA));
        return;
    }
    console.log('✅ Template found:', template);

    // Track template usage
    try {
        await fetch(`/api/templates/${templateId}/usage`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrf-token]')?.content || ''
            }
        });
    } catch (error) {
        console.warn('⚠️ Failed to track template usage:', error);
    }

    // Auto-select the recommended model
    this.selectedModel = template.defaultModel;
    const modelSelector = document.getElementById('llm-model');
    if (modelSelector) {
        modelSelector.value = template.defaultModel;
        modelSelector.dispatchEvent(new Event('change'));
        console.log('✅ Model set to:', template.defaultModel);
    } else {
        console.warn('⚠️ Model selector not found');
    }

    // Populate the message input with template content
    const messageInput = document.getElementById('message-input');
    if (messageInput) {
        messageInput.value = template.content;
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
        messageInput.focus();
        console.log('✅ Template content applied to message input');
    } else {
        console.error('❌ Message input not found');
    }

    // Show notification if available
    if (this.showNotification) {
        this.showNotification(`Template "${template.name}" applied with ${template.defaultModel}`, 'success');
    } else {
        console.log('📢 Template applied:', template.name);
    }

    this.closeTemplatePicker();
};

KnowledgeBaseApp.prototype.searchTemplates = function(query) {
    const cards = document.querySelectorAll('.template-card');
    const searchTerm = query.toLowerCase();

    cards.forEach(card => {
        const title = card.querySelector('h4')?.textContent.toLowerCase() || '';
        const description = card.querySelector('p')?.textContent.toLowerCase() || '';
        
        if (title.includes(searchTerm) || description.includes(searchTerm)) {
            card.style.display = 'flex';
        } else {
            card.style.display = 'none';
        }
    });
};

KnowledgeBaseApp.prototype.filterTemplates = function(category) {
    // Update active tab
    document.querySelectorAll('.category-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    const activeTab = document.querySelector(`[data-category="${category}"]`);
    if (activeTab) {
        activeTab.classList.add('active');
    }

    // Filter cards
    const cards = document.querySelectorAll('.template-card');
    cards.forEach(card => {
        if (category === 'all' || card.dataset.category === category) {
            card.style.display = 'flex';
        } else {
            card.style.display = 'none';
        }
    });
};

KnowledgeBaseApp.prototype.createCustomTemplate = function() {
    this.openTemplateEditor();
    this.closeTemplatePicker();
};

// ==================== TEMPLATE MANAGEMENT FUNCTIONS ====================

KnowledgeBaseApp.prototype.openTemplateEditor = function(templateId = null) {
    const modal = document.getElementById('template-editor-modal');
    const titleText = document.getElementById('editor-title-text');
    const templateIdInput = document.getElementById('template-id');
    
    if (templateId) {
        // Edit existing template
        const template = TEMPLATE_DATA[templateId];
        if (template) {
            titleText.textContent = 'Edit Template';
            templateIdInput.value = templateId;
            document.getElementById('template-name').value = template.name;
            document.getElementById('template-category').value = template.category;
            document.getElementById('template-model').value = template.defaultModel || '';
            document.getElementById('template-icon').value = template.icon || 'fas fa-file-alt';
            document.getElementById('template-description').value = template.description || '';
            document.getElementById('template-content').value = template.content;
            document.getElementById('template-public').checked = template.isPublic || false;
        }
    } else {
        // Create new template
        titleText.textContent = 'New Template';
        templateIdInput.value = '';
        document.getElementById('template-editor-form').reset();
    }
    
    modal.style.display = 'flex';
};

KnowledgeBaseApp.prototype.closeTemplateEditor = function() {
    const modal = document.getElementById('template-editor-modal');
    modal.style.display = 'none';
    document.getElementById('template-editor-form').reset();
};

KnowledgeBaseApp.prototype.saveTemplate = async function() {
    const form = document.getElementById('template-editor-form');
    const templateId = document.getElementById('template-id').value;
    
    // Validate form
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    
    const templateData = {
        name: document.getElementById('template-name').value,
        content: document.getElementById('template-content').value,
        category: document.getElementById('template-category').value,
        defaultModel: document.getElementById('template-model').value || null,
        description: document.getElementById('template-description').value || null,
        icon: document.getElementById('template-icon').value,
        isPublic: document.getElementById('template-public').checked
    };
    
    try {
        let response;
        if (templateId) {
            // Update existing template
            response = await fetch(`/api/templates/${templateId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrf-token]')?.content || ''
                },
                body: JSON.stringify(templateData)
            });
        } else {
            // Create new template
            response = await fetch('/api/templates', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrf-token]')?.content || ''
                },
                body: JSON.stringify(templateData)
            });
        }
        
        if (response.ok) {
            this.showNotification(templateId ? 'Template updated successfully!' : 'Template created successfully!', 'success');
            this.closeTemplateEditor();
            this.refreshTemplatesList();
            // Refresh template picker if it's open
            if (document.getElementById('template-modal').style.display !== 'none') {
                await this.loadTemplates();
            }
        } else {
            const error = await response.json();
            this.showNotification(`Error: ${error.error}`, 'error');
        }
    } catch (error) {
        console.error('Error saving template:', error);
        this.showNotification('Failed to save template', 'error');
    }
};

KnowledgeBaseApp.prototype.deleteTemplate = async function(templateId) {
    if (!confirm('Are you sure you want to delete this template? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/templates/${templateId}`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrf-token]')?.content || ''
            }
        });
        
        if (response.ok) {
            this.showNotification('Template deleted successfully!', 'success');
            this.refreshTemplatesList();
            // Refresh template picker if it's open
            if (document.getElementById('template-modal').style.display !== 'none') {
                await this.loadTemplates();
            }
        } else {
            const error = await response.json();
            this.showNotification(`Error: ${error.error}`, 'error');
        }
    } catch (error) {
        console.error('Error deleting template:', error);
        this.showNotification('Failed to delete template', 'error');
    }
};

KnowledgeBaseApp.prototype.refreshTemplatesList = async function() {
    const container = document.getElementById('templates-list');
    if (!container) return;
    
    container.innerHTML = '<div class="loading-templates">Loading templates...</div>';
    
    try {
        await this.loadTemplates();
        this.renderTemplatesManagementList();
    } catch (error) {
        console.error('Error refreshing templates:', error);
        container.innerHTML = '<div class="error-templates">Failed to load templates</div>';
    }
};

KnowledgeBaseApp.prototype.renderTemplatesManagementList = function() {
    const container = document.getElementById('templates-list');
    if (!container) return;
    
    container.innerHTML = '';
    
    const templates = Object.entries(TEMPLATE_DATA);
    if (templates.length === 0) {
        container.innerHTML = `
            <div class="empty-templates">
                <i class="fas fa-file-alt"></i>
                <h4>No templates yet</h4>
                <p>Create your first template to get started!</p>
                <button class="btn-primary" onclick="openTemplateEditor()">
                    <i class="fas fa-plus"></i>
                    Create Template
                </button>
            </div>
        `;
        return;
    }
    
    templates.forEach(([id, template]) => {
        const item = document.createElement('div');
        item.className = 'template-management-item';
        item.innerHTML = `
            <div class="template-item-info">
                <div class="template-item-header">
                    <div class="template-item-icon">
                        <i class="${template.icon || 'fas fa-file-alt'}"></i>
                    </div>
                    <div class="template-item-details">
                        <h4>${template.name}</h4>
                        <p class="template-item-category">${template.category}</p>
                        <p class="template-item-description">${template.description || 'No description'}</p>
                    </div>
                </div>
                <div class="template-item-meta">
                    <span class="template-item-model">${template.defaultModel || 'No default model'}</span>
                    <span class="template-item-usage">⭐ ${template.usageCount || 0} uses</span>
                    ${template.isPublic ? '<span class="template-item-public">🌐 Public</span>' : ''}
                </div>
            </div>
            <div class="template-item-actions">
                <button class="btn-sm btn-secondary" onclick="window.app.openTemplateEditor('${id}')" title="Edit">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="btn-sm btn-info" onclick="window.app.testTemplate('${id}')" title="Test">
                    <i class="fas fa-play"></i>
                </button>
                <button class="btn-sm btn-danger" onclick="window.app.deleteTemplate('${id}')" title="Delete">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
        container.appendChild(item);
    });
};

KnowledgeBaseApp.prototype.testTemplate = function(templateId) {
    const template = TEMPLATE_DATA[templateId];
    if (!template) return;
    
    const modal = document.getElementById('template-test-modal');
    const preview = document.getElementById('template-preview');
    
    preview.innerHTML = `
        <div class="template-test-content">
            <h4>${template.name}</h4>
            <p><strong>Category:</strong> ${template.category}</p>
            <p><strong>Model:</strong> ${template.defaultModel || 'No default model'}</p>
            <div class="template-content-preview">
                <strong>Content:</strong>
                <pre>${template.content}</pre>
            </div>
        </div>
    `;
    
    modal.style.display = 'flex';
    
    // Store template ID for apply function
    modal.dataset.templateId = templateId;
};

KnowledgeBaseApp.prototype.closeTemplateTest = function() {
    const modal = document.getElementById('template-test-modal');
    modal.style.display = 'none';
    delete modal.dataset.templateId;
};

KnowledgeBaseApp.prototype.applyTestTemplate = function() {
    const modal = document.getElementById('template-test-modal');
    const templateId = modal.dataset.templateId;
    
    if (templateId) {
        this.selectTemplate(templateId);
        this.closeTemplateTest();
    }
};

// Global functions for HTML onclick handlers
function openTemplateEditor(templateId = null) {
    window.app.openTemplateEditor(templateId);
}

function closeTemplateEditor() {
    window.app.closeTemplateEditor();
}

function saveTemplate() {
    window.app.saveTemplate();
}

function testTemplate(templateId) {
    window.app.testTemplate(templateId);
}

function closeTemplateTest() {
    window.app.closeTemplateTest();
}

function applyTestTemplate() {
    window.app.applyTestTemplate();
}

function refreshTemplatesList() {
    window.app.refreshTemplatesList();
}

// ==================== PERSONA MANAGEMENT FUNCTIONS ====================

// Render personas management list
KnowledgeBaseApp.prototype.renderPersonasManagementList = async function() {
    const container = document.getElementById('personas-list');
    if (!container) return;
    
    container.innerHTML = '<div class="loading-personas">Loading personas...</div>';
    
    try {
        const response = await fetch('/api/personas');
        const data = await response.json();
        
        if (data.success) {
            this.displayPersonasList(data.personas);
        } else {
            container.innerHTML = `
                <div class="error-personas">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h4>Error loading personas</h4>
                    <p>${data.error || 'Failed to load personas'}</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading personas:', error);
        container.innerHTML = `
            <div class="error-personas">
                <i class="fas fa-exclamation-triangle"></i>
                <h4>Error loading personas</h4>
                <p>Network error occurred</p>
            </div>
        `;
    }
};

// Display personas list
KnowledgeBaseApp.prototype.displayPersonasList = function(personas) {
    const container = document.getElementById('personas-list');
    if (!container) return;
    
    if (personas.length === 0) {
        container.innerHTML = `
            <div class="empty-personas">
                <i class="fas fa-user-tie"></i>
                <h4>No personas yet</h4>
                <p>Create your first persona to get started!</p>
                <button class="btn-primary" onclick="openPersonaEditor()">
                    <i class="fas fa-plus"></i>
                    Create Persona
                </button>
            </div>
        `;
        return;
    }
    
    // Group personas by category
    const personasByCategory = {};
    personas.forEach(persona => {
        if (!personasByCategory[persona.category]) {
            personasByCategory[persona.category] = [];
        }
        personasByCategory[persona.category].push(persona);
    });
    
    let html = '';
    Object.keys(personasByCategory).sort().forEach(category => {
        html += `
            <div class="personas-category">
                <h4 class="personas-category-title">${category}</h4>
                <div class="personas-category-items">
        `;
        
        personasByCategory[category].forEach(persona => {
            html += `
                <div class="template-management-item" data-persona-id="${persona.id}">
                    <div class="template-item-info">
                        <div class="template-item-header">
                            <div class="template-item-icon">
                                <i class="fas fa-user-tie"></i>
                            </div>
                            <div class="template-item-details">
                                <h4>${persona.name}</h4>
                                <p class="template-item-category">${persona.category}</p>
                                <p class="template-item-description">${persona.description || 'No description'}</p>
                            </div>
                        </div>
                        <div class="template-item-meta">
                            <span class="template-item-model">${persona.agent_name}</span>
                            <span class="template-item-usage">🎭 ${persona.role}</span>
                        </div>
                    </div>
                    <div class="template-item-actions">
                        <button class="btn-sm btn-secondary" onclick="editPersona('${persona.id}')" title="Edit Persona">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn-sm btn-danger" onclick="deletePersona('${persona.id}')" title="Delete Persona">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
};

// Refresh personas list
KnowledgeBaseApp.prototype.refreshPersonasList = async function() {
    await this.renderPersonasManagementList();
};

// Global functions for persona management
function refreshPersonasList() {
    window.app.refreshPersonasList();
}

function openPersonaEditor(personaId = null) {
    // Create persona editor modal
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content persona-editor-modal">
            <div class="modal-header">
                <h3>${personaId ? 'Edit Persona' : 'Create New Persona'}</h3>
                <button class="modal-close" onclick="closePersonaEditor()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <form id="persona-form">
                    <div class="form-group">
                        <label for="persona-name">Persona Name</label>
                        <input type="text" id="persona-name" name="name" required placeholder="e.g., Technical Assistant">
                    </div>
                    <div class="form-group">
                        <label for="persona-agent-name">Agent Name</label>
                        <input type="text" id="persona-agent-name" name="agent_name" required placeholder="e.g., TechBot">
                    </div>
                    <div class="form-group">
                        <label for="persona-category">Category</label>
                        <select id="persona-category" name="category" required>
                            <option value="">Select Category</option>
                            <option value="Technical">Technical</option>
                            <option value="Creative">Creative</option>
                            <option value="Business">Business</option>
                            <option value="Educational">Educational</option>
                            <option value="Customer Service">Customer Service</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="persona-role">Role</label>
                        <textarea id="persona-role" name="role" required placeholder="e.g., Technical Support Specialist"></textarea>
                    </div>
                    <div class="form-group">
                        <label for="persona-traits">Traits</label>
                        <textarea id="persona-traits" name="traits" required placeholder="e.g., Analytical, methodical, detail-oriented"></textarea>
                    </div>
                    <div class="form-group">
                        <label for="persona-description">Description</label>
                        <textarea id="persona-description" name="description" placeholder="Optional description"></textarea>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn-secondary" onclick="closePersonaEditor()">Cancel</button>
                <button type="button" class="btn-primary" onclick="savePersona('${personaId || ''}')">
                    ${personaId ? 'Update Persona' : 'Create Persona'}
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Load existing persona data if editing
    if (personaId) {
        loadPersonaData(personaId);
    }
}

function editPersona(personaId) {
    openPersonaEditor(personaId);
}

async function loadPersonaData(personaId) {
    try {
        const response = await fetch(`/api/personas/${personaId}`);
        const data = await response.json();
        
        if (data.success) {
            const persona = data.persona;
            document.getElementById('persona-name').value = persona.name;
            document.getElementById('persona-agent-name').value = persona.agent_name;
            document.getElementById('persona-category').value = persona.category;
            document.getElementById('persona-role').value = persona.role;
            document.getElementById('persona-traits').value = persona.traits;
            document.getElementById('persona-description').value = persona.description || '';
        }
    } catch (error) {
        console.error('Error loading persona data:', error);
    }
}

async function savePersona(personaId) {
    const form = document.getElementById('persona-form');
    const formData = new FormData(form);
    
    const personaData = {
        name: formData.get('name'),
        agent_name: formData.get('agent_name'),
        category: formData.get('category'),
        role: formData.get('role'),
        traits: formData.get('traits'),
        description: formData.get('description')
    };
    
    try {
        const url = personaId ? `/api/personas/${personaId}` : '/api/personas';
        const method = personaId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(personaData)
        });
        
        const data = await response.json();
        
        if (data.success) {
            closePersonaEditor();
            refreshPersonasList();
            if (window.app && window.app.showNotification) {
                window.app.showNotification(
                    `Persona ${personaId ? 'updated' : 'created'} successfully!`, 
                    'success'
                );
            }
        } else {
            alert(`Error: ${data.error}`);
        }
    } catch (error) {
        console.error('Error saving persona:', error);
        alert('Failed to save persona. Please try again.');
    }
}

function closePersonaEditor() {
    const modal = document.querySelector('.persona-editor-modal');
    if (modal) {
        modal.closest('.modal-overlay').remove();
    }
}

async function deletePersona(personaId) {
    if (!confirm('Are you sure you want to delete this persona? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/personas/${personaId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            refreshPersonasList();
            if (window.app && window.app.showNotification) {
                window.app.showNotification('Persona deleted successfully!', 'success');
            }
        } else {
            alert(`Error: ${data.error}`);
        }
    } catch (error) {
        console.error('Error deleting persona:', error);
        alert('Failed to delete persona. Please try again.');
    }
}

// ==================== END PERSONA MANAGEMENT FUNCTIONS ====================

// Function to migrate a legacy model to the dynamic system
window.migrateModel = async function(modelName) {
    try {
        // Get the legacy model info from the current display
        const modelRow = document.querySelector(`[data-model="${modelName}"]`);
        if (!modelRow) {
            alert('Model not found');
            return;
        }
        
        const provider = modelRow.querySelector('.model-provider').textContent;
        const apiKey = modelRow.querySelector('.model-api-key').textContent;
        
        // Add to dynamic system
        const response = await fetch('/api/models', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                name: modelName,
                provider: provider,
                api_key: apiKey !== 'Auto-detected' ? apiKey : null,
                description: `Migrated ${provider} model`
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            // Reload the models list to show the migrated model
            await loadCurrentModelsList();
            alert(`✓ Model "${modelName}" migrated to dynamic system!`);
        } else {
            alert(`✗ Failed to migrate model: ${result.error || 'Unknown error'}`);
        }
        
    } catch (error) {
        console.error('Error migrating model:', error);
        alert(`✗ Network error: ${error.message}`);
    }
};
// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // CRITICAL FIX: Clear any autofilled content in search field
    const searchField = document.getElementById('conversation-search');
    if (searchField) {
        searchField.value = '';
        console.log('🔧 Cleared search field to prevent autofill issues');
    }
    
    window.app = new KnowledgeBaseApp();
    
    // Ensure context button is visible
    setTimeout(() => {
        if (window.app && window.app.ensureContextButtonVisible) {
        window.app.ensureContextButtonVisible();
        }
    }, 100);
    
    // Confirm template system is loaded
    console.log('📝 Template & Prompt Library: LOADED');
    
    // Check if template modal exists
    const templateModal = document.getElementById('template-modal');
    if (templateModal) {
        console.log('✅ Template modal found in DOM');
    } else {
        console.error('❌ Template modal NOT found in DOM - check index.html');
    }
    
    // Check if template buttons exist
    const templateBtns = document.querySelectorAll('[onclick*="openTemplatePicker"]');
    console.log('🔘 Template buttons found:', templateBtns.length);
    templateBtns.forEach((btn, i) => {
        console.log(`   Button ${i + 1}:`, btn.className, btn.textContent.trim());
    });
    
    // Load dynamic models into main dropdown
    if (window.app && window.app.loadMainModelDropdown) {
    window.app.loadMainModelDropdown();
    }
    
    // Load templates from API (or fallback)
    if (window.app && window.app.loadTemplates) {
    window.app.loadTemplates().then(() => {
        console.log('📋 Available templates:', Object.keys(TEMPLATE_DATA).length);
        console.log('📋 Template IDs:', Object.keys(TEMPLATE_DATA));
    });
    }
    
    // Check admin status and show/hide settings buttons
    if (window.showUsersTabIfAdmin) {
    window.showUsersTabIfAdmin();
    }
    
    // Initialize image paste functionality
    if (window.app && window.app.setupImagePaste) {
    window.app.setupImagePaste();
    }
    
    // Initialize keyboard shortcuts
    if (window.app && window.app.setupKeyboardShortcuts) {
    window.app.setupKeyboardShortcuts();
    }
    
    // Only attach event handlers if elements exist
    const newChatBtn = document.getElementById('new-chat-btn');
    if (newChatBtn) {
        newChatBtn.onclick = function() {
            if (window.app && window.app.startNewChat) {
        window.app.startNewChat();
            }
    };
    }
    
    const settingsBtn = document.getElementById('settings-btn');
    if (settingsBtn) {
        settingsBtn.onclick = function() {
            if (window.app && window.app.openSettingsModal) {
        window.app.openSettingsModal();
            }
    };
    }
});

// Global functions for info button tooltip
function showInfoTooltip(button) {
    const tooltip = button.querySelector('.info-tooltip');
    if (tooltip) {
        // Get button position
        const rect = button.getBoundingClientRect();
        
        // Show tooltip first to get its dimensions
        tooltip.style.display = 'block';
        tooltip.style.visibility = 'hidden'; // Hidden but takes up space
        
        // Calculate position to the right of button
        const tooltipWidth = tooltip.offsetWidth;
        const tooltipHeight = tooltip.offsetHeight;
        
        // Position to the right of the button, centered vertically
        let left = rect.right + 8;
        let top = rect.top + (rect.height / 2) - (tooltipHeight / 2);
        
        // Check if tooltip would go off right edge
        if (left + tooltipWidth > window.innerWidth) {
            // Position to the left of button instead
            left = rect.left - tooltipWidth - 8;
        }
        
        // Check if tooltip would go off top
        if (top < 0) {
            top = 8;
        }
        
        // Check if tooltip would go off bottom
        if (top + tooltipHeight > window.innerHeight) {
            top = window.innerHeight - tooltipHeight - 8;
        }
        
        // Apply position and make visible
        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
        tooltip.style.visibility = 'visible';
        
        // Add mouseenter to keep tooltip visible when hovering over it
        tooltip.addEventListener('mouseenter', function() {
            tooltip.style.display = 'block';
        });
        
        // Add mouseleave to hide tooltip when leaving it
        tooltip.addEventListener('mouseleave', function() {
            tooltip.style.display = 'none';
        });
    }
}

function hideInfoTooltip(button) {
    const tooltip = button.querySelector('.info-tooltip');
    if (tooltip) {
        // Only hide if mouse is not over the tooltip
        setTimeout(() => {
            if (!tooltip.matches(':hover')) {
                tooltip.style.display = 'none';
            }
        }, 100);
    }
}

// Global functions for HTML onclick handlers
function startNewChat() {
    window.app.startNewChat();
}
// Global test function for template modal
function testTemplateModal() {
    console.log('🧪 Testing Template Modal...');
    console.log('1. window.app exists:', !!window.app);
    console.log('2. openTemplatePicker exists:', typeof window.app?.openTemplatePicker);
    
    const modal = document.getElementById('template-modal');
    console.log('3. Modal element:', modal);
    
    if (modal) {
        console.log('   - Display style:', modal.style.display);
        console.log('   - Computed display:', window.getComputedStyle(modal).display);
        console.log('   - Z-index:', window.getComputedStyle(modal).zIndex);
        console.log('   - Position:', window.getComputedStyle(modal).position);
    }
    
    const buttons = document.querySelectorAll('[onclick*="openTemplatePicker"]');
    console.log('4. Template buttons:', buttons.length);
    
    if (window.app && window.app.openTemplatePicker) {
        console.log('5. Attempting to open modal...');
        window.app.openTemplatePicker();
    }
}
console.log('💡 Debug tip: Type testTemplateModal() in console to test the template system');

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
    
    // Refresh the document display to show newly uploaded files
    this.refreshDocumentDisplay();
    
    // Clear the file input for next upload
    event.target.value = '';
};

KnowledgeBaseApp.prototype.showContextUploadMessage = function(filename, preview, fileType, wordCount, taskType) {
    console.log('📄 Showing upload message for:', filename);
    
    // Show success message
    this.showMessage(`✅ File uploaded successfully: ${filename}`, 'success');
    
    // Add visual indicator to context button
    const contextBtn = document.getElementById('context-toggle-btn');
    if (contextBtn) {
        contextBtn.style.backgroundColor = '#4CAF50';
        contextBtn.style.color = 'white';
        contextBtn.title = `Context Panel - ${filename} uploaded`;
        
        // Reset after 3 seconds
        setTimeout(() => {
            contextBtn.style.backgroundColor = '';
            contextBtn.style.color = '';
            contextBtn.title = 'Context Panel';
        }, 3000);
    }
    
    // Refresh context panel if it's open
    if (this.contextPanelOpen) {
        console.log('🔄 Refreshing context panel...');
        setTimeout(() => {
            this.loadContextData().catch(error => {
                console.error('❌ Error refreshing context panel:', error);
            });
        }, 500); // Small delay to ensure backend is updated
    }
    
    // Refresh the document display to show newly uploaded files
    this.refreshDocumentDisplay();
    
    return; // Skip the complex UI update for now
    
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
    if (!container) {
        console.warn('showUrlUploadMessage: Chat container not found, attempting to restore');
        
        // Preserve project context before restoring
        const preserveProject = this.currentProject;
        const preserveViewProject = this.currentViewProject;
        
        this.showChatView();
        
        // Restore project context after restoring chat view
        if (preserveProject) this.currentProject = preserveProject;
        if (preserveViewProject) this.currentViewProject = preserveViewProject;
        
        const retryContainer = document.getElementById('chat-messages');
        if (!retryContainer) {
            console.error('showUrlUploadMessage: Still cannot find chat container');
            return;
        }
        container = retryContainer;
    }
    
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

// Ensure context button is visible when appropriate
KnowledgeBaseApp.prototype.ensureContextButtonVisible = function() {
    const contextToggle = document.getElementById('context-toggle-btn');
    if (contextToggle) {
        // Show context button if we have a current conversation
        if (this.currentConversationId) {
            contextToggle.style.display = 'block';
        } else {
            contextToggle.style.display = 'block'; // Always show it
        }
    }
};

// Global map to store document content for view/download
KnowledgeBaseApp.prototype.documentContentMap = new Map();

// Toggle context panel visibility
function toggleContextPanel() {
    console.log('🔄 Toggling context panel...');
    const panel = document.getElementById('context-panel');
    const toggleBtn = document.getElementById('context-toggle-btn');
    
    console.log('Panel element:', panel);
    console.log('Toggle button:', toggleBtn);
    console.log('Current state:', window.app.contextPanelOpen);
    
    if (!panel) {
        console.error('❌ Context panel not found in DOM');
        return;
    }
    
    if (!toggleBtn) {
        console.error('❌ Context toggle button not found in DOM');
        return;
    }
    
    if (window.app.contextPanelOpen) {
        console.log('📤 Closing context panel');
        panel.style.display = 'none';
        toggleBtn.classList.remove('active');
        window.app.contextPanelOpen = false;
    } else {
        console.log('📥 Opening context panel');
        panel.style.display = 'flex';
        toggleBtn.classList.add('active');
        window.app.contextPanelOpen = true;
        
        // Load context data with error handling
        try {
            window.app.loadContextData();
        } catch (error) {
            console.error('❌ Error loading context data:', error);
            // Show error message to user
            window.app.showMessage('Failed to load context data. Please try again.', 'error');
        }
    }
}

// Load all context data
KnowledgeBaseApp.prototype.loadContextData = async function() {
    console.log('🔄 Loading context data...');
    try {
        // Load user context items
        console.log('📋 Loading context items...');
        await this.loadContextItems();
        
        // Load context stats
        console.log('📊 Loading context stats...');
        await this.loadContextStats();
        
        // Load conversation context if we have a current conversation
        if (this.currentConversationId) {
            console.log('💬 Loading conversation context for:', this.currentConversationId);
            await this.loadConversationContext();
        } else {
            console.log('⚠️ No current conversation ID, skipping conversation context');
        }
        
        console.log('✅ Context data loaded successfully');
        
    } catch (error) {
        console.error('❌ Error loading context data:', error);
        this.showErrorNotification('Failed to load context data');
        
        // Don't close the panel on error, just show the error
        // The panel should stay open so user can see what went wrong
    }
};

// Load user context items
KnowledgeBaseApp.prototype.loadContextItems = async function() {
    try {
        console.log('🌐 Fetching context items from /api/context');
        const response = await fetch('/api/context');
        console.log('📡 Response status:', response.status);
        
        const data = await response.json();
        console.log('📦 Response data:', data);
        
        if (data.success) {
            this.contextItems = data.items;
            console.log('📋 Loaded', data.items.length, 'context items');
            this.renderContextItems();
        } else {
            throw new Error(data.error || 'Failed to load context items');
        }
    } catch (error) {
        console.error('❌ Error loading context items:', error);
        document.getElementById('context-items-list').innerHTML = 
            '<div class="empty-context">Failed to load context items: ' + error.message + '</div>';
        throw error; // Re-throw to be caught by parent function
    }
};

// Load context statistics
KnowledgeBaseApp.prototype.loadContextStats = async function() {
    try {
        const url = this.currentConversationId ? 
            `/api/context/stats?conversation_id=${this.currentConversationId}` : 
            '/api/context/stats';
        
        console.log('🌐 Fetching context stats from:', url);
        console.log('🔍 Current conversation ID:', this.currentConversationId);
        const response = await fetch(url);
        console.log('📡 Stats response status:', response.status);
        
        const data = await response.json();
        console.log('📊 Stats response data:', data);
        
        if (data.success) {
            this.contextStats = data.stats;
            console.log('📊 Loaded context stats:', data.stats);
            this.renderContextStats();
        } else {
            throw new Error(data.error || 'Failed to load context stats');
        }
    } catch (error) {
        console.error('❌ Error loading context stats:', error);
        throw error; // Re-throw to be caught by parent function
    }
};

// Load conversation context
KnowledgeBaseApp.prototype.loadConversationContext = async function() {
    if (!this.currentConversationId) {
        console.log('⚠️ No current conversation ID, skipping conversation context');
        // Show helpful message in the context panel
        const section = document.getElementById('context-conversation-section');
        if (section) {
            section.innerHTML = '<div class="empty-context">Select a conversation to view its context documents</div>';
            section.style.display = 'block';
        }
        return;
    }
    
    try {
        const url = `/api/conversation/${this.currentConversationId}/context`;
        console.log('🌐 Fetching conversation context from:', url);
        const response = await fetch(url);
        console.log('📡 Conversation context response status:', response.status);
        
        const data = await response.json();
        console.log('💬 Conversation context response data:', data);
        
        if (data.success) {
            this.conversationContext = data.context;
            console.log('💬 Loaded', data.context.length, 'conversation context items');
            this.renderConversationContext();
            
            // Show conversation context section
            const section = document.getElementById('context-conversation-section');
            if (section) {
                section.style.display = data.context.length > 0 ? 'block' : 'none';
            } else {
                console.warn('⚠️ context-conversation-section element not found');
            }
        } else {
            throw new Error(data.error || 'Failed to load conversation context');
        }
    } catch (error) {
        console.error('❌ Error loading conversation context:', error);
        throw error; // Re-throw to be caught by parent function
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
                ${item.project_name ? `<div class="context-item-project">📁 ${item.project_name}</div>` : ''}
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
    
    // Update section counts
    this.updateSectionCounts();
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
    
    // Update conversation context count
    this.updateSectionCounts();
};

// Render context stats
KnowledgeBaseApp.prototype.renderContextStats = function() {
    document.getElementById('total-context-items').textContent = this.contextStats.total_items || 0;
    document.getElementById('total-context-tokens').textContent = this.contextStats.total_tokens || 0;
    
    // Update section counts
    this.updateSectionCounts();
};

// Update section counts
KnowledgeBaseApp.prototype.updateSectionCounts = function() {
    const conversationCount = document.getElementById('conversation-context-count');
    const availableCount = document.getElementById('available-context-count');
    
    if (conversationCount) {
        conversationCount.textContent = `${this.conversationContext.length} item${this.conversationContext.length !== 1 ? 's' : ''}`;
    }
    
    if (availableCount) {
        availableCount.textContent = `${this.contextItems.length} item${this.contextItems.length !== 1 ? 's' : ''}`;
    }
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
                ${item.project_name ? `<div class="context-item-project">📁 ${item.project_name}</div>` : ''}
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
    
    // Update section counts for filtered results
    this.updateSectionCounts();
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
    
    // Update section counts for search results
    this.updateSectionCounts();
};

// Highlight search terms in text
KnowledgeBaseApp.prototype.highlightSearchTerm = function(text, searchTerm) {
    if (!text || !searchTerm) return text || '';
    
    const regex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return text.replace(regex, '<mark style="background: #fff3cd; padding: 1px 2px; border-radius: 2px;">$1</mark>');
};

// Escape HTML to prevent XSS
KnowledgeBaseApp.prototype.escapeHtml = function(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
    // This will be implemented in later increments
};
// Edit context item
KnowledgeBaseApp.prototype.editContextItem = function(contextItemId) {
    // Find the context item to edit
    const contextItem = this.contextItems.find(item => item.id === contextItemId);
    if (!contextItem) {
        console.error('Context item not found:', contextItemId);
        return;
    }
    
    // Create modal for editing context
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content context-modal">
            <div class="modal-header">
                <h3><i class="fas fa-edit"></i> Edit Context Item</h3>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <form id="edit-context-form">
                    <div class="form-group">
                        <label for="edit-context-name">Context Name *</label>
                        <input type="text" id="edit-context-name" name="name" required 
                               value="${this.escapeHtml(contextItem.name)}"
                               placeholder="Enter a descriptive name for this context">
                    </div>
                    
                    <div class="form-group">
                        <label for="edit-context-description">Description</label>
                        <textarea id="edit-context-description" name="description" rows="3"
                                  placeholder="Describe what this context contains or its purpose">${this.escapeHtml(contextItem.description || '')}</textarea>
                    </div>
                    
                    <div class="form-group">
                        <label for="edit-context-type">Content Type *</label>
                        <select id="edit-context-type" name="content_type" required>
                            <option value="document" ${contextItem.content_type === 'document' ? 'selected' : ''}>Document</option>
                            <option value="instructions" ${contextItem.content_type === 'instructions' ? 'selected' : ''}>Instructions</option>
                            <option value="notes" ${contextItem.content_type === 'notes' ? 'selected' : ''}>Notes</option>
                            <option value="reference" ${contextItem.content_type === 'reference' ? 'selected' : ''}>Reference</option>
                            <option value="template" ${contextItem.content_type === 'template' ? 'selected' : ''}>Template</option>
                            <option value="other" ${contextItem.content_type === 'other' ? 'selected' : ''}>Other</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="edit-context-content">Content Text *</label>
                        <textarea id="edit-context-content" name="content_text" rows="6" required
                                  placeholder="Enter the actual content or text for this context item">${this.escapeHtml(contextItem.content_text || '')}</textarea>
                        <div class="form-help">This text will be used for AI context and search</div>
                    </div>
                    
                    <div class="form-group">
                        <label for="edit-context-project">Associate with Project (Optional)</label>
                        <select id="edit-context-project" name="project_id">
                            <option value="">No project association</option>
                            ${this.projects ? this.projects.map(p => 
                                `<option value="${p.id}" ${contextItem.project_id === p.id ? 'selected' : ''}>${p.name}</option>`
                            ).join('') : ''}
                        </select>
                    </div>
                    
                    <input type="hidden" name="context_id" value="${contextItemId}">
                </form>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                <button class="btn btn-primary" onclick="submitEditContext()">Update Context</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Focus on first input
    setTimeout(() => {
        document.getElementById('edit-context-name').focus();
    }, 100);
};

// Submit edit context form
function submitEditContext() {
    const form = document.getElementById('edit-context-form');
    const formData = new FormData(form);
    
    // Validate required fields
    const name = formData.get('name').trim();
    const contentType = formData.get('content_type');
    const contentText = formData.get('content_text').trim();
    const contextId = formData.get('context_id');
    
    if (!name || !contentType || !contentText || !contextId) {
        alert('Please fill in all required fields');
        return;
    }
    
    // Prepare data for API
    const contextData = {
        name: name,
        description: formData.get('description').trim() || null,
        content_type: contentType,
        content_text: contentText,
        project_id: formData.get('project_id') || null
    };
    
    // Show loading state
    const submitBtn = document.querySelector('.context-modal .btn-primary');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Updating...';
    submitBtn.disabled = true;
    
    // Call API to update context item
    fetch(`/api/context/${contextId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(contextData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Close modal
            document.querySelector('.modal-overlay').remove();
            
            // Refresh context panel
            if (window.app.contextPanelOpen) {
                window.app.loadContextData();
            }
            
            // Show success message
            window.app.showNotification('Context item updated successfully!', 'success');
        } else {
            throw new Error(data.error || 'Failed to update context item');
        }
    })
    .catch(error => {
        console.error('Error updating context item:', error);
        alert('Error updating context item: ' + error.message);
        
        // Reset button
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
    });
}

// Search context items through content
function searchContextItems() {
    const searchTerm = document.getElementById('context-search').value.trim();
    const clearBtn = document.getElementById('search-clear-btn');
    
    // Show/hide clear button based on search content
    if (searchTerm) {
        clearBtn.style.display = 'block';
    } else {
        clearBtn.style.display = 'none';
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

// Clear context search and show all items
function clearContextSearch() {
    const searchInput = document.getElementById('context-search');
    const clearBtn = document.getElementById('search-clear-btn');
    
    searchInput.value = '';
    clearBtn.style.display = 'none';
    
    // Show all context items
    window.app.renderContextItems();
    
    // Focus back to search input
    searchInput.focus();
}

// Refresh context panel
function refreshContextPanel() {
    if (window.app.contextPanelOpen) {
        window.app.loadContextData();
    }
}

// Add new context
function addNewContext() {
    // Create modal for adding new context
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content context-modal">
            <div class="modal-header">
                <h3><i class="fas fa-plus"></i> Add New Context</h3>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <form id="new-context-form">
                    <div class="form-group">
                        <label for="context-name">Context Name *</label>
                        <input type="text" id="context-name" name="name" required 
                               placeholder="Enter a descriptive name for this context">
                    </div>
                    
                    <div class="form-group">
                        <label for="context-description">Description</label>
                        <textarea id="context-description" name="description" rows="3"
                                  placeholder="Describe what this context contains or its purpose"></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label for="context-type">Content Type *</label>
                        <select id="context-type" name="content_type" required>
                            <option value="">Select content type</option>
                            <option value="document">Document</option>
                            <option value="instructions">Instructions</option>
                            <option value="notes">Notes</option>
                            <option value="reference">Reference</option>
                            <option value="template">Template</option>
                            <option value="other">Other</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="context-content">Content Text *</label>
                        <textarea id="context-content" name="content_text" rows="6" required
                                  placeholder="Enter the actual content or text for this context item"></textarea>
                        <div class="form-help">This text will be used for AI context and search</div>
                    </div>
                    
                    <div class="form-group">
                        <label for="context-project">Associate with Project (Optional)</label>
                        <select id="context-project" name="project_id">
                            <option value="">No project association</option>
                            ${window.app.projects ? window.app.projects.map(p => 
                                `<option value="${p.id}">${p.name}</option>`
                            ).join('') : ''}
                        </select>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                <button class="btn btn-primary" onclick="submitNewContext()">Create Context</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Focus on first input
    setTimeout(() => {
        document.getElementById('context-name').focus();
    }, 100);
}

// Submit new context form
function submitNewContext() {
    const form = document.getElementById('new-context-form');
    const formData = new FormData(form);
    
    // Validate required fields
    const name = formData.get('name').trim();
    const contentType = formData.get('content_type');
    const contentText = formData.get('content_text').trim();
    
    if (!name || !contentType || !contentText) {
        alert('Please fill in all required fields');
        return;
    }
    
    // Prepare data for API
    const contextData = {
        name: name,
        description: formData.get('description').trim() || null,
        content_type: contentType,
        content_text: contentText,
        project_id: formData.get('project_id') || null
    };
    
    // Show loading state
    const submitBtn = document.querySelector('.context-modal .btn-primary');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Creating...';
    submitBtn.disabled = true;
    
    // Call API to create context item
    fetch('/api/context', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(contextData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Close modal
            document.querySelector('.modal-overlay').remove();
            
            // Refresh context panel
            if (window.app.contextPanelOpen) {
                window.app.loadContextData();
            }
            
            // Show success message
            window.app.showNotification('Context item created successfully!', 'success');
        } else {
            throw new Error(data.error || 'Failed to create context item');
        }
    })
    .catch(error => {
        console.error('Error creating context item:', error);
        alert('Error creating context item: ' + error.message);
        
        // Reset button
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
    });
}

// Override loadConversation to update context panel
const originalLoadConversation = KnowledgeBaseApp.prototype.loadConversation;
KnowledgeBaseApp.prototype.loadConversation = function(conversationId) {
    originalLoadConversation.call(this, conversationId);
    
    // Ensure context button is visible
    this.ensureContextButtonVisible();
    
    // Update conversation context if panel is open
    if (this.contextPanelOpen) {
        setTimeout(() => {
            this.loadConversationContext();
        }, 100);
    }
};

// ==================== MAIN CONTENT VIEW METHODS ====================

// Start new chat and focus input area
KnowledgeBaseApp.prototype.startNewChatAndFocus = function() {
    console.log('🚀 Starting new chat and focusing input...');
    
    // Always ensure we're in chat view when starting new chat
    this.showChatView();
    
    // Start a new conversation
    this.startNewChat();
    
    // Focus the input area after a short delay to ensure it's visible
    setTimeout(() => {
        const inputArea = document.getElementById('message-input');
        if (inputArea) {
            inputArea.focus();
            console.log('✅ Input area focused');
        } else {
            console.warn('⚠️ Input area not found');
        }
    }, 500);
};

// Show home view in main content area
KnowledgeBaseApp.prototype.showHomeView = async function() {
    this.currentView = 'home';
    const contentArea = document.getElementById('content-area');
    
    // Update top bar to hide context toggle
    const contextToggle = document.getElementById('context-toggle-btn');
    if (contextToggle) contextToggle.style.display = 'none';
    
    if (!contentArea) {
        console.error('content-area div not found');
        return;
    }
    
    // Remove any existing main-view elements from content-area
    const existingMainViews = contentArea.querySelectorAll('.main-view');
    existingMainViews.forEach(view => view.remove());
    
    // Hide the dynamic-content wrapper (contains chat and context panel)
    const dynamicContent = document.getElementById('dynamic-content');
    if (dynamicContent) {
        dynamicContent.style.display = 'none';
        dynamicContent.style.height = '0';
        dynamicContent.style.overflow = 'hidden';
    }
    
    // Also hide bottom input area for this view
    const bottomInput = document.querySelector('.bottom-input');
    if (bottomInput) {
        bottomInput.style.display = 'none';
    }
    
    // Create the home view content
    const homeContent = document.createElement('div');
    homeContent.className = 'main-view';
    
    // Get user display name for welcome message - fetch it dynamically
    let displayName = 'Your';
    try {
        const response = await fetch('/auth/status');
        const data = await response.json();
        if (data.authenticated) {
            displayName = data.display_name || data.username || 'Your';
        }
    } catch (error) {
        console.log('Could not fetch user data for welcome message:', error);
    }
    
    homeContent.innerHTML = `
            <nav class="breadcrumb">
                <span class="breadcrumb-item active">
                    <i class="fas fa-home"></i>
                    Home
                </span>
            </nav>
            
            <div class="view-header">
                <div class="view-title">
                    <i class="fas fa-home"></i>
                    <h2>Welcome to ${displayName}'s Knowledge Base</h2>
                </div>
                <div class="view-actions">
                    <button class="view-action-btn" onclick="window.app.startNewChat()">
                        <i class="fas fa-plus"></i>
                        New Chat
                    </button>

                </div>
            </div>
            
            <div class="home-content">
                <div class="home-actions">
                    <!-- Row 1: Projects -->
                    <div class="action-card" onclick="window.app.promptCreateNewProject()">
                        <i class="fas fa-folder-plus"></i>
                        <h3>Create New Project</h3>
                        <p>Organize your chats into focused projects</p>
                    </div>

                    <div class="action-card" onclick="window.app.showProjectsView()">
                        <i class="fas fa-folder-open"></i>
                        <h3>View All Projects</h3>
                        <p>Browse and manage your existing projects</p>
                    </div>

                    <!-- Row 2: Chats -->
                    <div class="action-card" onclick="window.app.startNewChatAndFocus()">
                        <i class="fas fa-comments"></i>
                        <h3>Start New Chat</h3>
                        <p>Begin a new conversation or ask questions about your knowledge base</p>
                    </div>

                    <div class="action-card" onclick="window.app.showConversationsView()">
                        <i class="fas fa-clock"></i>
                        <h3>View All Chats</h3>
                        <p>Browse through your chat history</p>
                    </div>
                    </div>
            </div>
        </div>
    `;
    
    // Append to content-area
    contentArea.appendChild(homeContent);
    
    // Load home statistics
    this.loadHomeStats();
};

// Show conversations list view in main content area
KnowledgeBaseApp.prototype.showConversationsView = function() {
    this.currentView = 'conversations';
    
    // Update top bar to hide context toggle
    const contextToggle = document.getElementById('context-toggle-btn');
    if (contextToggle) contextToggle.style.display = 'none';
    
    // Get the content-area where views should be rendered
    const contentArea = document.getElementById('content-area');
    console.log('🔵 [Conversations] content-area:', contentArea);
    console.log('🔵 [Conversations] content-area parent:', contentArea?.parentElement);
    console.log('🔵 [Conversations] content-area children:', contentArea?.children.length);
    console.log('🔵 [Conversations] document ready state:', document.readyState);
    if (!contentArea) {
        console.error('❌ [Conversations] content-area div not found');
        console.error('❌ [Conversations] Available elements with "content" in id:', 
            Array.from(document.querySelectorAll('[id*="content"]')).map(el => el.id));
        return;
    }
    
    // Clear all existing content from content-area to prevent layout conflicts
    console.log('🔵 [Conversations] Clearing existing content from content-area');
    console.log('🔵 [Conversations] Content-area children before clear:', Array.from(contentArea.children).map(child => ({
        tagName: child.tagName,
        className: child.className,
        id: child.id
    })));
    
    while (contentArea.firstChild) {
        contentArea.removeChild(contentArea.firstChild);
    }
    
    console.log('🔵 [Conversations] Content-area cleared, children count:', contentArea.children.length);
    
    // Hide the dynamic-content wrapper (contains chat and context panel)
    const dynamicContent = document.getElementById('dynamic-content');
    if (dynamicContent) {
        dynamicContent.style.display = 'none';
        dynamicContent.style.height = '0';
        dynamicContent.style.overflow = 'hidden';
    }
    
    // Also hide bottom input area for this view
    const bottomInput = document.querySelector('.bottom-input');
    if (bottomInput) {
        bottomInput.style.display = 'none';
    }
    
    // Create the conversations view content
    const conversationsContent = document.createElement('div');
    conversationsContent.className = 'main-view';
    conversationsContent.innerHTML = `
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
                <button class="view-action-btn" onclick="window.app.startNewChat()">
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
    `;
    
    // Insert into content-area to maintain proper layout
    console.log('🔵 [Conversations] Appending conversations content to content-area');
    contentArea.appendChild(conversationsContent);
    console.log('🔵 [Conversations] Conversations view HTML appended');
    console.log('🔵 [Conversations] Conversations content element:', conversationsContent);
    console.log('🔵 [Conversations] Conversations content display:', window.getComputedStyle(conversationsContent).display);
    console.log('🔵 [Conversations] Conversations content visibility:', window.getComputedStyle(conversationsContent).visibility);
    console.log('🔵 [Conversations] Conversations content offsetHeight:', conversationsContent.offsetHeight);
    console.log('🔵 [Conversations] Content-area children count:', contentArea.children.length);
    
    // Check if conversations-grid element exists immediately after creation
    const conversationsGrid = document.getElementById('conversations-grid');
    console.log('🔵 [Conversations] conversations-grid element after creation:', conversationsGrid);
    console.log('🔵 [Conversations] conversations-grid parent:', conversationsGrid?.parentElement);
    console.log('🔵 [Conversations] conversations-grid siblings:', conversationsGrid?.parentElement?.children.length);
    
    // Also check if the element exists in the DOM tree
    console.log('🔵 [Conversations] All elements with conversations-grid id:', document.querySelectorAll('#conversations-grid'));
    
    console.log('🔵 [Conversations] Calling loadConversationsGrid');
    
    // Use requestAnimationFrame to ensure DOM is ready before loading conversations
    requestAnimationFrame(() => {
        console.log('🔵 [Conversations] In requestAnimationFrame, checking conversations-grid again');
        const conversationsGridAfterRAF = document.getElementById('conversations-grid');
        console.log('🔵 [Conversations] conversations-grid element after RAF:', conversationsGridAfterRAF);
        console.log('🔵 [Conversations] conversations-grid parent after RAF:', conversationsGridAfterRAF?.parentElement);
    this.loadConversationsGrid();
    });
};

// Show projects grid view in main content area
KnowledgeBaseApp.prototype.showProjectsView = function() {
    console.log('🔵 showProjectsView called');
    this.currentView = 'projects';
    
    // Update top bar to hide context toggle
    const contextToggle = document.getElementById('context-toggle-btn');
    if (contextToggle) contextToggle.style.display = 'none';
    
    // Get the content-area where views should be rendered
    const contentArea = document.getElementById('content-area');
    console.log('🔵 content-area:', contentArea);
    console.log('🔵 content-area parent:', contentArea?.parentElement);
    console.log('🔵 content-area children:', contentArea?.children.length);
    console.log('🔵 document ready state:', document.readyState);
    if (!contentArea) {
        console.error('❌ content-area div not found');
        console.error('❌ Available elements with "content" in id:', 
            Array.from(document.querySelectorAll('[id*="content"]')).map(el => el.id));
        return;
    }
    
    // Clear all existing content from content-area to prevent layout conflicts
    console.log('🔵 Clearing existing content from content-area');
    console.log('🔵 Content-area children before clear:', Array.from(contentArea.children).map(child => ({
        tagName: child.tagName,
        className: child.className,
        id: child.id
    })));
    
    // Remove all children from content-area
    while (contentArea.firstChild) {
        contentArea.removeChild(contentArea.firstChild);
    }
    
    console.log('🔵 Content-area cleared, children count:', contentArea.children.length);
    
    // Hide the dynamic-content wrapper (contains chat and context panel)
    const dynamicContent = document.getElementById('dynamic-content');
    if (dynamicContent) {
        console.log('🔵 Hiding dynamic-content wrapper');
        dynamicContent.style.display = 'none';
        dynamicContent.style.height = '0';
        dynamicContent.style.overflow = 'hidden';
    }
    
    // Also hide bottom input area for this view
    const bottomInput = document.querySelector('.bottom-input');
    if (bottomInput) {
        console.log('🔵 Hiding bottom input');
        bottomInput.style.display = 'none';
    }
    
    // Create the projects view content
    const projectsContent = document.createElement('div');
    projectsContent.className = 'main-view';
    console.log('🔵 Creating projects view HTML');
    projectsContent.innerHTML = `
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
    `;
    
    // Insert into content-area to maintain proper layout
    console.log('🔵 Appending projects content to content-area');
    contentArea.appendChild(projectsContent);
    console.log('🔵 Projects view HTML appended');
    console.log('🔵 Projects content element:', projectsContent);
    console.log('🔵 Projects content display:', window.getComputedStyle(projectsContent).display);
    console.log('🔵 Projects content visibility:', window.getComputedStyle(projectsContent).visibility);
    console.log('🔵 Projects content offsetHeight:', projectsContent.offsetHeight);
    console.log('🔵 Content-area children count:', contentArea.children.length);
    
    // Check if projects-grid element exists immediately after creation
    const projectsGrid = document.getElementById('projects-grid');
    console.log('🔵 projects-grid element after creation:', projectsGrid);
    console.log('🔵 projects-grid parent:', projectsGrid?.parentElement);
    console.log('🔵 projects-grid siblings:', projectsGrid?.parentElement?.children.length);
    
    // Also check if the element exists in the DOM tree
    console.log('🔵 All elements with projects-grid id:', document.querySelectorAll('#projects-grid'));
    
    console.log('🔵 Calling loadProjectsGrid');
    
    // Use requestAnimationFrame to ensure DOM is ready before loading projects
    requestAnimationFrame(() => {
        console.log('🔵 In requestAnimationFrame, checking projects-grid again');
        const projectsGridAfterRAF = document.getElementById('projects-grid');
        console.log('🔵 projects-grid element after RAF:', projectsGridAfterRAF);
        console.log('🔵 projects-grid parent after RAF:', projectsGridAfterRAF?.parentElement);
    this.loadProjectsGrid();
    });
};

// Show project conversations view
KnowledgeBaseApp.prototype.showProjectConversationsView = function(project) {
    this.currentView = 'project-conversations';
    this.currentViewProject = project;
    
    // Get the content-area where views should be rendered
    const contentArea = document.getElementById('content-area');
    if (!contentArea) {
        console.error('content-area div not found');
        return;
    }
    
    // Remove any existing main-view elements from content-area
    const existingMainViews = contentArea.querySelectorAll('.main-view');
    existingMainViews.forEach(view => view.remove());
    
    // Hide the dynamic-content wrapper (contains chat and context panel)
    const dynamicContent = document.getElementById('dynamic-content');
    if (dynamicContent) {
        dynamicContent.style.display = 'none';
        dynamicContent.style.height = '0';
        dynamicContent.style.overflow = 'hidden';
    }
    
    // Create the project conversations view content
    const projectContent = document.createElement('div');
    projectContent.className = 'main-view';
    projectContent.innerHTML = `
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
    
    // Insert into content-area to maintain proper layout
    contentArea.appendChild(projectContent);
    
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
        const container = document.getElementById('conversations-grid');
        if (container) {
            container.innerHTML = `
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
        } else {
            console.error('❌ [Conversations] conversations-grid container not found for error display');
        }
    }
};

// Load home statistics
KnowledgeBaseApp.prototype.loadHomeStats = async function() {
    try {
        // Load conversations count
        const convResponse = await fetch('/conversations');
        const conversations = await convResponse.json();
        const totalConversations = conversations.length;
        
        // Load context items count
        const contextResponse = await fetch('/api/context');
        const contextItems = await contextResponse.json();
        const totalContextItems = contextItems.length;
        
        // Update the stats display
        const convElement = document.getElementById('total-conversations');
        const contextElement = document.getElementById('total-context-items');
        
        if (convElement) convElement.textContent = totalConversations;
        if (contextElement) contextElement.textContent = totalContextItems;
        
    } catch (error) {
        console.error('Failed to load home stats:', error);
        // Don't show error on home page, just log it
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
        const container = document.getElementById('projects-grid');
        if (container) {
            container.innerHTML = `
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
        } else {
            console.error('❌ projects-grid container not found for error display');
        }
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
KnowledgeBaseApp.prototype.renderConversationsGrid = function(conversations, containerId = 'conversations-grid', retryCount = 0) {
    console.log('🟢 [Conversations] renderConversationsGrid called with', conversations.length, 'conversations, retry:', retryCount);
    const container = document.getElementById(containerId);
    console.log('🟢 [Conversations] conversations-grid container:', container);
    
    if (!container) {
        if (retryCount < 5) {
            console.error('❌ [Conversations] conversations-grid container not found, retrying...', retryCount + 1);
            // Retry after DOM is ready with exponential backoff
            setTimeout(() => {
                this.renderConversationsGrid(conversations, containerId, retryCount + 1);
            }, 100 * Math.pow(2, retryCount)); // 100ms, 200ms, 400ms, 800ms, 1600ms
            return;
        } else {
            console.error('❌ [Conversations] conversations-grid container not found after 5 retries, creating fallback');
            // Create fallback container in content-area
            const contentArea = document.getElementById('content-area');
            if (contentArea) {
                console.log('🔧 [Conversations] Creating fallback conversations-grid container');
                const fallbackContainer = document.createElement('div');
                fallbackContainer.id = containerId;
                fallbackContainer.className = 'conversations-grid';
                contentArea.appendChild(fallbackContainer);
                console.log('🔧 [Conversations] Fallback container created:', fallbackContainer);
                // Retry with the new container
                this.renderConversationsGrid(conversations, containerId, 0);
                return;
            } else {
                console.error('❌ [Conversations] content-area not found, cannot create fallback');
                return;
            }
        }
    }
    
    if (!conversations.length) {
        // Determine the correct onclick handler based on project context
        let newChatOnclick = 'window.app.startNewConversation()';
        if (this.currentViewProject && this.currentViewProject.id) {
            newChatOnclick = `window.app.startNewConversationInProject('${this.currentViewProject.id}')`;
        } else if (this.currentProject && this.currentProject.id) {
            newChatOnclick = `window.app.startNewConversationInProject('${this.currentProject.id}')`;
        }
        
        container.innerHTML = `
            <div class="empty-state-large">
                <i class="fas fa-comments"></i>
                <h3>No conversations yet</h3>
                <p>Start your first conversation to see it here.</p>
                <button class="view-action-btn" onclick="${newChatOnclick}">
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
        
        // Show message count and attachment count as preview
        const messageCount = conv.message_count || 0;
        const attachmentCount = conv.attachment_count || 0;
        
        let preview = '';
        if (messageCount > 0 && attachmentCount > 0) {
            preview = `${messageCount} message${messageCount !== 1 ? 's' : ''} • ${attachmentCount} attachment${attachmentCount !== 1 ? 's' : ''}`;
        } else if (messageCount > 0) {
            preview = `${messageCount} message${messageCount !== 1 ? 's' : ''}`;
        } else if (attachmentCount > 0) {
            preview = `${attachmentCount} attachment${attachmentCount !== 1 ? 's' : ''}`;
        } else {
            preview = 'No messages yet';
        }
            
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
KnowledgeBaseApp.prototype.renderProjectsGrid = function(projects, retryCount = 0) {
    console.log('🟢 renderProjectsGrid called with', projects.length, 'projects, retry:', retryCount);
    const container = document.getElementById('projects-grid');
    console.log('🟢 projects-grid container:', container);
    
    if (!container) {
        if (retryCount < 5) {
            console.error('❌ projects-grid container not found, retrying...', retryCount + 1);
            // Retry after DOM is ready with exponential backoff
            setTimeout(() => {
                this.renderProjectsGrid(projects, retryCount + 1);
            }, 100 * Math.pow(2, retryCount)); // 100ms, 200ms, 400ms, 800ms, 1600ms
            return;
        } else {
            console.error('❌ projects-grid container not found after 5 retries, creating fallback');
            // Create fallback container in content-area
            const contentArea = document.getElementById('content-area');
            if (contentArea) {
                console.log('🔧 Creating fallback projects-grid container');
                const fallbackContainer = document.createElement('div');
                fallbackContainer.id = 'projects-grid';
                fallbackContainer.className = 'projects-grid-view';
                contentArea.appendChild(fallbackContainer);
                console.log('🔧 Fallback container created:', fallbackContainer);
                // Retry with the new container
                this.renderProjectsGrid(projects, 0);
                return;
            } else {
                console.error('❌ content-area not found, cannot create fallback');
                return;
            }
        }
    }
    
    if (!projects.length) {
        console.log('🟢 No projects, showing empty state');

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
    
    console.log('🟢 Creating project cards HTML');
    const projectCards = projects.map(project => {
        const conversationCount = project.conversation_count || 0;
        
        return `
            <div class="project-card" onclick="window.app.openProject('${project.id}')">
                <div class="project-card-icon">
                    <i class="fas fa-folder-open"></i>
                </div>
                <h3 class="project-card-title">${project.name}</h3>
                <p class="project-card-count">${conversationCount} conversations</p>
                <div class="project-card-actions" style="display:flex; gap:8px; flex-wrap:nowrap; align-items:center; justify-content:flex-start;">
                    <button class="view-action-btn secondary" onclick="event.stopPropagation(); viewProjectTemplate('${project.id}')" title="Preview">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="view-action-btn secondary" onclick="event.stopPropagation(); editProjectTemplate('${project.id}')" title="Setup">
                        <i class="fas fa-cogs"></i>
                    </button>
                    <button class="view-action-btn secondary" onclick="event.stopPropagation(); window.app.editProject('${project.id}', '${project.name.replace(/'/g, "\\'")}')" title="Rename">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="view-action-btn secondary" onclick="event.stopPropagation(); window.app.deleteProject('${project.id}')" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                    <button class="view-action-btn secondary" onclick="event.stopPropagation(); window.app.cloneProject('${project.id}')" title="Clone">
                        <i class="fas fa-clone"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');
    
    console.log('🟢 Setting container innerHTML with', projectCards.length, 'characters');
    container.innerHTML = projectCards;
    console.log('🟢 Projects grid rendered successfully');
    console.log('🟢 Container after render:', container);
    console.log('🟢 Container offsetHeight:', container.offsetHeight);
    console.log('🟢 Container children:', container.children.length);
    console.log('🟢 Content-area offsetHeight:', document.getElementById('content-area').offsetHeight);
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
    
    // Ensure we're using the correct 'this' context
    if (this && typeof this.loadConversation === 'function') {
        this.loadConversation(conversationId);
    } else {
        // Fallback to window.app if 'this' context is lost
        console.warn('Lost context in openConversationFromGrid, using window.app fallback');
        if (window.app && typeof window.app.loadConversation === 'function') {
            window.app.loadConversation(conversationId);
        } else {
            console.error('Cannot load conversation: loadConversation method not found');
        }
    }
};

// Open project from grid view
KnowledgeBaseApp.prototype.openProject = function(projectId) {
    // Find project data
    const project = this.projects.find(p => p.id === projectId);
    if (project) {
        this.showProjectConversationsView(project);
    }
};

// Clone project
KnowledgeBaseApp.prototype.cloneProject = async function(projectId) {
    try {
        const res = await fetch(`/projects/${projectId}/clone`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            alert(`Failed to clone project: ${err.error || res.statusText}`);
            return;
        }
        const cloned = await res.json();
        // Refresh projects list
        const response = await fetch('/projects');
        const projects = await response.json();
        this.projects = projects;
        this.renderProjectsGrid(projects);
    } catch (e) {
        console.error('Error cloning project', e);
        alert('Error cloning project');
    }
};

// Show normal chat view
KnowledgeBaseApp.prototype.showChatView = function() {
    this.currentView = 'chat';
    
    // Get the content-area where views should be rendered
    const contentArea = document.getElementById('content-area');
    if (!contentArea) {
        console.error('content-area container not found for chat view');
        console.log('DEBUG: main-content exists?', document.getElementById('main-content'));
        console.log('DEBUG: All children of main-content:', Array.from(document.getElementById('main-content')?.children || []));
        return;
    }
    
    // Clear any existing view content (conversations, projects, etc.)
    const existingViewContent = contentArea.querySelector('.main-view');
    if (existingViewContent) {
        existingViewContent.remove();
    }
    
    // Restore the dynamic-content wrapper
    const dynamicContent = document.getElementById('dynamic-content');
    if (dynamicContent) {
        console.log('showChatView: Restoring dynamic-content wrapper');
        dynamicContent.style.display = '';
        dynamicContent.style.height = '';
        dynamicContent.style.overflow = '';
    }
    
    // Wait for DOM to be ready if needed
    if (document.readyState === 'loading') {
        console.log('showChatView: DOM still loading, waiting...');
        document.addEventListener('DOMContentLoaded', () => {
            this.showChatView();
        });
        return;
    }
    
    // Find the existing chat-messages-container instead of creating a new one
    let chatMessagesContainer = contentArea.querySelector('.chat-messages-container') || 
                                document.querySelector('.chat-messages-container');
    console.log('showChatView: Looking for existing chat container:', chatMessagesContainer);
    console.log('showChatView: All elements with chat-messages-container class:', document.querySelectorAll('.chat-messages-container'));
    console.log('showChatView: dynamic-content element:', document.getElementById('dynamic-content'));
    console.log('showChatView: dynamic-content children:', document.getElementById('dynamic-content') ? Array.from(document.getElementById('dynamic-content').children) : 'null');
    
    // Debug: Check the entire DOM structure
    console.log('showChatView: Full DOM structure check:');
    console.log('  - document.body:', document.body);
    console.log('  - content-area:', document.getElementById('content-area'));
    console.log('  - dynamic-content:', document.getElementById('dynamic-content'));
    console.log('  - All divs with id:', document.querySelectorAll('div[id]'));
    
    if (!chatMessagesContainer) {
        console.error('showChatView: Chat container not found in HTML template - this should not happen');
        console.log('showChatView: Attempting to create chat container manually');
        
        // Try to create the chat container manually
        const dynamicContent = document.getElementById('dynamic-content');
        if (dynamicContent) {
            const chatContainer = document.createElement('div');
            chatContainer.className = 'chat-messages-container';
            chatContainer.innerHTML = `
                <div class="chat-messages" id="chat-messages">
                    <div class="empty-state" id="empty-state">
                        <div class="empty-state-icon">
                            <i class="fas fa-comments"></i>
                        </div>
                        <h2 class="empty-state-title">New Conversation</h2>
                        <p class="empty-state-description">Start a conversation or search your knowledge base.</p>
                    </div>
                </div>
            `;
            dynamicContent.appendChild(chatContainer);
            console.log('showChatView: Created chat container manually');
            chatMessagesContainer = chatContainer;
        } else {
            console.error('showChatView: Cannot create chat container - dynamic-content not found');
            console.log('showChatView: Attempting to create entire structure from scratch');
            
            // Create the entire structure if it doesn't exist
            const contentArea = document.getElementById('content-area');
            if (!contentArea) {
                console.error('showChatView: content-area not found - cannot create structure');
        return;
            }
            
            // Create dynamic-content
            const dynamicContent = document.createElement('div');
            dynamicContent.id = 'dynamic-content';
            contentArea.appendChild(dynamicContent);
            
            // Create chat container
            const chatContainer = document.createElement('div');
            chatContainer.className = 'chat-messages-container';
            chatContainer.innerHTML = `
                <div class="chat-messages" id="chat-messages">
                    <div class="empty-state" id="empty-state">
                        <div class="empty-state-icon">
                            <i class="fas fa-comments"></i>
                        </div>
                        <h2 class="empty-state-title">New Conversation</h2>
                        <p class="empty-state-description">Start a conversation or search your knowledge base.</p>
                    </div>
                </div>
            `;
            dynamicContent.appendChild(chatContainer);
            console.log('showChatView: Created entire structure from scratch');
            chatMessagesContainer = chatContainer;
        }
    } else {
        console.log('showChatView: Using existing chat container from template');
        
        // Restore the chat container if it was hidden
        chatMessagesContainer.style.display = '';
        
        // Check if existing container has header, if not add it
        let existingHeader = chatMessagesContainer.querySelector('#chat-header');
        if (!existingHeader) {
            console.log('showChatView: Adding missing chat header to existing container');
            const headerHtml = `
                <!-- Chat Header (for project/conversation context) -->
                <div class="chat-header" id="chat-header" style="display: none;">
                    <div class="chat-breadcrumb">
                        <span class="breadcrumb-item breadcrumb-clickable" id="projects-breadcrumb" onclick="window.app.showProjectsView()">
                            <i class="fas fa-folder"></i>
                            <span>Projects</span>
                        </span>
                        <span class="breadcrumb-separator"><i class="fas fa-chevron-right"></i></span>
                        <span class="breadcrumb-item breadcrumb-clickable" id="project-breadcrumb" onclick="window.app.goBackToProject()">
                            <i class="fas fa-folder-open"></i>
                            <span id="project-name"></span>
                        </span>
                        <span class="breadcrumb-separator"><i class="fas fa-chevron-right"></i></span>
                        <span class="breadcrumb-item active">
                            <i class="fas fa-comment"></i>
                            <span id="conversation-title"></span>
                        </span>
                    </div>
                    <div class="chat-header-actions">
                        <button class="chat-header-btn" onclick="window.app.exportConversation()" title="Export Conversation">
                            <i class="fas fa-download"></i>
                            <span>Export</span>
                        </button>
                        <button class="chat-header-btn" onclick="window.app.deleteConversation()" title="Delete Conversation">
                            <i class="fas fa-trash"></i>
                            <span>Delete</span>
                        </button>
                    </div>
                </div>
            `;
            chatMessagesContainer.insertAdjacentHTML('afterbegin', headerHtml);
            existingHeader = chatMessagesContainer.querySelector('#chat-header');
        }
        console.log('showChatView: Header in existing container:', existingHeader);
    }
    
    // Show/hide chat header based on project context
    // Use a small delay to ensure the dynamically created elements are available in the DOM
    setTimeout(() => {
        const chatHeader = document.getElementById('chat-header');
        console.log('showChatView: Looking for chat header after timeout:', chatHeader);
        
        if (chatHeader) {
            if (this.currentViewProject) {
                // Show project context in header
                chatHeader.style.display = 'block';
                
                // Update breadcrumb content
                const projectName = document.getElementById('project-name');
                const conversationTitle = document.getElementById('conversation-title');
                const projectBreadcrumb = document.getElementById('project-breadcrumb');
                
                if (projectName) projectName.textContent = this.currentViewProject.name;
                if (conversationTitle) conversationTitle.textContent = this.currentConversationId ? 'Conversation' : 'New Conversation';
                
                // Update the project breadcrumb onclick to return to the correct project
                if (projectBreadcrumb) {
                    projectBreadcrumb.onclick = () => this.showProjectConversationsView(this.currentViewProject);
                }
                
                console.log('showChatView: Updated breadcrumb for project:', this.currentViewProject.name);
            } else {
                chatHeader.style.display = 'none';
                console.log('showChatView: No project context, hiding breadcrumb');
            }
        } else {
            console.log('showChatView: Chat header element still not found after timeout');
            // Try to find it in the container we just created
            const containerHeader = container.querySelector('#chat-header');
            console.log('showChatView: Looking for header in container:', containerHeader);
        }
    }, 10); // Small delay to allow DOM to update
    
    // Show context toggle again
    const contextToggle = document.getElementById('context-toggle-btn');
    if (contextToggle) contextToggle.style.display = 'block';
    
    // Remove any search results that might be interfering with the layout
    const searchResults = document.querySelector('.search-results-container');
    if (searchResults) {
        searchResults.remove();
    }
    
    // Restore content-area and bottom input if they were hidden during search
    if (contentArea) {
        contentArea.style.display = '';
    }
    
    const bottomInput = document.querySelector('.bottom-input');
    if (bottomInput) {
        bottomInput.style.display = '';
    }
    
    // Show empty state for new conversation
    if (!this.currentConversationId) {
        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
            chatMessages.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">
                        <i class="fas fa-comments"></i>
                    </div>
                    <h2 class="empty-state-title">New Conversation</h2>
                    <p class="empty-state-description">Start a conversation or search your knowledge base.</p>
                </div>
            `;
        }
    }
    
    // If there's a current conversation, it will be loaded by the caller
};



// Clear project context and return to home view
KnowledgeBaseApp.prototype.clearProjectContext = function() {
    this.currentViewProject = null;
    this.currentProject = null;
    this.showChatView();
};

// Start new conversation (enhanced to work from any view)
KnowledgeBaseApp.prototype.startNewConversation = function() {
    // Preserve the current view project context
    if (this.currentProject && !this.currentViewProject) {
        this.currentViewProject = this.currentProject;
    }
    this.startNewChat();
};

// Start new conversation in specific project
KnowledgeBaseApp.prototype.startNewConversationInProject = function(projectId) {
    // Find and set the project context
    this.currentProject = this.projects.find(p => p.id === projectId);
    this.currentViewProject = this.currentProject; // Set the view project context
    
    // Switch to chat view first, then start new conversation
    this.showChatView();
    

    
    // Use requestAnimationFrame to ensure DOM is updated before proceeding
    requestAnimationFrame(() => {
        this.startNewConversation();
    });
};

// Start new conversation from conversations view
KnowledgeBaseApp.prototype.startNewConversationFromConversations = function() {
    // Switch to chat view first, then start new conversation
    this.showChatView();
    
    // Use requestAnimationFrame to ensure DOM is updated before proceeding
    requestAnimationFrame(() => {
        this.startNewConversation();
    });
};

// Prompt for new project creation
KnowledgeBaseApp.prototype.promptCreateNewProject = function() {
    const name = prompt('Enter project name:');
    if (name && name.trim()) {
        // Store the project name and show setup modal
        this.pendingProjectName = name.trim();
        this.showProjectSetupModal();
    }
};

// Show project setup modal
KnowledgeBaseApp.prototype.showProjectSetupModal = function() {
    if (window.showProjectSetupModal) {
        window.showProjectSetupModal();
    } else {
        console.error('Project setup modal not available');
        alert('Project setup modal is not available. Please refresh the page and try again.');
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

// Show notification with type
KnowledgeBaseApp.prototype.showNotification = function(message, type = 'info') {
    // Simple notification for now - can be enhanced later
    if (type === 'success') {
        this.showSuccessNotification(message);
    } else if (type === 'error') {
        this.showErrorNotification(message);
    } else {
        alert(message);
    }
};

// Render uploaded context documents
KnowledgeBaseApp.prototype.renderContextDocuments = function(documents) {
    const container = document.getElementById('chat-messages');
    if (!container) {
        console.warn('renderContextDocuments: Chat container not found, attempting to restore');
        
        // Preserve project context before restoring
        const preserveProject = this.currentProject;
        const preserveViewProject = this.currentViewProject;
        
        this.showChatView();
        
        // Restore project context after restoring chat view
        if (preserveProject) this.currentProject = preserveProject;
        if (preserveViewProject) this.currentViewProject = preserveViewProject;
        
        const retryContainer = document.getElementById('chat-messages');
        if (!retryContainer) {
            console.error('renderContextDocuments: Still cannot find chat container');
            return;
        }
        container = retryContainer;
    }
    
    // Remove any existing context documents section
    const existingSection = container.querySelector('.context-documents-section');
    if (existingSection) {
        existingSection.remove();
    }
    
    // Clear previous document content map
    this.documentContentMap.clear();
    
    // First, populate the document content map
    documents.forEach(doc => {
        this.documentContentMap.set(doc.filename, doc.content || '');
    });
    
    // Create a subtle section for uploaded documents
    const docsSection = document.createElement('div');
    docsSection.className = 'context-documents-section';
    docsSection.innerHTML = `
        <div class="context-documents-subtle">
            <span class="context-documents-label">📎</span>
            ${documents.map(doc => this.renderDocumentItem(doc)).join('')}
        </div>
    `;
    
    // Insert at the top of the chat messages
    container.insertBefore(docsSection, container.firstChild);
};

KnowledgeBaseApp.prototype.renderDocumentItem = function(doc) {
    const fileType = this.getFileTypeIcon(doc.filename);
    
    // Store the document content in our global map
    this.documentContentMap.set(doc.filename, doc.content || '');
    
    const html = `
        <span class="document-item-subtle" 
              data-filename="${doc.filename}"
              title="${doc.filename} - Click to view/download"
              onclick="window.app.handleDocumentClick('${doc.filename}')">
            <i class="${fileType.icon}"></i>
        </span>
    `;
    
    return html;
};

KnowledgeBaseApp.prototype.getFileTypeIcon = function(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const iconMap = {
        'pdf': { icon: 'fas fa-file-pdf', name: 'PDF Document' },
        'doc': { icon: 'fas fa-file-word', name: 'Word Document' },
        'docx': { icon: 'fas fa-file-word', name: 'Word Document' },
        'png': { icon: 'fas fa-file-image', name: 'Image' },
        'jpg': { icon: 'fas fa-file-image', name: 'Image' },
        'jpeg': { icon: 'fas fa-file-image', name: 'Image' },
        'gif': { icon: 'fas fa-file-image', name: 'Image' },
        'svg': { icon: 'fas fa-file-image', name: 'Image' },
        'txt': { icon: 'fas fa-file-alt', name: 'Text Document' },
        'md': { icon: 'fas fa-file-alt', name: 'Markdown Document' }
    };
    
    return iconMap[ext] || { icon: 'fas fa-file', name: 'Document' };
};

KnowledgeBaseApp.prototype.formatFileSize = function(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

KnowledgeBaseApp.prototype.viewDocument = function(filename, content) {
    // Create a modal to view document content
    const modal = document.createElement('div');
    modal.className = 'document-modal';
    modal.innerHTML = `
        <div class="document-modal-content">
            <div class="document-modal-header">
                <h3>${filename}</h3>
                <button class="close-btn" onclick="this.parentElement.parentElement.parentElement.remove()">&times;</button>
            </div>
            <div class="document-modal-body">
                <pre>${content}</pre>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Close modal when clicking outside
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.remove();
    });
};

KnowledgeBaseApp.prototype.downloadDocument = function(filename, content) {
    // Create a blob and download the document
    const blob = new Blob([content], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
};

KnowledgeBaseApp.prototype.handleDocumentClick = function(filename) {
    try {
        // Remove any existing document menu
        const existingMenu = document.querySelector('.document-menu');
        if (existingMenu) {
            existingMenu.remove();
        }
        
        // Get the content from our global map
        const content = this.documentContentMap.get(filename) || '';
        
        if (!content) {
            return;
        }
        
        // Create a small floating menu
        const menu = document.createElement('div');
        menu.className = 'document-menu';
        
        // Use a different approach to avoid content escaping issues
        const viewButton = document.createElement('div');
        viewButton.className = 'document-menu-item';
        viewButton.innerHTML = '<i class="fas fa-eye"></i> View';
        viewButton.addEventListener('click', () => {
            this.viewDocument(filename, content);
        });
        
        const downloadButton = document.createElement('div');
        downloadButton.className = 'document-menu-item';
        downloadButton.innerHTML = '<i class="fas fa-download"></i> Download';
        downloadButton.addEventListener('click', () => {
            this.downloadDocument(filename, content);
        });
        
        menu.appendChild(viewButton);
        menu.appendChild(downloadButton);
        
        // Position the menu near the clicked element
        const clickedElement = document.querySelector(`[data-filename="${filename}"]`);
        if (clickedElement) {
            const rect = clickedElement.getBoundingClientRect();
            menu.style.position = 'fixed';
            menu.style.top = (rect.bottom + 5) + 'px';
            menu.style.left = rect.left + 'px';
            menu.style.zIndex = '1000';
        }
        
        document.body.appendChild(menu);
        
        // Close menu when clicking outside
        const closeMenu = (e) => {
            if (!menu.contains(e.target) && !clickedElement.contains(e.target)) {
                menu.remove();
                document.removeEventListener('click', closeMenu);
            }
        };
        
        // Delay adding the event listener to avoid immediate closure
        setTimeout(() => {
            document.addEventListener('click', closeMenu);
        }, 100);
        
    } catch (error) {
        console.error('DEBUG: Error in handleDocumentClick:', error);
    }
};

// Focus on first input - only when modal is open
// setTimeout(() => {
//     document.getElementById('edit-context-name').focus();
// }, 100);

// Submit edit context form
function submitEditContext() {
    const form = document.getElementById('edit-context-form');
    const formData = new FormData(form);
    
    // Validate required fields
    const name = formData.get('name').trim();
    const contentType = formData.get('content_type');
    const contentText = formData.get('content_text').trim();
    const contextId = formData.get('context_id');
    
    if (!name || !contentType || !contentText || !contextId) {
        alert('Please fill in all required fields');
        return;
    }
    
    // Prepare data for API
    const contextData = {
        name: name,
        description: formData.get('description').trim() || null,
        content_type: contentType,
        content_text: contentText,
        project_id: formData.get('project_id') || null
    };
    
    // Show loading state
    const submitBtn = document.querySelector('.context-modal .btn-primary');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Updating...';
    submitBtn.disabled = true;
    
    // Call API to update context item
    fetch(`/api/context/${contextId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(contextData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Close modal
            document.querySelector('.modal-overlay').remove();
            
            // Refresh context panel
            if (window.app.contextPanelOpen) {
                window.app.loadContextData();
            }
            
            // Show success message
            window.app.showNotification('Context item updated successfully!', 'success');
        } else {
            throw new Error(data.error || 'Failed to update context item');
        }
    })
    .catch(error => {
        console.error('Error updating context item:', error);
        alert('Error updating context item: ' + error.message);
        
        // Reset button
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
    });
}