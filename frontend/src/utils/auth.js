/**
 * Auth Helper Utilities
 */

import authService from '../services/authService';

/**
 * Check if user is authenticated
 */
export const isAuthenticated = () => {
    return authService.isAuthenticated();
};

/**
 * Get current user
 */
export const getCurrentUser = () => {
    return authService.getUser();
};

/**
 * Get user role
 */
export const getUserRole = () => {
    const user = getCurrentUser();
    return user?.role || null;
};

/**
 * Check if user has specific role
 */
export const hasRole = (role) => {
    const userRole = getUserRole();
    return userRole === role;
};

/**
 * Check if user is student
 */
export const isStudent = () => {
    return hasRole('student');
};

/**
 * Check if user is faculty
 */
export const isFaculty = () => {
    return hasRole('faculty');
};

/**
 * Get redirect path based on user role
 */
export const getDefaultRoute = () => {
    if (isStudent()) return '/student/dashboard';
    if (isFaculty()) return '/faculty/dashboard';
    return '/login';
};

/**
 * Format user display name
 */
export const getDisplayName = () => {
    const user = getCurrentUser();
    if (!user) return '';

    if (isStudent()) {
        return user.full_name || user.email;
    }

    if (isFaculty()) {
        return user.name || user.email;
    }

    return user.email;
};

/**
 * Get user initials for avatar
 */
export const getUserInitials = () => {
    const name = getDisplayName();
    if (!name) return 'U';

    const parts = name.split(' ');
    if (parts.length >= 2) {
        return (parts[0][0] + parts[1][0]).toUpperCase();
    }

    return name.substring(0, 2).toUpperCase();
};
