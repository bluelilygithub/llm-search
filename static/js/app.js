class KnowledgeBaseApp {
    constructor() {
        this.currentConversationId = null;
        this.selectedModel = 'gpt-4';
        this.uploadedFiles = [];
        this.urlReferences = [];
        this.isRecording = false;
        this.mediaRecorder = null;
        this.currentProject = null; // Added for project management
        
        this.init();
    }

    init() {
        this.loadProjects(); // Load projects on app initialization
        this.loadConversations();
        this.setupEventListeners();
        this.autoResizeTextarea();
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
            this.renderProjects(projects);
        } catch (error) {
            console.error('Failed to load projects:', error);
        }
    }

    renderProjects(projects) {
        const sidebar = document.querySelector('.sidebar');
        // Projects section wrapper
        let projectsSection = document.getElementById('projects-section');
        if (!projectsSection) {
            projectsSection = document.createElement('div');
            projectsSection.id = 'projects-section';
            projectsSection.className = 'projects-section';
            sidebar.insertBefore(projectsSection, sidebar.children[1]);
        }
        projectsSection.innerHTML = '';
        // Projects toggle button
        let toggleBtn = document.getElementById('toggle-projects-btn');
        if (!toggleBtn) {
            toggleBtn = document.createElement('button');
            toggleBtn.id = 'toggle-projects-btn';
            toggleBtn.className = 'new-chat-btn';
            toggleBtn.textContent = '▼ Projects';
            toggleBtn.onclick = () => {
                const projectList = document.getElementById('project-list');
                if (projectList) {
                    projectsSection.classList.toggle('collapsed');
                    toggleBtn.textContent = projectsSection.classList.contains('collapsed') ? '► Projects' : '▼ Projects';
                }
            };
        }
        projectsSection.appendChild(toggleBtn);
        // New Project button
        let newBtn = document.getElementById('new-project-btn');
        if (!newBtn) {
            newBtn = document.createElement('button');
            newBtn.id = 'new-project-btn';
            newBtn.className = 'new-chat-btn';
            newBtn.textContent = '+ New Project';
            newBtn.onclick = () => { this.addingProject = true; this.loadProjects(); };
        }
        projectsSection.appendChild(newBtn);
        // New project input field (styled like search input)
        let inputRow = document.getElementById('new-project-input-row');
        if (this.addingProject) {
            if (!inputRow) {
                inputRow = document.createElement('div');
                inputRow.id = 'new-project-input-row';
                inputRow.style.padding = '8px 20px 0 20px';
                const input = document.createElement('input');
                input.type = 'text';
                input.placeholder = 'Project name...';
                input.className = 'project-input';
                input.onkeydown = (e) => {
                    if (e.key === 'Enter') this.createProject(input.value);
                    if (e.key === 'Escape') this.addingProject = false, this.loadProjects();
                };
                inputRow.appendChild(input);
                projectsSection.appendChild(inputRow);
                input.focus();
            }
        } else if (inputRow) {
            inputRow.remove();
        }
        // Project list
        let projectList = document.getElementById('project-list');
        if (!projectList) {
            projectList = document.createElement('div');
            projectList.id = 'project-list';
        }
        if (projectList.classList.contains('collapsed')) {
            projectList.innerHTML = '';
            return;
        }
        projectList.innerHTML = '';
        // All Projects option
        const allItem = document.createElement('div');
        allItem.className = 'conversation-item';
        allItem.textContent = 'All Projects';
        allItem.onclick = () => this.selectProject(null);
        if (!this.currentProject) {
            allItem.classList.add('active');
        }
        projectList.appendChild(allItem);
        // List all projects
        projects.forEach(project => {
            const item = document.createElement('div');
            item.className = 'conversation-item';
            item.style.display = 'flex';
            item.style.alignItems = 'center';
            if (this.currentProject && this.currentProject.id === project.id) {
                item.classList.add('active');
            }
            // Project name or input for renaming
            if (this.renamingProject && this.renamingProject.id === project.id) {
                const input = document.createElement('input');
                input.type = 'text';
                input.value = project.name;
                input.className = 'project-input';
                input.style.flex = '1';
                input.onkeydown = (e) => {
                    if (e.key === 'Enter') this.renameProject(project, input.value);
                    if (e.key === 'Escape') this.renamingProject = null, this.loadProjects();
                };
                item.appendChild(input);
                input.focus();
            } else {
                const nameSpan = document.createElement('span');
                nameSpan.textContent = project.name;
                nameSpan.className = 'project-name';
                nameSpan.onclick = () => this.selectProject(project);
                item.appendChild(nameSpan);
            }
            // Inline edit/delete icons
            const iconRow = document.createElement('span');
            iconRow.style.display = 'flex';
            iconRow.style.gap = '4px';
            iconRow.style.alignItems = 'center';
            // Rename (pencil) icon
            const renameBtn = document.createElement('button');
            renameBtn.className = 'input-btn';
            renameBtn.style.width = '24px';
            renameBtn.style.height = '24px';
            renameBtn.title = 'Rename Project';
            renameBtn.innerHTML = '<i class="fas fa-pencil-alt"></i>';
            renameBtn.onclick = (e) => { e.stopPropagation(); this.renamingProject = project; this.loadProjects(); };
            iconRow.appendChild(renameBtn);
            // Delete (trash) icon
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'input-btn';
            deleteBtn.style.width = '24px';
            deleteBtn.style.height = '24px';
            deleteBtn.title = 'Delete Project';
            deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
            deleteBtn.onclick = (e) => { e.stopPropagation(); this.deleteProject(project); };
            iconRow.appendChild(deleteBtn);
            item.appendChild(iconRow);
            projectList.appendChild(item);
        });
        projectsSection.appendChild(projectList);
    }

    showNewProjectPrompt() { /* no-op, replaced by inline input */ }

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

    async deleteProject(project) {
        if (!confirm(`Delete project "${project.name}"? All related conversations will become unfiltered.`)) return;
        try {
            const response = await fetch(`/projects/${project.id}`, { method: 'DELETE' });
            if (!response.ok) throw new Error('Failed to delete project');
            if (this.currentProject && this.currentProject.id === project.id) this.currentProject = null;
            await this.loadProjects();
            this.loadConversations();
            console.log('Deleted project:', project.name);
        } catch (error) {
            console.error('Failed to delete project:', error);
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
            if (!response.ok) throw new Error('Failed to rename project');
            this.renamingProject = null;
            await this.loadProjects();
            console.log('Renamed project:', newName);
        } catch (error) {
            console.error('Failed to rename project:', error);
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
                    <h3>New Conversation</h3>
                    <p>Start a conversation or search your knowledge base.</p>
                </div>
            `;
            document.getElementById('message-input').value = '';
            this.autoResizeTextarea();
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
        const container = document.getElementById('conversations-list');
        container.innerHTML = '';

        conversations.forEach(conv => {
            const item = document.createElement('div');
            item.className = 'conversation-item';
            item.onclick = () => this.loadConversation(conv.id);
            
            const tags = conv.tags.map(tag => `<span class="tag">${tag}</span>`).join('');
            
            item.innerHTML = `
                <div class="conversation-title">${conv.title}</div>
                <div class="conversation-meta">
                    <span>${conv.llm_model}</span>
                    <span>${this.formatDate(conv.updated_at)}</span>
                </div>
                <div class="conversation-tags">${tags}</div>
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
            event.currentTarget.classList.add('active');

            const response = await fetch(`/conversations/${conversationId}/messages`);
            const data = await response.json();
            
            this.renderMessages(data.messages);
            this.selectedModel = data.conversation.llm_model;
            document.getElementById('llm-model').value = this.selectedModel;
            
        } catch (error) {
            console.error('Failed to load conversation:', error);
        }
    }

    renderMessages(messages) {
        const container = document.getElementById('chat-messages');
        container.innerHTML = '';

        messages.forEach(message => {
            this.addMessageToChat(message);
        });

        this.scrollToBottom();
    }

    addMessageToChat(message) {
        const container = document.getElementById('chat-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.role} new`;
        
        const avatar = message.role === 'user' ? 'U' : 'AI';
        
        // If assistant, include model in time
        let timeString = this.formatTime(message.timestamp);
        if (message.role === 'assistant' && this.selectedModel) {
            timeString += ` (${this.selectedModel})`;
        }
        messageDiv.innerHTML = `
            <div class="message-avatar">${avatar}</div>
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
            .replace(/\n/g, '<br>');
    }

    async sendMessage() {
        const input = document.getElementById('message-input');
        const content = input.value.trim();
        
        if (!content) return;

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
            
            return data.response;
            
        } catch (error) {
            console.error('LLM API error:', error);
            throw error; // Preserve the original error message
        }
    }

    showTypingIndicator() {
        const container = document.getElementById('chat-messages');
        const indicator = document.createElement('div');
        indicator.className = 'message assistant';
        indicator.id = 'typing-indicator';
        indicator.innerHTML = `
            <div class="message-avatar">AI</div>
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
                <h3>New Conversation</h3>
                <p>Start a conversation or search your knowledge base.</p>
            </div>
        `;
        
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
    tagConversation() {
        if (!this.currentConversationId) {
            this.showError('Please select a conversation to tag');
            return;
        }
        document.getElementById('tag-modal').style.display = 'flex';
        document.getElementById('tag-input').focus();
    }

    handleTagInput(event) {
        if (event.key === 'Enter') {
            this.saveTags();
        }
    }

    async saveTags() {
        const tagInput = document.getElementById('tag-input').value;
        const tags = tagInput.split(',').map(tag => tag.trim()).filter(tag => tag);
        
        // Save tags to conversation (API call needed)
        console.log('Saving tags:', tags);
        
        this.closeTagModal();
        this.loadConversations(); // Refresh to show new tags
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
            <div class="message-avatar">U</div>
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
    searchConversations() {
        const query = document.getElementById('conversation-search').value.toLowerCase();
        const items = document.querySelectorAll('.conversation-item');
        
        items.forEach(item => {
            // Only filter conversation items that have a .conversation-title (not project items)
            const titleElem = item.querySelector('.conversation-title');
            if (!titleElem) {
                // console.log('Skipping project item:', item.textContent);
                return;
            }
            const title = titleElem.textContent.toLowerCase();
            const tags = (item.querySelector('.conversation-tags')?.textContent || '').toLowerCase();
            
            if (title.includes(query) || tags.includes(query)) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
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
            <div class="message-avatar" style="background-color: #f44336;">!</div>
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
}

// --- Add at the top of the file, before class KnowledgeBaseApp ---
KnowledgeBaseApp.prototype.showNewProjectInput = function() {
    document.getElementById('new-project-input-row').style.display = '';
    document.getElementById('new-project-input').focus();
};

KnowledgeBaseApp.prototype.toggleProjects = function() {
    const section = document.getElementById('projects-section');
    const toggleBtn = document.getElementById('toggle-projects-btn');
    section.classList.toggle('collapsed');
    toggleBtn.textContent = section.classList.contains('collapsed') ? '► Projects' : '▼ Projects';
};

KnowledgeBaseApp.prototype.openSettingsModal = function() {
    document.getElementById('settings-modal').style.display = 'flex';
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
    const file = files[0]; // Only one context doc at a time
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
        } else {
            this.showError(data.error || 'Context upload failed.');
        }
    } catch (error) {
        this.showError('Context upload failed.');
        console.error('Context upload error:', error);
    }
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
        <div class="message-avatar">U</div>
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
        <div class="message-avatar">U</div>
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