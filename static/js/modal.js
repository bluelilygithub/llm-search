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
                padding: 1rem;
                box-sizing: border-box;
            }

            .modal-container.show {
                display: flex;
            }

            .modal {
                background-color: white;
                border-radius: 0.375rem;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
                max-width: 500px;
                width: 100%;
                margin: 1.75rem auto;
                position: relative;
                display: flex;
                flex-direction: column;
                max-height: calc(100% - 3.5rem);
                overflow: hidden;
                animation: modalSlideIn 0.3s ease-out;
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
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 1rem;
                border-bottom: 1px solid #dee2e6;
                border-top-left-radius: calc(0.375rem - 1px);
                border-top-right-radius: calc(0.375rem - 1px);
            }

            .modal-title {
                font-size: 1.25rem;
                font-weight: 500;
                color: #212529;
                margin: 0;
                line-height: 1.5;
            }

            .modal-close {
                background: transparent;
                border: 0;
                font-size: 1.5rem;
                font-weight: 700;
                line-height: 1;
                color: #000;
                text-shadow: 0 1px 0 #fff;
                opacity: 0.5;
                cursor: pointer;
                padding: 0;
                margin: 0;
                transition: opacity 0.15s;
            }

            .modal-close:hover {
                opacity: 0.75;
            }

            .modal-body {
                position: relative;
                flex: 1 1 auto;
                padding: 1rem;
                overflow-y: auto;
            }

            .modal-message {
                color: #212529;
                line-height: 1.5;
                margin-bottom: 1rem;
            }

            .modal-input {
                width: 100%;
                padding: 0.375rem 0.75rem;
                border: 1px solid #ced4da;
                border-radius: 0.375rem;
                font-size: 1rem;
                line-height: 1.5;
                transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
                box-sizing: border-box;
            }

            .modal-input:focus {
                outline: 0;
                border-color: #86b7fe;
                box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.25);
            }

            .modal-footer {
                display: flex;
                gap: 0.5rem;
                justify-content: flex-end;
                padding: 0.75rem;
                border-top: 1px solid #dee2e6;
                border-bottom-right-radius: calc(0.375rem - 1px);
                border-bottom-left-radius: calc(0.375rem - 1px);
            }

            .modal-btn {
                display: inline-block;
                font-weight: 400;
                line-height: 1.5;
                text-align: center;
                text-decoration: none;
                vertical-align: middle;
                cursor: pointer;
                user-select: none;
                border: 1px solid transparent;
                padding: 0.375rem 0.75rem;
                font-size: 1rem;
                border-radius: 0.375rem;
                transition: color 0.15s ease-in-out, background-color 0.15s ease-in-out, border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
            }

            .modal-btn-primary {
                color: #fff;
                background-color: #0d6efd;
                border-color: #0d6efd;
            }

            .modal-btn-primary:hover {
                color: #fff;
                background-color: #0b5ed7;
                border-color: #0a58ca;
            }

            .modal-btn-secondary {
                color: #fff;
                background-color: #6c757d;
                border-color: #6c757d;
            }

            .modal-btn-secondary:hover {
                color: #fff;
                background-color: #5c636a;
                border-color: #565e64;
            }

            .modal-btn-danger {
                color: #fff;
                background-color: #dc3545;
                border-color: #dc3545;
            }

            .modal-btn-danger:hover {
                color: #fff;
                background-color: #bb2d3b;
                border-color: #b02a37;
            }

            .modal-icon {
                margin-right: 8px;
            }

            .modal-error {
                border-left: 4px solid #ef4444;
                background: #fef2f2;
                padding: 12px 16px;
                margin-bottom: 16px;
                border-radius: 0 6px 6px 0;
            }

            .modal-success {
                border-left: 4px solid #10b981;
                background: #f0fdf4;
                padding: 12px 16px;
                margin-bottom: 16px;
                border-radius: 0 6px 6px 0;
            }

            .modal-warning {
                border-left: 4px solid #f59e0b;
                background: #fffbeb;
                padding: 12px 16px;
                margin-bottom: 16px;
                border-radius: 0 6px 6px 0;
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
