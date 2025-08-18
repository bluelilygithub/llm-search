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
        this.currentProject = project;
        this.loadProjects();
        this.loadConversations();
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
            this.showError('Failed to send message. Please try again.');
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

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            return data.response;
            
        } catch (error) {
            console.error('LLM API error:', error);
            throw new Error('Failed to get AI response');
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

    handleFileUpload(event) {
        const files = Array.from(event.target.files);
        this.uploadedFiles.push(...files);
        this.renderUploadedFiles();
    }

    renderUploadedFiles() {
        // Implementation for showing uploaded files
        console.log('Uploaded files:', this.uploadedFiles);
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
    addUrlReference() {
        const url = prompt('Enter URL to reference:');
        if (url && this.isValidUrl(url)) {
            this.urlReferences.push({
                url: url,
                title: this.extractDomain(url)
            });
            this.renderUrlReferences();
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
        // Simple error display
        console.error(message);
        // Could implement toast notifications here
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new KnowledgeBaseApp();
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

// Add these methods to KnowledgeBaseApp

// Toggle projects section
window.app.toggleProjects = function() {
    const section = document.getElementById('projects-section');
    const toggleBtn = document.getElementById('toggle-projects-btn');
    section.classList.toggle('collapsed');
    toggleBtn.textContent = section.classList.contains('collapsed') ? '► Projects' : '▼ Projects';
};

// Show new project input
window.app.showNewProjectInput = function() {
    document.getElementById('new-project-input-row').style.display = '';
    document.getElementById('new-project-input').focus();
};

// Handle new project input
window.app.handleNewProjectInput = function(e) {
    if (e.key === 'Enter') {
        window.app.createProject(e.target.value);
        e.target.value = '';
        document.getElementById('new-project-input-row').style.display = 'none';
    }
    if (e.key === 'Escape') {
        document.getElementById('new-project-input-row').style.display = 'none';
    }
};

// Update renderProjects to only update the project list
KnowledgeBaseApp.prototype.renderProjects = function(projects) {
    const projectList = document.getElementById('project-list');
    if (!projectList) return;
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
};