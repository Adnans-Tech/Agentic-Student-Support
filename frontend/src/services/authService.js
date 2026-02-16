/**
 * Authentication Service
 * Handles all authentication-related API calls
 */

import api from './api';

const authService = {
    // === STUDENT REGISTRATION ===

    async registerStudent(data) {
        try {
            const response = await api.post('/auth/register', {
                email: data.email,
                roll_number: data.rollNumber,
                full_name: data.fullName,
                password: data.password,
                department: data.department,
                year: data.year,
                phone: data.phone || '',
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Registration failed' };
        }
    },

    // === OTP MANAGEMENT ===

    async sendOTP(email, resend = false) {
        try {
            const response = await api.post('/auth/send-otp', {
                email,
                resend,
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to send OTP' };
        }
    },

    async verifyOTP(email, otp) {
        try {
            const response = await api.post('/auth/verify-otp', {
                email,
                otp,
            });

            // Store token and user data
            if (response.data.success && response.data.token) {
                localStorage.setItem('ace_auth_token', response.data.token);
                localStorage.setItem('ace_user', JSON.stringify(response.data.user));
            }

            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'OTP verification failed' };
        }
    },

    // === LOGIN ===

    async loginStudent(identifier, password) {
        try {
            const response = await api.post('/auth/login/student', {
                identifier,
                password,
            });

            // Store token and user data
            if (response.data.success && response.data.token) {
                localStorage.setItem('ace_auth_token', response.data.token);
                localStorage.setItem('ace_user', JSON.stringify(response.data.user));
            }

            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Login failed' };
        }
    },

    async loginFaculty(email, password) {
        try {
            const response = await api.post('/auth/faculty/login', {
                email,
                password,
            });

            // Store token and user data
            if (response.data.success && response.data.token) {
                localStorage.setItem('ace_auth_token', response.data.token);
                localStorage.setItem('ace_user', JSON.stringify(response.data.user));
            }

            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Login failed' };
        }
    },

    // === GET CURRENT USER ===

    async getCurrentUser() {
        try {
            const response = await api.get('/auth/me');

            if (response.data.success) {
                localStorage.setItem('ace_user', JSON.stringify(response.data.user));
            }

            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to fetch user data' };
        }
    },

    // === LOGOUT ===

    logout() {
        localStorage.removeItem('ace_auth_token');
        localStorage.removeItem('ace_user');
        window.location.href = '/login';
    },

    // === HELPERS ===

    isAuthenticated() {
        return !!localStorage.getItem('ace_auth_token');
    },

    getUser() {
        const userStr = localStorage.getItem('ace_user');
        return userStr ? JSON.parse(userStr) : null;
    },

    getToken() {
        return localStorage.getItem('ace_auth_token');
    },

    // === FACULTY REGISTRATION ===

    async registerFaculty(data) {
        try {
            const response = await api.post('/auth/faculty/register', {
                official_email: data.officialEmail,
                full_name: data.fullName,
                employee_id: data.employeeId,
                department: data.department,
                designation: data.designation || '',
                password: data.password,
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Registration failed' };
        }
    },

    async sendFacultyOTP(email, resend = false) {
        try {
            const response = await api.post('/auth/faculty/send-otp', {
                email,
                resend,
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to send OTP' };
        }
    },

    async verifyFacultyOTP(email, otp) {
        try {
            const response = await api.post('/auth/faculty/verify-otp', {
                email,
                otp,
            });

            // Store token and user data
            if (response.data.success && response.data.token) {
                localStorage.setItem('ace_auth_token', response.data.token);
                localStorage.setItem('ace_user', JSON.stringify(response.data.user));
            }

            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'OTP verification failed' };
        }
    },
};

export default authService;
