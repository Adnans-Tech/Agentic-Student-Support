/**
 * Student Register Page
 * Registration form with password strength indicator
 */

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import authService from '../../services/authService';
import { validators, formatBackendError } from '../../utils/validators';
import { pageTransition, fadeIn } from '../../animations/variants';
import styles from './Auth.module.css';

const StudentRegister = () => {
    const navigate = useNavigate();

    const [formData, setFormData] = useState({
        email: '',
        rollNumber: '',
        fullName: '',
        password: '',
        department: '',
        year: '',
        phone: '',
    });

    const [errors, setErrors] = useState({});
    const [loading, setLoading] = useState(false);
    const [backendError, setBackendError] = useState('');
    const [passwordStrength, setPasswordStrength] = useState({ strength: '', score: 0, className: '' });

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));

        // Password strength check
        if (name === 'password') {
            setPasswordStrength(validators.passwordStrength(value));
        }

        // Clear error
        if (errors[name]) {
            setErrors(prev => ({ ...prev, [name]: null }));
        }
        setBackendError('');
    };

    const validate = () => {
        const newErrors = {};

        newErrors.email = validators.email(formData.email);
        newErrors.rollNumber = validators.rollNumber(formData.rollNumber);
        newErrors.fullName = validators.required(formData.fullName, 'Full name');
        newErrors.password = validators.password(formData.password);
        newErrors.department = validators.required(formData.department, 'Department');
        newErrors.year = validators.year(formData.year);
        newErrors.phone = validators.phone(formData.phone);

        setErrors(newErrors);
        return !Object.values(newErrors).some(error => error !== null);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setBackendError('');

        if (!validate()) return;

        setLoading(true);

        try {
            console.log('Submitting registration with data:', {
                email: formData.email,
                rollNumber: formData.rollNumber,
                department: formData.department,
                year: formData.year
            }); // DEBUG

            const response = await authService.registerStudent(formData);
            console.log('Registration response:', response); // DEBUG

            if (response.success) {
                // Send OTP automatically
                await authService.sendOTP(formData.email);

                // Navigate to OTP verification
                navigate('/verify-otp', { state: { email: formData.email } });
            } else {
                const errorMsg = formatBackendError(response);
                console.log('Registration failed with error:', errorMsg); // DEBUG
                setBackendError(errorMsg);
            }
        } catch (error) {
            console.error('Registration error caught:', error); // DEBUG
            const errorMsg = formatBackendError(error);
            console.log('Formatted error message:', errorMsg); // DEBUG
            setBackendError(errorMsg);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className={styles.authContainer}>
            <motion.div
                className={styles.authCard}
                {...pageTransition}
                style={{ maxWidth: '540px' }}
            >
                {/* Logo */}
                <div className={styles.logoSection}>
                    <img src="/ace_logo.png" alt="ACE Logo" className={styles.logo} />
                    <h1 className={styles.title}>Student Registration</h1>
                    <p className={styles.subtitle}>ACE Engineering College</p>
                </div>

                {/* Register Form */}
                <form onSubmit={handleSubmit} className={styles.form}>
                    {backendError && (
                        <motion.div className={styles.errorAlert} {...fadeIn}>
                            {backendError}
                        </motion.div>
                    )}

                    {/* Email */}
                    <div className={styles.formGroup}>
                        <label htmlFor="email" className={styles.label}>Email Address</label>
                        <input
                            type="email"
                            id="email"
                            name="email"
                            value={formData.email}
                            onChange={handleChange}
                            className={`${styles.input} ${errors.email ? styles.inputError : ''}`}
                            placeholder="student@ace.edu"
                            disabled={loading}
                        />
                        {errors.email && <span className={styles.errorText}>{errors.email}</span>}
                    </div>

                    {/* Roll Number & Full Name */}
                    <div className={styles.formGrid}>
                        <div className={styles.formGroup}>
                            <label htmlFor="rollNumber" className={styles.label}>Roll Number</label>
                            <input
                                type="text"
                                id="rollNumber"
                                name="rollNumber"
                                value={formData.rollNumber}
                                onChange={(e) => {
                                    // Auto-convert to uppercase
                                    const value = e.target.value.toUpperCase();
                                    handleChange({ target: { name: 'rollNumber', value } });
                                }}
                                className={`${styles.input} ${errors.rollNumber ? styles.inputError : ''}`}
                                placeholder="22AG1A0000"
                                disabled={loading}
                                maxLength={10}
                            />
                            {errors.rollNumber && <span className={styles.errorText}>{errors.rollNumber}</span>}
                            {!errors.rollNumber && (
                                <span className={styles.helperText}>Example: 22AG1A0000 or 22AG1A66A8</span>
                            )}
                        </div>

                        <div className={styles.formGroup}>
                            <label htmlFor="fullName" className={styles.label}>Full Name</label>
                            <input
                                type="text"
                                id="fullName"
                                name="fullName"
                                value={formData.fullName}
                                onChange={handleChange}
                                className={`${styles.input} ${errors.fullName ? styles.inputError : ''}`}
                                placeholder="John Doe"
                                disabled={loading}
                            />
                            {errors.fullName && <span className={styles.errorText}>{errors.fullName}</span>}
                        </div>
                    </div>

                    {/* Department & Year */}
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
                            </select>
                            {errors.department && <span className={styles.errorText}>{errors.department}</span>}
                        </div>

                        <div className={styles.formGroup}>
                            <label htmlFor="year" className={styles.label}>Year</label>
                            <select
                                id="year"
                                name="year"
                                value={formData.year}
                                onChange={handleChange}
                                className={`${styles.input} ${errors.year ? styles.inputError : ''}`}
                                disabled={loading}
                            >
                                <option value="">Select Year</option>
                                <option value="1">1st Year</option>
                                <option value="2">2nd Year</option>
                                <option value="3">3rd Year</option>
                                <option value="4">4th Year</option>
                            </select>
                            {errors.year && <span className={styles.errorText}>{errors.year}</span>}
                        </div>
                    </div>

                    {/* Phone */}
                    <div className={styles.formGroup}>
                        <label htmlFor="phone" className={styles.label}>Phone (Optional)</label>
                        <input
                            type="tel"
                            id="phone"
                            name="phone"
                            value={formData.phone}
                            onChange={handleChange}
                            className={`${styles.input} ${errors.phone ? styles.inputError : ''}`}
                            placeholder="9876543210"
                            disabled={loading}
                        />
                        {errors.phone && <span className={styles.errorText}>{errors.phone}</span>}
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
                        <Link to="/login" className={styles.link}>
                            Login
                        </Link>
                    </p>
                </div>
            </motion.div>
        </div>
    );
};

export default StudentRegister;
