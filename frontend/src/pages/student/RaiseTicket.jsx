/**
 * Raise Ticket + Ticket History (Tabbed)
 * Raise tab: Figma-style form with category, priority pills, description
 * History tab: Ticket list with filtering, close functionality
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Ticket, Clock, Plus, X } from 'lucide-react';
import studentService from '../../services/studentService';
import { getCurrentUser } from '../../utils/auth';
import { pageTransition, staggerContainer, staggerItem } from '../../animations/variants';
import { LoadingState, EmptyState } from '../../components/dashboard/DashboardComponents';
import Toast from '../../components/common/Toast';
import styles from './RaiseTicket.module.css';

const RaiseTicket = () => {
    const user = getCurrentUser();
    const [activeTab, setActiveTab] = useState('raise');

    // === Raise Ticket State ===
    const [categories, setCategories] = useState({});
    const [catLoading, setCatLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [toast, setToast] = useState({ show: false, message: '', type: 'error' });
    const [formData, setFormData] = useState({
        student_email: user?.email || '',
        category: '', sub_category: '', priority: 'Medium', description: '', attachments: []
    });
    const [errors, setErrors] = useState({});

    // === History State ===
    const [tickets, setTickets] = useState([]);
    const [historyLoading, setHistoryLoading] = useState(false);
    const [filter, setFilter] = useState('all');
    const [closingTicketId, setClosingTicketId] = useState(null);
    const [showConfirmDialog, setShowConfirmDialog] = useState(false);
    const [ticketToClose, setTicketToClose] = useState(null);
    const [closeAllMode, setCloseAllMode] = useState(false);

    useEffect(() => { loadCategories(); }, []);

    useEffect(() => {
        if (activeTab === 'history' && tickets.length === 0) loadTickets();
    }, [activeTab]);

    const loadCategories = async () => {
        try {
            const response = await studentService.getTicketCategories();
            setCategories(response.categories || {});
        } catch (error) {
            console.error('Failed to load categories:', error);
        } finally {
            setCatLoading(false);
        }
    };

    const loadTickets = async () => {
        setHistoryLoading(true);
        try {
            const response = await studentService.getStudentTickets(user.email);
            if (response.success) setTickets(response.tickets || []);
        } catch (error) {
            console.error('Failed to load tickets:', error);
        } finally {
            setHistoryLoading(false);
        }
    };

    // === Raise Ticket Handlers ===
    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev, [name]: value,
            ...(name === 'category' && { sub_category: '' })
        }));
        if (errors[name]) setErrors(prev => ({ ...prev, [name]: '' }));
    };

    const validate = () => {
        const newErrors = {};
        if (!formData.category) newErrors.category = 'Category is required';
        if (!formData.sub_category) newErrors.sub_category = 'Subcategory is required';
        if (!formData.priority) newErrors.priority = 'Priority is required';
        if (!formData.description || formData.description.trim().length < 20)
            newErrors.description = 'Description must be at least 20 characters';
        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!validate()) return;
        setSubmitting(true);
        try {
            const response = await studentService.createTicket(formData);
            if (response.success) {
                setToast({ show: true, message: `Ticket ${response.ticket_id} created successfully!`, type: 'success' });
                setFormData({
                    student_email: user?.email || '', category: '',
                    sub_category: '', priority: 'Medium', description: '', attachments: []
                });
                setTickets([]); // force reload
                setTimeout(() => setActiveTab('history'), 1500);
            } else {
                if (response.error === 'duplicate') {
                    setToast({ show: true, message: response.message || 'You already have an open ticket in this category', type: 'error' });
                } else throw new Error(response.error || 'Failed to create ticket');
            }
        } catch (error) {
            setToast({ show: true, message: error.message || 'Failed to create ticket.', type: 'error' });
        } finally {
            setSubmitting(false);
        }
    };

    // === History Handlers ===
    const handleCloseTicket = (ticket) => {
        setTicketToClose(ticket); setCloseAllMode(false); setShowConfirmDialog(true);
    };
    const handleCloseAllTickets = () => {
        setTicketToClose(null); setCloseAllMode(true); setShowConfirmDialog(true);
    };

    const confirmClose = async () => {
        try {
            if (closeAllMode) {
                setClosingTicketId('all');
                const response = await studentService.closeAllTickets();
                if (response.success) {
                    setTickets(prev => prev.map(t =>
                        ['open', 'in progress', 'assigned'].includes(t.status?.toLowerCase())
                            ? { ...t, status: 'Closed' } : t
                    ));
                }
            } else if (ticketToClose) {
                const ticketId = ticketToClose.id || ticketToClose.ticket_id;
                setClosingTicketId(ticketId);
                const response = await studentService.closeTicket(ticketId);
                if (response.success) {
                    setTickets(prev => prev.map(t =>
                        (t.id === ticketId || t.ticket_id === ticketId)
                            ? { ...t, status: 'Closed' } : t
                    ));
                }
            }
        } catch (error) {
            console.error('Failed to close ticket:', error);
        } finally {
            setClosingTicketId(null); setShowConfirmDialog(false);
            setTicketToClose(null); setCloseAllMode(false);
        }
    };

    const cancelClose = () => {
        setShowConfirmDialog(false); setTicketToClose(null); setCloseAllMode(false);
    };

    const canCloseTicket = (status) => {
        const s = status?.toLowerCase();
        return s === 'open' || s === 'in progress' || s === 'assigned';
    };

    const openTicketsCount = tickets.filter(t => canCloseTicket(t.status)).length;
    const currentSubcategories = formData.category ? (categories[formData.category] || []) : [];

    const filteredTickets = tickets.filter(ticket => {
        if (filter === 'all') return true;
        return ticket.status?.toLowerCase() === filter;
    });

    const getStatusStyle = (status) => {
        switch (status?.toLowerCase()) {
            case 'open': return styles.statusOpen;
            case 'in progress': return styles.statusProgress;
            case 'resolved': return styles.statusResolved;
            case 'closed': return styles.statusClosed;
            default: return styles.statusOpen;
        }
    };

    const getPriorityStyle = (priority) => {
        switch (priority?.toLowerCase()) {
            case 'high': case 'urgent': return styles.priorityHigh;
            case 'medium': return styles.priorityMedium;
            case 'low': return styles.priorityLow;
            default: return styles.priorityMedium;
        }
    };

    if (catLoading) return <LoadingState />;

    return (
        <motion.div className={styles.raiseTicketPage} {...pageTransition}>
            <Toast
                message={toast.message} type={toast.type}
                show={toast.show} onClose={() => setToast({ ...toast, show: false })}
            />

            {/* === TAB BAR === */}
            <div className={styles.tabBar}>
                <button
                    className={`${styles.tab} ${activeTab === 'raise' ? styles.tabActive : ''}`}
                    onClick={() => setActiveTab('raise')}
                >
                    <Plus size={16} /> Raise Ticket
                </button>
                <button
                    className={`${styles.tab} ${activeTab === 'history' ? styles.tabActive : ''}`}
                    onClick={() => setActiveTab('history')}
                >
                    <Clock size={16} /> Ticket History
                </button>
            </div>

            {/* === RAISE TICKET TAB === */}
            {activeTab === 'raise' && (
                <div className={styles.formCard}>
                    <div className={styles.formCardHeader}>
                        <Ticket size={24} className={styles.formCardIcon} />
                        <div>
                            <h2>Raise Support Ticket</h2>
                            <p>Describe your issue and we'll help you resolve it</p>
                        </div>
                    </div>

                    <form onSubmit={handleSubmit}>
                        {/* Category */}
                        <div className={styles.formGroup}>
                            <label className={styles.label}>Category *</label>
                            <select name="category" value={formData.category}
                                onChange={handleChange} className={styles.select} disabled={submitting}>
                                <option value="">Select a category</option>
                                {Object.keys(categories).map(cat => (
                                    <option key={cat} value={cat}>{cat}</option>
                                ))}
                            </select>
                            {errors.category && <span className={styles.error}>{errors.category}</span>}
                        </div>

                        {/* Subcategory */}
                        {formData.category && (
                            <div className={styles.formGroup}>
                                <label className={styles.label}>Subcategory *</label>
                                <select name="sub_category" value={formData.sub_category}
                                    onChange={handleChange} className={styles.select} disabled={submitting}>
                                    <option value="">Select a subcategory</option>
                                    {currentSubcategories.map(sub => (
                                        <option key={sub} value={sub}>{sub}</option>
                                    ))}
                                </select>
                                {errors.sub_category && <span className={styles.error}>{errors.sub_category}</span>}
                            </div>
                        )}

                        {/* Priority Pills */}
                        <div className={styles.formGroup}>
                            <label className={styles.label}>Priority *</label>
                            <div className={styles.priorityPills}>
                                {['Low', 'Medium', 'High', 'Urgent'].map(p => (
                                    <button key={p} type="button"
                                        className={`${styles.priorityPill} ${formData.priority === p ? styles.priorityPillActive : ''} ${styles[`pill${p}`]}`}
                                        onClick={() => setFormData(prev => ({ ...prev, priority: p }))}
                                        disabled={submitting}
                                    >{p}</button>
                                ))}
                            </div>
                            {errors.priority && <span className={styles.error}>{errors.priority}</span>}
                        </div>

                        {/* Description */}
                        <div className={styles.formGroup}>
                            <label className={styles.label}>Description * (min. 20 characters)</label>
                            <textarea name="description" value={formData.description}
                                onChange={handleChange} className={styles.textarea}
                                rows={6} placeholder="Describe your issue in detail..."
                                disabled={submitting} />
                            <div className={styles.charCount}>{formData.description.length} characters</div>
                            {errors.description && <span className={styles.error}>{errors.description}</span>}
                        </div>

                        {/* Actions */}
                        <div className={styles.formActions}>
                            <button type="button" className={styles.cancelButton}
                                onClick={() => setActiveTab('history')} disabled={submitting}>
                                Cancel
                            </button>
                            <motion.button type="submit" className={styles.submitButton}
                                disabled={submitting}
                                whileHover={{ scale: submitting ? 1 : 1.01 }}
                                whileTap={{ scale: submitting ? 1 : 0.99 }}>
                                {submitting ? 'Creating Ticket...' : 'Submit Ticket'}
                            </motion.button>
                        </div>
                    </form>
                </div>
            )}

            {/* === HISTORY TAB === */}
            {activeTab === 'history' && (
                <div className={styles.historyContainer}>
                    <div className={styles.historyHeader}>
                        <div className={styles.filterBar}>
                            {['all', 'open', 'in progress', 'resolved', 'closed'].map(status => (
                                <button key={status}
                                    className={`${styles.filterBtn} ${filter === status ? styles.filterActive : ''}`}
                                    onClick={() => setFilter(status)}>
                                    {status.charAt(0).toUpperCase() + status.slice(1)}
                                </button>
                            ))}
                        </div>
                        {openTicketsCount > 0 && (
                            <motion.button className={styles.closeAllBtn}
                                whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                                onClick={handleCloseAllTickets} disabled={closingTicketId === 'all'}>
                                {closingTicketId === 'all' ? 'Closing...' : `Close All (${openTicketsCount})`}
                            </motion.button>
                        )}
                    </div>

                    {historyLoading ? (
                        <LoadingState />
                    ) : filteredTickets.length === 0 ? (
                        <EmptyState icon="🎫"
                            message={filter === 'all' ? 'No tickets yet. Raise your first ticket!' : `No ${filter} tickets.`}
                        />
                    ) : (
                        <motion.div className={styles.ticketsList} variants={staggerContainer} initial="hidden" animate="visible">
                            {filteredTickets.map(ticket => (
                                <motion.div key={ticket.id || ticket.ticket_id}
                                    className={styles.ticketCard} variants={staggerItem}>
                                    <div className={styles.ticketCardHeader}>
                                        <div>
                                            <h4>#{ticket.id || ticket.ticket_id}</h4>
                                            <p>{ticket.category} • {ticket.sub_category}</p>
                                        </div>
                                        <div className={styles.ticketBadges}>
                                            <span className={`${styles.badge} ${getStatusStyle(ticket.status)}`}>
                                                {ticket.status || 'Open'}
                                            </span>
                                            <span className={`${styles.badge} ${getPriorityStyle(ticket.priority)}`}>
                                                {ticket.priority || 'Medium'}
                                            </span>
                                        </div>
                                    </div>
                                    <p className={styles.ticketDesc}>{ticket.description}</p>
                                    <div className={styles.ticketFooter}>
                                        <div className={styles.ticketMeta}>
                                            <span>🏢 {ticket.department}</span>
                                            <span>📅 {new Date(ticket.created_at).toLocaleDateString()}</span>
                                        </div>
                                        {canCloseTicket(ticket.status) && (
                                            <motion.button className={styles.closeTicketBtn}
                                                whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                                                onClick={() => handleCloseTicket(ticket)}
                                                disabled={closingTicketId === (ticket.id || ticket.ticket_id)}>
                                                {closingTicketId === (ticket.id || ticket.ticket_id) ? 'Closing...' : 'Close'}
                                            </motion.button>
                                        )}
                                    </div>
                                </motion.div>
                            ))}
                        </motion.div>
                    )}
                </div>
            )}

            {/* === CONFIRMATION DIALOG === */}
            {showConfirmDialog && (
                <div className={styles.dialogOverlay} onClick={cancelClose}>
                    <motion.div className={styles.confirmDialog}
                        initial={{ scale: 0.9, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        onClick={e => e.stopPropagation()}>
                        <div className={styles.dialogIcon}>⚠️</div>
                        <h3>{closeAllMode ? 'Close All Tickets?' : 'Close Ticket?'}</h3>
                        <p>{closeAllMode
                            ? `Close all ${openTicketsCount} open ticket(s)? This cannot be undone.`
                            : `Close ticket #${ticketToClose?.id || ticketToClose?.ticket_id}? This cannot be undone.`
                        }</p>
                        <div className={styles.dialogActions}>
                            <button className={styles.cancelButton} onClick={cancelClose}>Cancel</button>
                            <button className={styles.confirmBtn} onClick={confirmClose}>
                                {closeAllMode ? 'Close All' : 'Close Ticket'}
                            </button>
                        </div>
                    </motion.div>
                </div>
            )}
        </motion.div>
    );
};

export default RaiseTicket;
