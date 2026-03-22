import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import facultyService from '../../services/facultyService';
import { pageTransition } from '../../animations/variants';
import { LoadingState, EmptyState } from '../../components/dashboard/DashboardComponents';
import styles from './EmailInbox.module.css';

const EmailInbox = () => {
    const [emails, setEmails] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('all');

    // Detail view state
    const [selectedEmailId, setSelectedEmailId] = useState(null);
    const [replyIntent, setReplyIntent] = useState('');

    // Email Notification Modal state
    const [showReplyModal, setShowReplyModal] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [previewData, setPreviewData] = useState(null);
    const [editedSubject, setEditedSubject] = useState('');
    const [editedBody, setEditedBody] = useState('');

    useEffect(() => {
        loadEmails();
    }, [filter]);

    const loadEmails = async () => {
        try {
            setLoading(true);
            const response = await facultyService.getEmails(filter);
            if (response.success) {
                setEmails(response.emails || []);
            }
        } catch (error) {
            console.error('Failed to load emails:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleSelectEmail = async (emailId) => {
        setSelectedEmailId(emailId);
        setReplyIntent('');

        // Fetch full email details if message is missing (optimization if needed)
        const email = emails.find(e => e.id === emailId);
        if (email && !email.message) {
            try {
                const response = await facultyService.getEmail(emailId);
                if (response.success && response.email) {
                    setEmails(prev => prev.map(e => e.id === emailId ? response.email : e));
                }
            } catch (error) {
                console.error('Failed to fetch full email:', error);
            }
        }
    };

    // === Reply Flow ===

    const handleOpenReplyModal = async (regenerate = false) => {
        if (!replyIntent.trim()) {
            alert('Please enter your reply intent before previewing.');
            return;
        }

        const emailData = emails.find(e => e.id === selectedEmailId);
        if (!emailData) return;

        try {
            setIsGenerating(true);
            if (!regenerate) setShowReplyModal(true);

            const data = {
                preview_mode: true,
                student_email: emailData.student_email,
                reply_intent: replyIntent,
                original_subject: emailData.subject,
                regenerate: regenerate
            };

            const response = await facultyService.replyEmail(selectedEmailId, data);
            if (response.success) {
                setPreviewData(response);
                setEditedSubject(response.subject);
                setEditedBody(response.body);
            }
        } catch (error) {
            alert(error.error || 'Failed to generate email preview');
            if (!regenerate) setShowReplyModal(false);
        } finally {
            setIsGenerating(false);
        }
    };

    const handleSendReply = async () => {
        const emailData = emails.find(e => e.id === selectedEmailId);
        if (!emailData) return;

        try {
            setIsGenerating(true);
            const data = {
                preview_mode: false,
                student_email: emailData.student_email,
                subject: editedSubject,
                body: editedBody
            };

            const response = await facultyService.replyEmail(selectedEmailId, data);
            if (response.success) {
                alert('Reply sent successfully!');
                setShowReplyModal(false);
                setReplyIntent('');

                // Update local state to show replied status
                setEmails(prev => prev.map(e =>
                    e.id === selectedEmailId ? { ...e, status: 'Replied' } : e
                ));
            } else {
                alert(response.error || 'Failed to send reply');
            }
        } catch (error) {
            alert(error.error || 'Failed to send reply');
        } finally {
            setIsGenerating(false);
        }
    };

    // === Render Helpers ===

    const getBadgeClass = (status, direction) => {
        if (direction === 'sent') return styles.badgeSent;
        const s = status?.toLowerCase();
        if (s === 'replied') return styles.badgeReplied;
        if (s === 'failed') return styles.badgeFailed;
        return styles.badgeSent;
    };

    // No client-side filtering needed — backend handles it
    const filteredEmails = emails;

    const selectedEmail = emails.find(e => e.id === selectedEmailId);
    const hasReplied = selectedEmail?.status?.toLowerCase() === 'replied';

    return (
        <motion.div className={styles.emailInboxPage} {...pageTransition}>
            <div className={styles.header}>
                <h1 className={styles.title}>📬 Email Inbox</h1>
                <p className={styles.subtitle}>View and reply to emails from students</p>
            </div>

            <div className={styles.content}>
                {/* Master List */}
                <div className={styles.emailList}>
                    <div className={styles.filters}>
                        {['all', 'pending', 'replied', 'sent'].map(f => (
                            <button
                                key={f}
                                className={`${styles.filterButton} ${filter === f ? styles.active : ''}`}
                                onClick={() => setFilter(f)}
                            >
                                {f === 'all' ? '📋 All (This Month)' :
                                    f === 'sent' ? '📤 Sent' :
                                        f.charAt(0).toUpperCase() + f.slice(1)}
                            </button>
                        ))}
                    </div>

                    <div className={styles.listScroll}>
                        {loading ? (
                            <LoadingState />
                        ) : filteredEmails.length === 0 ? (
                            <EmptyState icon="📭" message="No emails found" />
                        ) : (
                            filteredEmails.map(e => (
                                <div
                                    key={e.id}
                                    className={`${styles.emailItem} ${selectedEmailId === e.id ? styles.selected : ''}`}
                                    onClick={() => handleSelectEmail(e.id)}
                                >
                                    <div className={styles.emailItemHeader}>
                                        <span className={styles.emailSender}>
                                            {e.direction === 'sent' ? `📤 To: ${e.student_email}` : `📥 ${e.student_name}`}
                                        </span>
                                        <span className={styles.emailDate}>
                                            {new Date(e.timestamp).toLocaleDateString()}
                                        </span>
                                    </div>
                                    <div className={styles.emailSubject}>{e.subject}</div>
                                    <div className={styles.badges}>
                                        <span className={`${styles.badge} ${getBadgeClass(e.status, e.direction)}`}>
                                            {e.direction === 'sent' ? 'Sent' : (e.status?.toLowerCase() === 'sent' ? 'New' : e.status)}
                                        </span>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* Detail Panel */}
                <div className={styles.emailDetail}>
                    {!selectedEmail ? (
                        <div className={styles.emptyDetail}>Select an email to view details</div>
                    ) : (
                        <>
                            <div className={styles.detailHeader}>
                                <div className={styles.detailTitleRow}>
                                    <h2 className={styles.detailTitle}>{selectedEmail.subject}</h2>
                                    <span className={`${styles.badge} ${getBadgeClass(selectedEmail.status, selectedEmail.direction)}`}>
                                        {selectedEmail.direction === 'sent' ? '📤 Sent' : (selectedEmail.status?.toLowerCase() === 'sent' ? '📥 Received' : selectedEmail.status)}
                                    </span>
                                </div>
                                <div className={styles.detailMeta}>
                                    {selectedEmail.direction === 'sent' ? (
                                        <>
                                            <span>📤 <strong>To:</strong> {selectedEmail.student_email}</span>
                                            <span>📅 <strong>Sent:</strong> {new Date(selectedEmail.timestamp).toLocaleString()}</span>
                                        </>
                                    ) : (
                                        <>
                                            <span>👤 <strong>From:</strong> {selectedEmail.student_name} ({selectedEmail.student_email})</span>
                                            {selectedEmail.student_roll_no && <span>🆔 <strong>Roll No:</strong> {selectedEmail.student_roll_no}</span>}
                                            {selectedEmail.student_department && <span>🏢 <strong>Dept:</strong> {selectedEmail.student_department}</span>}
                                            {selectedEmail.student_year && <span>🎓 <strong>Year:</strong> {selectedEmail.student_year}</span>}
                                            <span>📅 <strong>Date:</strong> {new Date(selectedEmail.timestamp).toLocaleString()}</span>
                                        </>
                                    )}
                                </div>
                            </div>

                            <div className={styles.detailBody}>
                                <div className={styles.messageBox}>
                                    {selectedEmail.message || "Loading message content..."}

                                    {selectedEmail.attachment_name && (
                                        <div className={styles.attachmentList}>
                                            <div className={styles.attachmentItem}>📎 {selectedEmail.attachment_name}</div>
                                        </div>
                                    )}
                                </div>

                                {/* Reply Form — only for received emails */}
                                {selectedEmail.direction === 'sent' ? (
                                    <div className={styles.replyForm} style={{ opacity: 0.7 }}>
                                        <h3>📤 Outgoing Email</h3>
                                        <p style={{ color: 'var(--color-text-secondary)' }}>This email was sent by you.</p>
                                    </div>
                                ) : !hasReplied ? (
                                    <div className={styles.replyForm}>
                                        <h3>Reply with AI Agent</h3>
                                        <textarea
                                            className={styles.replyInput}
                                            placeholder="Briefly describe what you want the reply to say (e.g., 'Acknowledge the email, tell them I am available on Friday at 2 PM, and ask them to confirm'). The AI will draft a professional email."
                                            value={replyIntent}
                                            onChange={(e) => setReplyIntent(e.target.value)}
                                        />
                                        <div className={styles.replyActions}>
                                            <button
                                                className={styles.replyBtn}
                                                onClick={() => handleOpenReplyModal(false)}
                                                disabled={!replyIntent.trim() || isGenerating}
                                            >
                                                ✨ Preview AI Reply
                                            </button>
                                        </div>
                                    </div>
                                ) : (
                                    <div className={styles.replyForm} style={{ opacity: 0.7 }}>
                                        <h3>✅ Replied</h3>
                                        <p style={{ color: 'var(--color-text-secondary)' }}>You have already replied to this email.</p>
                                    </div>
                                )}
                            </div>
                        </>
                    )}
                </div>
            </div>

            {/* Email Notification Modal */}
            <AnimatePresence>
                {showReplyModal && (
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
                                <h2>Reply Preview (AI Draft)</h2>
                                <span style={{ cursor: 'pointer', fontSize: '24px' }} onClick={() => setShowReplyModal(false)}>×</span>
                            </div>

                            <div className={styles.modalBody}>
                                {isGenerating && !previewData ? (
                                    <div style={{ textAlign: 'center', padding: '40px' }}>
                                        <div className="agent-spinner" style={{ margin: '0 auto 16px' }}></div>
                                        <p style={{ color: 'var(--color-text-secondary)' }}>Agent is drafting your reply...</p>
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
                                <button className={styles.cancelBtn} onClick={() => setShowReplyModal(false)} disabled={isGenerating}>Cancel</button>
                                <button className={styles.regenerateBtn} onClick={() => handleOpenReplyModal(true)} disabled={isGenerating}>
                                    {isGenerating && previewData ? 'Regenerating...' : '🔄 Regenerate Draft'}
                                </button>
                                <button className={styles.sendBtn} onClick={handleSendReply} disabled={isGenerating}>
                                    {isGenerating && previewData ? 'Sending...' : 'Send Reply'}
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
};

export default EmailInbox;
