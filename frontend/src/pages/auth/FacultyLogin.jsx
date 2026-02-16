/**
 * Faculty Login Page
 * Separate login interface for faculty members
 */

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import authService from '../../services/authService';
import { validators, formatBackendError } from '../../utils/validators';
import { pageTransition, fadeIn } from '../../animations/variants';
import Toast from '../../components/common/Toast';
import styles from './Auth.module.css';

const FacultyLogin = () => {
    const navigate = useNavigate();

    const [formData, setFormData] = useState({
        email: '',
        password: '',
    });

    const [errors, setErrors] = useState({});
    const [loading, setLoading] = useState(false);
    const [toast, setToast] = useState({ show: false, message: '', type: 'error' });

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
        if (errors[name]) {
            setErrors(prev => ({ ...prev, [name]: null }));
        }
        setToast({ show: false, message: '', type: 'error' });
    };

    const validate = () => {
        const newErrors = {};
        newErrors.email = validators.email(formData.email);
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
            const response = await authService.loginFaculty(formData.email, formData.password);

            if (response.success) {
                navigate('/faculty/dashboard');
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
                <div className={styles.logoSection}>
                    <img src="/ace_logo.png" alt="ACE Logo" className={styles.logo} />
                    <h1 className={styles.title}>Faculty Login</h1>
                    <p className={styles.subtitle}>ACE Engineering College</p>
                </div>

                <form onSubmit={handleSubmit} className={styles.form}>

                    <div className={styles.formGroup}>
                        <label htmlFor="email" className={styles.label}>Official Email</label>
                        <input
                            type="email"
                            id="email"
                            name="email"
                            value={formData.email}
                            onChange={handleChange}
                            className={`${styles.input} ${errors.email ? styles.inputError : ''}`}
                            placeholder="faculty@ace.edu"
                            disabled={loading}
                        />
                        {errors.email && <span className={styles.errorText}>{errors.email}</span>}
                    </div>

                    <div className={styles.formGroup}>
                        <label htmlFor="password" className={styles.label}>Password</label>
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
                        {errors.password && <span className={styles.errorText}>{errors.password}</span>}
                    </div>

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

                <div className={styles.links}>
                    <p className={styles.linkText}>
                        Don't have an account?{' '}
                        <Link to="/faculty/register" className={styles.link}>
                            Register as Faculty
                        </Link>
                    </p>
                    <p className={styles.linkText}>
                        <Link to="/login" className={styles.link}>
                            ← Student Login
                        </Link>
                    </p>
                </div>
            </motion.div>
        </div>
    );
};

export default FacultyLogin;
