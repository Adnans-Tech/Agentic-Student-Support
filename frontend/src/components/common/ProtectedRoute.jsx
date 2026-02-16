/**
 * Protected Route Component
 * Redirects to login if user is not authenticated
 */

import { Navigate } from 'react-router-dom';
import { isAuthenticated, hasRole } from '../../utils/auth';

const ProtectedRoute = ({ children, allowedRoles = [] }) => {
    const isAuth = isAuthenticated();

    // Not authenticated - redirect to login
    if (!isAuth) {
        return <Navigate to="/login" replace />;
    }

    // Check role if specified
    if (allowedRoles.length > 0) {
        const userHasRole = allowedRoles.some(role => hasRole(role));

        if (!userHasRole) {
            // Unauthorized - redirect to appropriate dashboard
            const userRole = hasRole('student') ? 'student' : 'faculty';
            return <Navigate to={`/${userRole}/dashboard`} replace />;
        }
    }

    return children;
};

export default ProtectedRoute;
