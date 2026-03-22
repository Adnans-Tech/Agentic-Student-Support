/**
 * Student Dashboard — Figma Design
 * Welcome banner with gradient, stats cards, daily limits, CGPA display
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import {
    Ticket, Clock, CheckCircle2, ChevronRight,
    Mail, Shield, TrendingUp
} from 'lucide-react';
import studentService from '../../services/studentService';
import { getCurrentUser } from '../../utils/auth';
import { pageTransition, staggerContainer, staggerItem } from '../../animations/variants';
import styles from './Dashboard.module.css';

const StudentDashboard = () => {
    const user = getCurrentUser();
    const [stats, setStats] = useState(null);
    const [trend, setTrend] = useState([]);
    const [loading, setLoading] = useState(true);
    const [cgpa, setCgpa] = useState('');

    useEffect(() => {
        loadStats();
        // Load CGPA from localStorage
        const key = `ace-cgpa-${user?.roll_number || 'default'}`;
        const saved = localStorage.getItem(key);
        if (saved) setCgpa(saved);
    }, []);

    const loadStats = async () => {
        try {
            const response = await studentService.getStats();
            if (response.success) {
                setStats(response.stats);
                if (response.trend) setTrend(response.trend);
            }
        } catch (error) {
            console.error('Failed to load stats:', error);
        } finally {
            setLoading(false);
        }
    };

    const pendingTasks = stats?.tickets_open || 0;
    const totalTickets = stats?.tickets_total || 0;
    const openTickets = stats?.tickets_open || 0;
    const resolvedTickets = stats?.tickets_closed || 0;

    // Daily limits — derived from stats if available
    const emailsMax = stats?.limits?.emails_max || 5;
    const ticketsMax = stats?.limits?.tickets_max || 3;
    const emailsRemaining = stats?.limits?.emails_remaining ?? emailsMax;
    const ticketsRemaining = stats?.limits?.tickets_remaining ?? ticketsMax;

    const maxChartVal = Math.max(1, ...trend.map(d => Math.max(d.tickets, d.emails)));
    const getDayLabel = (dateStr) => {
        const d = new Date(dateStr + 'T00:00:00');
        return ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][d.getDay()];
    };

    return (
        <motion.div className={styles.dashboard} {...pageTransition}>
            {/* === WELCOME BANNER === */}
            <motion.div
                className={styles.welcomeBanner}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
            >
                <div className={styles.welcomeContent}>
                    <h1 className={styles.welcomeTitle}>
                        Welcome back, {user?.full_name || user?.name}!
                    </h1>
                    <p className={styles.welcomeSubtitle}>
                        {pendingTasks > 0
                            ? `You have ${pendingTasks} pending task${pendingTasks > 1 ? 's' : ''} for today.`
                            : 'You\'re all caught up! No pending tasks.'}
                    </p>
                    <Link to="/student/tickets" className={styles.viewTasksBtn}>
                        View Tasks <ChevronRight size={16} />
                    </Link>
                </div>
                <div className={styles.welcomeStats}>
                    {cgpa && (
                        <div className={styles.welcomeStatBox}>
                            <span className={styles.welcomeStatValue}>{cgpa}</span>
                            <span className={styles.welcomeStatLabel}>CGPA</span>
                        </div>
                    )}
                </div>
            </motion.div>

            {/* === MAIN CONTENT GRID === */}
            <div className={styles.mainGrid}>
                {/* Left: Stats Cards */}
                <div className={styles.statsSection}>
                    <motion.div
                        className={styles.statsGrid}
                        variants={staggerContainer}
                        initial="hidden"
                        animate="visible"
                    >
                        <motion.div className={styles.statCard} variants={staggerItem}>
                            <div className={`${styles.statIconWrap} ${styles.statBlue}`}>
                                <Ticket size={22} />
                            </div>
                            <span className={styles.statValue}>{loading ? '—' : totalTickets}</span>
                            <span className={styles.statLabel}>TOTAL TICKETS</span>
                        </motion.div>

                        <motion.div className={styles.statCard} variants={staggerItem}>
                            <div className={`${styles.statIconWrap} ${styles.statOrange}`}>
                                <Clock size={22} />
                            </div>
                            <span className={styles.statValue}>{loading ? '—' : openTickets}</span>
                            <span className={styles.statLabel}>OPEN TICKETS</span>
                        </motion.div>

                        <motion.div className={styles.statCard} variants={staggerItem}>
                            <div className={`${styles.statIconWrap} ${styles.statGreen}`}>
                                <CheckCircle2 size={22} />
                            </div>
                            <span className={styles.statValue}>{loading ? '—' : resolvedTickets}</span>
                            <span className={styles.statLabel}>RESOLVED</span>
                        </motion.div>
                    </motion.div>

                    {/* Activity Overview */}
                    <motion.div
                        className={styles.activityCard}
                        initial={{ opacity: 0, y: 15 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 }}
                    >
                        <div className={styles.activityHeader}>
                            <h3><TrendingUp size={18} /> Activity Overview</h3>
                            <span className={styles.activityPeriod}>This Week</span>
                        </div>
                        <div className={styles.activityContent}>
                            {trend && trend.length > 0 ? (
                                <div style={{ width: '100%' }}>
                                    <div className={styles.chartArea}>
                                        {trend.map((day, i) => (
                                            <div key={i} className={styles.chartBar}>
                                                <div className={styles.barGroup}>
                                                    <div className={`${styles.bar} ${styles.tickets}`}
                                                        style={{ height: `${(day.tickets / maxChartVal) * 100}px` }} title={`${day.tickets} Tickets`} />
                                                    <div className={`${styles.bar} ${styles.emails}`}
                                                        style={{ height: `${(day.emails / maxChartVal) * 100}px` }} title={`${day.emails} Emails`} />
                                                </div>
                                                <span className={styles.chartLabel}>{getDayLabel(day.date)}</span>
                                            </div>
                                        ))}
                                    </div>
                                    <div className={styles.chartLegend}>
                                        <div className={styles.legendItem}><span className={`${styles.legendDot} ${styles.orange}`} /> Tickets</div>
                                        <div className={styles.legendItem}><span className={`${styles.legendDot} ${styles.green}`} /> Emails</div>
                                    </div>
                                </div>
                            ) : (
                                <p className={styles.activityPlaceholder}>
                                    No activity data available for this week.
                                </p>
                            )}
                        </div>
                    </motion.div>
                </div>

                {/* Right: Daily Limits */}
                <motion.div
                    className={styles.limitsCard}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.25 }}
                >
                    <h3 className={styles.limitsTitle}>
                        <Shield size={18} /> Daily Limits
                    </h3>

                    <div className={styles.limitRow}>
                        <div className={styles.limitInfo}>
                            <span>Emails Remaining</span>
                            <span className={styles.limitCount}>{emailsRemaining}/{emailsMax}</span>
                        </div>
                        <div className={styles.limitBar}>
                            <div
                                className={`${styles.limitFill} ${styles.limitGreen}`}
                                style={{ width: `${(emailsRemaining / emailsMax) * 100}%` }}
                            />
                        </div>
                    </div>

                    <div className={styles.limitRow}>
                        <div className={styles.limitInfo}>
                            <span>Tickets Remaining</span>
                            <span className={styles.limitCount}>{ticketsRemaining}/{ticketsMax}</span>
                        </div>
                        <div className={styles.limitBar}>
                            <div
                                className={`${styles.limitFill} ${styles.limitOrange}`}
                                style={{ width: `${(ticketsRemaining / ticketsMax) * 100}%` }}
                            />
                        </div>
                    </div>

                    <Link to="/student/profile" className={styles.limitsLink}>
                        View Detailed Limits
                    </Link>
                </motion.div>
            </div>
        </motion.div>
    );
};

export default StudentDashboard;
