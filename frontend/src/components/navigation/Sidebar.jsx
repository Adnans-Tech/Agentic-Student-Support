/**
 * Student Sidebar Navigation
 * Fixed sidebar with navigation links and user info
 * Now with collapse/expand functionality and Lucide React icons
 */

import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Home,
    MessageCircle,
    Mail,
    Ticket,
    ClipboardList,
    UserCircle,
    Inbox,
    Users,
    Power,
    Menu,
    X
} from 'lucide-react';
import { getCurrentUser } from '../../utils/auth';
import authService from '../../services/authService';
import styles from './Sidebar.module.css';

const Sidebar = () => {
    const navigate = useNavigate();
    const user = getCurrentUser();
    const [isCollapsed, setIsCollapsed] = useState(false);

    const handleLogout = () => {
        authService.logout();
        navigate('/login');
    };

    const toggleSidebar = () => {
        setIsCollapsed(!isCollapsed);
    };

    const navItems = [
        { path: '/student/dashboard', icon: Home, label: 'Dashboard' },
        { path: '/student/chat', icon: MessageCircle, label: 'Chat Support' },
        { path: '/student/emails', icon: Mail, label: 'Send Email' },
        { path: '/student/tickets/new', icon: Ticket, label: 'Raise Ticket' },
        { path: '/student/tickets', icon: ClipboardList, label: 'Ticket History', end: true },
        { path: '/student/contact-faculty', icon: Users, label: 'Contact Faculty' },
        { path: '/student/email-history', icon: Inbox, label: 'Email History' },
        { path: '/student/profile', icon: UserCircle, label: 'My Profile' },
    ];

    return (
        <aside className={`${styles.sidebar} ${isCollapsed ? styles.collapsed : ''}`}>
            {/* Toggle Button */}
            <motion.button
                className={styles.toggleButton}
                onClick={toggleSidebar}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
                {isCollapsed ? <Menu size={20} /> : <X size={20} />}
            </motion.button>

            {/* Header */}
            <div className={styles.header}>
                <img src="/ace_logo.png" alt="ACE Logo" className={styles.logo} />
                <AnimatePresence>
                    {!isCollapsed && (
                        <motion.div
                            className={styles.userInfo}
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.2 }}
                        >
                            <h3 className={styles.userName}>{user?.full_name || user?.name}</h3>
                            <p className={styles.userRoll}>{user?.roll_number}</p>
                            <span className={styles.userBadge}>Student</span>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            {/* Navigation */}
            <nav className={styles.nav}>
                {navItems.map((item) => {
                    const Icon = item.icon;
                    return (
                        <NavLink
                            key={item.path}
                            to={item.path}
                            end={item.end}
                            className={({ isActive }) =>
                                `${styles.navItem} ${isActive ? styles.active : ''}`
                            }
                        >
                            <motion.div
                                className={styles.navContent}
                                whileHover={{ x: 4 }}
                                whileTap={{ scale: 0.98 }}
                            >
                                <Icon className={styles.navIcon} size={20} strokeWidth={2} />
                                <span className={styles.navLabel}>{item.label}</span>
                            </motion.div>
                        </NavLink>
                    );
                })}
            </nav>

            {/* Footer - Logout */}
            <div className={styles.footer}>
                <motion.button
                    onClick={handleLogout}
                    className={styles.logoutButton}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    aria-label="Logout"
                    title="Logout"
                >
                    <Power size={20} strokeWidth={2} />
                </motion.button>
            </div>
        </aside>
    );
};

export default Sidebar;
