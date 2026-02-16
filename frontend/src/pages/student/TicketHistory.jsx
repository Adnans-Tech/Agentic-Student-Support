/**
 * Ticket History
 * View all support tickets with filtering and close functionality
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import studentService from '../../services/studentService';
import { getCurrentUser } from '../../utils/auth';
import { pageTransition, staggerContainer, staggerItem } from '../../animations/variants';
import { LoadingState, EmptyState } from '../../components/dashboard/DashboardComponents';
import styles from './TicketHistory.module.css';

const TicketHistory = () => {
    const user = getCurrentUser();
    const [tickets, setTickets] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('all');
    const [closingTicketId, setClosingTicketId] = useState(null);
    const [showConfirmDialog, setShowConfirmDialog] = useState(false);
    const [ticketToClose, setTicketToClose] = useState(null);
    const [closeAllMode, setCloseAllMode] = useState(false);

    useEffect(() => {
        loadTickets();
    }, []);

    const loadTickets = async () => {
        try {
            const response = await studentService.getStudentTickets(user.email);
            if (response.success) {
                setTickets(response.tickets || []);
            }
        } catch (error) {
            console.error('Failed to load tickets:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleCloseTicket = (ticket) => {
        setTicketToClose(ticket);
        setCloseAllMode(false);
        setShowConfirmDialog(true);
    };

    const handleCloseAllTickets = () => {
        setTicketToClose(null);
        setCloseAllMode(true);
        setShowConfirmDialog(true);
    };

    const confirmClose = async () => {
        try {
            if (closeAllMode) {
                setClosingTicketId('all');
                const response = await studentService.closeAllTickets();
                if (response.success) {
                    // Update all open tickets to closed
                    setTickets(prev => prev.map(t =>
                        ['open', 'in progress', 'assigned'].includes(t.status?.toLowerCase())
                            ? { ...t, status: 'Closed' }
                            : t
                    ));
                }
            } else if (ticketToClose) {
                const ticketId = ticketToClose.id || ticketToClose.ticket_id;
                setClosingTicketId(ticketId);
                const response = await studentService.closeTicket(ticketId);
                if (response.success) {
                    // Update ticket status locally
                    setTickets(prev => prev.map(t =>
                        (t.id === ticketId || t.ticket_id === ticketId)
                            ? { ...t, status: 'Closed' }
                            : t
                    ));
                }
            }
        } catch (error) {
            console.error('Failed to close ticket:', error);
            alert(error.error || 'Failed to close ticket. Please try again.');
        } finally {
            setClosingTicketId(null);
            setShowConfirmDialog(false);
            setTicketToClose(null);
            setCloseAllMode(false);
        }
    };

    const cancelClose = () => {
        setShowConfirmDialog(false);
        setTicketToClose(null);
        setCloseAllMode(false);
    };

    const canCloseTicket = (status) => {
        const lowerStatus = status?.toLowerCase();
        return lowerStatus === 'open' || lowerStatus === 'in progress' || lowerStatus === 'assigned';
    };

    const openTicketsCount = tickets.filter(t => canCloseTicket(t.status)).length;

    const Status = ({ status }) => {
        const getStatusStyle = () => {
            switch (status?.toLowerCase()) {
                case 'open':
                    return styles.statusOpen;
                case 'in progress':
                    return styles.statusProgress;
                case 'resolved':
                    return styles.statusResolved;
                case 'closed':
                    return styles.statusClosed;
                default:
                    return styles.statusOpen;
            }
        };

        return <span className={`${styles.status} ${getStatusStyle()}`}>{status || 'Open'}</span>;
    };

    const Priority = ({ priority }) => {
        const getPriorityStyle = () => {
            switch (priority?.toLowerCase()) {
                case 'high':
                case 'urgent':
                    return styles.priorityHigh;
                case 'medium':
                    return styles.priorityMedium;
                case 'low':
                    return styles.priorityLow;
                default:
                    return styles.priorityMedium;
            }
        };

        return <span className={`${styles.priority} ${getPriorityStyle()}`}>{priority || 'Medium'}</span>;
    };

    const filteredTickets = tickets.filter(ticket => {
        if (filter === 'all') return true;
        return ticket.status?.toLowerCase() === filter;
    });

    return (
        <motion.div className={styles.ticketHistoryPage} {...pageTransition}>
            <div className={styles.container}>
                {/* Header */}
                <div className={styles.header}>
                    <div>
                        <h1 className={styles.title}>📋 Ticket History</h1>
                        <p className={styles.subtitle}>Track all your support tickets</p>
                    </div>
                    <div className={styles.headerActions}>
                        {openTicketsCount > 0 && (
                            <motion.button
                                className={styles.closeAllButton}
                                whileHover={{ scale: 1.05 }}
                                whileTap={{ scale: 0.95 }}
                                onClick={handleCloseAllTickets}
                                disabled={closingTicketId === 'all'}
                            >
                                {closingTicketId === 'all' ? 'Closing...' : `Close All (${openTicketsCount})`}
                            </motion.button>
                        )}
                        <Link to="/student/tickets/new" className={styles.createButton}>
                            <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                                + New Ticket
                            </motion.button>
                        </Link>
                    </div>
                </div>

                {/* Filters */}
                <div className={styles.filters}>
                    {['all', 'open', 'in progress', 'resolved', 'closed'].map(status => (
                        <button
                            key={status}
                            className={`${styles.filterButton} ${filter === status ? styles.active : ''}`}
                            onClick={() => setFilter(status)}
                        >
                            {status.charAt(0).toUpperCase() + status.slice(1)}
                        </button>
                    ))}
                </div>

                {loading ? (
                    <LoadingState />
                ) : filteredTickets.length === 0 ? (
                    <EmptyState
                        icon="🎫"
                        message={filter === 'all' ? 'No tickets yet. Raise your first ticket!' : `No ${filter} tickets.`}
                    />
                ) : (
                    <motion.div className={styles.ticketsList} variants={staggerContainer} initial="hidden" animate="visible">
                        {filteredTickets.map((ticket) => (
                            <motion.div key={ticket.id || ticket.ticket_id} className={styles.ticketCard} variants={staggerItem}>
                                <div className={styles.ticketHeader}>
                                    <div className={styles.ticketInfo}>
                                        <h3 className={styles.ticketId}>#{ticket.id || ticket.ticket_id}</h3>
                                        <p className={styles.ticketCategory}>{ticket.category} • {ticket.sub_category}</p>
                                    </div>
                                    <div className={styles.ticketBadges}>
                                        <Status status={ticket.status} />
                                        <Priority priority={ticket.priority} />
                                    </div>
                                </div>

                                <p className={styles.ticketDescription}>{ticket.description}</p>

                                <div className={styles.ticketFooter}>
                                    <div className={styles.ticketMeta}>
                                        <span className={styles.ticketDepartment}>🏢 {ticket.department}</span>
                                        <span className={styles.ticketDate}>
                                            📅 {new Date(ticket.created_at).toLocaleDateString()}
                                        </span>
                                    </div>
                                    {canCloseTicket(ticket.status) && (
                                        <motion.button
                                            className={styles.closeButton}
                                            whileHover={{ scale: 1.05 }}
                                            whileTap={{ scale: 0.95 }}
                                            onClick={() => handleCloseTicket(ticket)}
                                            disabled={closingTicketId === (ticket.id || ticket.ticket_id)}
                                        >
                                            {closingTicketId === (ticket.id || ticket.ticket_id) ? 'Closing...' : 'Close Ticket'}
                                        </motion.button>
                                    )}
                                </div>
                            </motion.div>
                        ))}
                    </motion.div>
                )}
            </div>

            {/* Confirmation Dialog */}
            {showConfirmDialog && (
                <div className={styles.dialogOverlay} onClick={cancelClose}>
                    <motion.div
                        className={styles.confirmDialog}
                        initial={{ scale: 0.9, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className={styles.dialogIcon}>⚠️</div>
                        <h3 className={styles.dialogTitle}>
                            {closeAllMode ? 'Close All Tickets?' : 'Close Ticket?'}
                        </h3>
                        <p className={styles.dialogMessage}>
                            {closeAllMode
                                ? `Are you sure you want to close all ${openTicketsCount} open ticket(s)? This action cannot be undone.`
                                : `Are you sure you want to close ticket #${ticketToClose?.id || ticketToClose?.ticket_id}? This action cannot be undone.`
                            }
                        </p>
                        <div className={styles.dialogActions}>
                            <button className={styles.cancelButton} onClick={cancelClose}>
                                Cancel
                            </button>
                            <button className={styles.confirmButton} onClick={confirmClose}>
                                {closeAllMode ? 'Close All' : 'Close Ticket'}
                            </button>
                        </div>
                    </motion.div>
                </div>
            )}
        </motion.div>
    );
};

export default TicketHistory;
