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
            container.className = 'modal fade';
            container.setAttribute('tabindex', '-1');
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
            .modal-open {
                overflow: hidden;
            }

            .modal {
                --bs-modal-zindex: 1055;
                --bs-modal-width: 500px;
                --bs-modal-padding: 1rem;
                --bs-modal-margin: 0.5rem;
                --bs-modal-bg: #fff;
                --bs-modal-border-color: #dee2e6;
                --bs-modal-border-width: 1px;
                --bs-modal-border-radius: 0.5rem;
                --bs-modal-box-shadow: 0 0.5rem 1rem rgba(0, 0, 0, 0.15);
                --bs-modal-inner-border-radius: calc(0.5rem - 1px);
                --bs-modal-header-padding: 1rem 1rem;
                --bs-modal-header-border-color: #dee2e6;
                --bs-modal-header-border-width: 1px;
                --bs-modal-title-line-height: 1.5;
                --bs-modal-footer-gap: 0.5rem;
                --bs-modal-footer-bg: ;
                --bs-modal-footer-border-color: #dee2e6;
                --bs-modal-footer-border-width: 1px;

                position: fixed;
                top: 0;
                left: 0;
                z-index: var(--bs-modal-zindex);
                display: none;
                width: 100%;
                height: 100%;
                overflow-x: hidden;
                overflow-y: auto;
                outline: 0;
            }

            .modal.show {
                display: block;
            }

            .modal-dialog {
                position: relative;
                width: auto;
                margin: var(--bs-modal-margin);
                pointer-events: none;
            }

            .modal.fade .modal-dialog {
                transition: transform 0.3s ease-out;
                transform: translate(0, -50px);
            }

            .modal.show .modal-dialog {
                transform: none;
            }

            .modal-dialog-centered {
                display: flex;
                align-items: center;
                min-height: calc(100% - var(--bs-modal-margin) * 2);
            }

            .modal-content {
                position: relative;
                display: flex;
                flex-direction: column;
                width: 100%;
                color: var(--bs-body-color);
                pointer-events: auto;
                background-color: var(--bs-modal-bg);
                background-clip: padding-box;
                border: var(--bs-modal-border-width) solid var(--bs-modal-border-color);
                border-radius: var(--bs-modal-border-radius);
                outline: 0;
                box-shadow: var(--bs-modal-box-shadow);
            }

            .modal-backdrop {
                position: fixed;
                top: 0;
                left: 0;
                z-index: 1050;
                width: 100vw;
                height: 100vh;
                background-color: #000;
            }

            .modal-backdrop.fade {
                opacity: 0;
            }

            .modal-backdrop.show {
                opacity: 0.5;
            }

            .modal-header {
                display: flex;
                flex-shrink: 0;
                align-items: center;
                justify-content: space-between;
                padding: var(--bs-modal-header-padding);
                border-bottom: var(--bs-modal-header-border-width) solid var(--bs-modal-header-border-color);
                border-top-left-radius: var(--bs-modal-inner-border-radius);
                border-top-right-radius: var(--bs-modal-inner-border-radius);
            }

            .modal-header .btn-close {
                padding: calc(var(--bs-modal-header-padding) * .5);
                margin-right: calc(var(--bs-modal-header-padding) * -.5);
            }

            .modal-title {
                margin-bottom: 0;
                line-height: var(--bs-modal-title-line-height);
            }

            .modal-body {
                position: relative;
                flex: 1 1 auto;
                padding: var(--bs-modal-padding);
            }

            .modal-footer {
                display: flex;
                flex-wrap: wrap;
                flex-shrink: 0;
                align-items: center;
                justify-content: flex-end;
                padding: calc(var(--bs-modal-padding) - var(--bs-modal-footer-gap) * .5);
                border-top: var(--bs-modal-footer-border-width) solid var(--bs-modal-footer-border-color);
                border-bottom-right-radius: var(--bs-modal-inner-border-radius);
                border-bottom-left-radius: var(--bs-modal-inner-border-radius);
            }

            .modal-sm {
                --bs-modal-width: 300px;
            }

            .modal-lg, .modal-xl {
                --bs-modal-width: 800px;
            }

            .modal-xl {
                --bs-modal-width: 1140px;
            }

            /* Custom styles for our modal system */
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
        modal.className = 'modal fade';
        modal.setAttribute('tabindex', '-1');
        
        const icon = config.icon || this.getDefaultIcon(config.type);
        const title = config.title || this.getDefaultTitle(config.type);
        
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fas ${icon} modal-icon"></i>
                            ${title}
                        </h5>
                        <button type="button" class="btn-close" onclick="window.modalManager.close()" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        ${this.createModalContent(config)}
                    </div>
                    <div class="modal-footer">
                        ${this.createModalButtons(config, resolve)}
                    </div>
                </div>
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
        
        // Add backdrop
        const backdrop = document.createElement('div');
        backdrop.className = 'modal-backdrop fade show';
        document.body.appendChild(backdrop);
        
        // Show modal
        container.classList.add('show');
        document.body.classList.add('modal-open');
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
        document.body.classList.remove('modal-open');
        
        // Remove backdrop
        const backdrop = document.querySelector('.modal-backdrop');
        if (backdrop) {
            backdrop.remove();
        }
        
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
