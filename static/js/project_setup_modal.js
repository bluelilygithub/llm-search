// Project Setup Modal Functions
window.showProjectSetupModal = function() {
    const modal = document.getElementById('project-setup-modal');
    const projectNameSpan = document.getElementById('project-setup-name');
    
    if (modal && window.app && window.app.pendingProjectName) {
        projectNameSpan.textContent = window.app.pendingProjectName;
        
        // Show modal with proper display and classes
        modal.style.display = 'flex';
        modal.classList.add('show');
        document.body.classList.add('modal-open');
        
        // Prevent body scrolling
        document.body.style.overflow = 'hidden';
        
        // Focus on first input
        setTimeout(() => {
            const firstInput = modal.querySelector('input, textarea');
            if (firstInput) firstInput.focus();
        }, 100);
    } else {
        console.error('Modal element not found or no pending project name');
    }
};

window.closeProjectSetup = function() {
    const modal = document.getElementById('project-setup-modal');
    if (modal) {
        // Hide modal
        modal.style.display = 'none';
        modal.classList.remove('show');
        document.body.classList.remove('modal-open');
        
        // Restore body scrolling
        document.body.style.overflow = '';
        
        // Clear form
        const form = document.getElementById('project-setup-form');
        if (form) form.reset();
        
        // Clear pending project name
        if (window.app) {
            window.app.pendingProjectName = null;
        }
    }
};

window.saveProjectSetup = function() {
    if (!window.app || !window.app.pendingProjectName) {
        console.error('No pending project name found');
        return;
    }
    
    // Collect form data
    const projectData = {
        name: window.app.pendingProjectName,
        agent_name: document.getElementById('agent-name').value.trim(),
        agent_role: document.getElementById('agent-role').value.trim(),
        agent_personality: document.getElementById('agent-personality').value.trim(),
        primary_goal: document.getElementById('primary-goal').value.trim(),
        goal_steps: document.getElementById('goal-steps').value.trim(),
        rules_do: document.getElementById('rules-do').value.trim(),
        rules_dont: document.getElementById('rules-dont').value.trim(),
        context_background: document.getElementById('context-background').value.trim(),
        user_role: document.getElementById('user-role').value.trim(),
        output_format: document.getElementById('output-format').value.trim()
    };
    
    // Remove empty fields
    Object.keys(projectData).forEach(key => {
        if (!projectData[key]) {
            delete projectData[key];
        }
    });
    
    // Create the project with setup data
    window.app.createProjectWithSetup(projectData);
    
    // Close modal
    closeProjectSetup();
};

// Add to KnowledgeBaseApp prototype
KnowledgeBaseApp.prototype.showProjectSetupModal = function() {
    window.showProjectSetupModal();
};

KnowledgeBaseApp.prototype.createProjectWithSetup = async function(projectData) {
    try {
        const response = await fetch('/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(projectData)
        });
        
        if (!response.ok) throw new Error('Failed to create project');
        
        const project = await response.json();
        
        this.addingProject = false;
        await this.loadProjects();
        
        // If currently viewing projects page, refresh the main content area too
        if (this.currentView === 'projects') {
            await this.loadProjectsGrid();
        }
        
        // Show success notification
        const hasTemplate = project.template && (project.template.agent_name || project.template.primary_goal);
        const message = hasTemplate 
            ? `Project "${project.name}" created with custom template!`
            : `Project "${project.name}" created successfully!`;
        this.showSuccessNotification(message);
        
    } catch (error) {
        console.error('Failed to create project:', error);
        alert('Failed to create project. Please try again.');
    }
};
