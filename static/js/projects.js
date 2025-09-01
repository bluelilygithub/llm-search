// Project Management Module
// Handles all project-related functionality

class ProjectManager {
    constructor(app) {
        this.app = app;
        this.currentProject = null;
        this.projects = [];
    }

    // Load projects from the server
    async loadProjects() {
        try {
            const response = await fetch('/api/projects');
            if (response.ok) {
                const projects = await response.json();
                this.projects = projects;
                this.renderProjects(projects);
            } else {
                console.error('Failed to load projects');
            }
        } catch (error) {
            console.error('Error loading projects:', error);
        }
    }

    // Render projects in the sidebar
    renderProjects(projects) {
        const projectsContainer = document.querySelector('.projects-scroll-area');
        if (!projectsContainer) return;

        projectsContainer.innerHTML = '';

        // Add "No Project" option first
        const noProjectItem = document.createElement('div');
        noProjectItem.className = 'project-item no-project';
        noProjectItem.onclick = () => this.selectProject(null);
        noProjectItem.innerHTML = `
            <i class="fas fa-home"></i>
            <span>No Project</span>
        `;
        projectsContainer.appendChild(noProjectItem);

        // Add actual projects
        projects.forEach(project => {
            const projectItem = document.createElement('div');
            projectItem.className = 'project-item';
            projectItem.onclick = () => this.selectProject(project);
            projectItem.innerHTML = `
                <i class="fas fa-folder"></i>
                <span>${project.name}</span>
                <span class="conversation-count">${project.conversation_count}</span>
            `;
            projectsContainer.appendChild(projectItem);
        });

        // Set "No Project" as active by default
        this.updateProjectSelectionUI(null);
    }

    // Select a project
    selectProject(project) {
        this.currentProject = project;
        
        if (project) {
            // Show project conversations view
            this.app.showProjectConversationsView(project);
        } else {
            // Show home view
            this.app.showHomeView();
        }

        // Update UI to reflect selection
        this.updateProjectSelectionUI(project);
    }

    // Update the project selection UI
    updateProjectSelectionUI(selectedProject) {
        // Remove active class from all project items
        const allProjectItems = document.querySelectorAll('.project-item');
        allProjectItems.forEach(item => item.classList.remove('active'));

        // Add active class to selected project or "No Project"
        if (selectedProject) {
            const selectedItem = Array.from(allProjectItems).find(item => 
                item.textContent.includes(selectedProject.name)
            );
            if (selectedItem) {
                selectedItem.classList.add('active');
            }
        } else {
            // "No Project" is selected
            const noProjectItem = document.querySelector('.project-item.no-project');
            if (noProjectItem) {
                noProjectItem.classList.add('active');
            }
        }
    }

    // Create a new project
    async createNewProject(name) {
        try {
            const response = await fetch('/api/projects', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                },
                body: JSON.stringify({ name })
            });

            if (response.ok) {
                const newProject = await response.json();
                this.projects.push(newProject);
                this.renderProjects(this.projects);
                this.selectProject(newProject);
                return newProject;
            } else {
                console.error('Failed to create project');
                return null;
            }
        } catch (error) {
            console.error('Error creating project:', error);
            return null;
        }
    }

    // Edit project name
    async editProject(projectId, currentName) {
        const newName = prompt('Enter new project name:', currentName);
        if (!newName || newName.trim() === currentName) return;

        try {
            const response = await fetch(`/api/projects/${projectId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                },
                body: JSON.stringify({ name: newName.trim() })
            });

            if (response.ok) {
                const updatedProject = await response.json();
                
                // Update local projects array
                const projectIndex = this.projects.findIndex(p => p.id === projectId);
                if (projectIndex !== -1) {
                    this.projects[projectIndex] = updatedProject;
                }

                // Update current project if it's the one being edited
                if (this.currentProject && this.currentProject.id === projectId) {
                    this.currentProject = updatedProject;
                }

                // Re-render projects
                this.renderProjects(this.projects);
                
                // Update project selection UI
                this.updateProjectSelectionUI(this.currentProject);
            } else {
                console.error('Failed to update project');
            }
        } catch (error) {
            console.error('Error updating project:', error);
        }
    }

    // Delete a project
    async deleteProject(projectId) {
        if (!confirm('Are you sure you want to delete this project? This action cannot be undone.')) {
            return;
        }

        try {
            const response = await fetch(`/api/projects/${projectId}`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                }
            });

            if (response.ok) {
                // Remove from local projects array
                this.projects = this.projects.filter(p => p.id !== projectId);

                // If this was the current project, go to home
                if (this.currentProject && this.currentProject.id === projectId) {
                    this.currentProject = null;
                    this.app.showHomeView();
                }

                // Re-render projects
                this.renderProjects(this.projects);
                
                // Update project selection UI
                this.updateProjectSelectionUI(this.currentProject);
            } else {
                console.error('Failed to delete project');
            }
        } catch (error) {
            console.error('Error deleting project:', error);
        }
    }

    // Get current project
    getCurrentProject() {
        return this.currentProject;
    }

    // Get all projects
    getAllProjects() {
        return this.projects;
    }

    // Check if a project exists
    projectExists(projectId) {
        return this.projects.some(p => p.id === projectId);
    }

    // Find project by ID
    findProjectById(projectId) {
        return this.projects.find(p => p.id === projectId);
    }

    // Find project by name
    findProjectByName(name) {
        return this.projects.find(p => p.name === name);
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ProjectManager;
} else {
    window.ProjectManager = ProjectManager;
}
