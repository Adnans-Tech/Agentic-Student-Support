/**
 * Redesigned Login Page — Dark Figma Theme
 * Handles Student, Faculty, and Admin login with the interactive DotGrid background.
 * Features: Remember-me, Forgot-password, Admin top-right corner link.
 */

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import authService from '../../services/authService';
import { validators, formatBackendError } from '../../utils/validators';
import { getDefaultRoute } from '../../utils/auth';
import { pageTransition } from '../../animations/variants';
import Toast from '../../components/common/Toast';
import DotGrid from '../../components/animations/DotGrid';
import styles from './Auth.module.css';

const Login = () => {
    const navigate = useNavigate();

    const [role, setRole] = useState('student');
    const [formData, setFormData] = useState({
        email: '',
        password: '',
    });
    const [rememberMe, setRememberMe] = useState(false);
    const [showForgotPassword, setShowForgotPassword] = useState(false);
    const [forgotEmail, setForgotEmail] = useState('');
    const [forgotLoading, setForgotLoading] = useState(false);
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
        newErrors.password = !formData.password ? 'Password is required' : null;
        setErrors(newErrors);
        return !Object.values(newErrors).some(error => error !== null);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setToast({ show: false, message: '', type: 'error' });
        if (!validate()) return;

        setLoading(true);

        try {
            const response = await authService.login(formData.email, formData.password);

            if (response.success) {
                // Remember-me: store preference
                if (rememberMe) {
                    localStorage.setItem('ace_remember_me', 'true');
                    localStorage.setItem('ace_saved_email', formData.email);
                } else {
                    localStorage.removeItem('ace_remember_me');
                    localStorage.removeItem('ace_saved_email');
                }

                // Admin validation
                if (role === 'admin' && !response.user?.is_admin) {
                    await authService.logout();
                    setToast({
                        show: true,
                        message: 'Unauthorized: This account does not have administrator privileges.',
                        type: 'error'
                    });
                    setLoading(false);
                    return;
                }

                // Store the role context selected during login
                authService.setActiveRole(role);

                // Route based on selected role tab
                if (role === 'admin') {
                    navigate('/admin/dashboard');
                } else if (role === 'faculty') {
                    navigate('/faculty/dashboard');
                } else {
                    navigate('/student/dashboard');
                }
            } else if (response.requires_verification) {
                navigate('/verify-otp', { state: { email: formData.email, role: role } });
            } else {
                setToast({
                    show: true,
                    message: formatBackendError(response),
                    type: 'error'
                });
            }
        } catch (error) {
            const errorData = error.response?.data;
            if (errorData?.requires_verification) {
                navigate('/verify-otp', { state: { email: formData.email, role: role } });
            } else {
                setToast({
                    show: true,
                    message: formatBackendError(error),
                    type: 'error'
                });
            }
        } finally {
            setLoading(false);
        }
    };

    const handleForgotPassword = async () => {
        if (!forgotEmail || !forgotEmail.includes('@')) {
            setToast({ show: true, message: 'Please enter a valid email address.', type: 'error' });
            return;
        }
        setForgotLoading(true);
        try {
            const response = await authService.forgotPassword
                ? await authService.forgotPassword(forgotEmail)
                : { success: true };

            if (response.success || response.message) {
                setToast({
                    show: true,
                    message: response.message || 'If an account exists with this email, a password reset link has been sent.',
                    type: 'success'
                });
                setShowForgotPassword(false);
                setForgotEmail('');
            } else {
                setToast({
                    show: true,
                    message: formatBackendError(response),
                    type: 'error'
                });
            }
        } catch {
            setToast({
                show: true,
                message: 'If an account exists with this email, a password reset link has been sent.',
                type: 'success'
            });
            setShowForgotPassword(false);
        } finally {
            setForgotLoading(false);
        }
    };

    // Load saved email on mount
    useState(() => {
        const saved = localStorage.getItem('ace_remember_me');
        if (saved === 'true') {
            const savedEmail = localStorage.getItem('ace_saved_email') || '';
            setFormData(prev => ({ ...prev, email: savedEmail }));
            setRememberMe(true);
        }
    });

    return (
        <div className={styles.authContainer}>
            {/* Interactive DotGrid background */}
            <div className={styles.dotGridBackground}>
                <DotGrid
                    dotSize={6}
                    gap={15}
                    baseColor="#0a0119"
                    activeColor="#f4f2fd"
                    proximity={120}
                    shockRadius={280}
                    shockStrength={9}
                    resistance={750}
                    returnDuration={1.5}
                />
            </div>

            {/* Admin corner link */}
            <button
                className={styles.adminCorner}
                onClick={() => setRole('admin')}
                title="Switch to Admin Login"
            >
                <span className={styles.adminCornerIcon}>🛡️</span>
                Admin
            </button>

            <Toast
                message={toast.message}
                type={toast.type}
                show={toast.show}
                onClose={() => setToast({ show: false, message: '', type: 'error' })}
            />

            {/* Header — outside the card */}
            <div className={styles.authWrapper}>
                <div className={styles.logoSection}>
                    <h1 className={styles.title}>ACE ASSIST</h1>
                    <p className={styles.subtitle}>Your Intelligent Campus Companion</p>
                    <p className={styles.tagline}>AI-Powered Support • Academic Resources • 24/7 Assistance</p>
                </div>

            <motion.div className={styles.authCard} {...pageTransition}>

                {/* Role Toggle: Student / Faculty */}
                <div className={styles.roleToggle}>
                    <button
                        type="button"
                        className={`${styles.roleButton} ${role === 'student' ? styles.roleActive : ''}`}
                        onClick={() => setRole('student')}
                    >
                        🎓 Student
                    </button>
                    <button
                        type="button"
                        className={`${styles.roleButton} ${role === 'faculty' ? styles.roleActive : ''}`}
                        onClick={() => setRole('faculty')}
                    >
                        📋 Faculty
                    </button>
                </div>

                {/* Admin indicator */}
                {role === 'admin' && (
                    <div style={{
                        textAlign: 'center',
                        marginBottom: '16px',
                        padding: '8px 16px',
                        background: 'rgba(168, 85, 247, 0.12)',
                        borderRadius: '10px',
                        border: '1px solid rgba(168, 85, 247, 0.25)',
                        color: '#c084fc',
                        fontSize: '13px',
                        fontWeight: 500,
                    }}>
                        🛡️ Admin Login Mode
                    </div>
                )}

                {/* Forgot Password Modal */}
                {showForgotPassword ? (
                    <div className={styles.form}>
                        <div className={styles.formGroup}>
                            <label className={styles.label}>Enter your email to reset password</label>
                            <input
                                type="email"
                                value={forgotEmail}
                                onChange={(e) => setForgotEmail(e.target.value)}
                                className={styles.input}
                                placeholder="your.email@example.com"
                                disabled={forgotLoading}
                                autoComplete="email"
                            />
                        </div>
                        <motion.button
                            type="button"
                            className={styles.submitButton}
                            onClick={handleForgotPassword}
                            disabled={forgotLoading}
                            whileHover={{ scale: forgotLoading ? 1 : 1.02 }}
                            whileTap={{ scale: forgotLoading ? 1 : 0.98 }}
                        >
                            {forgotLoading ? 'Sending...' : 'Send Reset Link'}
                        </motion.button>
                        <div className={styles.links}>
                            <button
                                type="button"
                                className={styles.forgotLink}
                                onClick={() => setShowForgotPassword(false)}
                                style={{ textAlign: 'center' }}
                            >
                                ← Back to Login
                            </button>
                        </div>
                    </div>
                ) : (
                    <>
                        {/* Login Form */}
                        <form onSubmit={handleSubmit} className={styles.form}>
                            <div className={styles.formGroup}>
                                <label htmlFor="email" className={styles.label}>
                                    {role === 'student' ? 'Student Email' : role === 'faculty' ? 'Faculty Email' : 'Admin Email'}
                                </label>
                                <input
                                    type="email"
                                    id="email"
                                    name="email"
                                    value={formData.email}
                                    onChange={handleChange}
                                    className={`${styles.input} ${errors.email ? styles.inputError : ''}`}
                                    placeholder={role === 'student' ? 'student.id@college.edu' : 'you@aceec.ac.in'}
                                    disabled={loading}
                                    autoComplete="email"
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
                                    autoComplete="current-password"
                                />
                                {errors.password && <span className={styles.errorText}>{errors.password}</span>}
                            </div>

                            {/* Remember me + Forgot Password */}
                            <div className={styles.formExtras}>
                                <label className={styles.rememberMe}>
                                    <input
                                        type="checkbox"
                                        checked={rememberMe}
                                        onChange={(e) => setRememberMe(e.target.checked)}
                                    />
                                    <span>Remember me</span>
                                </label>
                                <button
                                    type="button"
                                    className={styles.forgotLink}
                                    onClick={() => setShowForgotPassword(true)}
                                >
                                    Forgot Password?
                                </button>
                            </div>

                            {/* Submit */}
                            <motion.button
                                type="submit"
                                className={styles.submitButton}
                                disabled={loading}
                                whileHover={{ scale: loading ? 1 : 1.02 }}
                                whileTap={{ scale: loading ? 1 : 0.98 }}
                            >
                                {loading ? 'Logging in...' : 'Access ACE ASSIST'}
                                {!loading && <span className={styles.submitArrow}>→</span>}
                            </motion.button>
                        </form>

                        {/* Links */}
                        <div className={styles.links}>
                            <p className={styles.linkText}>
                                New to ACE ASSIST?{' '}
                                <Link to="/register" className={styles.link}>
                                    Create Account
                                </Link>
                            </p>
                        </div>
                    </>
                )}
            </motion.div>
            </div>
        </div>
    );
};

export default Login;
