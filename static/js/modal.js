/**
 * Modern Modal System
 * Replaces basic JavaScript alert, confirm, and prompt dialogs
 */
class ModalManager {
    constructor() {
        this.activeModal = null;
        this.modalStack = [];
        this.init();
    }

    init() {
        // Create modal container if it doesn't exist
        if (!document.getElementById('modal-container')) {
            const container = document.createElement('div');
            container.id = 'modal-container';
            container.className = 'modal-container';
            document.body.appendChild(container);
        }

        // Add global styles
        this.addStyles();
    }

    addStyles() {
        if (document.getElementById('modal-styles')) return;

        const style = document.createElement('style');
        style.id = 'modal-styles';
        style.textContent = `
            .modal-container {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: 9999;
                display: none;
                align-items: center;
                justify-content: center;
                background: rgba(0, 0, 0, 0.5);
                backdrop-filter: blur(4px);
                padding: 20px;
                box-sizing: border-box;
            }

            .modal-container.show {
                display: flex;
            }

            .modal {
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
                max-width: 500px;
                width: 100%;
                max-height: calc(100vh - 40px);
                overflow: hidden;
                animation: modalSlideIn 0.3s ease-out;
                margin: auto;
            }

            @keyframes modalSlideIn {
                from {
                    opacity: 0;
                    transform: scale(0.9) translateY(-20px);
                }
                to {
                    opacity: 1;
                    transform: scale(1) translateY(0);
                }
            }

            .modal-header {
                padding: 20px 24px 0;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }

            .modal-title {
                font-size: 18px;
                font-weight: 600;
                color: #1f2937;
                margin: 0;
            }

            .modal-close {
                background: none;
                border: none;
                font-size: 20px;
                color: #6b7280;
                cursor: pointer;
                padding: 4px;
                border-radius: 4px;
                transition: all 0.2s;
            }

            .modal-close:hover {
                background: #f3f4f6;
                color: #374151;
            }

            .modal-body {
                padding: 16px 24px 20px;
            }

            .modal-message {
                color: #374151;
                line-height: 1.6;
                margin-bottom: 16px;
            }

            .modal-input {
                width: 100%;
                padding: 12px 16px;
                border: 2px solid #e5e7eb;
                border-radius: 8px;
                font-size: 14px;
                transition: border-color 0.2s;
                box-sizing: border-box;
            }

            .modal-input:focus {
                outline: none;
                border-color: #3b82f6;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
            }

            .modal-footer {
                padding: 0 24px 20px;
                display: flex;
                gap: 12px;
                justify-content: flex-end;
            }

            .modal-btn {
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s;
                min-width: 80px;
            }

            .modal-btn-primary {
                background: #3b82f6;
                color: white;
            }

            .modal-btn-primary:hover {
                background: #2563eb;
            }

            .modal-btn-secondary {
                background: #f3f4f6;
                color: #374151;
            }

            .modal-btn-secondary:hover {
                background: #e5e7eb;
            }

            .modal-btn-danger {
                background: #ef4444;
                color: white;
            }

            .modal-btn-danger:hover {
                background: #dc2626;
            }

            .modal-icon {
                margin-right: 8px;
            }

            .modal-error {
                border-left: 4px solid #ef4444;
                background: #fef2f2;
                padding: 12px 16px;
                margin-bottom: 16px;
                border-radius: 0 8px 8px 0;
            }

            .modal-success {
                border-left: 4px solid #10b981;
                background: #f0fdf4;
                padding: 12px 16px;
                margin-bottom: 16px;
                border-radius: 0 8px 8px 0;
            }

            .modal-warning {
                border-left: 4px solid #f59e0b;
                background: #fffbeb;
                padding: 12px 16px;
                margin-bottom: 16px;
                border-radius: 0 8px 8px 0;
            }
        `;
        document.head.appendChild(style);
    }

    show(modalConfig) {
        return new Promise((resolve) => {
            const modal = this.createModal(modalConfig, resolve);
            this.modalStack.push(modal);
            this.showModal(modal);
        });
    }

    createModal(config, resolve) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        
        const icon = config.icon || this.getDefaultIcon(config.type);
        const title = config.title || this.getDefaultTitle(config.type);
        
        modal.innerHTML = `
            <div class="modal-header">
                <h3 class="modal-title">
                    <i class="fas ${icon} modal-icon"></i>
                    ${title}
                </h3>
                <button class="modal-close" onclick="window.modalManager.close()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                ${this.createModalContent(config)}
            </div>
            <div class="modal-footer">
                ${this.createModalButtons(config, resolve)}
            </div>
        `;

        return { element: modal, config, resolve };
    }

    createModalContent(config) {
        let content = '';

        // Add message if provided
        if (config.message) {
            const messageClass = config.type ? `modal-${config.type}` : '';
            content += `<div class="modal-message ${messageClass}">${config.message}</div>`;
        }

        // Add input if needed
        if (config.input) {
            const inputType = config.input.type || 'text';
            const inputValue = config.input.value || '';
            const inputPlaceholder = config.input.placeholder || '';
            content += `<input type="${inputType}" class="modal-input" value="${inputValue}" placeholder="${inputPlaceholder}" id="modal-input">`;
        }

        return content;
    }

    createModalButtons(config, resolve) {
        const buttons = [];

        if (config.type === 'confirm') {
            buttons.push(`
                <button class="modal-btn modal-btn-secondary" onclick="window.modalManager.close()">
                    ${config.cancelText || 'Cancel'}
                </button>
                <button class="modal-btn modal-btn-danger" onclick="window.modalManager.confirm()">
                    ${config.confirmText || 'Confirm'}
                </button>
            `);
        } else if (config.input) {
            buttons.push(`
                <button class="modal-btn modal-btn-secondary" onclick="window.modalManager.close()">
                    ${config.cancelText || 'Cancel'}
                </button>
                <button class="modal-btn modal-btn-primary" onclick="window.modalManager.confirm()">
                    ${config.confirmText || 'OK'}
                </button>
            `);
        } else {
            buttons.push(`
                <button class="modal-btn modal-btn-primary" onclick="window.modalManager.close()">
                    ${config.confirmText || 'OK'}
                </button>
            `);
        }

        return buttons.join('');
    }

    showModal(modal) {
        const container = document.getElementById('modal-container');
        container.innerHTML = '';
        container.appendChild(modal.element);
        container.classList.add('show');
        this.activeModal = modal;

        // Focus input if present
        const input = modal.element.querySelector('#modal-input');
        if (input) {
            setTimeout(() => input.focus(), 100);
        }

        // Handle Enter key for input modals
        if (modal.config.input) {
            const handleKeydown = (e) => {
                if (e.key === 'Enter') {
                    this.confirm();
                } else if (e.key === 'Escape') {
                    this.close();
                }
            };
            document.addEventListener('keydown', handleKeydown);
            modal.handleKeydown = handleKeydown;
        }
    }

    close() {
        if (this.activeModal) {
            // Remove event listener if present
            if (this.activeModal.handleKeydown) {
                document.removeEventListener('keydown', this.activeModal.handleKeydown);
            }

            // Resolve with null/undefined for cancel
            this.activeModal.resolve(null);
            this.hideModal();
        }
    }

    confirm() {
        if (this.activeModal) {
            let result = true;

            // Get input value if present
            if (this.activeModal.config.input) {
                const input = this.activeModal.element.querySelector('#modal-input');
                result = input ? input.value.trim() : '';
            }

            // Remove event listener if present
            if (this.activeModal.handleKeydown) {
                document.removeEventListener('keydown', this.activeModal.handleKeydown);
            }

            this.activeModal.resolve(result);
            this.hideModal();
        }
    }

    hideModal() {
        const container = document.getElementById('modal-container');
        container.classList.remove('show');
        this.activeModal = null;
        this.modalStack.pop();
    }

    getDefaultIcon(type) {
        const icons = {
            'error': 'fa-exclamation-circle',
            'success': 'fa-check-circle',
            'warning': 'fa-exclamation-triangle',
            'info': 'fa-info-circle',
            'confirm': 'fa-question-circle',
            'prompt': 'fa-edit'
        };
        return icons[type] || 'fa-info-circle';
    }

    getDefaultTitle(type) {
        const titles = {
            'error': 'Error',
            'success': 'Success',
            'warning': 'Warning',
            'info': 'Information',
            'confirm': 'Confirm',
            'prompt': 'Input Required'
        };
        return titles[type] || 'Dialog';
    }

    // Convenience methods
    alert(message, title = 'Information', type = 'info') {
        return this.show({
            type: type,
            title: title,
            message: message
        });
    }

    info(message, title = 'Information') {
        return this.alert(message, title, 'info');
    }

    confirm(message, title = 'Confirm') {
        return this.show({
            type: 'confirm',
            title: title,
            message: message
        });
    }

    prompt(message, defaultValue = '', placeholder = '') {
        return this.show({
            type: 'prompt',
            title: 'Input Required',
            message: message,
            input: {
                type: 'text',
                value: defaultValue,
                placeholder: placeholder
            }
        });
    }

    error(message, title = 'Error') {
        return this.alert(message, title, 'error');
    }

    success(message, title = 'Success') {
        return this.alert(message, title, 'success');
    }

    warning(message, title = 'Warning') {
        return this.alert(message, title, 'warning');
    }
}

// Initialize global modal manager
window.modalManager = new ModalManager();

// Export for module usage
window.ModalManager = ModalManager;
