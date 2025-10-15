# Template Management Enhancement Plan

## 🎯 Goal
Create a comprehensive template management system that allows users to:
- View all templates
- Edit existing templates
- Create new templates
- Delete unused templates
- Import/export template collections
- Share templates with other users

## 📋 Implementation Steps

### Phase 1: Database Schema
```sql
-- Add to models.py
class Template(db.Model):
    __tablename__ = 'templates'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.String(255), nullable=False)  # For user-specific templates
    name = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    default_model = db.Column(db.String(100))
    description = db.Column(db.Text)
    usage_count = db.Column(db.Integer, default=0)
    is_public = db.Column(db.Boolean, default=False)  # For sharing
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Phase 2: API Endpoints
```python
# Add to app.py
@app.route('/api/templates', methods=['GET', 'POST'])
def templates():
    if request.method == 'GET':
        # Return user's templates + public templates
        pass
    elif request.method == 'POST':
        # Create new template
        pass

@app.route('/api/templates/<template_id>', methods=['PUT', 'DELETE'])
def template_detail(template_id):
    if request.method == 'PUT':
        # Update template
        pass
    elif request.method == 'DELETE':
        # Delete template
        pass
```

### Phase 3: Admin Interface
Add to `templates/modals/settings.html`:

```html
<!-- New tab in settings modal -->
<div class="settings-tab" id="templates-tab">
    <h3>Template Management</h3>
    
    <div class="template-actions">
        <button onclick="createNewTemplate()">+ New Template</button>
        <button onclick="importTemplates()">Import</button>
        <button onclick="exportTemplates()">Export</button>
    </div>
    
    <div class="templates-list" id="admin-templates-list">
        <!-- Dynamic template list -->
    </div>
</div>
```

### Phase 4: Dynamic Template Loading
Update `app.js` to load templates from API:

```javascript
// Replace TEMPLATE_DATA with API call
KnowledgeBaseApp.prototype.loadTemplates = async function() {
    try {
        const response = await fetch('/api/templates');
        this.templates = await response.json();
        this.renderTemplateCards();
    } catch (error) {
        console.error('Failed to load templates:', error);
        // Fallback to hardcoded templates
        this.templates = TEMPLATE_DATA;
    }
};

KnowledgeBaseApp.prototype.renderTemplateCards = function() {
    const grid = document.getElementById('template-grid');
    grid.innerHTML = '';
    
    Object.entries(this.templates).forEach(([id, template]) => {
        const card = this.createTemplateCard(id, template);
        grid.appendChild(card);
    });
};
```

## 🎨 UI Enhancements

### Template Editor Modal
```html
<div class="template-editor-modal" id="template-editor">
    <div class="editor-header">
        <h3>Edit Template</h3>
        <button onclick="closeTemplateEditor()">×</button>
    </div>
    
    <div class="editor-body">
        <div class="form-group">
            <label>Template Name</label>
            <input type="text" id="template-name" placeholder="e.g., Email Template">
        </div>
        
        <div class="form-group">
            <label>Category</label>
            <select id="template-category">
                <option value="writing">Writing</option>
                <option value="code">Code</option>
                <option value="research">Research</option>
                <option value="creative">Creative</option>
            </select>
        </div>
        
        <div class="form-group">
            <label>Default Model</label>
            <select id="template-model">
                <option value="gpt-4">GPT-4</option>
                <option value="claude-3.5-sonnet">Claude 3.5 Sonnet</option>
                <!-- etc -->
            </select>
        </div>
        
        <div class="form-group">
            <label>Template Content</label>
            <textarea id="template-content" rows="10" placeholder="Enter your template with {{placeholders}}..."></textarea>
            <small>Use {{placeholder}} syntax for variables</small>
        </div>
    </div>
    
    <div class="editor-footer">
        <button onclick="saveTemplate()">Save Template</button>
        <button onclick="testTemplate()">Test Template</button>
    </div>
</div>
```

## 🔧 Quick Implementation (Minimal)

For immediate template management without database changes:

### 1. Add Template Management to Settings
```javascript
// Add to settings modal
KnowledgeBaseApp.prototype.openTemplateManager = function() {
    const modal = document.getElementById('template-manager-modal');
    modal.style.display = 'flex';
    this.loadTemplateManager();
};

KnowledgeBaseApp.prototype.loadTemplateManager = function() {
    const container = document.getElementById('template-manager-list');
    container.innerHTML = '';
    
    Object.entries(TEMPLATE_DATA).forEach(([id, template]) => {
        const item = document.createElement('div');
        item.className = 'template-manager-item';
        item.innerHTML = `
            <div class="template-info">
                <h4>${template.name}</h4>
                <p>${template.content.substring(0, 100)}...</p>
            </div>
            <div class="template-actions">
                <button onclick="editTemplate('${id}')">Edit</button>
                <button onclick="duplicateTemplate('${id}')">Duplicate</button>
                <button onclick="deleteTemplate('${id}')">Delete</button>
            </div>
        `;
        container.appendChild(item);
    });
};
```

### 2. Template Editor Functions
```javascript
KnowledgeBaseApp.prototype.editTemplate = function(templateId) {
    const template = TEMPLATE_DATA[templateId];
    if (!template) return;
    
    // Populate editor form
    document.getElementById('edit-template-id').value = templateId;
    document.getElementById('edit-template-name').value = template.name;
    document.getElementById('edit-template-content').value = template.content;
    document.getElementById('edit-template-category').value = template.category;
    document.getElementById('edit-template-model').value = template.defaultModel;
    
    // Show editor modal
    document.getElementById('template-editor-modal').style.display = 'flex';
};

KnowledgeBaseApp.prototype.saveTemplate = function() {
    const id = document.getElementById('edit-template-id').value;
    const name = document.getElementById('edit-template-name').value;
    const content = document.getElementById('edit-template-content').value;
    const category = document.getElementById('edit-template-category').value;
    const model = document.getElementById('edit-template-model').value;
    
    // Update TEMPLATE_DATA
    TEMPLATE_DATA[id] = { name, content, category, defaultModel: model };
    
    // Refresh template picker
    this.refreshTemplatePicker();
    
    // Close editor
    document.getElementById('template-editor-modal').style.display = 'none';
    
    // Show success message
    this.showNotification('Template saved successfully!', 'success');
};
```

## 🎯 Next Steps

1. **Immediate**: Add template management to existing settings modal
2. **Short-term**: Create template editor with save/load to localStorage
3. **Long-term**: Database-driven templates with user management and sharing

Would you like me to implement any of these approaches?
