// Chat Management Module
// Handles all chat/conversation related functionality

class ChatManager {
    constructor(app) {
        this.app = app;
        this.currentConversationId = null;
    }

    // Render messages in the chat container
    renderMessages(messages) {
        const chatContainer = document.getElementById('chat-container');
        if (!chatContainer) {
            console.warn('Chat container not found');
            return;
        }

        chatContainer.innerHTML = '';
        
        if (!messages || messages.length === 0) {
            chatContainer.innerHTML = `
                <div class="welcome-message">
                    <h2>Welcome to AI Knowledge Base</h2>
                    <p>Start a conversation by typing a message below.</p>
                </div>
            `;
            return;
        }

        messages.forEach(message => {
            this.addMessageToChat(message);
        });

        this.scrollToBottom();
    }

    // Add a single message to the chat
    addMessageToChat(message) {
        const chatContainer = document.getElementById('chat-container');
        if (!chatContainer) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.role}`;
        messageDiv.id = `message-${message.id}`;

        const timestamp = this.formatTime(message.timestamp);
        const formattedContent = this.formatMessageContent(message.content);

        messageDiv.innerHTML = `
            <div class="message-header">
                <span class="message-role">${message.role === 'user' ? 'You' : 'AI'}</span>
                <span class="message-time">${timestamp}</span>
            </div>
            <div class="message-content">${formattedContent}</div>
        `;

        chatContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    // Format message content (markdown, code blocks, etc.)
    formatMessageContent(content) {
        if (!content) return '';

        // Handle markdown code blocks
        content = content.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            const language = lang || 'text';
            return `<pre><code class="language-${language}">${this.escapeHtml(code)}</code></pre>`;
        });

        // Handle inline code
        content = content.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Handle line breaks
        content = content.replace(/\n/g, '<br>');

        // Handle bold text
        content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

        // Handle italic text
        content = content.replace(/\*(.*?)\*/g, '<em>$1</em>');

        return content;
    }

    // Escape HTML to prevent XSS
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Show typing indicator
    showTypingIndicator() {
        const chatContainer = document.getElementById('chat-container');
        if (!chatContainer) return;

        // Remove existing typing indicator
        const existingIndicator = chatContainer.querySelector('.typing-indicator');
        if (existingIndicator) {
            existingIndicator.remove();
        }

        const typingDiv = document.createElement('div');
        typingDiv.className = 'message ai typing-indicator';
        typingDiv.innerHTML = `
            <div class="message-header">
                <span class="message-role">AI</span>
            </div>
            <div class="message-content">
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;

        chatContainer.appendChild(typingDiv);
        this.scrollToBottom();
    }

    // Hide typing indicator
    hideTypingIndicator() {
        const typingIndicator = document.querySelector('.typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    // Start a new chat
    startNewChat() {
        this.currentConversationId = null;
        
        // Clear chat container
        const chatContainer = document.getElementById('chat-container');
        if (chatContainer) {
            chatContainer.innerHTML = `
                <div class="welcome-message">
                    <h2>Welcome to AI Knowledge Base</h2>
                    <p>Start a conversation by typing a message below.</p>
                </div>
            `;
        }

        // Update UI to show chat view
        this.app.showChatView();
        
        // Clear input field
        const messageInput = document.getElementById('message-input');
        if (messageInput) {
            messageInput.value = '';
            messageInput.focus();
        }
    }

    // Update chat header with conversation info
    updateChatHeader(conversation) {
        const chatHeader = document.getElementById('chat-header');
        if (!chatHeader) return;

        if (conversation) {
            chatHeader.innerHTML = `
                <div class="chat-header-content">
                    <h2>${conversation.title || 'Untitled Conversation'}</h2>
                    <div class="chat-meta">
                        <span class="conversation-date">${this.formatDate(conversation.created_at)}</span>
                        ${conversation.project_name ? `<span class="project-name">Project: ${conversation.project_name}</span>` : ''}
                    </div>
                </div>
                <div class="chat-actions">
                    <button onclick="window.app.exportConversation()" class="btn btn-secondary">
                        <i class="fas fa-download"></i> Export
                    </button>
                    <button onclick="window.app.tagConversation()" class="btn btn-secondary">
                        <i class="fas fa-tags"></i> Tags
                    </button>
                </div>
            `;
            chatHeader.style.display = 'flex';
        } else {
            chatHeader.style.display = 'none';
        }
    }

    // Go back to project view
    goBackToProject() {
        if (this.app.currentProject) {
            this.app.showProjectConversationsView(this.app.currentProject);
        } else {
            this.app.goToHome();
        }
    }

    // Go to home view
    goToHome() {
        this.app.showHomeView();
    }

    // Scroll chat to bottom
    scrollToBottom() {
        const chatContainer = document.getElementById('chat-container');
        if (chatContainer) {
            requestAnimationFrame(() => {
                chatContainer.scrollTop = chatContainer.scrollHeight;
            });
        }
    }

    // Format date for display
    formatDate(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        return date.toLocaleDateString();
    }

    // Format time for display
    formatTime(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    // Show image editing complete message
    showImageEditingComplete() {
        const chatContainer = document.getElementById('chat-container');
        if (!chatContainer) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai image-edit-complete';
        messageDiv.innerHTML = `
            <div class="message-header">
                <span class="message-role">AI</span>
            </div>
            <div class="message-content">
                <div class="image-edit-status">
                    <i class="fas fa-check-circle"></i>
                    <span>Image editing complete! The edited image has been added to your conversation.</span>
                </div>
            </div>
        `;

        chatContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChatManager;
} else {
    window.ChatManager = ChatManager;
}
