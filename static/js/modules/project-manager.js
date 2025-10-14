/**
 * Project Manager Module
 * Handles all project-related functionality including CRUD operations, templates, and project views
 * Manages project state and provides clean API for project operations
 */

class ProjectManager {
    constructor(apiClient, uiController) {
        this.apiClient = apiClient;
        this.uiController = uiController;
        
        // Project state
        this.projects = [];
        this.currentProject = null;
        this.currentViewProject = null;
        
        this.initializeProjectManager();
    }

    /**
     * Initialize project manager
     */
    initializeProjectManager() {
        this.loadProjects();
    }

    /**
     * Load all projects
     */
    async loadProjects() {
        try {
            this.projects = await this.apiClient.getProjects();
            this.updateProjectsList();
            return this.projects;
        } catch (error) {
            console.error('Error loading projects:', error);
            this.uiController.showNotification('Failed to load projects', 'error');
            return [];
        }
    }

    /**
     * Create a new project
     */
    async createProject(projectData) {
        try {
            const project = await this.apiClient.createProject(projectData);
            
            // Add to local projects array
            this.projects.push(project);
            
            // Update UI
            this.updateProjectsList();
            
            this.uiController.showNotification(`Project "${project.name}" created successfully`, 'success');
            
            return project;
        } catch (error) {
            console.error('Error creating project:', error);
            this.uiController.showNotification('Failed to create project', 'error');
            throw error;
        }
    }

    /**
     * Update an existing project
     */
    async updateProject(projectId, projectData) {
        try {
            const updatedProject = await this.apiClient.updateProject(projectId, projectData);
            
            // Update local projects array
            const index = this.projects.findIndex(p => p.id === projectId);
            if (index !== -1) {
                this.projects[index] = { ...this.projects[index], ...updatedProject };
            }
            
            // Update UI
            this.updateProjectsList();
            
            this.uiController.showNotification('Project updated successfully', 'success');
            
            return updatedProject;
        } catch (error) {
            console.error('Error updating project:', error);
            this.uiController.showNotification('Failed to update project', 'error');
            throw error;
        }
    }

    /**
     * Delete a project
     */
    async deleteProject(projectId, deleteConversations = false) {
        try {
            // Get project name for confirmation
            const project = this.projects.find(p => p.id === projectId);
            const projectName = project ? project.name : 'Unknown';
            
            // Get conversation count
            const conversationCount = project ? project.conversation_count || 0 : 0;
            
            // Show confirmation dialog
            let confirmMessage = `Are you sure you want to delete the project "${projectName}"?`;
            if (conversationCount > 0) {
                confirmMessage += `\n\nThis project has ${conversationCount} associated conversation${conversationCount > 1 ? 's' : ''}.`;
                if (deleteConversations) {
                    confirmMessage += '\n\nAll conversations will also be deleted.';
                } else {
                    confirmMessage += '\n\nConversations will be unassigned from the project.';
                }
            }
            
            if (!confirm(confirmMessage)) {
                return;
            }
            
            // Delete project
            await this.apiClient.deleteProject(projectId, deleteConversations);
            
            // Remove from local projects array
            this.projects = this.projects.filter(p => p.id !== projectId);
            
            // Clear current project if it was deleted
            if (this.currentProject?.id === projectId) {
                this.currentProject = null;
            }
            if (this.currentViewProject?.id === projectId) {
                this.currentViewProject = null;
            }
            
            // Update UI
            this.updateProjectsList();
            
            // Navigate to projects view if we were in the deleted project
            if (this.uiController.currentView === 'project-detail') {
                this.uiController.showView('projects');
            }
            
            this.uiController.showNotification(`Project "${projectName}" deleted successfully`, 'success');
            
        } catch (error) {
            console.error('Error deleting project:', error);
            this.uiController.showNotification('Failed to delete project', 'error');
        }
    }

    /**
     * Show projects view
     */
    showProjectsView() {
        const mainContent = this.uiController.getElement('main-content');
        if (!mainContent) return;

        const projectsHTML = `
            <div class="main-view">
                <nav class="breadcrumb">
                    <span class="breadcrumb-item active">
                        <i class="fas fa-folder-open"></i>
                        Projects
                    </span>
                </nav>
                
                <div class="view-header">
                    <div class="view-title">
                        <i class="fas fa-folder-open"></i>
                        <h2>Projects</h2>
                    </div>
                    <div class="view-actions">
                        <button class="view-action-btn" onclick="window.projectManager.showCreateProjectModal()">
                            <i class="fas fa-plus"></i>
                            New Project
                        </button>
                    </div>
                </div>
                
                <div class="projects-grid" id="projects-grid">
                    <div class="loading-placeholder">
                        <i class="fas fa-spinner fa-spin"></i>
                        <p>Loading projects...</p>
                    </div>
                </div>
            </div>
        `;

        mainContent.innerHTML = projectsHTML;
        
        // Load and render projects
        this.renderProjectsGrid();
    }

    /**
     * Show project detail view
     */
    async showProjectDetailView(projectId) {
        try {
            const project = this.projects.find(p => p.id === projectId);
            if (!project) {
                throw new Error('Project not found');
            }

            this.currentViewProject = project;

            const mainContent = this.uiController.getElement('main-content');
            if (!mainContent) return;

            const projectHTML = `
                <div class="main-view">
                    <nav class="breadcrumb">
                        <span class="breadcrumb-item breadcrumb-clickable" onclick="window.uiController.showView('projects')">
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
                            <button class="view-action-btn" onclick="window.chatManager.startNewConversation('${project.id}')">
                                <i class="fas fa-plus"></i>
                                New Chat
                            </button>
                            <button class="view-action-btn secondary" onclick="window.projectManager.showEditProjectModal('${project.id}')">
                                <i class="fas fa-edit"></i>
                                Edit Project
                            </button>
                        </div>
                    </div>
                    
                    <div class="project-conversations" id="project-conversations-grid">
                        <div class="loading-placeholder">
                            <i class="fas fa-spinner fa-spin"></i>
                            <p>Loading conversations...</p>
                        </div>
                    </div>
                </div>
            `;

            mainContent.innerHTML = projectHTML;
            
            // Load project conversations
            this.loadProjectConversations(projectId);

        } catch (error) {
            console.error('Error showing project detail:', error);
            this.uiController.showNotification('Failed to load project', 'error');
        }
    }

    /**
     * Load conversations for a project
     */
    async loadProjectConversations(projectId) {
        try {
            const conversations = await this.apiClient.request(`/projects/${projectId}/conversations`);
            this.renderProjectConversations(conversations);
        } catch (error) {
            console.error('Error loading project conversations:', error);
            const grid = document.getElementById('project-conversations-grid');
            if (grid) {
                grid.innerHTML = `
                    <div class="empty-state-large">
                        <i class="fas fa-exclamation-circle"></i>
                        <h3>Failed to load conversations</h3>
                        <p>Please try again later.</p>
                    </div>
                `;
            }
        }
    }

    /**
     * Render projects grid
     */
    async renderProjectsGrid() {
        const grid = document.getElementById('projects-grid');
        if (!grid) return;

        if (this.projects.length === 0) {
            grid.innerHTML = `
                <div class="empty-state-large">
                    <i class="fas fa-folder-plus"></i>
                    <h3>No projects yet</h3>
                    <p>Create your first project to organize your conversations.</p>
                    <button class="view-action-btn" onclick="window.projectManager.showCreateProjectModal()">
                        <i class="fas fa-plus"></i>
                        Create Project
                    </button>
                </div>
            `;
            return;
        }

        const projectCards = this.projects.map(project => {
            const conversationCount = project.conversation_count || 0;
            
            return `
                <div class="project-card" onclick="window.projectManager.showProjectDetailView('${project.id}')">
                    <div class="project-card-icon">
                        <i class="fas fa-folder-open"></i>
                    </div>
                    <h3 class="project-card-title">${project.name}</h3>
                    <p class="project-card-description">${project.description || 'No description'}</p>
                    <p class="project-card-count">${conversationCount} conversation${conversationCount !== 1 ? 's' : ''}</p>
                    <div class="project-card-actions">
                        <button class="view-action-btn secondary" onclick="event.stopPropagation(); window.projectManager.showProjectTemplatePreview('${project.id}')" title="Preview Template">
                            <i class="fas fa-eye"></i>
                            Preview
                        </button>
                        <button class="view-action-btn secondary" onclick="event.stopPropagation(); window.projectManager.showEditProjectTemplateModal('${project.id}')" title="Edit Template">
                            <i class="fas fa-cogs"></i>
                            Setup
                        </button>
                        <button class="view-action-btn secondary" onclick="event.stopPropagation(); window.projectManager.showEditProjectModal('${project.id}')" title="Rename Project">
                            <i class="fas fa-edit"></i>
                            Rename
                        </button>
                        <button class="view-action-btn secondary" onclick="event.stopPropagation(); window.projectManager.deleteProject('${project.id}')" title="Delete Project">
                            <i class="fas fa-trash"></i>
                            Delete
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        grid.innerHTML = `<div class="projects-grid-container">${projectCards}</div>`;
    }

    /**
     * Render project conversations
     */
    renderProjectConversations(conversations) {
        const grid = document.getElementById('project-conversations-grid');
        if (!grid) return;

        if (conversations.length === 0) {
            grid.innerHTML = `
                <div class="empty-state-large">
                    <i class="fas fa-comments"></i>
                    <h3>No conversations yet</h3>
                    <p>Start your first conversation in this project.</p>
                    <button class="view-action-btn" onclick="window.chatManager.startNewConversation('${this.currentViewProject?.id}')">
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

            return `
                <div class="conversation-card" onclick="window.chatManager.loadConversation('${conv.id}')">
                    <div class="conversation-card-header">
                        <h4 class="conversation-title">${conv.title}</h4>
                        <div class="conversation-actions">
                            <button class="conversation-card-action" onclick="event.stopPropagation(); window.projectManager.editConversationTitle('${conv.id}', '${conv.title.replace(/'/g, "\\'")}')" title="Edit">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="conversation-card-action" onclick="event.stopPropagation(); window.chatManager.deleteConversation('${conv.id}')" title="Delete">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                    <div class="conversation-meta">
                        <span class="conversation-model">
                            <i class="fas fa-robot"></i>
                            ${conv.llm_model}
                        </span>
                        <span class="conversation-date">
                            <i class="fas fa-calendar"></i>
                            ${new Date(conv.created_at).toLocaleDateString()}
                        </span>
                    </div>
                    ${tags ? `<div class="conversation-tags">${tags}</div>` : ''}
                </div>
            `;
        }).join('');

        grid.innerHTML = `<div class="conversations-grid-container">${conversationCards}</div>`;
    }

    /**
     * Update projects list in sidebar
     */
    updateProjectsList() {
        const projectsList = document.getElementById('projects-list');
        if (!projectsList) return;

        if (this.projects.length === 0) {
            projectsList.innerHTML = `
                <div class="empty-projects">
                    <p>No projects yet</p>
                    <button class="create-project-btn" onclick="window.projectManager.showCreateProjectModal()">
                        <i class="fas fa-plus"></i>
                        Create Project
                    </button>
                </div>
            `;
            return;
        }

        const projectItems = this.projects.map(project => `
            <div class="project-item" onclick="window.projectManager.showProjectDetailView('${project.id}')">
                <div class="project-item-icon">
                    <i class="fas fa-folder"></i>
                </div>
                <div class="project-item-content">
                    <span class="project-item-name">${project.name}</span>
                    <span class="project-item-count">${project.conversation_count || 0} chats</span>
                </div>
            </div>
        `).join('');

        projectsList.innerHTML = projectItems;
    }

    /**
     * Show create project modal
     */
    showCreateProjectModal() {
        // This would integrate with your existing project setup modal
        if (window.showProjectSetupModal) {
            window.showProjectSetupModal();
        } else {
            // Fallback to simple prompt
            const name = prompt('Enter project name:');
            if (name && name.trim()) {
                this.createProject({ name: name.trim() });
            }
        }
    }

    /**
     * Show edit project modal
     */
    showEditProjectModal(projectId) {
        const project = this.projects.find(p => p.id === projectId);
        if (!project) return;

        const newName = prompt('Edit project name:', project.name);
        if (newName && newName.trim() && newName.trim() !== project.name) {
            this.updateProject(projectId, { name: newName.trim() });
        }
    }

    /**
     * Edit conversation title
     */
    async editConversationTitle(conversationId, currentTitle) {
        const newTitle = prompt('Edit conversation title:', currentTitle);
        if (newTitle && newTitle.trim() && newTitle.trim() !== currentTitle) {
            try {
                await this.apiClient.updateConversation(conversationId, { title: newTitle.trim() });
                
                // Refresh the current view
                if (this.currentViewProject) {
                    this.loadProjectConversations(this.currentViewProject.id);
                }
                
                this.uiController.showNotification('Conversation title updated', 'success');
            } catch (error) {
                console.error('Error updating conversation title:', error);
                this.uiController.showNotification('Failed to update conversation title', 'error');
            }
        }
    }

    /**
     * Get project by ID
     */
    getProject(projectId) {
        return this.projects.find(p => p.id === projectId);
    }

    /**
     * Set current project
     */
    setCurrentProject(project) {
        this.currentProject = project;
        this.currentViewProject = project;
    }

    /**
     * Clear project context
     */
    clearProjectContext() {
        this.currentProject = null;
        this.currentViewProject = null;
    }
}

// Export for global use
window.ProjectManager = ProjectManager;
