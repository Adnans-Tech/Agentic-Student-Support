/**
 * Protected Route Component
 * Redirects to login if user is not authenticated
 */

import { Navigate } from 'react-router-dom';
import { isAuthenticated, hasRole, getDefaultRoute } from '../../utils/auth';

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
            return <Navigate to={getDefaultRoute()} replace />;
        }
    }

    return children;
};

export default ProtectedRoute;
