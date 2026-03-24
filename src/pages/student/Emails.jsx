/**
 * Send Emails - AI-Powered Email Composition + History (Tabbed)
 * Compose tab: Figma-style two-panel layout with form & preview
 * History tab: Inline email history list
 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Clock, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';
import studentService from '../../services/studentService';
import { getCurrentUser } from '../../utils/auth';
import { pageTransition, modalBackdrop, modalContent, staggerContainer, staggerItem } from '../../animations/variants';
import { LoadingState, EmptyState } from '../../components/dashboard/DashboardComponents';
import Toast from '../../components/common/Toast';
import styles from './Emails.module.css';

const Emails = () => {
    const user = getCurrentUser();
    const [activeTab, setActiveTab] = useState('compose');

    // --- Compose State ---
    const [formData, setFormData] = useState({
        toEmail: '', purpose: '', tone: 'semi-formal', length: 'medium'
    });
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [preview, setPreview] = useState(null);
    const [showPreview, setShowPreview] = useState(false);
    const [loading, setLoading] = useState(false);
    const [sending, setSending] = useState(false);
    const [toast, setToast] = useState({ show: false, message: '', type: 'info' });

    // --- History State ---
    const [emails, setEmails] = useState([]);
    const [historyLoading, setHistoryLoading] = useState(false);
    const [expandedId, setExpandedId] = useState(null);

    const toneOptions = [
        { value: 'formal', label: 'Formal' },
        { value: 'semi-formal', label: 'Semi-formal' },
        { value: 'friendly', label: 'Friendly' },
        { value: 'urgent', label: 'Urgent' }
    ];

    const lengthOptions = [
        { value: 'short', label: 'Short' },
        { value: 'medium', label: 'Medium' },
        { value: 'detailed', label: 'Detailed' }
    ];

    // Load history when tab switches
    useEffect(() => {
        if (activeTab === 'history' && emails.length === 0) {
            loadEmailHistory();
        }
    }, [activeTab]);

    const loadEmailHistory = async () => {
        setHistoryLoading(true);
        try {
            const response = await studentService.getEmailHistory(user.email);
            if (response.success) setEmails(response.history || []);
        } catch (error) {
            console.error('Failed to load email history:', error);
        } finally {
            setHistoryLoading(false);
        }
    };

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleGeneratePreview = async () => {
        if (!formData.toEmail || !formData.purpose) {
            setToast({ show: true, message: 'Please fill in all required fields', type: 'error' });
            return;
        }
        if (formData.purpose.split(' ').length < 5) {
            setToast({ show: true, message: 'Please provide more detail (minimum 5 words)', type: 'error' });
            return;
        }

        setLoading(true);
        setToast({ show: false, message: '', type: 'info' });
        try {
            const response = await studentService.generateEmailPreview({
                to_email: formData.toEmail, purpose: formData.purpose,
                tone: formData.tone, length: formData.length,
                student_name: user.full_name || user.name, preview_mode: true
            });
            if (response.success) {
                setPreview({ subject: response.subject, body: response.body, editable: true });
                setShowPreview(true);
            } else {
                setToast({ show: true, message: response.error || 'Failed to generate preview', type: 'error' });
            }
        } catch (error) {
            setToast({ show: true, message: error.message || 'Failed to generate email', type: 'error' });
        } finally {
            setLoading(false);
        }
    };

    const handleEditPreview = (field, value) => setPreview(prev => ({ ...prev, [field]: value }));

    const handleSendEmail = async () => {
        if (!preview) return;
        setSending(true);
        setToast({ show: false, message: '', type: 'info' });
        try {
            const response = await studentService.sendEmail({
                to_email: formData.toEmail, subject: preview.subject,
                body: preview.body, purpose: formData.purpose, preview_mode: false
            });
            if (response.success) {
                setToast({ show: true, message: '✅ Email sent successfully!', type: 'success' });
                setShowPreview(false);
                setFormData({ toEmail: '', purpose: '', tone: 'semi-formal', length: 'medium' });
                setPreview(null);
                // Refresh history
                setEmails([]);
            } else {
                setToast({ show: true, message: response.error || 'Failed to send email', type: 'error' });
            }
        } catch (error) {
            setToast({ show: true, message: error.message || 'Failed to send email', type: 'error' });
        } finally {
            setSending(false);
        }
    };

    const getStatusColor = (status) => {
        switch (status?.toLowerCase()) {
            case 'sent': case 'success': return styles.success;
            case 'pending': return styles.warning;
            case 'failed': case 'error': return styles.danger;
            default: return '';
        }
    };

    const wordCount = formData.purpose.split(' ').filter(w => w).length;

    return (
        <motion.div className={styles.emailPage} {...pageTransition}>
            <Toast
                message={toast.message} type={toast.type} show={toast.show}
                onClose={() => setToast({ ...toast, show: false })}
            />

            {/* === TAB BAR === */}
            <div className={styles.tabBar}>
                <button
                    className={`${styles.tab} ${activeTab === 'compose' ? styles.tabActive : ''}`}
                    onClick={() => setActiveTab('compose')}
                >
                    <Send size={16} /> Compose Email
                </button>
                <button
                    className={`${styles.tab} ${activeTab === 'history' ? styles.tabActive : ''}`}
                    onClick={() => setActiveTab('history')}
                >
                    <Clock size={16} /> Email History
                </button>
            </div>

            {/* === COMPOSE TAB === */}
            {activeTab === 'compose' && (
                <div className={styles.composeLayout}>
                    {/* Left Panel: Compose Form */}
                    <div className={styles.composeCard}>
                        <div className={styles.composeHeader}>
                            <Sparkles size={24} className={styles.composeIcon} />
                            <div>
                                <h2>AI-powered email composer</h2>
                                <span className={styles.statusBadge}>● Ready</span>
                            </div>
                        </div>

                        {/* Recipient Email */}
                        <div className={styles.formGroup}>
                            <label className={styles.label}>
                                Recipient Email <span className={styles.required}>*</span>
                            </label>
                            <input
                                type="email" name="toEmail"
                                value={formData.toEmail} onChange={handleChange}
                                placeholder="professor@college.edu"
                                disabled={loading || sending}
                                className={styles.input}
                            />
                        </div>

                        {/* Purpose */}
                        <div className={styles.formGroup}>
                            <label className={styles.label}>
                                Email Purpose <span className={styles.required}>*</span>
                            </label>
                            <textarea
                                name="purpose" value={formData.purpose}
                                onChange={handleChange}
                                placeholder="Describe what you want to communicate (minimum 5 words)..."
                                disabled={loading || sending} rows={5}
                                className={styles.textarea}
                            />
                            <div className={styles.wordCountRow}>
                                <small>Min. 5 words required</small>
                                <small>{wordCount}/5 words</small>
                            </div>
                        </div>

                        {/* Advanced Options */}
                        <button onClick={() => setShowAdvanced(!showAdvanced)} className={styles.advancedToggle}>
                            {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            Advanced Options
                        </button>

                        <AnimatePresence>
                            {showAdvanced && (
                                <motion.div
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    exit={{ opacity: 0, height: 0 }}
                                    className={styles.advancedOptions}
                                >
                                    <div className={styles.optionsGrid}>
                                        <div className={styles.formGroup}>
                                            <label className={styles.label}>Tone</label>
                                            <select name="tone" value={formData.tone} onChange={handleChange}
                                                disabled={loading || sending} className={styles.select}>
                                                {toneOptions.map(opt => (
                                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                                ))}
                                            </select>
                                        </div>
                                        <div className={styles.formGroup}>
                                            <label className={styles.label}>Length</label>
                                            <select name="length" value={formData.length} onChange={handleChange}
                                                disabled={loading || sending} className={styles.select}>
                                                {lengthOptions.map(opt => (
                                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Generate Preview Button */}
                        <motion.button
                            onClick={handleGeneratePreview}
                            disabled={loading || sending}
                            whileHover={{ scale: loading ? 1 : 1.01 }}
                            whileTap={{ scale: loading ? 1 : 0.99 }}
                            className={styles.generateButton}
                        >
                            {loading ? '✨ Generating Preview...' : 'Generate Preview →'}
                        </motion.button>
                    </div>

                    {/* Right Panel: Preview */}
                    <div className={styles.previewCard}>
                        {preview && showPreview ? (
                            <div className={styles.previewContent}>
                                <h3 className={styles.previewTitle}>Email Preview</h3>
                                <div className={styles.formGroup}>
                                    <label className={styles.label}>Subject</label>
                                    <input type="text" value={preview.subject}
                                        onChange={(e) => handleEditPreview('subject', e.target.value)}
                                        disabled={sending} className={styles.input} />
                                </div>
                                <div className={styles.formGroup}>
                                    <label className={styles.label}>Email Body</label>
                                    <textarea value={preview.body}
                                        onChange={(e) => handleEditPreview('body', e.target.value)}
                                        disabled={sending} rows={14} className={styles.textarea} />
                                </div>
                                <div className={styles.previewActions}>
                                    <button
                                        onClick={() => setShowPreview(false)}
                                        disabled={sending} className={styles.cancelButton}
                                    >Cancel</button>
                                    <motion.button
                                        onClick={handleSendEmail} disabled={sending}
                                        whileHover={{ scale: sending ? 1 : 1.01 }}
                                        className={styles.sendButton}
                                    >
                                        {sending ? '📤 Sending...' : '✉️ Send Email'}
                                    </motion.button>
                                </div>
                            </div>
                        ) : (
                            <div className={styles.previewEmpty}>
                                <Sparkles size={48} className={styles.previewEmptyIcon} />
                                <h3>No Preview Yet</h3>
                                <p>Fill out the details on the left to let AI compose your email.</p>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* === HISTORY TAB === */}
            {activeTab === 'history' && (
                <div className={styles.historyContainer}>
                    {historyLoading ? (
                        <LoadingState />
                    ) : emails.length === 0 ? (
                        <EmptyState icon="📭" message="No emails sent yet. Start by composing an email!" />
                    ) : (
                        <motion.div className={styles.historyList} variants={staggerContainer} initial="hidden" animate="visible">
                            {emails.map((email, index) => (
                                <motion.div
                                    key={email.id || index}
                                    className={`${styles.historyCard} ${expandedId === index ? styles.historyCardExpanded : ''}`}
                                    variants={staggerItem}
                                    onClick={() => setExpandedId(expandedId === index ? null : index)}
                                >
                                    <div className={styles.historyCardHeader}>
                                        <div>
                                            <h4>To: {email.faculty_name || email.recipient || 'Unknown'}
                                                {(email.faculty_id === 'external' || (!email.faculty_name && email.recipient)) && (
                                                    <span className={styles.externalBadge}>External</span>
                                                )}
                                            </h4>
                                            <p className={styles.historySubject}>📌 {email.subject || 'No subject'}</p>
                                        </div>
                                        <div className={styles.historyMeta}>
                                            <span className={`${styles.statusBadgeSmall} ${getStatusColor(email.status)}`}>
                                                {email.status || 'Sent'}
                                            </span>
                                            {expandedId === index ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                                        </div>
                                    </div>

                                    <AnimatePresence>
                                        {expandedId === index && email.message && (
                                            <motion.div className={styles.historyPreview}
                                                initial={{ height: 0, opacity: 0 }}
                                                animate={{ height: 'auto', opacity: 1 }}
                                                exit={{ height: 0, opacity: 0 }}
                                            >
                                                <div className={styles.historyBody}>{email.message}</div>
                                            </motion.div>
                                        )}
                                    </AnimatePresence>

                                    <div className={styles.historyFooter}>
                                        <span>📅 {new Date(email.timestamp || email.created_at || email.date)
                                            .toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                                    </div>
                                </motion.div>
                            ))}
                        </motion.div>
                    )}
                </div>
            )}
        </motion.div>
    );
};

export default Emails;
