class KnowledgeBaseApp {
    constructor() {
        this.currentConversationId = null;
        this.selectedModel = 'gpt-3.5-turbo';
        this.uploadedFiles = [];
        this.urlReferences = [];
        this.isRecording = false;
        this.mediaRecorder = null;
        
        this.init();
    }

    init() {
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

    async loadConversations() {
        try {
            const response = await fetch('/conversations');
            const conversations = await response.json();
            this.renderConversations(conversations);
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
        
        messageDiv.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                ${this.formatMessageContent(message.content)}
                <div class="message-time">${this.formatTime(message.timestamp)}</div>
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
            
            // Don't reset currentConversationId on error - keep the conversation
            // Remove the user message that was added to UI since it failed
            const messages = document.querySelectorAll('.message');
            const lastMessage = messages[messages.length - 1];
            if (lastMessage && lastMessage.classList.contains('user')) {
                lastMessage.remove();
            }
        }
    }

    async createNewConversation(firstMessage) {
        const title = firstMessage.length > 50 ? 
            firstMessage.substring(0, 50) + '...' : firstMessage;
            
        const response = await fetch('/conversations', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: title,
                llm_model: this.selectedModel,
                tags: []
            })
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

    // Voice input functionality
    setupVoiceInput() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            console.warn('Voice input not supported in this browser');
            return;
        }
    }

    async startVoiceInput() {
        if (this.isRecording) {
            this.stopVoiceInput();
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaRecorder = new MediaRecorder(stream);
            this.isRecording = true;
            
            const voiceBtn = document.getElementById('voice-btn');
            voiceBtn.classList.add('recording');
            
            const audioChunks = [];
            this.mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };
            
            this.mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                await this.transcribeAudio(audioBlob);
                voiceBtn.classList.remove('recording');
                this.isRecording = false;
            };
            
            this.mediaRecorder.start();
            
        } catch (error) {
            console.error('Voice input failed:', error);
            this.showError('Voice input not available');
        }
    }

    stopVoiceInput() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
        }
    }

    async transcribeAudio(audioBlob) {
        // Placeholder for Whisper API integration
        console.log('Transcribing audio...', audioBlob);
        this.showError('Voice transcription coming soon!');
    }

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
            const title = item.querySelector('.conversation-title').textContent.toLowerCase();
            const tags = item.querySelector('.conversation-tags').textContent.toLowerCase();
            
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
        
        // Trigger knowledge base search suggestions as user types
        const query = document.getElementById('message-input').value.trim();
        if (query.length > 3) {
            this.debounce(this.showSearchSuggestions.bind(this), 300)(query);
        } else {
            this.hideSearchSuggestions();
        }
    }

    showSearchSuggestions(query) {
        // Placeholder for integrated search suggestions
        console.log('Searching for:', query);
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