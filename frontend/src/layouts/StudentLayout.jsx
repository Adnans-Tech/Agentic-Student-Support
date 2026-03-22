/**
 * Shared Layout — Used for both Student & Faculty
 * Wraps pages with role-aware sidebar navigation
 */

import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from '../components/navigation/Sidebar';
import AnnouncementBanner from '../components/common/AnnouncementBanner';
import styles from './StudentLayout.module.css';

const StudentLayout = () => {
    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

    return (
        <div className={styles.layout}>
            <Sidebar isCollapsed={isSidebarCollapsed} toggleSidebar={() => setIsSidebarCollapsed(!isSidebarCollapsed)} />
            <main className={`${styles.main} ${isSidebarCollapsed ? styles.collapsed : ''}`}>
                <AnnouncementBanner />
                <Outlet />
            </main>
        </div>
    );
};

export default StudentLayout;
