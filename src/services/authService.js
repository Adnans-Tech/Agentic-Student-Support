/**
 * Unified Authentication Service
 * Handles all auth API calls: register, login, OTP, logout
 */

import api from './api';

const TOKEN_KEY = 'aceToken';
const USER_KEY = 'aceUser';
const ACTIVE_ROLE_KEY = 'aceActiveRole';

const authService = {

    // =============================================
    // Unified Registration
    // =============================================

    /**
     * Register a new user (student or faculty)
     * @param {Object} data - Registration data including 'role' field
     */
    register: async (data) => {
        try {
            const response = await api.post('/auth/register', data);
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Registration failed' };
        }
    },

    // =============================================
    // OTP
    // =============================================

    /**
     * Send OTP to email
     * @param {string} email
     * @param {boolean} resend - Whether this is a resend request
     */
    sendOTP: async (email, resend = false) => {
        try {
            const response = await api.post('/auth/send-otp', { email, resend });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to send OTP' };
        }
    },

    /**
     * Verify OTP code
     * @param {string} email
     * @param {string} otp
     */
    verifyOTP: async (email, otp) => {
        try {
            const response = await api.post('/auth/verify-otp', { email, otp });
            if (response.data.success && response.data.token) {
                authService.setToken(response.data.token);
                authService.setUser(response.data.user);
            }
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'OTP verification failed' };
        }
    },

    // =============================================
    // Login
    // =============================================

    /**
     * Login with email + password (unified for student & faculty)
     * @param {string} email
     * @param {string} password
     */
    login: async (email, password) => {
        try {
            const response = await api.post('/auth/login', { email, password });
            if (response.data.success && response.data.token) {
                authService.setToken(response.data.token);
                authService.setUser(response.data.user);
            }
            return response.data;
        } catch (error) {
            // Pass through the response data for requires_verification handling
            if (error.response?.data) {
                throw error;
            }
            throw { response: { data: { error: 'Login failed' } } };
        }
    },

    // =============================================
    // Logout
    // =============================================

    logout: async () => {
        try {
            const token = authService.getToken();
            if (token) {
                await api.post('/auth/logout');
            }
        } catch (e) {
            // Ignore errors during logout
        } finally {
            authService.clearAuth();
            window.location.href = '/login';
        }
    },

    // =============================================
    // Change Password
    // =============================================

    /**
     * Change the current user's password
     * @param {string} currentPassword
     * @param {string} newPassword
     * @param {string} confirmNewPassword
     */
    changePassword: async (currentPassword, newPassword, confirmNewPassword) => {
        try {
            const response = await api.post('/auth/change-password', {
                current_password: currentPassword,
                new_password: newPassword,
                confirm_new_password: confirmNewPassword,
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to change password' };
        }
    },

    // =============================================
    // Current User
    // =============================================

    /**
     * Get current authenticated user details
     */
    getCurrentUser: async () => {
        try {
            const response = await api.get('/auth/me');
            if (response.data.success) {
                authService.setUser(response.data.user);
            }
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to get user data' };
        }
    },

    // =============================================
    // Token & Storage Management
    // =============================================

    setToken: (token) => {
        localStorage.setItem(TOKEN_KEY, token);
    },

    getToken: () => {
        return localStorage.getItem(TOKEN_KEY);
    },

    setUser: (user) => {
        localStorage.setItem(USER_KEY, JSON.stringify(user));
    },

    getUser: () => {
        try {
            const user = localStorage.getItem(USER_KEY);
            return user ? JSON.parse(user) : null;
        } catch {
            return null;
        }
    },

    clearAuth: () => {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        localStorage.removeItem(ACTIVE_ROLE_KEY);
    },

    setActiveRole: (role) => {
        if (role) {
            localStorage.setItem(ACTIVE_ROLE_KEY, role);
        }
    },

    getActiveRole: () => {
        return localStorage.getItem(ACTIVE_ROLE_KEY);
    },

    isAuthenticated: () => {
        return !!authService.getToken();
    },

    getUserRole: () => {
        const user = authService.getUser();
        return user?.role || null;
    },
};

export default authService;
