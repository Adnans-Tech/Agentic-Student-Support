/**
 * Form Validators
 * Client-side validation utilities for auth forms
 */

export const validators = {

    /**
     * Required field check
     */
    required: (value, fieldName = 'This field') => {
        if (!value || !value.trim()) {
            return `${fieldName} is required`;
        }
        return null;
    },

    /**
     * Email validation
     */
    email: (value) => {
        if (!value || !value.trim()) return 'Email is required';
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value.trim())) return 'Please enter a valid email address';
        return null;
    },

    /**
     * Password validation
     * At least 8 chars, one uppercase, one digit, one special char (_, -, ., !)
     */
    password: (value) => {
        if (!value) return 'Password is required';
        if (value.length < 8) return 'Password must be at least 8 characters';
        if (!/[A-Z]/.test(value)) return 'Password must contain at least one uppercase letter';
        if (!/[0-9]/.test(value)) return 'Password must contain at least one digit';
        if (!/[_\-.!]/.test(value)) return 'Password must contain at least one special character (_, -, ., !)';
        return null;
    },

    /**
     * Confirm password validation
     */
    confirmPassword: (password, confirmPassword) => {
        if (!confirmPassword) return 'Please confirm your password';
        if (password !== confirmPassword) return 'Passwords do not match';
        return null;
    },

    /**
     * Roll Number validation (CSM department only)
     * Regular: 22AG1A66XX
     * Lateral: 23AG5A66XX
     */
    rollNumber: (value) => {
        if (!value || !value.trim()) return 'Roll number is required';
        const upper = value.trim().toUpperCase();
        if (upper.length !== 10) return 'Roll number must be exactly 10 characters';
        const regularPattern = /^22AG1A66[A-Z0-9]{2}$/;
        const lateralPattern = /^23AG5A66[A-Z0-9]{2}$/;
        if (!regularPattern.test(upper) && !lateralPattern.test(upper)) {
            return 'Invalid roll number. Expected: 22AG1A66XX (regular) or 23AG5A66XX (lateral)';
        }
        return null;
    },

    /**
     * Phone number validation
     */
    phone: (value) => {
        if (!value || !value.trim()) return null; // Optional
        const phone = value.trim();
        if (!/^\d{10}$/.test(phone)) return 'Phone number must be exactly 10 digits';
        return null;
    },

    /**
     * OTP validation
     */
    otp: (value) => {
        if (!value) return 'OTP is required';
        if (!/^\d{6}$/.test(value)) return 'OTP must be exactly 6 digits';
        return null;
    },

    /**
     * Official email validation for faculty
     */
    officialEmail: (value) => {
        if (!value || !value.trim()) return 'Official email is required';
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value.trim())) return 'Please enter a valid email address';
        // Admin exception
        if (value.trim().toLowerCase() === 'mailtomohdadnan@gmail.com') return null;
        if (!value.trim().toLowerCase().endsWith('@aceec.ac.in')) {
            return 'Faculty email must end with @aceec.ac.in';
        }
        return null;
    },

    /**
     * Employee ID validation
     */
    employeeId: (value) => {
        // Optional field
        if (!value || !value.trim()) return null;
        const id = value.trim().toUpperCase();
        if (id.length < 3) return 'Employee ID must be at least 3 characters';
        return null;
    },

    /**
     * Password strength meter
     */
    passwordStrength: (password) => {
        if (!password) return { strength: '', score: 0, className: '' };

        let score = 0;
        if (password.length >= 8) score++;
        if (password.length >= 12) score++;
        if (/[A-Z]/.test(password)) score++;
        if (/[0-9]/.test(password)) score++;
        if (/[_\-.!]/.test(password)) score++;
        if (/[^A-Za-z0-9_\-.!]/.test(password)) score++;

        if (score <= 2) return { strength: 'Weak', score, className: 'strengthWeak' };
        if (score === 3) return { strength: 'Medium', score, className: 'strengthMedium' };
        return { strength: 'Strong', score, className: 'strengthStrong' };
    },
};

/**
 * Format backend error response
 */
export const formatBackendError = (error) => {
    if (typeof error === 'string') return error;

    // Axios error with response
    if (error?.response?.data) {
        const data = error.response.data;
        if (data.error) return data.error;
        if (data.message) return data.message;
    }

    // Direct error object
    if (error?.error) return error.error;
    if (error?.message) return error.message;

    return 'Something went wrong. Please try again.';
};
