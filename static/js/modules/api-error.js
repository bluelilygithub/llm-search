/**
 * API Error Class
 * Standardized error handling for API responses
 * Works with ErrorHandler for consistent error experience
 */

class APIError extends Error {
    constructor(message, status = null, response = null, originalError = null) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.response = response;
        this.originalError = originalError;
        this.timestamp = new Date().toISOString();
    }

    /**
     * Check if this is a network error (no response received)
     */
    isNetworkError() {
        return !this.status && !this.response;
    }

    /**
     * Check if this is a client error (4xx)
     */
    isClientError() {
        return this.status >= 400 && this.status < 500;
    }

    /**
     * Check if this is a server error (5xx)
     */
    isServerError() {
        return this.status >= 500;
    }

    /**
     * Check if this error is retryable
     */
    isRetryable() {
        // Network errors are retryable
        if (this.isNetworkError()) return true;
        
        // Rate limiting is retryable
        if (this.status === 429) return true;
        
        // Server errors are retryable
        if (this.isServerError()) return true;
        
        // Client errors are generally not retryable
        return false;
    }

    /**
     * Get user-friendly error message
     */
    getUserMessage() {
        if (this.isNetworkError()) {
            return 'Unable to connect to the server. Please check your internet connection.';
        }
        
        switch (this.status) {
            case 400:
                return 'Invalid request. Please check your input and try again.';
            case 401:
                return 'You need to log in to perform this action.';
            case 403:
                return 'You don\'t have permission to perform this action.';
            case 404:
                return 'The requested resource was not found.';
            case 409:
                return 'This action conflicts with the current state. Please refresh and try again.';
            case 422:
                return 'The data provided is invalid. Please check your input.';
            case 429:
                return 'Too many requests. Please wait a moment before trying again.';
            case 500:
                return 'Server error. Please try again in a few minutes.';
            case 502:
            case 503:
            case 504:
                return 'Service temporarily unavailable. Please try again later.';
            default:
                return this.message || 'An unexpected error occurred.';
        }
    }

    /**
     * Create APIError from fetch response
     */
    static async fromResponse(response, originalError = null) {
        let message = `HTTP ${response.status}`;
        let errorData = null;

        try {
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                errorData = await response.json();
                message = errorData.message || errorData.error || message;
            } else {
                const text = await response.text();
                // Check if it's an HTML error page
                if (text.includes('<!DOCTYPE') || text.includes('<html')) {
                    message = `Server returned HTML instead of JSON (${response.status})`;
                } else {
                    message = text || message;
                }
            }
        } catch (parseError) {
            // If we can't parse the response, use the status text
            message = response.statusText || message;
        }

        const apiError = new APIError(message, response.status, response, originalError);
        apiError.errorData = errorData;
        return apiError;
    }

    /**
     * Create APIError from network error
     */
    static fromNetworkError(originalError) {
        let message = 'Network error occurred';
        
        if (originalError) {
            if (originalError.message.includes('fetch')) {
                message = 'Unable to connect to server';
            } else if (originalError.message.includes('timeout')) {
                message = 'Request timed out';
            } else {
                message = originalError.message;
            }
        }

        return new APIError(message, null, null, originalError);
    }

    /**
     * Create APIError from validation errors
     */
    static fromValidationErrors(errors, message = 'Validation failed') {
        const apiError = new APIError(message, 400);
        apiError.validationErrors = errors;
        return apiError;
    }

    /**
     * Convert to JSON for logging
     */
    toJSON() {
        return {
            name: this.name,
            message: this.message,
            status: this.status,
            timestamp: this.timestamp,
            isNetworkError: this.isNetworkError(),
            isClientError: this.isClientError(),
            isServerError: this.isServerError(),
            isRetryable: this.isRetryable(),
            stack: this.stack,
            originalError: this.originalError ? {
                name: this.originalError.name,
                message: this.originalError.message,
                stack: this.originalError.stack
            } : null
        };
    }
}

// Export for global use
window.APIError = APIError;
