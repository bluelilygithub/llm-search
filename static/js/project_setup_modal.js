// Project Setup Modal Functions
console.log('🚀 project_setup_modal.js starting to load...');

// Immediate test to verify script loading
window.projectModalScriptLoaded = true;
console.log('✅ project_setup_modal.js script loaded successfully');

window.showProjectSetupModal = function() {
    const modal = document.getElementById('project-setup-modal');
    const projectNameSpan = document.getElementById('project-setup-name');
    const modalTitle = document.getElementById('projectSetupModalLabel');
    
    if (modal && window.app && window.app.pendingProjectName) {
        // Reset modal title for create mode
        modalTitle.innerHTML = '<i class="fas fa-cogs"></i> Project Setup - <span id="project-setup-name"></span>';
        projectNameSpan.textContent = window.app.pendingProjectName;
        
        // Remove edit mode attributes
        modal.removeAttribute('data-project-id');
        
        // Show modal with proper display and classes
        modal.style.display = 'flex';
        modal.classList.add('show');
        document.body.classList.add('modal-open');
        
        // Prevent body scrolling
        document.body.style.overflow = 'hidden';
        
        // Load personas into dropdown
        loadPersonasIntoDropdown();
        
        // Focus on first input
        setTimeout(() => {
            const firstInput = modal.querySelector('input, textarea');
            if (firstInput) firstInput.focus();
        }, 100);
    } else {
        console.error('Modal element not found or no pending project name');
    }
};

window.showProjectEditModal = function(projectId) {
    const modal = document.getElementById('project-setup-modal');
    const projectNameSpan = document.getElementById('project-setup-name');
    const modalTitle = document.getElementById('projectSetupModalLabel');
    
    if (!modal) {
        console.error('Project setup modal not found');
        return;
    }
    
    // Change modal title to indicate edit mode
    modalTitle.innerHTML = '<i class="fas fa-edit"></i> Edit Project - <span id="project-setup-name"></span>';
    projectNameSpan.textContent = 'Loading...';
    
    // Show modal
    modal.style.display = 'flex';
    modal.classList.add('show');
    document.body.classList.add('modal-open');
    document.body.style.overflow = 'hidden';
    
    // Load project data
    fetch(`/api/projects/${projectId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const project = data.project;
                projectNameSpan.textContent = project.name;
                
                // Populate form with existing project data
                populateProjectEditForm(project);
                
                // Load personas into dropdown
                loadPersonasIntoDropdown();
                
                // Store project ID for update
                modal.setAttribute('data-project-id', projectId);
                
                // Set editing project ID on app for save function
                if (window.app) {
                    window.app.editingProjectId = projectId;
                    console.log('✅ Set editingProjectId:', projectId);
                }
                
                // Focus on first input
                setTimeout(() => {
                    const firstInput = modal.querySelector('input, textarea');
                    if (firstInput) firstInput.focus();
                }, 100);
            } else {
                alert('Failed to load project data: ' + (data.error || 'Unknown error'));
                closeProjectSetup();
            }
        })
        .catch(error => {
            console.error('Error loading project:', error);
            alert('Failed to load project data');
            closeProjectSetup();
        });
};

// Test function to verify script loading
window.testProjectModal = function() {
    console.log('✅ testProjectModal function is available');
    return 'Script loaded successfully';
};

function populateProjectEditForm(project) {
    // Populate form fields with actual field IDs from the HTML and correct API response fields
    const agentNameField = document.getElementById('agent-name');
    const agentRoleField = document.getElementById('agent-role');
    const agentPersonalityField = document.getElementById('agent-personality');
    const primaryGoalField = document.getElementById('primary-goal');
    const goalStepsField = document.getElementById('goal-steps');
    const rulesDoField = document.getElementById('rules-do');
    const rulesDontField = document.getElementById('rules-dont');
    const contextBackgroundField = document.getElementById('context-background');
    const outputFormatField = document.getElementById('output-format');
    const userRoleField = document.getElementById('project-user-role');
    
    if (agentNameField) agentNameField.value = project.agent_name || '';
    if (agentRoleField) agentRoleField.value = project.agent_role || '';
    if (agentPersonalityField) agentPersonalityField.value = project.agent_personality || '';
    if (primaryGoalField) primaryGoalField.value = project.primary_goal || '';
    if (goalStepsField) goalStepsField.value = project.goal_steps || '';
    if (rulesDoField) rulesDoField.value = project.rules_do || '';
    if (rulesDontField) rulesDontField.value = project.rules_dont || '';
    if (contextBackgroundField) contextBackgroundField.value = project.context_background || '';
    if (outputFormatField) outputFormatField.value = project.output_format || '';
    if (userRoleField) userRoleField.value = project.user_role || '';
    
    // Handle math-specific fields
    const mathLevelField = document.getElementById('math-level');
    const mathSubjectField = document.getElementById('math-subject');
    const learningStyleField = document.getElementById('learning-style');
    const difficultyPreferenceField = document.getElementById('difficulty-preference');
    
    if (mathLevelField) mathLevelField.value = project.math_level || '';
    if (mathSubjectField) mathSubjectField.value = project.math_subject || '';
    if (learningStyleField) learningStyleField.value = project.learning_style || '';
    if (difficultyPreferenceField) difficultyPreferenceField.value = project.difficulty_preference || '';
    
    // Handle persona selection
    const personaSelectField = document.getElementById('persona-select');
    if (personaSelectField && project.persona_id) {
        personaSelectField.value = project.persona_id;
    }
}

// Function to edit existing project template
window.editProjectTemplate = function(projectId) {
    console.log('✅ editProjectTemplate function called with projectId:', projectId);
    console.log('✅ showProjectEditModal function available:', typeof window.showProjectEditModal);
    
    if (typeof window.showProjectEditModal === 'function') {
        window.showProjectEditModal(projectId);
    } else {
        console.error('❌ showProjectEditModal function not available');
        alert('Project editing functionality is not available. Please refresh the page and try again.');
    }
};

// Debug: Log when the function is defined
console.log('✅ editProjectTemplate function defined:', typeof window.editProjectTemplate);
console.log('✅ project_setup_modal.js loaded successfully');
console.log('✅ Available functions:', Object.keys(window).filter(key => key.includes('Project') || key.includes('Template')));

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

window.saveProjectSetup = async function() {
    console.log('🔄 saveProjectSetup called');
    
    if (!window.app || (!window.app.pendingProjectName && !window.app.editingProjectId)) {
        console.error('No pending project name or editing project ID found');
        console.log('window.app:', window.app);
        console.log('pendingProjectName:', window.app?.pendingProjectName);
        console.log('editingProjectId:', window.app?.editingProjectId);
        return;
    }
    
    // Collect form data
    const projectData = {
        name: window.app.pendingProjectName || document.getElementById('project-setup-name')?.textContent || 'Unnamed Project',
        agent_name: document.getElementById('agent-name').value.trim(),
        agent_role: document.getElementById('agent-role').value.trim(),
        agent_personality: document.getElementById('agent-personality').value.trim(),
        primary_goal: document.getElementById('primary-goal').value.trim(),
        goal_steps: document.getElementById('goal-steps').value.trim(),
        rules_do: document.getElementById('rules-do').value.trim(),
        rules_dont: document.getElementById('rules-dont').value.trim(),
        context_background: document.getElementById('context-background').value.trim(),
        user_role: document.getElementById('project-user-role').value.trim(),
        output_format: document.getElementById('output-format').value.trim(),
        persona_id: document.getElementById('persona-select').value || null,
        // Math-specific fields
        math_level: document.getElementById('math-level').value || null,
        math_subject: document.getElementById('math-subject').value || null,
        learning_style: document.getElementById('learning-style').value || null,
        difficulty_preference: document.getElementById('difficulty-preference').value || null
    };
    
    // Remove empty fields (except for name)
    Object.keys(projectData).forEach(key => {
        if (key !== 'name' && !projectData[key]) {
            delete projectData[key];
        }
    });
    
    const modal = document.getElementById('project-setup-modal');
    const projectId = modal.getAttribute('data-project-id');
    
    if (projectId) {
        // Update existing project
        await updateProjectWithSetup(projectId, projectData);
    } else {
        // Create new project with setup data
        window.app.createProjectWithSetup(projectData);
    }
    
    // Close modal
    closeProjectSetup();
};

async function updateProjectWithSetup(projectId, projectData) {
    console.log('🔄 updateProjectWithSetup called with projectId:', projectId);
    console.log('🔄 projectData:', projectData);
    
    try {
        // Update project profile - use correct field names that match the Project model
        const profileResponse = await fetch(`/projects/${projectId}/profile`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: projectData.name,
                description: projectData.description,
                agent_name: projectData.agent_name,
                agent_role: projectData.agent_role,
                agent_personality: projectData.agent_personality,
                primary_goal: projectData.primary_goal,
                context_background: projectData.context_background,
                user_role: projectData.user_role,
                output_format: projectData.output_format,
                math_level: projectData.math_level,
                math_subject: projectData.math_subject,
                learning_style: projectData.learning_style,
                difficulty_preference: projectData.difficulty_preference,
                persona_id: projectData.persona_id
            })
        });
        
        if (!profileResponse.ok) {
            throw new Error('Failed to update project profile');
        }
        
        // Update project template
        const templateResponse = await fetch(`/projects/${projectId}/template`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                goal_steps: projectData.goal_steps,
                rules_do: projectData.rules_do,
                rules_dont: projectData.rules_dont
            })
        });
        
        if (!templateResponse.ok) {
            throw new Error('Failed to update project template');
        }
        
        // Show success message
        if (window.app && window.app.showNotification) {
            window.app.showNotification('Project updated successfully!', 'success');
        }
        
        // Refresh projects list if visible
        if (window.app && window.app.loadProjectsGrid) {
            window.app.loadProjectsGrid();
        }
        
    } catch (error) {
        console.error('Error updating project:', error);
        if (window.app && window.app.showNotification) {
            window.app.showNotification('Failed to update project: ' + error.message, 'error');
        }
    }
}

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
        
        // Make the newly created project active immediately
        this.currentProject = project;
        this.currentViewProject = project;
        this.updateProjectSelectionUI(project);
        
        // If currently viewing projects page, refresh the main content area too
        if (this.currentView === 'projects') {
            await this.loadProjectsGrid();
        }
        
        // Show success notification with option to start chatting
        const hasTemplate = project.template && (project.template.agent_name || project.template.primary_goal);
        const message = hasTemplate 
            ? `Project "${project.name}" created with custom template! Ready to start chatting.`
            : `Project "${project.name}" created successfully! Ready to start chatting.`;
        this.showSuccessNotification(message);
        
        // Automatically switch to chat view to encourage immediate usage
        setTimeout(() => {
            this.showChatView();
            this.startNewChat();
        }, 1000); // Small delay to let user see the success message
        
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

// Function to view project template (read-only)
window.viewProjectTemplate = function(projectId) {
    console.log('viewProjectTemplate called with:', projectId);
    
    fetch(`/projects/${projectId}/template`)
        .then(response => {
            console.log('View template response:', response);
            return response.json();
        })
        .then(data => {
            console.log('View template data:', data);
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
    document.getElementById('project-user-role').value = template.user_role || '';
    document.getElementById('output-format').value = template.output_format || '';
    
    // Set persona dropdown if persona_id exists
    if (template.persona_id) {
        document.getElementById('persona-select').value = template.persona_id;
    }
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

// ==================== PERSONA INTEGRATION FUNCTIONS ====================

// Load personas into the dropdown
async function loadPersonasIntoDropdown() {
    const dropdown = document.getElementById('persona-select');
    if (!dropdown) return;
    
    try {
        const response = await fetch('/api/personas');
        const data = await response.json();
        
        if (data.success) {
            // Clear existing options except the first one
            dropdown.innerHTML = '<option value="">Select a persona or create custom...</option>';
            
            // Group personas by category
            const personasByCategory = {};
            data.personas.forEach(persona => {
                if (!personasByCategory[persona.category]) {
                    personasByCategory[persona.category] = [];
                }
                personasByCategory[persona.category].push(persona);
            });
            
            // Add personas grouped by category
            Object.keys(personasByCategory).sort().forEach(category => {
                const optgroup = document.createElement('optgroup');
                optgroup.label = category;
                
                personasByCategory[category].forEach(persona => {
                    const option = document.createElement('option');
                    option.value = persona.id;
                    option.textContent = `${persona.name} (${persona.agent_name})`;
                    optgroup.appendChild(option);
                });
                
                dropdown.appendChild(optgroup);
            });
        }
    } catch (error) {
        console.error('Error loading personas:', error);
    }
}

// Handle persona selection and populate fields
window.loadPersonaData = function() {
    const dropdown = document.getElementById('persona-select');
    const selectedPersonaId = dropdown.value;
    
    if (!selectedPersonaId) {
        // Clear fields if no persona selected
        clearPersonaFields();
        return;
    }
    
    // Find the selected persona from the dropdown options
    const selectedOption = dropdown.querySelector(`option[value="${selectedPersonaId}"]`);
    if (!selectedOption) return;
    
    // Extract persona name and agent name from option text
    const optionText = selectedOption.textContent;
    const match = optionText.match(/^(.+?) \((.+?)\)$/);
    
    if (match) {
        const personaName = match[1];
        const agentName = match[2];
        
        // Populate the fields with basic info
        document.getElementById('agent-name').value = agentName;
        
        // Fetch full persona data to get role and traits
        fetch(`/api/personas/${selectedPersonaId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const persona = data.persona;
                    document.getElementById('agent-name').value = persona.agent_name;
                    document.getElementById('agent-role').value = persona.role;
                    document.getElementById('agent-personality').value = persona.traits;
                }
            })
            .catch(error => {
                console.error('Error loading persona details:', error);
                // Fallback to basic info
                document.getElementById('agent-name').value = agentName;
            });
    }
};

// Clear persona fields
function clearPersonaFields() {
    document.getElementById('agent-name').value = '';
    document.getElementById('agent-role').value = '';
    document.getElementById('agent-personality').value = '';
}
