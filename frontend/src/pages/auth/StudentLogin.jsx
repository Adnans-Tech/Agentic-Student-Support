/**
 * Student Login Page
 * Modern, animated login interface for ACE students
 */

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import authService from '../../services/authService';
import { validators, formatBackendError } from '../../utils/validators';
import { pageTransition, fadeIn } from '../../animations/variants';
import Toast from '../../components/common/Toast';
import styles from './Auth.module.css';

const StudentLogin = () => {
    const navigate = useNavigate();

    const [formData, setFormData] = useState({
        identifier: '',
        password: '',
    });

    const [errors, setErrors] = useState({});
    const [loading, setLoading] = useState(false);
    const [toast, setToast] = useState({ show: false, message: '', type: 'error' });

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
        // Clear error for this field
        if (errors[name]) {
            setErrors(prev => ({ ...prev, [name]: null }));
        }
        setToast({ show: false, message: '', type: 'error' });
    };

    const validate = () => {
        const newErrors = {};

        // Roll Number validation - just check it's not empty
        if (!formData.identifier || formData.identifier.trim() === '') {
            newErrors.identifier = 'Roll Number is required';
        } else {
            newErrors.identifier = null;
        }
        newErrors.password = validators.password(formData.password);

        setErrors(newErrors);
        return !Object.values(newErrors).some(error => error !== null);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setToast({ show: false, message: '', type: 'error' });

        if (!validate()) return;

        setLoading(true);

        try {
            const response = await authService.loginStudent(formData.identifier, formData.password);

            if (response.success) {
                // Check if email needs verification
                if (response.requires_verification) {
                    navigate('/verify-otp', { state: { email: formData.identifier } });
                    return;
                }

                // Success - redirect to dashboard
                navigate('/student/dashboard');
            } else {
                setToast({
                    show: true,
                    message: formatBackendError(response),
                    type: 'error'
                });
            }
        } catch (error) {
            setToast({
                show: true,
                message: formatBackendError(error),
                type: 'error'
            });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className={styles.authContainer}>
            <Toast
                message={toast.message}
                type={toast.type}
                show={toast.show}
                onClose={() => setToast({ show: false, message: '', type: 'error' })}
            />

            <motion.div
                className={styles.authCard}
                {...pageTransition}
            >
                {/* Logo */}
                <div className={styles.logoSection}>
                    <img src="/ace_logo.png" alt="ACE Logo" className={styles.logo} />
                    <h1 className={styles.title}>Student Login</h1>
                    <p className={styles.subtitle}>ACE Engineering College</p>
                </div>

                {/* Login Form */}
                <form onSubmit={handleSubmit} className={styles.form}>

                    {/* Roll Number */}
                    <div className={styles.formGroup}>
                        <label htmlFor="identifier" className={styles.label}>
                            Roll Number
                        </label>
                        <input
                            type="text"
                            id="identifier"
                            name="identifier"
                            value={formData.identifier}
                            onChange={handleChange}
                            className={`${styles.input} ${errors.identifier ? styles.inputError : ''}`}
                            placeholder="e.g., 22AG1A6665"
                            disabled={loading}
                        />
                        {errors.identifier && (
                            <span className={styles.errorText}>{errors.identifier}</span>
                        )}
                    </div>

                    {/* Password */}
                    <div className={styles.formGroup}>
                        <label htmlFor="password" className={styles.label}>
                            Password
                        </label>
                        <input
                            type="password"
                            id="password"
                            name="password"
                            value={formData.password}
                            onChange={handleChange}
                            className={`${styles.input} ${errors.password ? styles.inputError : ''}`}
                            placeholder="••••••••"
                            disabled={loading}
                        />
                        {errors.password && (
                            <span className={styles.errorText}>{errors.password}</span>
                        )}
                    </div>

                    {/* Submit Button */}
                    <motion.button
                        type="submit"
                        className={styles.submitButton}
                        disabled={loading}
                        whileHover={{ scale: loading ? 1 : 1.02 }}
                        whileTap={{ scale: loading ? 1 : 0.98 }}
                    >
                        {loading ? 'Logging in...' : 'Login'}
                    </motion.button>
                </form>

                {/* Links */}
                <div className={styles.links}>
                    <p className={styles.linkText}>
                        Don't have an account?{' '}
                        <Link to="/register" className={styles.link}>
                            Register Now
                        </Link>
                    </p>

                    <p className={styles.linkText}>
                        <Link to="/faculty/login" className={styles.link}>
                            Faculty Login →
                        </Link>
                    </p>
                </div>
            </motion.div>
        </div>
    );
};

export default StudentLogin;
