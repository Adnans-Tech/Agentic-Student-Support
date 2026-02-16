/**
 * Student Dashboard
 * Main dashboard with stats and quick access
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Ticket, Clock, CheckCircle2, Mail, MessageCircle, Users } from 'lucide-react';
import studentService from '../../services/studentService';
import { getCurrentUser } from '../../utils/auth';
import { pageTransition, staggerContainer, staggerItem } from '../../animations/variants';
import { StatsCard, QuickAccessCard, LoadingState } from '../../components/dashboard/DashboardComponents';
import styles from './Dashboard.module.css';

const StudentDashboard = () => {
    const user = getCurrentUser();
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadStats();
    }, []);

    const loadStats = async () => {
        try {
            const response = await studentService.getStats();
            if (response.success) {
                setStats(response.stats);
            }
        } catch (error) {
            console.error('Failed to load stats:', error);
        } finally {
            setLoading(false);
        }
    };

    const quickAccessItems = [
        {
            title: 'Chat Support',
            description: 'Ask questions instantly',
            icon: <MessageCircle size={48} strokeWidth={1.5} />,
            link: '/student/chat',
            color: 'primary'
        },
        {
            title: 'Send Email',
            description: 'Email faculty or admin',
            icon: <Mail size={48} strokeWidth={1.5} />,
            link: '/student/emails',
            color: 'info'
        },
        {
            title: 'Raise Ticket',
            description: 'Report an issue',
            icon: <Ticket size={48} strokeWidth={1.5} />,
            link: '/student/tickets/new',
            color: 'warning'
        },
        {
            title: 'Contact Faculty',
            description: 'Browse faculty directory',
            icon: <Users size={48} strokeWidth={1.5} />,
            link: '/student/contact-faculty',
            color: 'success'
        }
    ];

    return (
        <motion.div className={styles.dashboard} {...pageTransition}>
            {/* Header */}
            <div className={styles.header}>
                <div>
                    <h1 className={styles.title}>Welcome back, {user?.full_name || user?.name}!</h1>
                    <p className={styles.subtitle}>
                        {user?.roll_number} • {user?.department}
                    </p>
                </div>
            </div>

            {loading ? (
                <LoadingState />
            ) : (
                <>
                    {/* Stats Cards */}
                    <motion.div
                        className={styles.statsGrid}
                        variants={staggerContainer}
                        initial="hidden"
                        animate="visible"
                    >
                        <motion.div variants={staggerItem}>
                            <StatsCard
                                icon={<Ticket size={32} strokeWidth={2} />}
                                label="Total Tickets"
                                value={stats?.total_tickets || 0}
                                color="primary"
                            />
                        </motion.div>
                        <motion.div variants={staggerItem}>
                            <StatsCard
                                icon={<Clock size={32} strokeWidth={2} />}
                                label="Pending Tickets"
                                value={stats?.pending_tickets || 0}
                                color="warning"
                            />
                        </motion.div>
                        <motion.div variants={staggerItem}>
                            <StatsCard
                                icon={<CheckCircle2 size={32} strokeWidth={2} />}
                                label="Resolved Tickets"
                                value={stats?.resolved_tickets || 0}
                                color="success"
                            />
                        </motion.div>
                        <motion.div variants={staggerItem}>
                            <StatsCard
                                icon={<Mail size={32} strokeWidth={2} />}
                                label="Emails Sent"
                                value={stats?.emails_sent || 0}
                                color="info"
                            />
                        </motion.div>
                    </motion.div>

                    {/* Quick Access */}
                    <div className={styles.section}>
                        <h2 className={styles.sectionTitle}>Quick Access</h2>
                        <motion.div
                            className={styles.quickAccessGrid}
                            variants={staggerContainer}
                            initial="hidden"
                            animate="visible"
                        >
                            {quickAccessItems.map((item, index) => (
                                <motion.div key={item.title} variants={staggerItem}>
                                    <QuickAccessCard {...item} />
                                </motion.div>
                            ))}
                        </motion.div>
                    </div>
                </>
            )}
        </motion.div>
    );
};

export default StudentDashboard;
