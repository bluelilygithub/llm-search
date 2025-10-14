/**
 * Error Handler Module
 * Centralized error handling with user-friendly messages and proper categorization
 * Provides consistent error experience across the application
 */

class ErrorHandler {
    constructor(uiController) {
        this.uiController = uiController;
        this.errorCategories = {
            NETWORK: 'network',
            VALIDATION: 'validation',
            AUTHENTICATION: 'authentication',
            AUTHORIZATION: 'authorization',
            SERVER: 'server',
            CLIENT: 'client',
            RATE_LIMIT: 'rate_limit'
        };
        
        this.setupGlobalErrorHandling();
    }

    /**
     * Setup global error handling
     */
    setupGlobalErrorHandling() {
        // Handle unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled promise rejection:', event.reason);
            this.handleError(event.reason, 'Unexpected error occurred');
            event.preventDefault(); // Prevent default browser error handling
        });

        // Handle JavaScript errors
        window.addEventListener('error', (event) => {
            console.error('JavaScript error:', event.error);
            this.handleError(event.error, 'Application error occurred');
        });
    }

    /**
     * Main error handling method
     */
    handleError(error, fallbackMessage = 'An unexpected error occurred') {
        const errorInfo = this.categorizeError(error);
        const userMessage = this.getUserFriendlyMessage(errorInfo);
        
        // Log error for debugging
        this.logError(error, errorInfo);
        
        // Show user notification
        this.showUserNotification(userMessage, errorInfo.severity);
        
        // Handle specific error actions
        this.handleSpecificError(errorInfo);
        
        return errorInfo;
    }

    /**
     * Categorize error type and severity
     */
    categorizeError(error) {
        let category = this.errorCategories.CLIENT;
        let severity = 'error';
        let code = 'UNKNOWN';
        let retryable = false;

        if (error instanceof APIError) {
            if (error.isNetworkError()) {
                category = this.errorCategories.NETWORK;
                severity = 'warning';
                code = 'NETWORK_ERROR';
                retryable = true;
            } else if (error.status === 400) {
                category = this.errorCategories.VALIDATION;
                severity = 'warning';
                code = 'VALIDATION_ERROR';
                retryable = false;
            } else if (error.status === 401) {
                category = this.errorCategories.AUTHENTICATION;
                severity = 'error';
                code = 'AUTH_REQUIRED';
                retryable = false;
            } else if (error.status === 403) {
                category = this.errorCategories.AUTHORIZATION;
                severity = 'error';
                code = 'ACCESS_DENIED';
                retryable = false;
            } else if (error.status === 429) {
                category = this.errorCategories.RATE_LIMIT;
                severity = 'warning';
                code = 'RATE_LIMITED';
                retryable = true;
            } else if (error.status >= 500) {
                category = this.errorCategories.SERVER;
                severity = 'error';
                code = 'SERVER_ERROR';
                retryable = true;
            }
        } else if (error instanceof TypeError && error.message.includes('fetch')) {
            category = this.errorCategories.NETWORK;
            severity = 'warning';
            code = 'NETWORK_ERROR';
            retryable = true;
        }

        return {
            originalError: error,
            category,
            severity,
            code,
            retryable,
            message: error.message || 'Unknown error',
            timestamp: new Date().toISOString()
        };
    }

    /**
     * Get user-friendly error messages
     */
    getUserFriendlyMessage(errorInfo) {
        const messages = {
            NETWORK_ERROR: {
                title: 'Connection Problem',
                message: 'Unable to connect to the server. Please check your internet connection and try again.',
                action: 'Retry'
            },
            VALIDATION_ERROR: {
                title: 'Invalid Input',
                message: 'Please check your input and try again. Some required fields may be missing or invalid.',
                action: 'Fix Input'
            },
            AUTH_REQUIRED: {
                title: 'Authentication Required',
                message: 'You need to log in to perform this action.',
                action: 'Log In'
            },
            ACCESS_DENIED: {
                title: 'Access Denied',
                message: 'You don\'t have permission to perform this action.',
                action: 'Contact Support'
            },
            RATE_LIMITED: {
                title: 'Too Many Requests',
                message: 'You\'re making requests too quickly. Please wait a moment before trying again.',
                action: 'Wait & Retry'
            },
            SERVER_ERROR: {
                title: 'Server Error',
                message: 'Something went wrong on our end. We\'re working to fix it. Please try again in a few minutes.',
                action: 'Retry Later'
            },
            UNKNOWN: {
                title: 'Unexpected Error',
                message: 'An unexpected error occurred. Please try refreshing the page.',
                action: 'Refresh Page'
            }
        };

        const template = messages[errorInfo.code] || messages.UNKNOWN;
        
        return {
            title: template.title,
            message: template.message,
            action: template.action,
            details: errorInfo.message
        };
    }

    /**
     * Show user notification with appropriate styling
     */
    showUserNotification(userMessage, severity) {
        const notificationType = severity === 'warning' ? 'warning' : 'error';
        
        // Create enhanced notification with action button
        const notificationId = this.uiController.showNotification(
            `${userMessage.title}: ${userMessage.message}`, 
            notificationType,
            8000 // 8 seconds
        );

        // Add action button if retryable
        this.addNotificationAction(notificationId, userMessage);
    }

    /**
     * Add action button to notification
     */
    addNotificationAction(notificationId, userMessage) {
        setTimeout(() => {
            const notification = document.querySelector(`[data-id="${notificationId}"]`);
            if (notification && userMessage.action) {
                const actionButton = document.createElement('button');
                actionButton.className = 'notification-action-btn';
                actionButton.textContent = userMessage.action;
                actionButton.onclick = () => this.handleNotificationAction(userMessage.action);
                
                const content = notification.querySelector('.notification-content');
                if (content) {
                    content.appendChild(actionButton);
                }
            }
        }, 100);
    }

    /**
     * Handle notification action buttons
     */
    handleNotificationAction(action) {
        switch (action) {
            case 'Retry':
                // Implement retry logic
                window.location.reload();
                break;
            case 'Refresh Page':
                window.location.reload();
                break;
            case 'Log In':
                // Redirect to login or show login modal
                window.location.href = '/login';
                break;
            case 'Contact Support':
                // Open support contact
                window.open('mailto:support@example.com', '_blank');
                break;
            default:
                // Do nothing for other actions
                break;
        }
    }

    /**
     * Handle specific error types
     */
    handleSpecificError(errorInfo) {
        switch (errorInfo.category) {
            case this.errorCategories.AUTHENTICATION:
                // Clear any cached auth data
                localStorage.removeItem('auth_token');
                // Redirect to login after delay
                setTimeout(() => {
                    if (confirm('You need to log in. Redirect to login page?')) {
                        window.location.href = '/login';
                    }
                }, 2000);
                break;
                
            case this.errorCategories.NETWORK:
                // Implement retry mechanism
                this.scheduleRetry(errorInfo);
                break;
                
            case this.errorCategories.RATE_LIMIT:
                // Implement backoff strategy
                this.handleRateLimit(errorInfo);
                break;
        }
    }

    /**
     * Schedule automatic retry for network errors
     */
    scheduleRetry(errorInfo) {
        if (errorInfo.retryable) {
            setTimeout(() => {
                // This would need to be implemented based on the specific operation
                console.log('Auto-retry could be implemented here');
            }, 5000);
        }
    }

    /**
     * Handle rate limiting with exponential backoff
     */
    handleRateLimit(errorInfo) {
        const backoffTime = Math.min(30000, Math.pow(2, this.retryCount || 0) * 1000);
        this.retryCount = (this.retryCount || 0) + 1;
        
        setTimeout(() => {
            this.retryCount = 0; // Reset retry count
        }, backoffTime);
    }

    /**
     * Log error for debugging and monitoring
     */
    logError(error, errorInfo) {
        const logEntry = {
            timestamp: errorInfo.timestamp,
            category: errorInfo.category,
            code: errorInfo.code,
            message: errorInfo.message,
            url: window.location.href,
            userAgent: navigator.userAgent,
            stack: error.stack || 'No stack trace available'
        };

        // Log to console for development
        console.group(`🚨 Error [${errorInfo.code}]`);
        console.error('Error Info:', errorInfo);
        console.error('Original Error:', error);
        console.error('Log Entry:', logEntry);
        console.groupEnd();

        // In production, you could send this to a logging service
        this.sendErrorToLoggingService(logEntry);
    }

    /**
     * Send error to logging service (placeholder)
     */
    sendErrorToLoggingService(logEntry) {
        // In production, implement actual error logging service
        // Example: Sentry, LogRocket, or custom endpoint
        
        try {
            // Only send critical errors to avoid spam
            if (logEntry.category !== 'client' && logEntry.code !== 'VALIDATION_ERROR') {
                fetch('/api/log-error', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(logEntry)
                }).catch(() => {
                    // Silently fail if logging service is unavailable
                });
            }
        } catch (e) {
            // Don't let logging errors break the app
        }
    }

    /**
     * Create user-friendly validation error messages
     */
    createValidationError(field, rule, value) {
        const messages = {
            required: `${field} is required`,
            email: `Please enter a valid email address`,
            minLength: `${field} must be at least ${rule.min} characters`,
            maxLength: `${field} cannot exceed ${rule.max} characters`,
            pattern: `${field} format is invalid`,
            uuid: `Invalid ${field} format`
        };

        return new ValidationError(
            messages[rule.type] || `${field} is invalid`,
            field,
            rule,
            value
        );
    }
}

/**
 * Custom Validation Error class
 */
class ValidationError extends Error {
    constructor(message, field, rule, value) {
        super(message);
        this.name = 'ValidationError';
        this.field = field;
        this.rule = rule;
        this.value = value;
    }
}

// Export for global use
window.ErrorHandler = ErrorHandler;
window.ValidationError = ValidationError;
