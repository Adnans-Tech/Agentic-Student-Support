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
 * Get user role — prioritizes the session's activeRole,
 * falls back to the database-assigned role from JWT.
 */
export const getUserRole = () => {
    const activeRole = authService.getActiveRole();
    if (activeRole) return activeRole;

    const user = getCurrentUser();
    if (!user) return null;
    
    // Explicitly check for admin privilege as a high-priority fallback
    if (user.is_admin) return 'admin';
    
    return user.role || 'student';
};

/**
 * Check if user has specific role.
 * Explicitly checks against the active session role.
 */
export const hasRole = (role) => {
    const activeRole = getUserRole();
    return activeRole === role;
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
 * Check if user has admin privileges (regardless of current mode)
 */
export const hasAdminPrivileges = () => {
    const user = getCurrentUser();
    return user?.is_admin === true;
};

/**
 * Check if user is currently in Admin Mode
 */
export const isAdmin = () => {
    return getUserRole() === 'admin';
};

/**
 * Get redirect path based on the user's active session role
 */
export const getDefaultRoute = () => {
    const role = getUserRole();
    
    if (role === 'admin') return '/admin/dashboard';
    if (role === 'faculty') return '/faculty/dashboard';
    if (role === 'student') return '/student/dashboard';
    
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
