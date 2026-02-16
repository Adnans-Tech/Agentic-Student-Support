/**
 * Faculty Register Page
 * Registration form for faculty members with OTP verification
 */

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import authService from '../../services/authService';
import { validators, formatBackendError } from '../../utils/validators';
import { pageTransition, fadeIn } from '../../animations/variants';
import Toast from '../../components/common/Toast';
import styles from './Auth.module.css';

const FacultyRegister = () => {
    const navigate = useNavigate();

    const [formData, setFormData] = useState({
        officialEmail: '',
        fullName: '',
        employeeId: '',
        department: '',
        designation: '',
        password: '',
        confirmPassword: '',
    });

    const [errors, setErrors] = useState({});
    const [loading, setLoading] = useState(false);
    const [toast, setToast] = useState({ show: false, message: '', type: 'error' });
    const [passwordStrength, setPasswordStrength] = useState({ strength: '', score: 0, className: '' });

    const handleChange = (e) => {
        const { name, value } = e.target;

        // Auto-uppercase employee ID
        const processedValue = name === 'employeeId' ? value.toUpperCase() : value;

        setFormData(prev => ({ ...prev, [name]: processedValue }));

        // Password strength check
        if (name === 'password') {
            setPasswordStrength(validators.passwordStrength(value));
        }

        // Clear error
        if (errors[name]) {
            setErrors(prev => ({ ...prev, [name]: null }));
        }
        setToast({ show: false, message: '', type: 'error' });
    };

    const validate = () => {
        const newErrors = {};

        newErrors.officialEmail = validators.officialEmail(formData.officialEmail);
        newErrors.fullName = validators.required(formData.fullName, 'Full name');
        newErrors.employeeId = validators.employeeId(formData.employeeId);
        newErrors.department = validators.required(formData.department, 'Department');
        newErrors.password = validators.password(formData.password);
        newErrors.confirmPassword = validators.confirmPassword(formData.password, formData.confirmPassword);

        setErrors(newErrors);
        return !Object.values(newErrors).some(error => error !== null);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setToast({ show: false, message: '', type: 'error' });

        if (!validate()) return;

        setLoading(true);

        try {
            const response = await authService.registerFaculty(formData);

            if (response.success) {
                // Send OTP automatically
                await authService.sendFacultyOTP(formData.officialEmail);

                // Navigate to OTP verification
                navigate('/faculty/verify-otp', { state: { email: formData.officialEmail } });
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
                style={{ maxWidth: '540px' }}
            >
                {/* Logo */}
                <div className={styles.logoSection}>
                    <img src="/ace_logo.png" alt="ACE Logo" className={styles.logo} />
                    <h1 className={styles.title}>Faculty Registration</h1>
                    <p className={styles.subtitle}>ACE Engineering College</p>
                </div>

                {/* Register Form */}
                <form onSubmit={handleSubmit} className={styles.form}>
                    {/* Full Name & Employee ID */}
                    <div className={styles.formGrid}>
                        <div className={styles.formGroup}>
                            <label htmlFor="fullName" className={styles.label}>Full Name</label>
                            <input
                                type="text"
                                id="fullName"
                                name="fullName"
                                value={formData.fullName}
                                onChange={handleChange}
                                className={`${styles.input} ${errors.fullName ? styles.inputError : ''}`}
                                placeholder="Dr. John Doe"
                                disabled={loading}
                            />
                            {errors.fullName && <span className={styles.errorText}>{errors.fullName}</span>}
                        </div>

                        <div className={styles.formGroup}>
                            <label htmlFor="employeeId" className={styles.label}>Employee ID</label>
                            <input
                                type="text"
                                id="employeeId"
                                name="employeeId"
                                value={formData.employeeId}
                                onChange={handleChange}
                                className={`${styles.input} ${errors.employeeId ? styles.inputError : ''}`}
                                placeholder="FAC12345"
                                disabled={loading}
                            />
                            {errors.employeeId && <span className={styles.errorText}>{errors.employeeId}</span>}
                        </div>
                    </div>

                    {/* Official Email */}
                    <div className={styles.formGroup}>
                        <label htmlFor="officialEmail" className={styles.label}>Official Email</label>
                        <input
                            type="email"
                            id="officialEmail"
                            name="officialEmail"
                            value={formData.officialEmail}
                            onChange={handleChange}
                            className={`${styles.input} ${errors.officialEmail ? styles.inputError : ''}`}
                            placeholder="john.doe@ace.edu"
                            disabled={loading}
                        />
                        {errors.officialEmail && <span className={styles.errorText}>{errors.officialEmail}</span>}
                    </div>

                    {/* Department & Designation */}
                    <div className={styles.formGrid}>
                        <div className={styles.formGroup}>
                            <label htmlFor="department" className={styles.label}>Department</label>
                            <select
                                id="department"
                                name="department"
                                value={formData.department}
                                onChange={handleChange}
                                className={`${styles.input} ${errors.department ? styles.inputError : ''}`}
                                disabled={loading}
                            >
                                <option value="">Select Department</option>
                                <option value="Computer Science">Computer Science</option>
                                <option value="Electronics">Electronics</option>
                                <option value="Mechanical">Mechanical</option>
                                <option value="Civil">Civil</option>
                                <option value="Electrical">Electrical</option>
                                <option value="Administration">Administration</option>
                            </select>
                            {errors.department && <span className={styles.errorText}>{errors.department}</span>}
                        </div>

                        <div className={styles.formGroup}>
                            <label htmlFor="designation" className={styles.label}>Designation (Optional)</label>
                            <input
                                type="text"
                                id="designation"
                                name="designation"
                                value={formData.designation}
                                onChange={handleChange}
                                className={styles.input}
                                placeholder="Professor"
                                disabled={loading}
                            />
                        </div>
                    </div>

                    {/* Password */}
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

                        {/* Password Strength */}
                        {formData.password && (
                            <div className={styles.passwordStrength}>
                                <div className={styles.strengthBar}>
                                    <div className={`${styles.strengthFill} ${styles[passwordStrength.className]}`} />
                                </div>
                                <span className={`${styles.strengthLabel} ${styles[passwordStrength.className]}`}>
                                    {passwordStrength.strength}
                                </span>
                            </div>
                        )}
                    </div>

                    {/* Confirm Password */}
                    <div className={styles.formGroup}>
                        <label htmlFor="confirmPassword" className={styles.label}>Confirm Password</label>
                        <input
                            type="password"
                            id="confirmPassword"
                            name="confirmPassword"
                            value={formData.confirmPassword}
                            onChange={handleChange}
                            className={`${styles.input} ${errors.confirmPassword ? styles.inputError : ''}`}
                            placeholder="••••••••"
                            disabled={loading}
                        />
                        {errors.confirmPassword && <span className={styles.errorText}>{errors.confirmPassword}</span>}
                    </div>

                    {/* Submit */}
                    <motion.button
                        type="submit"
                        className={styles.submitButton}
                        disabled={loading}
                        whileHover={{ scale: loading ? 1 : 1.02 }}
                        whileTap={{ scale: loading ? 1 : 0.98 }}
                    >
                        {loading ? 'Creating Account...' : 'Register'}
                    </motion.button>
                </form>

                {/* Links */}
                <div className={styles.links}>
                    <p className={styles.linkText}>
                        Already have an account?{' '}
                        <Link to="/faculty/login" className={styles.link}>
                            Login
                        </Link>
                    </p>
                    <p className={styles.linkText}>
                        Are you a student?{' '}
                        <Link to="/login" className={styles.link}>
                            Student Login
                        </Link>
                    </p>
                </div>
            </motion.div>
        </div>
    );
};

export default FacultyRegister;
