/**
 * Dashboard Components
 * Reusable components for dashboard cards and stats
 */

import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import styles from './DashboardComponents.module.css';

// Stats Card
export const StatsCard = ({ icon, label, value, color = 'primary' }) => {
    return (
        <motion.div
            className={`${styles.statsCard} ${styles[color]}`}
            whileHover={{ scale: 1.02, y: -2 }}
            transition={{ duration: 0.2 }}
        >
            <div className={styles.statsIcon}>{icon}</div>
            <div className={styles.statsContent}>
                <h3 className={styles.statsValue}>{value}</h3>
                <p className={styles.statsLabel}>{label}</p>
            </div>
        </motion.div>
    );
};

// Quick Access Card
export const QuickAccessCard = ({ title, description, icon, link, color = 'primary' }) => {
    return (
        <Link to={link} className={styles.quickAccessLink}>
            <motion.div
                className={`${styles.quickAccessCard} ${styles[color]}`}
                whileHover={{ scale: 1.03, y: -3 }}
                whileTap={{ scale: 0.98 }}
                transition={{ duration: 0.2 }}
            >
                <div className={styles.quickAccessIcon}>{icon}</div>
                <div className={styles.quickAccessContent}>
                    <h3 className={styles.quickAccessTitle}>{title}</h3>
                    <p className={styles.quickAccessDesc}>{description}</p>
                </div>
            </motion.div>
        </Link>
    );
};

// Empty State
export const EmptyState = ({ icon, message }) => {
    return (
        <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>{icon}</div>
            <p className={styles.emptyMessage}>{message}</p>
        </div>
    );
};

// Loading State
export const LoadingState = () => {
    return (
        <div className={styles.loadingState}>
            <div className={styles.spinner}></div>
            <p>Loading...</p>
        </div>
    );
};
