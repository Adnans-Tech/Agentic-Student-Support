import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import facultyService from '../../services/facultyService';
import { pageTransition } from '../../animations/variants';
import { LoadingState, EmptyState } from '../../components/dashboard/DashboardComponents';
import styles from './ViewTickets.module.css';

const ViewTickets = () => {
    const [tickets, setTickets] = useState([]);
    const [department, setDepartment] = useState('');
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('all');

    // Detail view state
    const [selectedTicketId, setSelectedTicketId] = useState(null);
    const [resolutionNote, setResolutionNote] = useState('');
    const [isResolving, setIsResolving] = useState(false);

    // Email Notification Modal state
    const [showNotifyModal, setShowNotifyModal] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [previewData, setPreviewData] = useState(null);
    const [editedSubject, setEditedSubject] = useState('');
    const [editedBody, setEditedBody] = useState('');

    useEffect(() => {
        loadTickets();
    }, []);

    const loadTickets = async () => {
        try {
            setLoading(true);
            const response = await facultyService.getTickets();
            if (response.success) {
                setTickets(response.tickets || []);
                setDepartment(response.department || '');
            }
        } catch (error) {
            console.error('Failed to load tickets:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleSelectTicket = (ticketId) => {
        setSelectedTicketId(ticketId);
        // Reset inputs
        const ticket = tickets.find(t => t.ticket_id === ticketId);
        setResolutionNote(ticket?.resolution_note || '');
    };

    const handleResolve = async () => {
        if (!resolutionNote.trim()) {
            alert("Please enter a resolution note.");
            return;
        }
        try {
            setIsResolving(true);
            const response = await facultyService.resolveTicket(selectedTicketId, resolutionNote);
            if (response.success) {
                // Re-fetch tickets from backend to get full server-side data
                await loadTickets();
            }
        } catch (error) {
            alert(error.error || 'Failed to resolve ticket');
        } finally {
            setIsResolving(false);
        }
    };

    // === Email Notification Flow ===

    const handleOpenNotifyModal = async (regenerate = false) => {
        const ticket = tickets.find(t => t.ticket_id === selectedTicketId);
        if (!ticket) return;

        try {
            setIsGenerating(true);
            if (!regenerate) setShowNotifyModal(true); // show modal immediately, show loading inside

            const data = {
                preview_mode: true,
                student_email: ticket.student_email,
                resolution_note: resolutionNote,
                regenerate: regenerate
            };

            const response = await facultyService.notifyStudent(selectedTicketId, data);
            if (response.success) {
                setPreviewData(response);
                setEditedSubject(response.subject);
                setEditedBody(response.body);
            }
        } catch (error) {
            alert(error.error || 'Failed to generate email preview');
            if (!regenerate) setShowNotifyModal(false);
        } finally {
            setIsGenerating(false);
        }
    };

    const handleSendNotification = async () => {
        const ticket = tickets.find(t => t.ticket_id === selectedTicketId);
        if (!ticket) return;

        try {
            setIsGenerating(true);
            const data = {
                preview_mode: false,
                student_email: ticket.student_email,
                subject: editedSubject,
                body: editedBody
            };

            const response = await facultyService.notifyStudent(selectedTicketId, data);
            if (response.success) {
                alert('Email notification sent successfully!');
                setShowNotifyModal(false);
            } else {
                alert(response.error || 'Failed to send email');
            }
        } catch (error) {
            alert(error.error || 'Failed to send email');
        } finally {
            setIsGenerating(false);
        }
    };


    // === Render Helpers ===

    const getBadgeClass = (status) => {
        const s = status?.toLowerCase();
        if (s === 'open') return styles.badgeOpen;
        if (s === 'in progress') return styles.badgeProgress;
        if (s === 'resolved') return styles.badgeResolved;
        if (s === 'closed') return styles.badgeClosed;
        return styles.badgeOpen;
    };

    const getPriorityClass = (priority) => {
        const p = priority?.toLowerCase();
        if (p === 'high' || p === 'urgent') return styles.badgeHigh;
        if (p === 'medium') return styles.badgeMedium;
        if (p === 'low') return styles.badgeLow;
        return styles.badgeMedium;
    };

    const filteredTickets = tickets.filter(t => {
        if (filter === 'all') return true;
        if (filter === 'active') return ['open', 'in progress', 'assigned'].includes(t.status?.toLowerCase());
        return t.status?.toLowerCase() === filter;
    });

    const selectedTicket = tickets.find(t => t.ticket_id === selectedTicketId);
    const isEditingResolution = selectedTicket && !['resolved', 'closed'].includes(selectedTicket.status?.toLowerCase());

    return (
        <motion.div className={styles.ticketInboxPage} {...pageTransition}>
            <div className={styles.header}>
                <h1 className={styles.title}>📋 Ticket Inbox {department && `— ${department}`}</h1>
                <p className={styles.subtitle}>Manage support tickets assigned to your department</p>
            </div>

            <div className={styles.content}>
                {/* Master List */}
                <div className={styles.ticketList}>
                    <div className={styles.filters}>
                        {['all', 'active', 'resolved', 'closed'].map(f => (
                            <button
                                key={f}
                                className={`${styles.filterButton} ${filter === f ? styles.active : ''}`}
                                onClick={() => setFilter(f)}
                            >
                                {f.charAt(0).toUpperCase() + f.slice(1)}
                            </button>
                        ))}
                    </div>

                    <div className={styles.listScroll}>
                        {loading ? (
                            <LoadingState />
                        ) : filteredTickets.length === 0 ? (
                            <EmptyState icon="📥" message="No tickets found" />
                        ) : (
                            filteredTickets.map(t => (
                                <div
                                    key={t.ticket_id}
                                    className={`${styles.ticketItem} ${selectedTicketId === t.ticket_id ? styles.selected : ''}`}
                                    onClick={() => handleSelectTicket(t.ticket_id)}
                                >
                                    <div className={styles.ticketItemHeader}>
                                        <span className={styles.ticketItemId}>#{t.ticket_id}</span>
                                        <span className={styles.ticketItemDate}>
                                            {new Date(t.created_at).toLocaleDateString()}
                                        </span>
                                    </div>
                                    <div className={styles.ticketItemCategory}>{t.category} • {t.sub_category}</div>
                                    <div className={styles.ticketItemTitle}>{t.description}</div>
                                    <div className={styles.badges}>
                                        <span className={`${styles.badge} ${getBadgeClass(t.status)}`}>{t.status || 'Open'}</span>
                                        <span className={`${styles.badge} ${getPriorityClass(t.priority)}`}>{t.priority}</span>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* Detail Panel */}
                <div className={styles.ticketDetail}>
                    {!selectedTicket ? (
                        <div className={styles.emptyDetail}>Select a ticket to view details</div>
                    ) : (
                        <>
                            <div className={styles.detailHeader}>
                                <div className={styles.detailTitleRow}>
                                    <h2 className={styles.detailTitle}>Ticket #{selectedTicket.ticket_id}</h2>
                                    <div className={styles.badges}>
                                        <span className={`${styles.badge} ${getBadgeClass(selectedTicket.status)}`}>{selectedTicket.status || 'Open'}</span>
                                        <span className={`${styles.badge} ${getPriorityClass(selectedTicket.priority)}`}>{selectedTicket.priority}</span>
                                    </div>
                                </div>
                                <div className={styles.detailMeta}>
                                    <span>👤 <strong>Student:</strong> {selectedTicket.student_email}</span>
                                    <span>📂 <strong>Category:</strong> {selectedTicket.category} • {selectedTicket.sub_category}</span>
                                    <span>📅 <strong>Created:</strong> {new Date(selectedTicket.created_at).toLocaleString()}</span>
                                </div>
                            </div>

                            <div className={styles.detailBody}>
                                <div className={styles.descriptionBox}>
                                    <h4 style={{ marginBottom: '12px', color: 'var(--color-text-secondary)' }}>Description</h4>
                                    {selectedTicket.description}
                                </div>

                                {/* Resolution Status */}
                                {!isEditingResolution ? (
                                    <div className={styles.resolvedState}>
                                        <h4>✅ Resolution Log</h4>
                                        <p>{selectedTicket.resolution_note || "No resolution note provided."}</p>
                                        <div className={styles.resolvedMeta}>
                                            Resolved by {selectedTicket.resolved_by || 'System'} on {selectedTicket.resolved_at ? new Date(selectedTicket.resolved_at).toLocaleString() : 'Unknown Date'}
                                        </div>
                                    </div>
                                ) : (
                                    <div className={styles.resolutionForm}>
                                        <h3>Resolve Ticket</h3>
                                        <textarea
                                            className={styles.resolutionInput}
                                            placeholder="Enter resolution notes or troubleshooting steps taken... (Required for resolution)"
                                            value={resolutionNote}
                                            onChange={(e) => setResolutionNote(e.target.value)}
                                        />
                                        <div className={styles.resolutionActions}>
                                            <button
                                                className={styles.resolveBtn}
                                                onClick={handleResolve}
                                                disabled={isResolving || !resolutionNote.trim()}
                                            >
                                                {isResolving ? 'Resolving...' : 'Mark as Resolved'}
                                            </button>

                                            <button
                                                className={styles.notifyBtn}
                                                onClick={() => handleOpenNotifyModal(false)}
                                                disabled={isResolving || !resolutionNote.trim()}
                                            >
                                                ✉️ Notify Student by Email
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </>
                    )}
                </div>
            </div>

            {/* Email Notification Modal */}
            <AnimatePresence>
                {showNotifyModal && (
                    <motion.div
                        className={styles.modalOverlay}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                    >
                        <motion.div
                            className={styles.modalContent}
                            initial={{ scale: 0.95, y: 20 }}
                            animate={{ scale: 1, y: 0 }}
                            exit={{ scale: 0.95, y: 20 }}
                        >
                            <div className={styles.modalHeader}>
                                <h2>Email Agent Preview</h2>
                                <span style={{ cursor: 'pointer', fontSize: '24px' }} onClick={() => setShowNotifyModal(false)}>×</span>
                            </div>

                            <div className={styles.modalBody}>
                                {isGenerating && !previewData ? (
                                    <div style={{ textAlign: 'center', padding: '40px' }}>
                                        <div className="agent-spinner" style={{ margin: '0 auto 16px' }}></div>
                                        <p style={{ color: 'var(--color-text-secondary)' }}>Agent is drafting email...</p>
                                    </div>
                                ) : (
                                    <>
                                        <div>
                                            <label style={{ display: 'block', marginBottom: '8px', color: 'var(--color-text-secondary)' }}>Subject</label>
                                            <input
                                                type="text"
                                                className={styles.modalInput}
                                                value={editedSubject}
                                                onChange={(e) => setEditedSubject(e.target.value)}
                                                disabled={isGenerating}
                                            />
                                        </div>
                                        <div>
                                            <label style={{ display: 'block', marginBottom: '8px', color: 'var(--color-text-secondary)' }}>Message Body</label>
                                            <textarea
                                                className={styles.modalTextarea}
                                                value={editedBody}
                                                onChange={(e) => setEditedBody(e.target.value)}
                                                disabled={isGenerating}
                                            />
                                        </div>
                                    </>
                                )}
                            </div>

                            <div className={styles.modalFooter}>
                                <button className={styles.cancelBtn} onClick={() => setShowNotifyModal(false)} disabled={isGenerating}>Cancel</button>
                                <button className={styles.regenerateBtn} onClick={() => handleOpenNotifyModal(true)} disabled={isGenerating}>
                                    {isGenerating && previewData ? 'Regenerating...' : '🔄 Regenerate Draft'}
                                </button>
                                <button className={styles.resolveBtn} onClick={handleSendNotification} disabled={isGenerating}>
                                    {isGenerating && previewData ? 'Sending...' : 'Send Email'}
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
};

export default ViewTickets;
