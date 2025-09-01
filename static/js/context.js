// Context Management Module
// Handles context panel, context items, and conversation context

class ContextManager {
    constructor(app) {
        this.app = app;
        this.contextPanelOpen = false;
        this.contextItems = [];
        this.conversationContext = [];
        this.contextStats = { total_items: 0, total_tokens: 0 };
        this.documentContentMap = new Map();
    }

    // Toggle context panel visibility
    toggleContextPanel() {
        const panel = document.getElementById('context-panel');
        const toggleBtn = document.getElementById('context-toggle-btn');
        
        if (this.contextPanelOpen) {
            panel.style.display = 'none';
            toggleBtn.classList.remove('active');
            this.contextPanelOpen = false;
        } else {
            panel.style.display = 'flex';
            toggleBtn.classList.add('active');
            this.contextPanelOpen = true;
            this.loadContextData();
        }
    }

    // Load all context data
    async loadContextData() {
        try {
            // Load user context items
            await this.loadContextItems();
            
            // Load context stats
            await this.loadContextStats();
            
            // Load conversation context if we have a current conversation
            if (this.app.currentConversationId) {
                await this.loadConversationContext();
            }
            
        } catch (error) {
            console.error('Error loading context data:', error);
            this.app.showErrorNotification('Failed to load context data');
        }
    }

    // Load user context items
    async loadContextItems() {
        try {
            const response = await fetch('/api/context');
            const data = await response.json();
            
            if (data.success) {
                this.contextItems = data.items;
                this.renderContextItems();
            } else {
                throw new Error(data.error || 'Failed to load context items');
            }
        } catch (error) {
            console.error('Error loading context items:', error);
            document.getElementById('context-items-list').innerHTML = 
                '<div class="empty-context">Failed to load context items</div>';
        }
    }

    // Load context statistics
    async loadContextStats() {
        try {
            const response = await fetch('/api/context/stats');
            const data = await response.json();
            
            if (data.success) {
                this.contextStats = data.stats;
                this.renderContextStats();
            }
        } catch (error) {
            console.error('Error loading context stats:', error);
        }
    }

    // Load conversation context
    async loadConversationContext() {
        if (!this.app.currentConversationId) return;
        
        try {
            const response = await fetch(`/api/conversation/${this.app.currentConversationId}/context`);
            const data = await response.json();
            
            if (data.success) {
                this.conversationContext = data.context;
                this.renderConversationContext();
                
                // Show conversation context section
                const section = document.getElementById('context-conversation-section');
                section.style.display = data.context.length > 0 ? 'block' : 'none';
            }
        } catch (error) {
            console.error('Error loading conversation context:', error);
        }
    }

    // Render context items list
    renderContextItems() {
        const container = document.getElementById('context-items-list');
        
        if (this.contextItems.length === 0) {
            container.innerHTML = '<div class="empty-context">No context items found. Add some context to get started!</div>';
            return;
        }
        
        const contextInConversation = new Set(this.conversationContext.map(c => c.item_id));
        
        container.innerHTML = this.contextItems.map(item => `
            <div class="context-item-card ${contextInConversation.has(item.id) ? 'in-conversation' : ''}"
                 onclick="window.app.contextManager.showContextItemDetails('${item.id}')">
                <div class="context-item-header">
                    <div class="context-item-name">${item.name}</div>
                    <div class="context-item-type">${item.content_type}</div>
                    ${item.project_name ? `<div class="context-item-project">📁 ${item.project_name}</div>` : ''}
                </div>
                ${item.description ? `<div class="context-item-description">${item.description}</div>` : ''}
                <div class="context-item-meta">
                    <div class="context-item-tokens">${item.token_count} tokens</div>
                    <div class="context-item-actions">
                        ${contextInConversation.has(item.id) 
                            ? `<button class="context-item-action remove" onclick="event.stopPropagation(); window.app.contextManager.removeContextFromConversation('${item.id}')" title="Remove from conversation">
                                 <i class="fas fa-minus-circle"></i>
                               </button>`
                            : `<button class="context-item-action add" onclick="event.stopPropagation(); window.app.contextManager.addContextToConversation('${item.id}')" title="Add to conversation">
                                 <i class="fas fa-plus-circle"></i>
                               </button>`
                        }
                        <button class="context-item-action" onclick="event.stopPropagation(); window.app.contextManager.editContextItem('${item.id}')" title="Edit">
                            <i class="fas fa-edit"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
        
        // Update section counts
        this.updateSectionCounts();
    }

    // Render conversation context
    renderConversationContext() {
        const container = document.getElementById('conversation-context-list');
        
        if (this.conversationContext.length === 0) {
            container.innerHTML = '<div class="empty-context">No context items added to this conversation yet.</div>';
            return;
        }
        
        container.innerHTML = this.conversationContext.map(context => `
            <div class="context-item-card in-conversation">
                <div class="context-item-header">
                    <div class="context-item-name">${context.name}</div>
                    <div class="context-item-type">${context.content_type}</div>
                </div>
                ${context.description ? `<div class="context-item-description">${context.description}</div>` : ''}
                <div class="context-item-meta">
                    <div class="context-item-tokens">${context.token_count} tokens</div>
                    <div class="context-item-actions">
                        <button class="context-item-action remove" onclick="window.app.contextManager.removeContextFromConversation('${context.item_id}')" title="Remove from conversation">
                            <i class="fas fa-minus-circle"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
        
        // Update conversation context count
        this.updateSectionCounts();
    }

    // Render context stats
    renderContextStats() {
        document.getElementById('total-context-items').textContent = this.contextStats.total_items || 0;
        document.getElementById('total-context-tokens').textContent = this.contextStats.total_tokens || 0;
        
        // Update section counts
        this.updateSectionCounts();
    }

    // Update section counts
    updateSectionCounts() {
        const conversationCount = document.getElementById('conversation-context-count');
        const availableCount = document.getElementById('available-context-count');
        
        if (conversationCount) {
            conversationCount.textContent = `${this.conversationContext.length} item${this.conversationContext.length !== 1 ? 's' : ''}`;
        }
        
        if (availableCount) {
            availableCount.textContent = `${this.contextItems.length} item${this.contextItems.length !== 1 ? 's' : ''}`;
        }
    }

    // Render filtered context items (used by search)
    renderFilteredContextItems(filteredItems, searchTerm) {
        const container = document.getElementById('context-items-list');
        
        if (filteredItems.length === 0) {
            container.innerHTML = `<div class="empty-context">No context items found for "${searchTerm}"</div>`;
            return;
        }
        
        const contextInConversation = new Set(this.conversationContext.map(c => c.item_id));
        
        // Use same rendering logic but with filtered items
        container.innerHTML = filteredItems.map(item => `
            <div class="context-item-card ${contextInConversation.has(item.id) ? 'in-conversation' : ''}"
                 onclick="window.app.contextManager.showContextItemDetails('${item.id}')">
                <div class="context-item-header">
                    <div class="context-item-name">${this.highlightSearchTerm(item.name, searchTerm)}</div>
                    <div class="context-item-type">${item.content_type}</div>
                    ${item.project_name ? `<div class="context-item-project">📁 ${item.project_name}</div>` : ''}
                </div>
                ${item.description ? `<div class="context-item-description">${this.highlightSearchTerm(item.description, searchTerm)}</div>` : ''}
                <div class="context-item-meta">
                    <div class="context-item-tokens">${item.token_count} tokens</div>
                    <div class="context-item-actions">
                        ${contextInConversation.has(item.id) 
                            ? `<button class="context-item-action remove" onclick="event.stopPropagation(); window.app.contextManager.removeContextFromConversation('${item.id}')" title="Remove from conversation">
                                 <i class="fas fa-minus-circle"></i>
                               </button>`
                            : `<button class="context-item-action add" onclick="event.stopPropagation(); window.app.contextManager.addContextToConversation('${item.id}')" title="Add to conversation">
                                 <i class="fas fa-plus-circle"></i>
                               </button>`
                        }
                        <button class="context-item-action" onclick="event.stopPropagation(); window.app.contextManager.editContextItem('${item.id}')" title="Edit">
                            <i class="fas fa-edit"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
        
        // Update section counts for filtered results
        this.updateSectionCounts();
    }

    // Search through context content using API
    async searchContextContentAPI(searchTerm) {
        try {
            const response = await fetch(`/api/context/suggestions?query=${encodeURIComponent(searchTerm)}&limit=10`);
            const data = await response.json();
            
            if (data.success && data.suggestions.length > 0) {
                // Show API search results with content matching
                this.renderContentSearchResults(data.suggestions, searchTerm);
            } else {
                // Show no results message
                document.getElementById('context-items-list').innerHTML = 
                    `<div class="empty-context">No context items found for "${searchTerm}"</div>`;
            }
        } catch (error) {
            console.error('Content search error:', error);
            document.getElementById('context-items-list').innerHTML = 
                '<div class="empty-context">Search failed. Please try again.</div>';
        }
    }

    // Render content search results
    renderContentSearchResults(suggestions, searchTerm) {
        const container = document.getElementById('context-items-list');
        const contextInConversation = new Set(this.conversationContext.map(c => c.item_id));
        
        container.innerHTML = suggestions.map(item => `
            <div class="context-item-card ${contextInConversation.has(item.item_id) ? 'in-conversation' : ''}"
                 onclick="window.app.contextManager.showContextItemDetails('${item.item_id}')">
                <div class="context-item-header">
                    <div class="context-item-name">${this.highlightSearchTerm(item.name, searchTerm)}</div>
                    <div class="context-item-type">${item.content_type}</div>
                </div>
                ${item.description ? `<div class="context-item-description">${this.highlightSearchTerm(item.description, searchTerm)}</div>` : ''}
                <div class="search-relevance" style="font-size: 11px; color: #2563eb; margin: 4px 0;">
                    Relevance: ${Math.round(item.relevance_score * 100) / 100} | Used: ${item.usage_count} times
                </div>
                <div class="context-item-meta">
                    <div class="context-item-tokens">${item.token_count} tokens</div>
                    <div class="context-item-actions">
                        ${contextInConversation.has(item.item_id) 
                            ? `<button class="context-item-action remove" onclick="event.stopPropagation(); window.app.contextManager.removeContextFromConversation('${item.item_id}')" title="Remove from conversation">
                                 <i class="fas fa-minus-circle"></i>
                               </button>`
                            : `<button class="context-item-action add" onclick="event.stopPropagation(); window.app.contextManager.addContextToConversation('${item.item_id}')" title="Add to conversation">
                                 <i class="fas fa-plus-circle"></i>
                               </button>`
                        }
                        <button class="context-item-action" onclick="event.stopPropagation(); window.app.contextManager.editContextItem('${item.item_id}')" title="Edit">
                            <i class="fas fa-edit"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
        
        // Update section counts for search results
        this.updateSectionCounts();
    }

    // Highlight search terms in text
    highlightSearchTerm(text, searchTerm) {
        if (!text || !searchTerm) return text || '';
        
        const regex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        return text.replace(regex, '<mark style="background: #fff3cd; padding: 1px 2px; border-radius: 2px;">$1</mark>');
    }

    // Escape HTML to prevent XSS
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Add context item to conversation
    async addContextToConversation(contextItemId) {
        if (!this.app.currentConversationId) {
            this.app.showErrorNotification('Please start a conversation first');
            return;
        }
        
        try {
            const response = await fetch(`/api/conversation/${this.app.currentConversationId}/context/${contextItemId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ relevance_score: 1.0 })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Reload context data to update UI
                await this.loadConversationContext();
                this.renderContextItems(); // Re-render to update button states
                
                this.app.showSuccessNotification('Context added to conversation');
            } else {
                throw new Error(data.error || 'Failed to add context');
            }
        } catch (error) {
            console.error('Error adding context to conversation:', error);
            this.app.showErrorNotification('Failed to add context to conversation');
        }
    }

    // Remove context item from conversation
    async removeContextFromConversation(contextItemId) {
        if (!this.app.currentConversationId) return;
        
        try {
            const response = await fetch(`/api/conversation/${this.app.currentConversationId}/context/${contextItemId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Reload context data to update UI
                await this.loadConversationContext();
                this.renderContextItems(); // Re-render to update button states
                
                this.app.showSuccessNotification('Context removed from conversation');
            } else {
                throw new Error(data.error || 'Failed to remove context');
            }
        } catch (error) {
            console.error('Error removing context from conversation:', error);
            this.app.showErrorNotification('Failed to remove context from conversation');
        }
    }

    // Show context item details (placeholder)
    showContextItemDetails(contextItemId) {
        // This will be implemented in later increments
    }

    // Edit context item
    editContextItem(contextItemId) {
        // Find the context item to edit
        const contextItem = this.contextItems.find(item => item.id === contextItemId);
        if (!contextItem) {
            console.error('Context item not found:', contextItemId);
            return;
        }
        
        // Create modal for editing context
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content context-modal">
                <div class="modal-header">
                    <h3><i class="fas fa-edit"></i> Edit Context Item</h3>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <form id="edit-context-form">
                        <div class="form-group">
                            <label for="edit-context-name">Context Name *</label>
                            <input type="text" id="edit-context-name" name="name" required 
                                   value="${this.escapeHtml(contextItem.name)}"
                                   placeholder="Enter a descriptive name for this context">
                        </div>
                        
                        <div class="form-group">
                            <label for="edit-context-description">Description</label>
                            <textarea id="edit-context-description" name="description" rows="3"
                                      placeholder="Describe what this context contains or its purpose">${this.escapeHtml(contextItem.description || '')}</textarea>
                        </div>
                        
                        <div class="form-group">
                            <label for="edit-context-type">Content Type *</label>
                            <select id="edit-context-type" name="content_type" required>
                                <option value="document" ${contextItem.content_type === 'document' ? 'selected' : ''}>Document</option>
                                <option value="instructions" ${contextItem.content_type === 'instructions' ? 'selected' : ''}>Instructions</option>
                                <option value="notes" ${contextItem.content_type === 'notes' ? 'selected' : ''}>Notes</option>
                                <option value="reference" ${contextItem.content_type === 'reference' ? 'selected' : ''}>Reference</option>
                                <option value="template" ${contextItem.content_type === 'template' ? 'selected' : ''}>Template</option>
                                <option value="other" ${contextItem.content_type === 'other' ? 'selected' : ''}>Other</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label for="edit-context-content">Content Text *</label>
                            <textarea id="edit-context-content" name="content_text" rows="6" required
                                      placeholder="Enter the actual content or text for this context item">${this.escapeHtml(contextItem.content_text || '')}</textarea>
                            <div class="form-help">This text will be used for AI context and search</div>
                        </div>
                        
                        <div class="form-group">
                            <label for="edit-context-project">Associate with Project (Optional)</label>
                            <select id="edit-context-project" name="project_id">
                                <option value="">No project association</option>
                                ${this.app.projects ? this.app.projects.map(p => 
                                    `<option value="${p.id}" ${contextItem.project_id === p.id ? 'selected' : ''}>${p.name}</option>`
                                ).join('') : ''}
                            </select>
                        </div>
                        
                        <input type="hidden" name="context_id" value="${contextItemId}">
                    </form>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                    <button class="btn btn-primary" onclick="window.app.contextManager.submitEditContext()">Update Context</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Focus on first input
        setTimeout(() => {
            document.getElementById('edit-context-name').focus();
        }, 100);
    }

    // Submit edit context form
    async submitEditContext() {
        const form = document.getElementById('edit-context-form');
        const formData = new FormData(form);
        
        // Validate required fields
        const name = formData.get('name').trim();
        const contentType = formData.get('content_type');
        const contentText = formData.get('content_text').trim();
        const contextId = formData.get('context_id');
        
        if (!name || !contentType || !contentText || !contextId) {
            await window.modalManager.warning('Please fill in all required fields');
            return;
        }
        
        // Prepare data for API
        const contextData = {
            name: name,
            description: formData.get('description').trim() || null,
            content_type: contentType,
            content_text: contentText,
            project_id: formData.get('project_id') || null
        };
        
        // Show loading state
        const submitBtn = document.querySelector('.context-modal .btn-primary');
        const originalText = submitBtn.textContent;
        submitBtn.textContent = 'Updating...';
        submitBtn.disabled = true;
        
        try {
            // Call API to update context item
            const response = await fetch(`/api/context/${contextId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(contextData)
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Close modal
                document.querySelector('.modal-overlay').remove();
                
                // Refresh context panel
                if (this.contextPanelOpen) {
                    this.loadContextData();
                }
                
                // Show success message
                this.app.showNotification('Context item updated successfully!', 'success');
            } else {
                throw new Error(data.error || 'Failed to update context item');
            }
        } catch (error) {
            console.error('Error updating context item:', error);
            await window.modalManager.error('Error updating context item: ' + error.message);
        } finally {
            // Reset button
            submitBtn.textContent = originalText;
            submitBtn.disabled = false;
        }
    }

    // Search context items through content
    searchContextItems() {
        const searchTerm = document.getElementById('context-search').value.trim();
        const clearBtn = document.getElementById('search-clear-btn');
        
        // Show/hide clear button based on search content
        if (searchTerm) {
            clearBtn.style.display = 'block';
        } else {
            clearBtn.style.display = 'none';
            // If empty search, show all items
            this.renderContextItems();
            return;
        }
        
        // Filter context items based on search term
        const filteredItems = this.contextItems.filter(item => {
            const searchLower = searchTerm.toLowerCase();
            
            // Search through multiple fields
            const name = (item.name || '').toLowerCase();
            const description = (item.description || '').toLowerCase();
            const contentType = (item.content_type || '').toLowerCase();
            const filename = (item.original_filename || '').toLowerCase();
            
            // Basic text matching
            if (name.includes(searchLower) || 
                description.includes(searchLower) || 
                contentType.includes(searchLower) || 
                filename.includes(searchLower)) {
                return true;
            }
            
            return false;
        });
        
        // If no items match basic fields, search through content text
        if (filteredItems.length === 0 && searchTerm.length >= 3) {
            this.searchContextContentAPI(searchTerm);
        } else {
            // Render filtered results
            this.renderFilteredContextItems(filteredItems, searchTerm);
        }
    }

    // Clear context search and show all items
    clearContextSearch() {
        const searchInput = document.getElementById('context-search');
        const clearBtn = document.getElementById('search-clear-btn');
        
        searchInput.value = '';
        clearBtn.style.display = 'none';
        
        // Show all context items
        this.renderContextItems();
        
        // Focus back to search input
        searchInput.focus();
    }

    // Refresh context panel
    refreshContextPanel() {
        if (this.contextPanelOpen) {
            this.loadContextData();
        }
    }

    // Add new context
    addNewContext() {
        // Create modal for adding new context
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content context-modal">
                <div class="modal-header">
                    <h3><i class="fas fa-plus"></i> Add New Context</h3>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <form id="new-context-form">
                        <div class="form-group">
                            <label for="context-name">Context Name *</label>
                            <input type="text" id="context-name" name="name" required 
                                   placeholder="Enter a descriptive name for this context">
                        </div>
                        
                        <div class="form-group">
                            <label for="context-description">Description</label>
                            <textarea id="context-description" name="description" rows="3"
                                      placeholder="Describe what this context contains or its purpose"></textarea>
                        </div>
                        
                        <div class="form-group">
                            <label for="context-type">Content Type *</label>
                            <select id="context-type" name="content_type" required>
                                <option value="">Select content type</option>
                                <option value="document">Document</option>
                                <option value="instructions">Instructions</option>
                                <option value="notes">Notes</option>
                                <option value="reference">Reference</option>
                                <option value="template">Template</option>
                                <option value="other">Other</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label for="context-content">Content Text *</label>
                            <textarea id="context-content" name="content_text" rows="6" required
                                      placeholder="Enter the actual content or text for this context item"></textarea>
                            <div class="form-help">This text will be used for AI context and search</div>
                        </div>
                        
                        <div class="form-group">
                            <label for="context-project">Associate with Project (Optional)</label>
                            <select id="context-project" name="project_id">
                                <option value="">No project association</option>
                                ${this.app.projects ? this.app.projects.map(p => 
                                    `<option value="${p.id}">${p.name}</option>`
                                ).join('') : ''}
                            </select>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                    <button class="btn btn-primary" onclick="window.app.contextManager.submitNewContext()">Create Context</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Focus on first input
        setTimeout(() => {
            document.getElementById('context-name').focus();
        }, 100);
    }

    // Submit new context form
    async submitNewContext() {
        const form = document.getElementById('new-context-form');
        const formData = new FormData(form);
        
        // Validate required fields
        const name = formData.get('name').trim();
        const contentType = formData.get('content_type');
        const contentText = formData.get('content_text').trim();
        
        if (!name || !contentType || !contentText) {
            await window.modalManager.warning('Please fill in all required fields');
            return;
        }
        
        // Prepare data for API
        const contextData = {
            name: name,
            description: formData.get('description').trim() || null,
            content_type: contentType,
            content_text: contentText,
            project_id: formData.get('project_id') || null
        };
        
        // Show loading state
        const submitBtn = document.querySelector('.context-modal .btn-primary');
        const originalText = submitBtn.textContent;
        submitBtn.textContent = 'Creating...';
        submitBtn.disabled = true;
        
        try {
            // Call API to create context item
            const response = await fetch('/api/context', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(contextData)
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Close modal
                document.querySelector('.modal-overlay').remove();
                
                // Refresh context panel
                if (this.contextPanelOpen) {
                    this.loadContextData();
                }
                
                // Show success message
                this.app.showNotification('Context item created successfully!', 'success');
            } else {
                throw new Error(data.error || 'Failed to create context item');
            }
        } catch (error) {
            console.error('Error creating context item:', error);
            await window.modalManager.error('Error creating context item: ' + error.message);
        } finally {
            // Reset button
            submitBtn.textContent = originalText;
            submitBtn.disabled = false;
        }
    }

    // Update conversation context when conversation changes
    updateConversationContext() {
        if (this.contextPanelOpen) {
            setTimeout(() => {
                this.loadConversationContext();
            }, 100);
        }
    }
}

// Export for use in main app
window.ContextManager = ContextManager;
