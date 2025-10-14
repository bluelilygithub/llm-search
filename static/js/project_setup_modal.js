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
        
        // Reset modal to create mode
        const title = modal.querySelector('.modal-title');
        title.innerHTML = `
            <i class="fas fa-cogs"></i>
            Project Setup - <span id="project-setup-name"></span>
        `;
        
        const saveBtn = modal.querySelector('.btn-primary');
        saveBtn.innerHTML = '<i class="fas fa-save"></i> Save & Continue';
        
        // Clear pending project name and editing ID
        if (window.app) {
            window.app.pendingProjectName = null;
            window.app.editingProjectId = null;
        }
    }
};

window.saveProjectSetup = function() {
    if (!window.app || (!window.app.pendingProjectName && !window.app.editingProjectId)) {
        console.error('No pending project name or editing project ID found');
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
    
    // Remove empty fields (except for name)
    Object.keys(projectData).forEach(key => {
        if (key !== 'name' && !projectData[key]) {
            delete projectData[key];
        }
    });
    
    if (window.app.editingProjectId) {
        // Update existing project template
        window.app.updateProjectTemplate(window.app.editingProjectId, projectData);
    } else {
        // Create new project with setup data
        window.app.createProjectWithSetup(projectData);
    }
    
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

KnowledgeBaseApp.prototype.updateProjectTemplate = async function(projectId, templateData) {
    try {
        const response = await fetch(`/projects/${projectId}/template`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(templateData)
        });
        
        if (!response.ok) throw new Error('Failed to update project template');
        
        const result = await response.json();
        
        // Refresh projects if needed
        if (this.currentView === 'projects') {
            await this.loadProjectsGrid();
        }
        
        // Show success notification
        this.showSuccessNotification('Project template updated successfully!');
        
    } catch (error) {
        console.error('Failed to update project template:', error);
        alert('Failed to update project template. Please try again.');
    }
};

// Function to edit existing project template
window.editProjectTemplate = function(projectId) {
    // Load existing project template data
    fetch(`/projects/${projectId}/template`)
        .then(response => response.json())
        .then(data => {
            if (data.project && data.template) {
                // Set up modal for editing
                window.app.editingProjectId = projectId;
                window.app.pendingProjectName = data.project.name;
                
                // Populate form with existing data
                populateProjectSetupForm(data.template);
                
                // Update modal title
                const modal = document.getElementById('project-setup-modal');
                const title = modal.querySelector('.modal-title');
                title.innerHTML = `
                    <i class="fas fa-edit"></i>
                    Edit Template - <span id="project-setup-name">${data.project.name}</span>
                `;
                
                // Update save button text
                const saveBtn = modal.querySelector('.btn-primary');
                saveBtn.innerHTML = '<i class="fas fa-save"></i> Update Template';
                
                // Show modal
                showProjectSetupModal();
            } else {
                alert('Failed to load project template data');
            }
        })
        .catch(error => {
            console.error('Error loading project template:', error);
            alert('Failed to load project template');
        });
};

// Function to view project template (read-only)
window.viewProjectTemplate = function(projectId) {
    fetch(`/projects/${projectId}/template`)
        .then(response => response.json())
        .then(data => {
            if (data.project && data.template) {
                showProjectTemplatePreview(data.project, data.template);
            } else {
                alert('No template configured for this project');
            }
        })
        .catch(error => {
            console.error('Error loading project template:', error);
            alert('Failed to load project template');
        });
};

// Function to populate form with existing data
function populateProjectSetupForm(template) {
    document.getElementById('agent-name').value = template.agent_name || '';
    document.getElementById('agent-role').value = template.agent_role || '';
    document.getElementById('agent-personality').value = template.agent_personality || '';
    document.getElementById('primary-goal').value = template.primary_goal || '';
    
    // Handle arrays for steps and rules
    const goalSteps = Array.isArray(template.goal_steps) ? template.goal_steps.join('\n') : (template.goal_steps || '');
    document.getElementById('goal-steps').value = goalSteps;
    
    const rulesDo = Array.isArray(template.rules_do) ? template.rules_do.join('\n') : (template.rules_do || '');
    document.getElementById('rules-do').value = rulesDo;
    
    const rulesDont = Array.isArray(template.rules_dont) ? template.rules_dont.join('\n') : (template.rules_dont || '');
    document.getElementById('rules-dont').value = rulesDont;
    
    document.getElementById('context-background').value = template.context_background || '';
    document.getElementById('user-role').value = template.user_role || '';
    document.getElementById('output-format').value = template.output_format || '';
}

// Function to show template preview
function showProjectTemplatePreview(project, template) {
    const previewHtml = `
        <div class="template-preview-modal" onclick="closeTemplatePreview()">
            <div class="template-preview-content" onclick="event.stopPropagation()">
                <div class="template-preview-header">
                    <h3><i class="fas fa-eye"></i> ${project.name} - Template Preview</h3>
                    <button class="btn-close" onclick="closeTemplatePreview()">&times;</button>
                </div>
                <div class="template-preview-body">
                    <div class="template-section">
                        <h4>Generated System Prompt:</h4>
                        <pre class="system-prompt-preview">${generateSystemPromptPreview(template)}</pre>
                    </div>
                    <div class="template-actions">
                        <button class="btn btn-primary" onclick="closeTemplatePreview(); editProjectTemplate('${project.id}')">
                            <i class="fas fa-edit"></i> Edit Template
                        </button>
                        <button class="btn btn-secondary" onclick="closeTemplatePreview()">
                            <i class="fas fa-times"></i> Close
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', previewHtml);
    document.body.classList.add('modal-open');
}

// Function to close template preview
window.closeTemplatePreview = function() {
    const preview = document.querySelector('.template-preview-modal');
    if (preview) {
        preview.remove();
        document.body.classList.remove('modal-open');
    }
};

// Function to generate system prompt preview
function generateSystemPromptPreview(template) {
    let prompt = '';
    
    // Identity & Persona
    if (template.agent_name || template.agent_role || template.agent_personality) {
        prompt += '# IDENTITY & PERSONA\n';
        if (template.agent_name && template.agent_role) {
            const personality = template.agent_personality ? `, ${template.agent_personality}` : '';
            prompt += `You are ${template.agent_name}, a ${template.agent_role}. Your personality is ${template.agent_personality || 'professional'}${personality}.\n`;
        } else if (template.agent_name) {
            prompt += `You are ${template.agent_name}.\n`;
        } else if (template.agent_role) {
            prompt += `You are a ${template.agent_role}.\n`;
        }
        if (template.agent_personality && !(template.agent_name && template.agent_role)) {
            prompt += `Your personality is ${template.agent_personality}.\n`;
        }
        prompt += '\n';
    }
    
    // Task & Goal
    if (template.primary_goal || (template.goal_steps && template.goal_steps.length > 0)) {
        prompt += '# TASK & GOAL\n';
        if (template.primary_goal) {
            prompt += `Your primary goal is to ${template.primary_goal}\n`;
        }
        if (template.goal_steps && template.goal_steps.length > 0) {
            prompt += 'You will accomplish this by following these steps:\n';
            template.goal_steps.forEach((step, i) => {
                prompt += `${i + 1}. ${step}\n`;
            });
        }
        prompt += '\n';
    }
    
    // Rules & Constraints
    if ((template.rules_do && template.rules_do.length > 0) || (template.rules_dont && template.rules_dont.length > 0)) {
        prompt += '# RULES & CONSTRAINTS\n';
        if (template.rules_do && template.rules_do.length > 0) {
            template.rules_do.forEach(rule => {
                prompt += `- DO: ${rule}\n`;
            });
        }
        if (template.rules_dont && template.rules_dont.length > 0) {
            template.rules_dont.forEach(rule => {
                prompt += `- DO NOT: ${rule}\n`;
            });
        }
        prompt += '\n';
    }
    
    // Context
    if (template.context_background || template.user_role) {
        prompt += '# CONTEXT\n';
        if (template.context_background) {
            prompt += `The context for our conversation is ${template.context_background}\n`;
        }
        if (template.user_role) {
            prompt += `I, the user, am a ${template.user_role}.\n`;
        }
        prompt += '\n';
    }
    
    // Output Format
    if (template.output_format) {
        prompt += '# OUTPUT FORMAT\n';
        prompt += `${template.output_format}\n`;
    }
    
    return prompt || 'No template configured';
}
