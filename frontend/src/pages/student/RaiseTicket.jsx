/**
 * Raise Ticket
 * Create new support ticket with category selection
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import studentService from '../../services/studentService';
import { getCurrentUser } from '../../utils/auth';
import { pageTransition } from '../../animations/variants';
import { LoadingState } from '../../components/dashboard/DashboardComponents';
import Toast from '../../components/common/Toast';
import styles from './RaiseTicket.module.css';

const RaiseTicket = () => {
    const navigate = useNavigate();
    const user = getCurrentUser();
    const [categories, setCategories] = useState({});
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [toast, setToast] = useState({ show: false, message: '', type: 'error' });

    const [formData, setFormData] = useState({
        student_email: user?.email || '',
        category: '',
        sub_category: '',
        priority: 'Medium',
        description: '',
        attachments: []
    });

    const [errors, setErrors] = useState({});

    useEffect(() => {
        loadCategories();
    }, []);

    const loadCategories = async () => {
        try {
            const response = await studentService.getTicketCategories();
            setCategories(response.categories || {});
        } catch (error) {
            console.error('Failed to load categories:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: value,
            // Reset subcategory when category changes
            ...(name === 'category' && { sub_category: '' })
        }));
        // Clear error for this field
        if (errors[name]) {
            setErrors(prev => ({ ...prev, [name]: '' }));
        }
    };

    const validate = () => {
        const newErrors = {};
        if (!formData.category) newErrors.category = 'Category is required';
        if (!formData.sub_category) newErrors.sub_category = 'Subcategory is required';
        if (!formData.priority) newErrors.priority = 'Priority is required';
        if (!formData.description || formData.description.trim().length < 20) {
            newErrors.description = 'Description must be at least 20 characters';
        }
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
                setToast({
                    show: true,
                    message: `Ticket ${response.ticket_id} created successfully!`,
                    type: 'success'
                });
                setTimeout(() => {
                    navigate('/student/tickets');
                }, 2000);
            } else {
                if (response.error === 'duplicate') {
                    setToast({
                        show: true,
                        message: response.message || 'You already have an open ticket in this category',
                        type: 'error'
                    });
                } else {
                    throw new Error(response.error || 'Failed to create ticket');
                }
            }
        } catch (error) {
            setToast({
                show: true,
                message: error.message || 'Failed to create ticket. Please try again.',
                type: 'error'
            });
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) return <LoadingState />;

    const currentSubcategories = formData.category ? (categories[formData.category] || []) : [];

    return (
        <motion.div className={styles.raiseTicketPage} {...pageTransition}>
            <Toast
                message={toast.message}
                type={toast.type}
                show={toast.show}
                onClose={() => setToast({ ...toast, show: false })}
            />

            <div className={styles.container}>
                <div className={styles.header}>
                    <h1 className={styles.title}>🎫 Raise Support Ticket</h1>
                    <p className={styles.subtitle}>Describe your issue and we'll help you resolve it</p>
                </div>

                <form onSubmit={handleSubmit} className={styles.form}>
                    {/* Category */}
                    <div className={styles.formGroup}>
                        <label className={styles.label}>Category *</label>
                        <select
                            name="category"
                            value={formData.category}
                            onChange={handleChange}
                            className={styles.select}
                            disabled={submitting}
                        >
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
                            <select
                                name="sub_category"
                                value={formData.sub_category}
                                onChange={handleChange}
                                className={styles.select}
                                disabled={submitting}
                            >
                                <option value="">Select a subcategory</option>
                                {currentSubcategories.map(subcat => (
                                    <option key={subcat} value={subcat}>{subcat}</option>
                                ))}
                            </select>
                            {errors.sub_category && <span className={styles.error}>{errors.sub_category}</span>}
                        </div>
                    )}

                    {/* Priority */}
                    <div className={styles.formGroup}>
                        <label className={styles.label}>Priority *</label>
                        <div className={styles.radioGroup}>
                            {['Low', 'Medium', 'High', 'Urgent'].map(priority => (
                                <label key={priority} className={styles.radioLabel}>
                                    <input
                                        type="radio"
                                        name="priority"
                                        value={priority}
                                        checked={formData.priority === priority}
                                        onChange={handleChange}
                                        disabled={submitting}
                                    />
                                    <span>{priority}</span>
                                </label>
                            ))}
                        </div>
                        {errors.priority && <span className={styles.error}>{errors.priority}</span>}
                    </div>

                    {/* Description */}
                    <div className={styles.formGroup}>
                        <label className={styles.label}>Description * (min. 20 characters)</label>
                        <textarea
                            name="description"
                            value={formData.description}
                            onChange={handleChange}
                            className={styles.textarea}
                            rows={6}
                            placeholder="Describe your issue in detail..."
                            disabled={submitting}
                        />
                        <div className={styles.charCount}>
                            {formData.description.length} characters
                        </div>
                        {errors.description && <span className={styles.error}>{errors.description}</span>}
                    </div>

                    {/* Submit Button */}
                    <div className={styles.actions}>
                        <motion.button
                            type="submit"
                            className={styles.submitButton}
                            disabled={submitting}
                            whileHover={{ scale: submitting ? 1 : 1.02 }}
                            whileTap={{ scale: submitting ? 1 : 0.98 }}
                        >
                            {submitting ? 'Creating Ticket...' : 'Submit Ticket'}
                        </motion.button>
                        <button
                            type="button"
                            className={styles.cancelButton}
                            onClick={() => navigate('/student/tickets')}
                            disabled={submitting}
                        >
                            Cancel
                        </button>
                    </div>
                </form>
            </div>
        </motion.div>
    );
};

export default RaiseTicket;
