/**
 * Student Layout
 * Wraps student pages with sidebar navigation
 */

import { Outlet } from 'react-router-dom';
import Sidebar from '../components/navigation/Sidebar';
import styles from './StudentLayout.module.css';

const StudentLayout = () => {
    return (
        <div className={styles.layout}>
            <Sidebar />
            <main className={styles.main}>
                <Outlet />
            </main>
        </div>
    );
};

export default StudentLayout;
