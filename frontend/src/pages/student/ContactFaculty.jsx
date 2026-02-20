/**
 * Contact Faculty
 * Browse faculty directory and send emails
 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import studentService from '../../services/studentService';
import { getCurrentUser } from '../../utils/auth';
import { pageTransition, staggerContainer, staggerItem } from '../../animations/variants';
import { LoadingState, EmptyState } from '../../components/dashboard/DashboardComponents';
import Toast from '../../components/common/Toast';
import styles from './ContactFaculty.module.css';

const ContactFaculty = () => {
    const user = getCurrentUser();
    const [departments, setDepartments] = useState([]);
    const [faculty, setFaculty] = useState([]);
    const [selectedDept, setSelectedDept] = useState('all');
    const [loading, setLoading] = useState(true);
    const [quota, setQuota] = useState(null);
    const [toast, setToast] = useState({ show: false, message: '', type: 'info' });

    useEffect(() => {
        loadDepartments();
        loadQuota();
    }, []);

    useEffect(() => {
        loadFaculty();
    }, [selectedDept]);

    const loadDepartments = async () => {
        try {
            const response = await studentService.getDepartments();
            if (response.success) {
                setDepartments(response.departments || []);
            }
        } catch (error) {
            console.error('Failed to load departments:', error);
        }
    };

    const loadFaculty = async () => {
        setLoading(true);
        try {
            const dept = selectedDept === 'all' ? '' : selectedDept;
            const response = await studentService.getFacultyList(dept);
            if (response.success) {
                setFaculty(response.faculty || []);
            }
        } catch (error) {
            console.error('Failed to load faculty:', error);
        } finally {
            setLoading(false);
        }
    };

    const [selectedFaculty, setSelectedFaculty] = useState(null);
    const [showEmailModal, setShowEmailModal] = useState(false);
    const [emailForm, setEmailForm] = useState({ subject: '', message: '' });
    const [sending, setSending] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');

    const loadQuota = async () => {
        try {
            const response = await studentService.checkEmailQuota(user.email);
            if (response.success) {
                setQuota(response);
            }
        } catch (error) {
            console.error('Failed to load quota:', error);
        }
    };

    const handleEmailClick = (facultyMember) => {
        if (quota && quota.emails_remaining <= 0) {
            setToast({
                show: true,
                message: 'Daily email limit reached. Try again tomorrow.',
                type: 'error'
            });
            return;
        }
        setSelectedFaculty(facultyMember);
        setEmailForm({ subject: '', message: '' });
        setShowEmailModal(true);
    };

    const handleSendFacultyEmail = async () => {
        if (!emailForm.subject.trim() || !emailForm.message.trim()) {
            setToast({ show: true, message: 'Please fill in all fields', type: 'error' });
            return;
        }

        setSending(true);
        setToast({ show: false, message: '', type: 'info' });

        try {
            const response = await studentService.sendFacultyEmail({
                student_email: user.email,
                student_name: user.full_name,
                student_roll_no: user.roll_number,
                student_department: user.department,
                student_year: user.year,
                faculty_id: selectedFaculty.id,
                subject: emailForm.subject,
                message: emailForm.message
            });

            if (response.success) {
                setToast({ show: true, message: '✅ Email sent successfully to ' + selectedFaculty.name, type: 'success' });
                setShowEmailModal(false);
                setEmailForm({ subject: '', message: '' });
                // Reload quota
                await loadQuota();
            } else {
                setToast({ show: true, message: response.message || 'Failed to send email', type: 'error' });
            }
        } catch (error) {
            setToast({ show: true, message: error.message || 'Failed to send email', type: 'error' });
        } finally {
            setSending(false);
        }
    };

    const filteredFaculty = (selectedDept === 'all' ? faculty : faculty.filter(f => f.department === selectedDept))
        .filter(f => {
            if (!searchQuery.trim()) return true;
            const q = searchQuery.toLowerCase();
            return (f.name || '').toLowerCase().includes(q) ||
                (f.department || '').toLowerCase().includes(q) ||
                (f.designation || '').toLowerCase().includes(q);
        });

    return (
        <motion.div className={styles.contactFacultyPage} {...pageTransition}>
            <Toast
                message={toast.message}
                type={toast.type}
                show={toast.show}
                onClose={() => setToast({ ...toast, show: false })}
            />

            <div className={styles.container}>
                {/* Header */}
                <div className={styles.header}>
                    <div>
                        <h1 className={styles.title}>👩‍🏫 Contact Faculty</h1>
                        <p className={styles.subtitle}>Browse faculty directory</p>
                    </div>
                    {quota && (
                        <div className={styles.quotaCard}>
                            <span className={styles.quotaLabel}>Emails Remaining Today:</span>
                            <span className={styles.quotaValue}>{quota.emails_remaining}/5</span>
                        </div>
                    )}
                </div>

                {/* Department Filter */}
                <div className={styles.filters}>
                    <button
                        className={`${styles.filterButton} ${selectedDept === 'all' ? styles.active : ''}`}
                        onClick={() => setSelectedDept('all')}
                    >
                        All Departments
                    </button>
                    {departments.map(dept => (
                        <button
                            key={dept}
                            className={`${styles.filterButton} ${selectedDept === dept ? styles.active : ''}`}
                            onClick={() => setSelectedDept(dept)}
                        >
                            {dept}
                        </button>
                    ))}
                </div>

                {/* Search Box */}
                <div className={styles.searchContainer}>
                    <div className={styles.searchWrapper}>
                        <span className={styles.searchIcon}>🔍</span>
                        <input
                            type="text"
                            className={styles.searchBox}
                            placeholder="Search faculty by name, department..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                </div>

                {/* Faculty Grid */}
                {loading ? (
                    <LoadingState />
                ) : filteredFaculty.length === 0 ? (
                    <EmptyState icon="👨‍🏫" message="No faculty members found in this department" />
                ) : (
                    <motion.div
                        className={styles.facultyGrid}
                        variants={staggerContainer}
                        initial="hidden"
                        animate="visible"
                    >
                        {filteredFaculty.map((member) => (
                            <motion.div
                                key={member.id}
                                className={styles.facultyCard}
                                variants={staggerItem}
                            >
                                <div className={styles.facultyAvatar}>
                                    {member.name?.charAt(0) || '👤'}
                                </div>
                                <div className={styles.facultyInfo}>
                                    <h3 className={styles.facultyName}>{member.name}</h3>
                                    <p className={styles.facultyDesignation}>{member.designation}</p>
                                    <p className={styles.facultyDepartment}>🏢 {member.department}</p>
                                    {member.contact && (
                                        <p className={styles.facultyContact}>📞 {member.contact}</p>
                                    )}
                                </div>
                                <motion.button
                                    className={styles.emailButton}
                                    onClick={() => handleEmailClick(member)}
                                    disabled={quota && quota.emails_remaining <= 0}
                                    whileHover={{ scale: 1.05 }}
                                    whileTap={{ scale: 0.95 }}
                                >
                                    📧 Email
                                </motion.button>
                            </motion.div>
                        ))}
                    </motion.div>
                )}
            </div>

            {/* Email Modal */}
            <AnimatePresence>
                {showEmailModal && selectedFaculty && (
                    <motion.div
                        className={styles.modalOverlay}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={() => !sending && setShowEmailModal(false)}
                    >
                        <motion.div
                            className={styles.modalContent}
                            initial={{ opacity: 0, scale: 0.95, y: 20 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95, y: 20 }}
                            onClick={(e) => e.stopPropagation()}
                        >
                            <h2 className={styles.modalTitle}>
                                📧 Email {selectedFaculty.name}
                            </h2>
                            <p className={styles.modalSubtitle}>
                                {selectedFaculty.designation} • {selectedFaculty.department}
                            </p>

                            {/* Subject */}
                            <div className={styles.formGroup}>
                                <label className={styles.formLabel}>
                                    Subject <span className={styles.required}>*</span>
                                </label>
                                <input
                                    type="text"
                                    className={styles.formInput}
                                    value={emailForm.subject}
                                    onChange={(e) => setEmailForm(prev => ({ ...prev, subject: e.target.value }))}
                                    placeholder="Enter email subject"
                                    disabled={sending}
                                />
                            </div>

                            {/* Message */}
                            <div className={styles.formGroup}>
                                <label className={styles.formLabel}>
                                    Message <span className={styles.required}>*</span>
                                </label>
                                <textarea
                                    className={styles.formTextarea}
                                    value={emailForm.message}
                                    onChange={(e) => setEmailForm(prev => ({ ...prev, message: e.target.value }))}
                                    placeholder="Enter your message"
                                    disabled={sending}
                                    rows={8}
                                />
                            </div>

                            {/* Action Buttons */}
                            <div className={styles.modalActions}>
                                <motion.button
                                    className={styles.cancelBtn}
                                    onClick={() => setShowEmailModal(false)}
                                    disabled={sending}
                                    whileHover={{ scale: sending ? 1 : 1.02 }}
                                    whileTap={{ scale: sending ? 1 : 0.98 }}
                                >
                                    Cancel
                                </motion.button>

                                <motion.button
                                    className={styles.sendBtn}
                                    onClick={handleSendFacultyEmail}
                                    disabled={sending || !emailForm.subject.trim() || !emailForm.message.trim()}
                                    whileHover={{ scale: (sending || !emailForm.subject.trim() || !emailForm.message.trim()) ? 1 : 1.02 }}
                                    whileTap={{ scale: (sending || !emailForm.subject.trim() || !emailForm.message.trim()) ? 1 : 0.98 }}
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

export default ContactFaculty;
