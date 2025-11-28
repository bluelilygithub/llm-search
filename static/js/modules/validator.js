/**
 * Input Validator Module
 * Comprehensive client-side validation with schema-based approach
 * Prevents bad data and improves security
 */

class Validator {
    constructor(errorHandler) {
        this.errorHandler = errorHandler;
        this.schemas = this.initializeSchemas();
    }

    /**
     * Initialize validation schemas for different data types
     */
    initializeSchemas() {
        return {
            // Chat message validation
            chatMessage: {
                message: {
                    required: true,
                    type: 'string',
                    minLength: 1,
                    maxLength: 10000,
                    sanitize: true
                },
                model: {
                    required: true,
                    type: 'string',
                    enum: [
                        'gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-4o-mini',
                        'claude-3.5-sonnet', 'claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku',
                        'gemini-pro', 'gemini-flash'
                    ]
                },
                conversation_id: {
                    required: false,
                    type: 'uuid'
                },
                project_id: {
                    required: false,
                    type: 'uuid'
                }
            },

            // Project creation/update validation
            project: {
                name: {
                    required: true,
                    type: 'string',
                    minLength: 1,
                    maxLength: 255,
                    sanitize: true,
                    pattern: /^[a-zA-Z0-9\s\-_\.]+$/
                },
                description: {
                    required: false,
                    type: 'string',
                    maxLength: 1000,
                    sanitize: true
                }
            },

            // Conversation validation
            conversation: {
                title: {
                    required: true,
                    type: 'string',
                    minLength: 1,
                    maxLength: 255,
                    sanitize: true
                },
                llm_model: {
                    required: true,
                    type: 'string',
                    enum: [
                        'gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-4o-mini',
                        'claude-3.5-sonnet', 'claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku',
                        'gemini-pro', 'gemini-flash'
                    ]
                },
                tags: {
                    required: false,
                    type: 'array',
                    maxItems: 10,
                    itemType: 'string',
                    itemMaxLength: 50
                },
                project_id: {
                    required: false,
                    type: 'uuid'
                }
            },

            // Context item validation
            contextItem: {
                name: {
                    required: true,
                    type: 'string',
                    minLength: 1,
                    maxLength: 255,
                    sanitize: true
                },
                description: {
                    required: false,
                    type: 'string',
                    maxLength: 1000,
                    sanitize: true
                },
                content_type: {
                    required: true,
                    type: 'string',
                    enum: ['document', 'url', 'text', 'conversation']
                },
                content_text: {
                    required: false,
                    type: 'string',
                    maxLength: 100000,
                    sanitize: true
                }
            },

            // User preferences validation
            userPreferences: {
                defaultModel: {
                    required: false,
                    type: 'string',
                    enum: [
                        'gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-4o-mini',
                        'claude-3.5-sonnet', 'claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku',
                        'gemini-pro', 'gemini-flash'
                    ]
                },
                theme: {
                    required: false,
                    type: 'string',
                    enum: ['light', 'dark', 'auto']
                }
            },

            // File upload validation
            fileUpload: {
                file: {
                    required: true,
                    type: 'file',
                    maxSize: 50 * 1024 * 1024, // 50MB
                    allowedTypes: [
                        'application/pdf',
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'application/msword',
                        'text/plain',
                        'text/csv',
                        'text/markdown',
                        'text/x-markdown',
                        'application/json'
                    ]
                }
            }
        };
    }

    /**
     * Validate data against a schema
     */
    validate(data, schemaName) {
        const schema = this.schemas[schemaName];
        if (!schema) {
            throw new Error(`Unknown validation schema: ${schemaName}`);
        }

        const errors = [];
        const sanitizedData = {};

        // Validate each field in the schema
        for (const [fieldName, rules] of Object.entries(schema)) {
            const value = data[fieldName];
            const fieldErrors = this.validateField(fieldName, value, rules);
            
            if (fieldErrors.length > 0) {
                errors.push(...fieldErrors);
            } else {
                // Apply sanitization if validation passed
                sanitizedData[fieldName] = this.sanitizeValue(value, rules);
            }
        }

        // Check for unexpected fields
        for (const fieldName of Object.keys(data)) {
            if (!schema[fieldName]) {
                console.warn(`Unexpected field in ${schemaName}: ${fieldName}`);
            }
        }

        if (errors.length > 0) {
            throw new ValidationError('Validation failed', errors);
        }

        return sanitizedData;
    }

    /**
     * Validate a single field
     */
    validateField(fieldName, value, rules) {
        const errors = [];

        // Check required
        if (rules.required && (value === undefined || value === null || value === '')) {
            errors.push({
                field: fieldName,
                rule: 'required',
                message: `${fieldName} is required`
            });
            return errors; // Don't continue validation if required field is missing
        }

        // Skip further validation if field is optional and empty
        if (!rules.required && (value === undefined || value === null || value === '')) {
            return errors;
        }

        // Type validation
        if (rules.type && !this.validateType(value, rules.type)) {
            errors.push({
                field: fieldName,
                rule: 'type',
                message: `${fieldName} must be of type ${rules.type}`
            });
            return errors;
        }

        // String validations
        if (rules.type === 'string' && typeof value === 'string') {
            if (rules.minLength && value.length < rules.minLength) {
                errors.push({
                    field: fieldName,
                    rule: 'minLength',
                    message: `${fieldName} must be at least ${rules.minLength} characters`
                });
            }

            if (rules.maxLength && value.length > rules.maxLength) {
                errors.push({
                    field: fieldName,
                    rule: 'maxLength',
                    message: `${fieldName} cannot exceed ${rules.maxLength} characters`
                });
            }

            if (rules.pattern && !rules.pattern.test(value)) {
                errors.push({
                    field: fieldName,
                    rule: 'pattern',
                    message: `${fieldName} format is invalid`
                });
            }

            if (rules.enum && !rules.enum.includes(value)) {
                errors.push({
                    field: fieldName,
                    rule: 'enum',
                    message: `${fieldName} must be one of: ${rules.enum.join(', ')}`
                });
            }
        }

        // Array validations
        if (rules.type === 'array' && Array.isArray(value)) {
            if (rules.maxItems && value.length > rules.maxItems) {
                errors.push({
                    field: fieldName,
                    rule: 'maxItems',
                    message: `${fieldName} cannot have more than ${rules.maxItems} items`
                });
            }

            if (rules.itemType) {
                value.forEach((item, index) => {
                    if (!this.validateType(item, rules.itemType)) {
                        errors.push({
                            field: `${fieldName}[${index}]`,
                            rule: 'itemType',
                            message: `${fieldName} items must be of type ${rules.itemType}`
                        });
                    }

                    if (rules.itemMaxLength && typeof item === 'string' && item.length > rules.itemMaxLength) {
                        errors.push({
                            field: `${fieldName}[${index}]`,
                            rule: 'itemMaxLength',
                            message: `${fieldName} items cannot exceed ${rules.itemMaxLength} characters`
                        });
                    }
                });
            }
        }

        // UUID validation
        if (rules.type === 'uuid' && !this.isValidUUID(value)) {
            errors.push({
                field: fieldName,
                rule: 'uuid',
                message: `${fieldName} must be a valid UUID`
            });
        }

        // File validation
        if (rules.type === 'file' && value instanceof File) {
            if (rules.maxSize && value.size > rules.maxSize) {
                errors.push({
                    field: fieldName,
                    rule: 'maxSize',
                    message: `${fieldName} size cannot exceed ${this.formatFileSize(rules.maxSize)}`
                });
            }

            if (rules.allowedTypes && !rules.allowedTypes.includes(value.type)) {
                errors.push({
                    field: fieldName,
                    rule: 'allowedTypes',
                    message: `${fieldName} type not allowed. Allowed types: ${rules.allowedTypes.join(', ')}`
                });
            }
        }

        return errors;
    }

    /**
     * Validate value type
     */
    validateType(value, expectedType) {
        switch (expectedType) {
            case 'string':
                return typeof value === 'string';
            case 'number':
                return typeof value === 'number' && !isNaN(value);
            case 'boolean':
                return typeof value === 'boolean';
            case 'array':
                return Array.isArray(value);
            case 'object':
                return typeof value === 'object' && value !== null && !Array.isArray(value);
            case 'uuid':
                return typeof value === 'string' && this.isValidUUID(value);
            case 'file':
                return value instanceof File;
            default:
                return true;
        }
    }

    /**
     * Validate UUID format
     */
    isValidUUID(uuid) {
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
        return uuidRegex.test(uuid);
    }

    /**
     * Sanitize value based on rules
     */
    sanitizeValue(value, rules) {
        if (!rules.sanitize || typeof value !== 'string') {
            return value;
        }

        // Basic HTML sanitization
        let sanitized = value
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#x27;')
            .replace(/\//g, '&#x2F;');

        // Trim whitespace
        sanitized = sanitized.trim();

        // Remove null bytes
        sanitized = sanitized.replace(/\0/g, '');

        return sanitized;
    }

    /**
     * Format file size for display
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * Validate form data with real-time feedback
     */
    validateForm(formElement, schemaName) {
        const formData = new FormData(formElement);
        const data = {};
        
        // Convert FormData to object
        for (const [key, value] of formData.entries()) {
            data[key] = value;
        }

        try {
            const sanitizedData = this.validate(data, schemaName);
            this.clearFormErrors(formElement);
            return { valid: true, data: sanitizedData };
        } catch (error) {
            if (error instanceof ValidationError) {
                this.showFormErrors(formElement, error.errors);
                return { valid: false, errors: error.errors };
            }
            throw error;
        }
    }

    /**
     * Show validation errors on form
     */
    showFormErrors(formElement, errors) {
        this.clearFormErrors(formElement);

        errors.forEach(error => {
            const field = formElement.querySelector(`[name="${error.field}"]`);
            if (field) {
                field.classList.add('validation-error');
                
                // Create error message element
                const errorElement = document.createElement('div');
                errorElement.className = 'field-error-message';
                errorElement.textContent = error.message;
                
                // Insert error message after field
                field.parentNode.insertBefore(errorElement, field.nextSibling);
            }
        });
    }

    /**
     * Clear form validation errors
     */
    clearFormErrors(formElement) {
        // Remove error classes
        const errorFields = formElement.querySelectorAll('.validation-error');
        errorFields.forEach(field => field.classList.remove('validation-error'));

        // Remove error messages
        const errorMessages = formElement.querySelectorAll('.field-error-message');
        errorMessages.forEach(message => message.remove());
    }

    /**
     * Add real-time validation to form
     */
    addRealTimeValidation(formElement, schemaName) {
        const fields = formElement.querySelectorAll('input, textarea, select');
        
        fields.forEach(field => {
            field.addEventListener('blur', () => {
                this.validateSingleField(field, schemaName);
            });

            field.addEventListener('input', () => {
                // Clear error on input
                if (field.classList.contains('validation-error')) {
                    field.classList.remove('validation-error');
                    const errorMessage = field.parentNode.querySelector('.field-error-message');
                    if (errorMessage) {
                        errorMessage.remove();
                    }
                }
            });
        });
    }

    /**
     * Validate single field
     */
    validateSingleField(field, schemaName) {
        const schema = this.schemas[schemaName];
        const fieldName = field.name;
        const fieldRules = schema[fieldName];
        
        if (!fieldRules) return;

        const errors = this.validateField(fieldName, field.value, fieldRules);
        
        if (errors.length > 0) {
            field.classList.add('validation-error');
            
            // Show first error
            const errorElement = document.createElement('div');
            errorElement.className = 'field-error-message';
            errorElement.textContent = errors[0].message;
            
            // Remove existing error message
            const existingError = field.parentNode.querySelector('.field-error-message');
            if (existingError) {
                existingError.remove();
            }
            
            field.parentNode.insertBefore(errorElement, field.nextSibling);
        }
    }
}

/**
 * Enhanced Validation Error class
 */
class ValidationError extends Error {
    constructor(message, errors) {
        super(message);
        this.name = 'ValidationError';
        this.errors = errors || [];
    }
}

// Export for global use
window.Validator = Validator;
window.ValidationError = ValidationError;
