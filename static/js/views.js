// View Management Module
// Handles different application views (home, conversations, projects, chat)

class ViewManager {
    constructor(app) {
        this.app = app;
        this.currentView = 'home';
    }

    // Show home view in main content area
    showHomeView() {
        this.currentView = 'home';
        const container = document.getElementById('main-content');
        
        // Update top bar to hide context toggle
        const contextToggle = document.getElementById('context-toggle-btn');
        if (contextToggle) contextToggle.style.display = 'none';
        
        if (!container) {
            console.error('main-content div not found');
            return;
        }
        
        container.innerHTML = `
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
                            <p>Begin a new conversation or ask questions about your knowledge base</p>
                        </div>

                        <div class="action-card" onclick="window.app.showConversationsView()">
                            <i class="fas fa-clock"></i>
                            <h3>View All Conversations</h3>
                            <p>Browse through your conversation history</p>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Show the bottom input in home view
        const bottomInput = document.querySelector('.bottom-input-container');
        if (bottomInput) {
            bottomInput.style.display = 'block';
            bottomInput.classList.remove('hidden-in-projects');
        }
        
        // Load home statistics
        this.loadHomeStats();
    }

    // Show conversations list view in main content area
    showConversationsView() {
        this.currentView = 'conversations';
        const container = document.getElementById('main-content');
        
        // Update top bar to hide context toggle
        const contextToggle = document.getElementById('context-toggle-btn');
        if (contextToggle) contextToggle.style.display = 'none';
        
        if (!container) {
            console.error('main-content div not found');
            return;
        }
        
        // Preserve the top bar and bottom input container
        const topBar = container.querySelector('.top-bar');
        const bottomInput = container.querySelector('.bottom-input-container');
        
        // Remove any existing main-view elements to prevent appending
        const existingMainViews = container.querySelectorAll('.main-view');
        existingMainViews.forEach(view => view.remove());
        
        // Clear only the chat messages area, not the entire container
        const chatMessagesContainer = container.querySelector('.chat-messages-container');
        if (chatMessagesContainer) {
            chatMessagesContainer.remove();
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
                    <button class="view-action-btn" onclick="window.app.startNewConversationFromConversations()">
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
        
        // Insert after the top bar to maintain proper layout
        if (topBar) {
            topBar.insertAdjacentElement('afterend', conversationsContent);
        } else {
            container.appendChild(conversationsContent);
        }
        
        // Show the bottom input in conversations view
        if (bottomInput) {
            bottomInput.style.display = 'block';
            bottomInput.classList.remove('hidden-in-projects');
        }
        
        this.loadConversationsGrid();
    }

    // Show projects grid view in main content area
    showProjectsView() {
        this.currentView = 'projects';
        const container = document.getElementById('main-content');
        
        // Update top bar to hide context toggle
        const contextToggle = document.getElementById('context-toggle-btn');
        if (contextToggle) contextToggle.style.display = 'none';
        
        if (!container) {
            console.error('main-content div not found');
            return;
        }
        
        // Preserve the top bar and bottom input container
        const topBar = container.querySelector('.top-bar');
        const bottomInput = container.querySelector('.bottom-input-container');
        
        // Remove any existing main-view elements to prevent appending
        const existingMainViews = container.querySelectorAll('.main-view');
        existingMainViews.forEach(view => view.remove());
        
        // Clear only the chat messages area, not the entire container
        const chatMessagesContainer = container.querySelector('.chat-messages-container');
        if (chatMessagesContainer) {
            chatMessagesContainer.remove();
        }
        
        // Create the projects view content
        const projectsContent = document.createElement('div');
        projectsContent.className = 'main-view';
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
        
        // Insert after the top bar to maintain proper layout
        if (topBar) {
            topBar.insertAdjacentElement('afterend', projectsContent);
        } else {
            container.appendChild(projectsContent);
        }
        
        // Hide the bottom input in projects view
        if (bottomInput) {
            bottomInput.style.display = 'none';
            bottomInput.classList.add('hidden-in-projects');
            console.log('showProjectsView: Hidden bottom input container');
        } else {
            console.log('showProjectsView: Bottom input container not found');
        }
        
        this.loadProjectsGrid();
        
        // Double-check that bottom input is still hidden after loading projects
        setTimeout(() => {
            const bottomInput = document.querySelector('.bottom-input-container');
            if (bottomInput && bottomInput.style.display !== 'none') {
                console.log('showProjectsView: Bottom input became visible again, re-hiding...');
                bottomInput.style.display = 'none';
                bottomInput.classList.add('hidden-in-projects');
            }
        }, 100);
    }

    // Show project conversations view
    showProjectConversationsView(project) {
        this.currentView = 'project-conversations';
        this.app.currentViewProject = project;
        const container = document.getElementById('main-content');
        
        if (!container) {
            console.error('main-content div not found');
            return;
        }
        
        // Preserve the top bar and bottom input container
        const topBar = container.querySelector('.top-bar');
        const bottomInput = container.querySelector('.bottom-input-container');
        
        // Hide the bottom input when in project view
        if (bottomInput) {
            bottomInput.style.display = 'none';
        }
        
        // Remove any existing main-view elements to prevent appending
        const existingMainViews = container.querySelectorAll('.main-view');
        existingMainViews.forEach(view => view.remove());
        
        // Clear only the chat messages area, not the entire container
        const chatMessagesContainer = container.querySelector('.chat-messages-container');
        if (chatMessagesContainer) {
            chatMessagesContainer.remove();
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
        `;
        
        // Insert after the top bar to maintain proper layout
        if (topBar) {
            topBar.insertAdjacentElement('afterend', projectContent);
        } else {
            container.appendChild(projectContent);
        }
        
        this.loadProjectConversationsGrid(project.id);
    }

    // Show normal chat view
    showChatView() {
        this.currentView = 'chat';
        
        // Always use main-content container for chat view to ensure proper layout
        const container = document.getElementById('main-content');
        if (!container) {
            console.error('main-content container not found for chat view');
            return;
        }
        
        // Clear any existing view content (conversations, projects, etc.)
        const existingViewContent = container.querySelector('.main-view');
        if (existingViewContent) {
            existingViewContent.remove();
        }
        
        // Ensure the main-content div has the proper CSS classes for chat layout
        container.className = 'main-content';
        
        // Find the existing chat-messages-container in the template
        let chatMessagesContainer = container.querySelector('.chat-messages-container');
        console.log('showChatView: Looking for existing chat container:', chatMessagesContainer);
        
        if (!chatMessagesContainer) {
            console.log('showChatView: Chat container not found in template, creating new one');
            // Only create if it doesn't exist in the template
            chatMessagesContainer = document.createElement('div');
            chatMessagesContainer.className = 'chat-messages-container';
            chatMessagesContainer.innerHTML = `
                <div class="chat-messages" id="chat-messages">
                    <!-- Messages will be loaded here -->
                </div>
            `;
            
            // Insert after the chat header (which is now below the top bar)
            const chatHeader = container.querySelector('.chat-header');
            if (chatHeader) {
                console.log('showChatView: Inserting after chat header');
                chatHeader.insertAdjacentElement('afterend', chatMessagesContainer);
            } else {
                // Fallback: insert after top bar if chat header not found
                const topBar = container.querySelector('.top-bar');
                if (topBar) {
                    console.log('showChatView: Chat header not found, inserting after top bar');
                    topBar.insertAdjacentElement('afterend', chatMessagesContainer);
                } else {
                    console.log('showChatView: No top bar found, appending to container');
                    container.appendChild(chatMessagesContainer);
                }
            }
            console.log('showChatView: Chat container created and inserted');
        } else {
            console.log('showChatView: Existing chat container found in template');
            // Ensure the existing container is in the right place (after chat header)
            const chatHeader = container.querySelector('.chat-header');
            if (chatHeader && chatMessagesContainer.previousElementSibling !== chatHeader) {
                console.log('showChatView: Moving existing chat container to correct position after chat header');
                chatHeader.insertAdjacentElement('afterend', chatMessagesContainer);
            } else if (!chatHeader) {
                // Fallback: check if it's after top bar
                const topBar = container.querySelector('.top-bar');
                if (topBar && chatMessagesContainer.previousElementSibling !== topBar) {
                    console.log('showChatView: Moving existing chat container to correct position after top bar');
                    topBar.insertAdjacentElement('afterend', chatMessagesContainer);
                }
            }
        }
        
        // Show/hide chat header based on project context
        const chatHeader = document.getElementById('chat-header');
        if (chatHeader) {
            if (this.app.currentViewProject) {
                // Show project context in header
                chatHeader.style.display = 'block';
                const projectName = document.getElementById('project-name');
                const conversationTitle = document.getElementById('conversation-title');
                if (projectName) projectName.textContent = this.app.currentViewProject.name;
                if (conversationTitle) conversationTitle.textContent = 'New Conversation';
                console.log('showChatView: Breadcrumb displayed for project:', this.app.currentViewProject.name);
            } else {
                chatHeader.style.display = 'none';
                console.log('showChatView: Breadcrumb hidden - no project context');
            }
        } else {
            console.warn('showChatView: Chat header not found');
        }
        
        // Show context toggle again
        const contextToggle = document.getElementById('context-toggle-btn');
        if (contextToggle) contextToggle.style.display = 'block';
        
        // Hide any remaining search results that might be interfering with the layout
        const searchResults = document.querySelector('.search-results-container');
        if (searchResults) {
            searchResults.style.display = 'none';
        }
        
        // Show empty state for new conversation
        if (!this.app.currentConversationId) {
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
        
        // Show the bottom input when in chat view
        const bottomInput = container.querySelector('.bottom-input-container');
        if (bottomInput) {
            bottomInput.style.display = 'block';
            bottomInput.classList.remove('hidden-in-projects');
        }
        
        // If there's a current conversation, it will be loaded by the caller
    }

    // Load conversations grid data
    async loadConversationsGrid() {
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
                    <button class="view-action-btn" onclick="window.app.viewManager.loadConversationsGrid()">
                        <i class="fas fa-refresh"></i>
                        Retry
                    </button>
                </div>
            `;
        }
    }

    // Load home statistics
    async loadHomeStats() {
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
    }

    // Load projects grid data
    async loadProjectsGrid() {
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
                    <button class="view-action-btn" onclick="window.app.viewManager.loadProjectsGrid()">
                        <i class="fas fa-refresh"></i>
                        Retry
                    </button>
                </div>
            `;
        }
    }

    // Load project conversations grid data
    async loadProjectConversationsGrid(projectId) {
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
                    <button class="view-action-btn" onclick="window.app.viewManager.loadProjectConversationsGrid('${projectId}')">
                        <i class="fas fa-refresh"></i>
                        Retry
                    </button>
                </div>
            `;
        }
    }

    // Render conversations in grid format
    renderConversationsGrid(conversations, containerId = 'conversations-grid') {
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
                        <span>${this.app.formatDate(conv.updated_at)}</span>
                    </div>
                    <div class="conversation-card-tags">${tags}</div>
                    <div class="conversation-card-preview">${preview}</div>
                </div>
            `;
        }).join('');
        
        container.innerHTML = conversationCards;
    }

    // Render projects in grid format
    renderProjectsGrid(projects) {
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
    }

    // Open conversation from grid view
    openConversationFromGrid(conversationId) {
        // Preserve project context when opening conversation from project view
        const preserveProjectContext = this.app.currentViewProject;
        
        // Switch back to chat view and load the conversation
        this.showChatView();
        
        // Restore project context if we came from a project view
        if (preserveProjectContext) {
            this.app.currentViewProject = preserveProjectContext;
        }
        
        // Ensure we're using the correct 'this' context
        if (this.app && typeof this.app.loadConversation === 'function') {
            this.app.loadConversation(conversationId);
        } else {
            // Fallback to window.app if 'this' context is lost
            console.warn('Lost context in openConversationFromGrid, using window.app fallback');
            if (window.app && typeof window.app.loadConversation === 'function') {
                window.app.loadConversation(conversationId);
            } else {
                console.error('Cannot load conversation: loadConversation method not found');
            }
        }
    }

    // Open project from grid view
    openProject(projectId) {
        // Find project data
        const project = this.app.projects.find(p => p.id === projectId);
        if (project) {
            this.showProjectConversationsView(project);
        }
    }

    // Clear project context and return to home view
    clearProjectContext() {
        this.app.currentViewProject = null;
        this.app.currentProject = null;
        this.showChatView();
    }
}

// Export for use in main app
window.ViewManager = ViewManager;
