/**
 * Admin Reports & Analytics
 * Shows Department-wise Ticket breakdown and Agent Email usage across Roles
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { BarChart3, Mail, Ticket, Users, Building2 } from 'lucide-react';
import adminService from '../../services/adminService';
import styles from './Reports.module.css';

const fadeInUp = { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } };

const Reports = () => {
    const [ticketData, setTicketData] = useState([]);
    const [emailData, setEmailData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchReports = async () => {
            try {
                setLoading(true);
                const [ticketsRes, emailsRes] = await Promise.all([
                    adminService.getTicketReports(),
                    adminService.getEmailUsageReports()
                ]);

                if (ticketsRes.success) setTicketData(ticketsRes.data);
                if (emailsRes.success) setEmailData(emailsRes.data);
            } catch (err) {
                console.error('Error fetching reports:', err);
                alert('Failed to load reports');
            } finally {
                setLoading(false);
            }
        };

        fetchReports();
    }, []);

    if (loading) {
        return (
            <div className={styles.pageContainer}>
                <div className={styles.fullPageLoader}>
                    <div className={styles.spinner} />
                </div>
            </div>
        );
    }

    return (
        <motion.div className={styles.pageContainer} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>

            <div className={styles.pageHeader}>
                <h1>System Reports</h1>
                <p>Analytics on support tickets and AI Email Agent usage</p>
            </div>

            <div className={styles.reportsGrid}>

                {/* Tickets by Department Report */}
                <motion.div className={styles.reportCard} variants={fadeInUp} initial="initial" animate="animate">
                    <div className={styles.cardTitle}>
                        <Ticket className={styles.cardIcon} size={20} />
                        Tickets by Department
                    </div>

                    {ticketData.length === 0 ? (
                        <div className={styles.emptyState}>No ticket data available.</div>
                    ) : (
                        <div className={styles.tableWrapper}>
                            <table className={styles.ticketsTable}>
                                <thead>
                                    <tr>
                                        <th>Department</th>
                                        <th style={{ textAlign: 'center' }}>Open</th>
                                        <th style={{ textAlign: 'center' }}>In Progress</th>
                                        <th style={{ textAlign: 'center' }}>Resolved</th>
                                        <th style={{ textAlign: 'center' }}>Closed</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {ticketData.map((row, idx) => (
                                        <tr key={idx}>
                                            <td className={styles.deptName}>{row.department}</td>
                                            <td style={{ textAlign: 'center' }}>
                                                <span className={`${styles.badge} ${styles.open}`}>{row.open ?? 0}</span>
                                            </td>
                                            <td style={{ textAlign: 'center' }}>
                                                <span className={`${styles.badge} ${styles.inProgress}`}>{row.in_progress ?? 0}</span>
                                            </td>
                                            <td style={{ textAlign: 'center' }}>
                                                <span className={`${styles.badge} ${styles.resolved}`}>{row.resolved ?? 0}</span>
                                            </td>
                                            <td style={{ textAlign: 'center' }}>
                                                <span className={`${styles.badge} ${styles.closed}`}>{row.closed ?? 0}</span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </motion.div>

                {/* Email Agent Usage Report */}
                <motion.div className={styles.reportCard} variants={fadeInUp} initial="initial" animate="animate" transition={{ delay: 0.1 }}>
                    <div className={styles.cardTitle}>
                        <Mail className={styles.cardIcon} size={20} />
                        AI Email Agent Usage
                    </div>

                    {!emailData ? (
                        <div className={styles.emptyState}>No email analytics available.</div>
                    ) : (
                        <div className={styles.emailStatsContainer}>

                            {/* Student Stats */}
                            <div className={styles.emailStatGroup}>
                                <div className={styles.statRole}>
                                    <Users size={16} /> Students
                                </div>
                                <div className={styles.statNumber}>{emailData.student_total}</div>
                                <div className={styles.statLabel}>Total Emails Exchanged</div>

                                <div className={styles.statRow}>
                                    <span>Last 7 Days</span>
                                    <span>{emailData.student_last7days} emails</span>
                                </div>
                            </div>

                            {/* Faculty Stats */}
                            <div className={styles.emailStatGroup}>
                                <div className={styles.statRole}>
                                    <Building2 size={16} /> Faculty
                                </div>
                                <div className={styles.statNumber}>{emailData.faculty_total}</div>
                                <div className={styles.statLabel}>Total Emails Exchanged</div>

                                <div className={styles.statRow}>
                                    <span>Last 7 Days</span>
                                    <span>{emailData.faculty_last7days} emails</span>
                                </div>
                            </div>

                        </div>
                    )}
                </motion.div>

            </div>

        </motion.div>
    );
};

export default Reports;
