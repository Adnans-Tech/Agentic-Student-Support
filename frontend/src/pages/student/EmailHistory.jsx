/**
 * Email History
 * View all sent emails to faculty/admin
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import studentService from '../../services/studentService';
import { getCurrentUser } from '../../utils/auth';
import { pageTransition, staggerContainer, staggerItem } from '../../animations/variants';
import { LoadingState, EmptyState } from '../../components/dashboard/DashboardComponents';
import styles from './EmailHistory.module.css';

const EmailHistory = () => {
    const user = getCurrentUser();
    const [emails, setEmails] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadEmailHistory();
    }, []);

    const loadEmailHistory = async () => {
        try {
            const response = await studentService.getEmailHistory(user.email);
            if (response.success) {
                setEmails(response.history || []);
            }
        } catch (error) {
            console.error('Failed to load email history:', error);
        } finally {
            setLoading(false);
        }
    };

    const getStatusColor = (status) => {
        switch (status?.toLowerCase()) {
            case 'sent':
            case 'success':
                return styles.success;
            case 'pending':
                return styles.warning;
            case 'failed':
            case 'error':
                return styles.error;
            default:
                return '';
        }
    };

    return (
        <motion.div className={styles.emailHistoryPage} {...pageTransition}>
            <div className={styles.container}>
                {/* Header */}
                <div className={styles.header}>
                    <h1 className={styles.title}>📬 Email History</h1>
                    <p className={styles.subtitle}>
                        View all your sent emails
                    </p>
                </div>

                {loading ? (
                    <LoadingState />
                ) : emails.length === 0 ? (
                    <EmptyState
                        icon="📭"
                        message="No emails sent yet. Start by contacting faculty or sending an email!"
                    />
                ) : (
                    <motion.div
                        className={styles.emailList}
                        variants={staggerContainer}
                        initial="hidden"
                        animate="visible"
                    >
                        {emails.map((email, index) => (
                            <motion.div
                                key={email.id || index}
                                className={styles.emailCard}
                                variants={staggerItem}
                            >
                                <div className={styles.emailHeader}>
                                    <div className={styles.emailInfo}>
                                        <h3 className={styles.emailRecipient}>
                                            To: {email.faculty_name || email.recipient || 'Unknown'}
                                        </h3>
                                        <p className={styles.emailSubject}>
                                            {email.subject || 'No subject'}
                                        </p>
                                    </div>
                                    <span className={`${styles.emailStatus} ${getStatusColor(email.status)}`}>
                                        {email.status || 'Sent'}
                                    </span>
                                </div>

                                <div className={styles.emailFooter}>
                                    <span className={styles.emailDate}>
                                        📅 {new Date(email.created_at || email.date).toLocaleDateString('en-US', {
                                            year: 'numeric',
                                            month: 'short',
                                            day: 'numeric',
                                            hour: '2-digit',
                                            minute: '2-digit'
                                        })}
                                    </span>
                                </div>
                            </motion.div>
                        ))}
                    </motion.div>
                )}
            </div>
        </motion.div>
    );
};

export default EmailHistory;
