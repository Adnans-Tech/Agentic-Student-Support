/**
 * Form Validation Utilities
 */

export const validators = {
    // Email validation
    email: (value) => {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!value) return 'Email is required';
        if (!emailRegex.test(value)) return 'Invalid email format';
        return null;
    },

    // Password validation
    password: (value) => {
        if (!value) return 'Password is required';
        if (value.length < 6) return 'Password must be at least 6 characters';
        return null;
    },

    // Password strength check
    passwordStrength: (value) => {
        if (!value) return { strength: '', score: 0 };

        let score = 0;

        // Length check
        if (value.length >= 8) score++;
        if (value.length >= 12) score++;

        // Character variety
        if (/[a-z]/.test(value)) score++;
        if (/[A-Z]/.test(value)) score++;
        if (/[0-9]/.test(value)) score++;
        if (/[^a-zA-Z0-9]/.test(value)) score++;

        if (score <= 2) return { strength: 'Weak', score, className: 'weak' };
        if (score <= 4) return { strength: 'Medium', score, className: 'medium' };
        return { strength: 'Strong', score, className: 'strong' };
    },

    // Required field
    required: (value, fieldName = 'This field') => {
        if (!value || value.trim() === '') return `${fieldName} is required`;
        return null;
    },

    // Roll number validation - Format: 22AG1A0000 or 22AG5A0000
    // 2 digits + AG + digit(1-5) + A + 4 digits
    rollNumber: (value) => {
        if (!value) return 'Roll number is required';

        // Auto-convert to uppercase for validation
        const formatted = value.toUpperCase().trim();

        // Check minimum length
        if (formatted.length < 8) return 'Roll number is too short';

        // Pattern: 2 digits + AG + 1 digit (1-5) + A + at least 2 alphanumeric
        const rollRegex = /^\d{2}AG[1-5]A[A-Z0-9]{2,}$/;

        if (!rollRegex.test(formatted)) {
            return 'Roll number must start with format like 22AG1A (e.g., 22AG1A0000 or 22AG1A66A8)';
        }

        return null;
    },

    // Phone validation (10 digits)
    phone: (value) => {
        if (!value) return null; // Phone is optional
        const phoneRegex = /^[0-9]{10}$/;
        if (!phoneRegex.test(value)) return 'Phone must be 10 digits';
        return null;
    },

    // OTP validation (6 digits)
    otp: (value) => {
        if (!value) return 'OTP is required';
        if (!/^[0-9]{6}$/.test(value)) return 'OTP must be 6 digits';
        return null;
    },

    // Year validation
    year: (value) => {
        if (!value) return 'Year is required';
        const yearNum = parseInt(value);
        if (![1, 2, 3, 4].includes(yearNum)) return 'Year must be 1, 2, 3, or 4';
        return null;
    },

    // === Faculty-Specific Validators ===

    // Official email validation (stricter for faculty)
    officialEmail: (value) => {
        if (!value) return 'Official email is required';
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) return 'Invalid email format';
        return null;
    },

    // Employee ID validation
    employeeId: (value) => {
        if (!value) return 'Employee ID is required';
        // Allow alphanumeric employee IDs (e.g., EMP12345, FAC001)
        if (value.trim().length < 3) return 'Employee ID must be at least 3 characters';
        return null;
    },

    // Password confirmation validation
    confirmPassword: (password, confirmPassword) => {
        if (!confirmPassword) return 'Please confirm your password';
        if (password !== confirmPassword) return 'Passwords do not match';
        return null;
    },
};

/**
 * Format validation errors from backend
 */
export const formatBackendError = (error) => {
    if (typeof error === 'string') return error;
    if (error.error) return error.error;
    if (error.message) return error.message;
    return 'An error occurred. Please try again.';
};
