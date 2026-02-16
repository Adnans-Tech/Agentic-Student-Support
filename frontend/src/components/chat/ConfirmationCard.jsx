/**
 * Confirmation Card Component
 * Inline confirmation UI for action execution
 * Extended to support email preview with edit mode
 */

import { useState } from 'react';
import { motion } from 'framer-motion';
import styles from './ConfirmationCard.module.css';

const ConfirmationCard = ({ action, summary, details, onConfirm, onCancel, preview }) => {
    const [loading, setLoading] = useState(false);
    const [editMode, setEditMode] = useState(false);
    // For emails: editedSubject = subject, editedBody = body
    // For tickets: editedSubject = title, editedBody = description
    const [editedSubject, setEditedSubject] = useState(
        preview?.subject || preview?.title || ''
    );
    const [editedBody, setEditedBody] = useState(
        preview?.body || preview?.description || ''
    );

    const handleConfirm = async () => {
        setLoading(true);
        // Pass edited content if modified
        const isEmail = action === 'email_preview';
        const isTicket = action === 'ticket_preview';

        if (isEmail && (editedSubject !== preview?.subject || editedBody !== preview?.body)) {
            await onConfirm({ subject: editedSubject, body: editedBody });
        } else if (isTicket && (editedSubject !== preview?.title || editedBody !== preview?.description)) {
            // For tickets, return all fields including edited ones
            await onConfirm({
                category: preview.category,
                sub_category: preview.sub_category,
                priority: preview.priority,
                title: editedSubject,
                description: editedBody
            });
        } else {
            await onConfirm();
        }
        setLoading(false);
    };

    const handleEdit = () => {
        setEditMode(!editMode);
        if (!editMode) {
            // Entering edit mode - initialize with current values
            setEditedSubject(preview?.subject || preview?.title || '');
            setEditedBody(preview?.body || preview?.description || '');
        }
    };

    // Render email preview with edit capability
    if (action === 'email_preview' && preview) {
        return (
            <motion.div
                className={styles.confirmationCard}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
            >
                <div className={styles.iconContainer}>
                    <span className={styles.icon}>✉️</span>
                </div>

                <div className={styles.content}>
                    <h4 className={styles.title}>Email Preview</h4>
                    <p className={styles.summary}>{summary}</p>

                    <div className={styles.emailPreview}>
                        {/* Recipient */}
                        <div className={styles.previewRow}>
                            <span className={styles.previewLabel}>To:</span>
                            <span className={styles.previewValue}>{preview.to}</span>
                        </div>

                        {/* Subject - editable */}
                        <div className={styles.previewRow}>
                            <span className={styles.previewLabel}>Subject:</span>
                            {editMode ? (
                                <input
                                    type="text"
                                    className={styles.editInput}
                                    value={editedSubject}
                                    onChange={(e) => setEditedSubject(e.target.value)}
                                    placeholder="Email subject"
                                />
                            ) : (
                                <span className={styles.previewValue}>{preview.subject}</span>
                            )}
                        </div>

                        {/* Body - editable */}
                        <div className={styles.previewBody}>
                            <span className={styles.previewLabel}>Message:</span>
                            {editMode ? (
                                <div className={styles.editBodyContainer}>
                                    <textarea
                                        className={styles.editTextarea}
                                        value={editedBody}
                                        onChange={(e) => setEditedBody(e.target.value)}
                                        placeholder="Email body"
                                        rows={10}
                                    />
                                    <div className={styles.charCount}>
                                        {editedBody.length} characters
                                    </div>
                                </div>
                            ) : (
                                <div className={styles.bodyPreview}>
                                    {preview.body}
                                </div>
                            )}
                        </div>
                    </div>

                    <div className={styles.buttonGroup}>
                        <motion.button
                            className={`${styles.button} ${styles.editButton}`}
                            onClick={handleEdit}
                            disabled={loading}
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                        >
                            {editMode ? '👁️ Preview' : '✎ Edit'}
                        </motion.button>

                        <motion.button
                            className={`${styles.button} ${styles.regenerateButton}`}
                            onClick={() => !loading && onConfirm({ regenerate: true })}
                            disabled={loading}
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                        >
                            🔄 Regenerate
                        </motion.button>

                        <motion.button
                            className={`${styles.button} ${styles.confirmButton}`}
                            onClick={handleConfirm}
                            disabled={loading || !editedSubject || !editedBody}
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                        >
                            {loading ? 'Sending...' : '✓ Send Email'}
                        </motion.button>

                        <motion.button
                            className={`${styles.button} ${styles.cancelButton}`}
                            onClick={() => !loading && onCancel()}
                            disabled={loading}
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                        >
                            ✕ Cancel
                        </motion.button>
                    </div>
                </div>
            </motion.div>
        );
    }

    // Render ticket preview with edit capability
    if (action === 'ticket_preview' && preview) {
        return (
            <motion.div
                className={styles.confirmationCard}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
            >
                <div className={styles.iconContainer}>
                    <span className={styles.icon}>🎫</span>
                </div>

                <div className={styles.content}>
                    <h4 className={styles.title}>Ticket Preview</h4>
                    <p className={styles.summary}>{summary}</p>

                    <div className={styles.emailPreview}>
                        {/* Category */}
                        <div className={styles.previewRow}>
                            <span className={styles.previewLabel}>Category:</span>
                            <span className={styles.previewValue}>{preview.category}</span>
                        </div>

                        {/* Sub-category */}
                        {preview.sub_category && (
                            <div className={styles.previewRow}>
                                <span className={styles.previewLabel}>Type:</span>
                                <span className={styles.previewValue}>{preview.sub_category}</span>
                            </div>
                        )}

                        {/* Priority */}
                        <div className={styles.previewRow}>
                            <span className={styles.previewLabel}>Priority:</span>
                            <span className={styles.previewValue}>{preview.priority}</span>
                        </div>

                        {/* Title - editable */}
                        <div className={styles.previewRow}>
                            <span className={styles.previewLabel}>Title:</span>
                            {editMode ? (
                                <input
                                    type="text"
                                    className={styles.editInput}
                                    value={editedSubject}
                                    onChange={(e) => setEditedSubject(e.target.value)}
                                    placeholder="Issue title"
                                />
                            ) : (
                                <span className={styles.previewValue}>{preview.title}</span>
                            )}
                        </div>

                        {/* Description - editable */}
                        <div className={styles.previewBody}>
                            <span className={styles.previewLabel}>Description:</span>
                            {editMode ? (
                                <div className={styles.editBodyContainer}>
                                    <textarea
                                        className={styles.editTextarea}
                                        value={editedBody}
                                        onChange={(e) => setEditedBody(e.target.value)}
                                        placeholder="Describe the issue in detail"
                                        rows={8}
                                    />
                                    <div className={styles.charCount}>
                                        {editedBody.length} characters
                                    </div>
                                </div>
                            ) : (
                                <div className={styles.bodyPreview}>
                                    {preview.description}
                                </div>
                            )}
                        </div>
                    </div>

                    <div className={styles.buttonGroup}>
                        {preview.editable && (
                            <motion.button
                                className={`${styles.button} ${styles.editButton}`}
                                onClick={handleEdit}
                                disabled={loading}
                                whileHover={{ scale: 1.02 }}
                                whileTap={{ scale: 0.98 }}
                            >
                                {editMode ? '👁️ Preview' : '✎ Edit'}
                            </motion.button>
                        )}

                        <motion.button
                            className={`${styles.button} ${styles.confirmButton}`}
                            onClick={handleConfirm}
                            disabled={loading || !editedSubject || !editedBody}
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                        >
                            {loading ? 'Creating...' : '✓ Raise Ticket'}
                        </motion.button>

                        <motion.button
                            className={`${styles.button} ${styles.cancelButton}`}
                            onClick={() => !loading && onCancel()}
                            disabled={loading}
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                        >
                            ✕ Cancel
                        </motion.button>
                    </div>
                </div>
            </motion.div>
        );
    }

    // Original confirmation card for other actions
    const renderDetails = () => {
        if (!details) return null;

        if (action === 'send_email') {
            return (
                <div className={styles.detailsSection}>
                    {details.to && (
                        <div className={styles.detailRow}>
                            <span className={styles.detailLabel}>To:</span>
                            <span className={styles.detailValue}>{details.to}</span>
                        </div>
                    )}
                    {details.subject && (
                        <div className={styles.detailRow}>
                            <span className={styles.detailLabel}>Subject:</span>
                            <span className={styles.detailValue}>{details.subject}</span>
                        </div>
                    )}
                    {details.preview && (
                        <div className={styles.detailRow}>
                            <span className={styles.detailLabel}>Preview:</span>
                            <span className={styles.detailValue}>{details.preview}</span>
                        </div>
                    )}
                </div>
            );
        } else if (action === 'raise_ticket') {
            return (
                <div className={styles.detailsSection}>
                    {details.category && (
                        <div className={styles.detailRow}>
                            <span className={styles.detailLabel}>Category:</span>
                            <span className={styles.detailValue}>{details.category}</span>
                        </div>
                    )}
                    {details.priority && (
                        <div className={styles.detailRow}>
                            <span className={styles.detailLabel}>Priority:</span>
                            <span className={styles.detailValue}>{details.priority}</span>
                        </div>
                    )}
                    {details.description && (
                        <div className={styles.detailRow}>
                            <span className={styles.detailLabel}>Description:</span>
                            <span className={styles.detailValue}>{details.description}</span>
                        </div>
                    )}
                </div>
            );
        }

        return null;
    };

    return (
        <motion.div
            className={styles.confirmationCard}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
        >
            <div className={styles.iconContainer}>
                <span className={styles.icon}>⚡</span>
            </div>

            <div className={styles.content}>
                <h4 className={styles.title}>Confirm Action</h4>
                <p className={styles.summary}>{summary}</p>

                {renderDetails()}

                <div className={styles.buttonGroup}>
                    <motion.button
                        className={`${styles.button} ${styles.confirmButton}`}
                        onClick={handleConfirm}
                        disabled={loading}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                    >
                        {loading ? 'Processing...' : '✓ Confirm'}
                    </motion.button>

                    <motion.button
                        className={`${styles.button} ${styles.cancelButton}`}
                        onClick={() => !loading && onCancel()}
                        disabled={loading}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                    >
                        ✕ Cancel
                    </motion.button>
                </div>
            </div>
        </motion.div>
    );
};

export default ConfirmationCard;
