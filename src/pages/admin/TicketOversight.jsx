/**
 * Admin Ticket Oversight
 * Global view of all support tickets with force-close capability
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Ticket, XCircle, Search, Calendar, FolderHeart } from 'lucide-react';
import adminService from '../../services/adminService';
import styles from './TicketOversight.module.css';

const fadeInUp = { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } };

const TicketOversight = () => {
    const [tickets, setTickets] = useState([]);
    const [loading, setLoading] = useState(true);
    const [statusFilter, setStatusFilter] = useState('all');
    const [actionLoading, setActionLoading] = useState(null);

    useEffect(() => {
        fetchTickets();
    }, [statusFilter]);

    const fetchTickets = async () => {
        try {
            setLoading(true);
            const res = await adminService.getTickets(statusFilter);
            if (res.success) {
                setTickets(res.data);
            } else {
                alert(res.error || 'Failed to fetch tickets');
            }
        } catch (err) {
            console.error(err);
            alert('Server error loading tickets');
        } finally {
            setLoading(false);
        }
    };

    const handleForceClose = async (ticketId) => {
        if (!window.confirm(`Are you sure you want to FORCE CLOSE ticket ${ticketId}?\nThis cannot be undone.`)) {
            return;
        }

        try {
            setActionLoading(ticketId);
            const res = await adminService.forceCloseTicket(ticketId);
            if (res.success) {
                // Remove or update the ticket in the local list
                if (statusFilter === 'all' || statusFilter === 'Closed') {
                    setTickets(prev => prev.map(t =>
                        t.ticket_id === ticketId ? { ...t, status: 'Closed', closed_at: new Date().toISOString() } : t
                    ));
                } else {
                    setTickets(prev => prev.filter(t => t.ticket_id !== ticketId));
                }
            } else {
                alert(res.error || 'Failed to close ticket');
            }
        } catch (err) {
            console.error(err);
            alert('Server error closing ticket');
        } finally {
            setActionLoading(null);
        }
    };

    const formatDate = (dateString) => {
        if (!dateString) return '—';
        return new Date(dateString).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    };

    return (
        <motion.div className={styles.pageContainer} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>

            <div className={styles.pageHeader}>
                <div className={styles.headerTitle}>
                    <h1>Ticket Oversight</h1>
                    <p>Global monitor of all student support requests</p>
                </div>
            </div>

            <div className={styles.filterRow}>
                {['all', 'Open', 'In Progress', 'Resolved', 'Closed'].map(status => (
                    <button
                        key={status}
                        className={`${styles.filterBtn} ${statusFilter === status ? styles.active : ''}`}
                        onClick={() => setStatusFilter(status)}
                    >
                        {status.charAt(0).toUpperCase() + status.slice(1)}
                    </button>
                ))}
            </div>

            <motion.div className={styles.ticketsCard} variants={fadeInUp} initial="initial" animate="animate">
                {loading ? (
                    <div className={styles.fullPageLoader}>
                        <div className={styles.spinner} />
                    </div>
                ) : (
                    <div className={styles.tableWrapper}>
                        <table className={styles.ticketsTable}>
                            <thead>
                                <tr>
                                    <th>Status</th>
                                    <th>Ticket details</th>
                                    <th>Department</th>
                                    <th>Student</th>
                                    <th>Created On</th>
                                    <th style={{ textAlign: 'right' }}>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {tickets.length === 0 ? (
                                    <tr className={styles.emptyRow}>
                                        <td colSpan="6">
                                            <FolderHeart size={48} style={{ opacity: 0.3, marginBottom: '12px' }} />
                                            <div>No {statusFilter !== 'all' ? statusFilter.toLowerCase() : ''} tickets found.</div>
                                        </td>
                                    </tr>
                                ) : tickets.map(ticket => (
                                    <tr key={ticket.ticket_id}>
                                        <td>
                                            <span className={`${styles.statusBadge} ${styles[(ticket.status || '').toLowerCase().replace(/\s+/g, '')] || ''}`}>
                                                {ticket.status || 'Unknown'}
                                            </span>
                                        </td>
                                        <td>
                                            <div className={styles.ticketId}>{ticket.ticket_id}</div>
                                            <div className={styles.ticketSubject}>{ticket.category || '—'}</div>
                                            <div className={styles.ticketDesc} title={ticket.description || ''}>
                                                {ticket.description || '—'}
                                            </div>
                                        </td>
                                        <td>
                                            <span className={styles.metaLabel}>{ticket.department}</span>
                                        </td>
                                        <td>
                                            <div className={styles.userInfo}>
                                                <span className={styles.userName}>{ticket.student_name || 'Student'}</span>
                                                <span className={styles.userEmail}>{ticket.student_email}</span>
                                            </div>
                                        </td>
                                        <td style={{ color: 'var(--color-text-secondary)', fontSize: '13px' }}>
                                            {formatDate(ticket.created_at)}
                                        </td>
                                        <td style={{ textAlign: 'right' }}>
                                            {ticket.status !== 'Closed' && (
                                                <button
                                                    className={styles.forceCloseBtn}
                                                    onClick={() => handleForceClose(ticket.ticket_id)}
                                                    disabled={actionLoading === ticket.ticket_id}
                                                    title="Force close this ticket bypassing regular resolution"
                                                >
                                                    <XCircle size={14} /> Close
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </motion.div>
        </motion.div>
    );
};

export default TicketOversight;
