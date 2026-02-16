/**
 * Send Emails - AI-Powered Email Composition
 * Students can send AI-generated emails to external recipients
 */

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import studentService from '../../services/studentService';
import { getCurrentUser } from '../../utils/auth';
import { pageTransition, modalBackdrop, modalContent } from '../../animations/variants';
import Toast from '../../components/common/Toast';
import styles from './Emails.module.css';

const Emails = () => {
    const user = getCurrentUser();

    const [formData, setFormData] = useState({
        toEmail: '',
        purpose: '',
        tone: 'semi-formal',
        length: 'medium'
    });

    const [showAdvanced, setShowAdvanced] = useState(false);
    const [preview, setPreview] = useState(null);
    const [showPreview, setShowPreview] = useState(false);
    const [loading, setLoading] = useState(false);
    const [sending, setSending] = useState(false);
    const [toast, setToast] = useState({ show: false, message: '', type: 'info' });

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

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleGeneratePreview = async () => {
        // Validation
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
                to_email: formData.toEmail,
                purpose: formData.purpose,
                tone: formData.tone,
                length: formData.length,
                student_name: user.full_name || user.name,
                preview_mode: true
            });

            if (response.success) {
                setPreview({
                    subject: response.subject,
                    body: response.body,
                    editable: true
                });
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

    const handleEditPreview = (field, value) => {
        setPreview(prev => ({ ...prev, [field]: value }));
    };

    const handleSendEmail = async () => {
        if (!preview) return;

        setSending(true);
        setToast({ show: false, message: '', type: 'info' });

        try {
            const response = await studentService.sendEmail({
                to_email: formData.toEmail,
                subject: preview.subject,
                body: preview.body,
                purpose: formData.purpose,
                preview_mode: false
            });

            if (response.success) {
                setToast({ show: true, message: '✅ Email sent successfully!', type: 'success' });
                setShowPreview(false);
                // Reset form
                setFormData({ toEmail: '', purpose: '', tone: 'semi-formal', length: 'medium' });
                setPreview(null);
            } else {
                setToast({ show: true, message: response.error || 'Failed to send email', type: 'error' });
            }
        } catch (error) {
            setToast({ show: true, message: error.message || 'Failed to send email', type: 'error' });
        } finally {
            setSending(false);
        }
    };

    return (
        <motion.div className={styles.emailPage} {...pageTransition}>
            <Toast
                message={toast.message}
                type={toast.type}
                show={toast.show}
                onClose={() => setToast({ ...toast, show: false })}
            />

            <div className={styles.emailContainer}>
                {/* Header */}
                <div className={styles.emailHeader}>
                    <div className={styles.headerInfo}>
                        <h1>📧 Send Emails</h1>
                        <p>AI-powered email composition</p>
                    </div>
                </div>

                {/* Email Form */}
                <div className={styles.formContainer}>
                    {/* To Email */}
                    <div className={styles.formGroup}>
                        <label className={styles.label}>
                            Recipient Email <span className={styles.required}>*</span>
                        </label>
                        <input
                            type="email"
                            name="toEmail"
                            value={formData.toEmail}
                            onChange={handleChange}
                            placeholder="recipient@example.com"
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
                            name="purpose"
                            value={formData.purpose}
                            onChange={handleChange}
                            placeholder="Describe what you want to communicate (minimum 5 words)..."
                            disabled={loading || sending}
                            rows={4}
                            className={styles.textarea}
                        />
                        <small className={styles.wordCount}>
                            {formData.purpose.split(' ').filter(w => w).length} / 5 words minimum
                        </small>
                    </div>

                    {/* Advanced Options Toggle */}
                    <button
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        className={styles.advancedToggle}
                    >
                        {showAdvanced ? '▼' : '▶'} Advanced Options
                    </button>

                    {/* Advanced Options */}
                    <AnimatePresence>
                        {showAdvanced && (
                            <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                className={styles.advancedOptions}
                            >
                                <div className={styles.optionsGrid}>
                                    {/* Tone */}
                                    <div className={styles.formGroup}>
                                        <label className={styles.label}>Tone</label>
                                        <select
                                            name="tone"
                                            value={formData.tone}
                                            onChange={handleChange}
                                            disabled={loading || sending}
                                            className={styles.select}
                                        >
                                            {toneOptions.map(opt => (
                                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                                            ))}
                                        </select>
                                    </div>

                                    {/* Length */}
                                    <div className={styles.formGroup}>
                                        <label className={styles.label}>Length</label>
                                        <select
                                            name="length"
                                            value={formData.length}
                                            onChange={handleChange}
                                            disabled={loading || sending}
                                            className={styles.select}
                                        >
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
                        whileHover={{ scale: loading ? 1 : 1.02 }}
                        whileTap={{ scale: loading ? 1 : 0.98 }}
                        className={styles.generateButton}
                    >
                        {loading ? '✨ Generating Preview...' : '🔍 Generate Preview'}
                    </motion.button>
                </div>
            </div>

            {/* Preview Modal */}
            <AnimatePresence>
                {showPreview && preview && (
                    <motion.div
                        className={styles.modalBackdrop}
                        variants={modalBackdrop}
                        initial="hidden"
                        animate="visible"
                        exit="exit"
                        onClick={() => !sending && setShowPreview(false)}
                    >
                        <motion.div
                            variants={modalContent}
                            onClick={(e) => e.stopPropagation()}
                            className={styles.modalContent}
                        >
                            <h2 className={styles.modalHeader}>
                                📧 Preview & Edit Email
                            </h2>

                            {/* Subject */}
                            <div className={styles.formGroup}>
                                <label className={styles.label}>Subject</label>
                                <input
                                    type="text"
                                    value={preview.subject}
                                    onChange={(e) => handleEditPreview('subject', e.target.value)}
                                    disabled={sending}
                                    className={styles.input}
                                />
                            </div>

                            {/* Body */}
                            <div className={styles.formGroup}>
                                <label className={styles.label}>Email Body</label>
                                <textarea
                                    value={preview.body}
                                    onChange={(e) => handleEditPreview('body', e.target.value)}
                                    disabled={sending}
                                    rows={12}
                                    className={styles.textarea}
                                />
                            </div>

                            {/* Action Buttons */}
                            <div className={styles.modalActions}>
                                <motion.button
                                    onClick={() => setShowPreview(false)}
                                    disabled={sending}
                                    whileHover={{ scale: sending ? 1 : 1.02 }}
                                    whileTap={{ scale: sending ? 1 : 0.98 }}
                                    className={styles.cancelButton}
                                >
                                    Cancel
                                </motion.button>

                                <motion.button
                                    onClick={handleSendEmail}
                                    disabled={sending}
                                    whileHover={{ scale: sending ? 1 : 1.02 }}
                                    whileTap={{ scale: sending ? 1 : 0.98 }}
                                    className={styles.sendButton}
                                >
                                    {sending ? '📤 Sending...' : '✉️ Send Email'}
                                </motion.button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
};

export default Emails;
