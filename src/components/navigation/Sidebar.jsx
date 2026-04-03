/**
 * Sidebar Navigation — Role-Aware (Student & Faculty)
 * Shows different nav items, branding, and accent colors based on user role
 */

import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
    LayoutDashboard,
    MessageCircle,
    Send,
    Ticket,
    Users,
    UserCircle,
    LogOut,
    Menu,
    X,
    Mail,
    Calendar,
    Bot,
    Inbox,
    Megaphone,
    BarChart3,
    ArrowLeftRight,
    ShieldCheck
} from 'lucide-react';
import { getCurrentUser, isAdmin, getUserRole, hasAdminPrivileges } from '../../utils/auth';
import authService from '../../services/authService';
import styles from './Sidebar.module.css';

const API_BASE = import.meta.env.VITE_API_URL || '';

const STUDENT_NAV = [
    { path: '/student/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/student/chat', icon: MessageCircle, label: 'Chat Support' },
    { path: '/student/emails', icon: Send, label: 'Send Email' },
    { path: '/student/tickets/new', icon: Ticket, label: 'Raise Ticket' },
    { path: '/student/contact-faculty', icon: Users, label: 'Contact Faculty' },
    { path: '/student/profile', icon: UserCircle, label: 'My Profile' },
];

const FACULTY_NAV = [
    { path: '/faculty/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/faculty/assistant', icon: Bot, label: 'Faculty Assistant' },
    { path: '/faculty/tickets', icon: Ticket, label: 'Ticket Inbox' },
    { path: '/faculty/inbox', icon: Mail, label: 'Email Inbox' },
    { path: '/faculty/profile', icon: UserCircle, label: 'Profile' },
];

const ADMIN_NAV = [
    { path: '/admin/dashboard', icon: LayoutDashboard, label: 'Admin Dashboard' },
    { path: '/admin/users', icon: Users, label: 'User Directory' },
    { path: '/admin/tickets', icon: Ticket, label: 'Ticket Oversight' },
    { path: '/admin/announcements', icon: Megaphone, label: 'Announcements' },
    { path: '/admin/reports', icon: BarChart3, label: 'System Reports' },
];
const Sidebar = ({ isCollapsed, toggleSidebar }) => {
    const navigate = useNavigate();
    const location = useLocation();
    const user = getCurrentUser();
    
    // Core Role Checks
    const activeRole = getUserRole();
    const isAdminPrivileged = hasAdminPrivileges();
    
    const isFacultyRoute = location.pathname.startsWith('/faculty');
    const isAdminRoute = location.pathname.startsWith('/admin');

    // Navigation setup based on active role
    let navItems = STUDENT_NAV;
    if (activeRole === 'admin') {
        navItems = ADMIN_NAV;
    } else if (activeRole === 'faculty') {
        navItems = FACULTY_NAV;
    }

    const handleLogout = () => {
        authService.logout();
        navigate('/login');
    };

    const handleSwitchRole = () => {
        const nextRole = activeRole === 'admin' ? 'faculty' : 'admin';
        authService.setActiveRole(nextRole);
        navigate(nextRole === 'admin' ? '/admin/dashboard' : '/faculty/dashboard');
    };

    // Build profile photo URL
    let photoUrl = null;
    try {
        const storedUser = JSON.parse(localStorage.getItem('aceUser') || '{}');
        if (storedUser.profile_photo) {
            photoUrl = `${API_BASE}${storedUser.profile_photo}`;
        }
    } catch (err) {
        console.error('Error parsing user data from localStorage:', err);
    }

    const getInitials = (name) => {
        if (!name) return '?';
        return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
    };

    return (
        <aside className={`${styles.sidebar} ${isCollapsed ? styles.collapsed : ''} ${isFacultyRoute ? styles.facultySidebar : ''} ${isAdminRoute ? styles.adminSidebar : ''}`}>
            {/* Toggle Button */}
            <motion.button
                className={styles.toggleButton}
                onClick={toggleSidebar}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
                {isCollapsed ? <Menu size={18} /> : <X size={18} />}
            </motion.button>

            {/* Header: Logo + Brand */}
            <div className={styles.header}>
                <img src="/ace_logo.png" alt="ACE Logo" className={styles.logo} />
                <div className={styles.brandWrapper}>
                    <span className={styles.brandName}>ACE</span>
                </div>
            </div>

            {/* Navigation */}
            <nav className={styles.nav}>
                {navItems.map((item) => {
                    const Icon = item.icon;
                    return (
                        <NavLink
                            key={item.path}
                            to={item.path}
                            className={({ isActive }) =>
                                `${styles.navItem} ${isActive ? styles.active : ''} ${isFacultyRoute && isActive ? styles.facultyActive : ''} ${isAdminRoute && isActive ? styles.adminActive : ''}`
                            }
                        >
                            <div
                                className={styles.navContent}
                                title={isCollapsed ? item.label : undefined}
                            >
                                <Icon className={styles.navIcon} size={20} strokeWidth={2} />
                                <span className={styles.navLabel}>{item.label}</span>
                            </div>
                        </NavLink>
                    );
                })}
            </nav>

            {/* Footer: User Profile + Logout + Switch Role */}
            <div className={styles.footer}>
                {isAdminPrivileged && (
                    <motion.button
                        onClick={handleSwitchRole}
                        className={styles.switchButton}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        title={activeRole === 'admin' ? 'Switch to Faculty Mode' : 'Switch to Admin Mode'}
                    >
                        <ArrowLeftRight size={18} strokeWidth={2} />
                        {!isCollapsed && <span className={styles.switchText}>Switch to {activeRole === 'admin' ? 'Faculty' : 'Admin'}</span>}
                    </motion.button>
                )}
                
                <div className={styles.userFooterSection}>
                    <div className={styles.userSection}>
                        {photoUrl ? (
                            <img src={photoUrl} alt="Profile" className={styles.userAvatar} />
                        ) : (
                            <div className={styles.userAvatarPlaceholder}>
                                {getInitials(user?.full_name || user?.name)}
                            </div>
                        )}
                        <div className={styles.userInfoWrapper}>
                            <span className={styles.userName}>{user?.full_name || user?.name}</span>
                            <span className={styles.userRole}>
                                {activeRole === 'admin' ? 'Admin' : activeRole === 'faculty' ? 'Faculty' : 'Student'}
                            </span>
                        </div>
                    </div>
                    <motion.button
                        onClick={handleLogout}
                        className={styles.logoutButton}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        aria-label="Logout"
                        title="Logout"
                    >
                        <LogOut size={18} strokeWidth={2} />
                    </motion.button>
                </div>
            </div>
        </aside>
    );
};

export default Sidebar;
