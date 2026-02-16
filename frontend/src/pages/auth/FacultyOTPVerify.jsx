/**
 * Faculty OTP Verification Page
 * 6-digit OTP input with resend cooldown
 */

import { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import authService from '../../services/authService';
import { formatBackendError } from '../../utils/validators';
import { pageTransition, fadeIn, otpStagger, otpDigit } from '../../animations/variants';
import Toast from '../../components/common/Toast';
import styles from './Auth.module.css';

const FacultyOTPVerify = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const email = location.state?.email;

    const [otp, setOtp] = useState(['', '', '', '', '', '']);
    const [loading, setLoading] = useState(false);
    const [toast, setToast] = useState({ show: false, message: '', type: 'error' });
    const [resendCooldown, setResendCooldown] = useState(0);
    const [resending, setResending] = useState(false);

    const inputRefs = [
        useRef(null),
        useRef(null),
        useRef(null),
        useRef(null),
        useRef(null),
        useRef(null),
    ];

    // Redirect if no email
    useEffect(() => {
        if (!email) {
            navigate('/faculty/register');
        }
    }, [email, navigate]);

    // Auto-focus first input
    useEffect(() => {
        if (inputRefs[0].current) {
            inputRefs[0].current.focus();
        }
    }, []);

    // Cooldown timer
    useEffect(() => {
        if (resendCooldown > 0) {
            const timer = setTimeout(() => {
                setResendCooldown(resendCooldown - 1);
            }, 1000);
            return () => clearTimeout(timer);
        }
    }, [resendCooldown]);

    const handleChange = (index, value) => {
        // Only allow digits
        if (value && !/^\d$/.test(value)) return;

        const newOtp = [...otp];
        newOtp[index] = value;
        setOtp(newOtp);

        // Auto-focus next input
        if (value && index < 5) {
            inputRefs[index + 1].current?.focus();
        }

        // Auto-submit when all 6 digits are entered
        if (newOtp.every(digit => digit) && newOtp.join('').length === 6) {
            handleVerify(newOtp.join(''));
        }

        setToast({ show: false, message: '', type: 'error' });
    };

    const handleKeyDown = (index, e) => {
        // Handle backspace
        if (e.key === 'Backspace') {
            if (!otp[index] && index > 0) {
                inputRefs[index - 1].current?.focus();
            }
        }

        // Handle arrow keys
        if (e.key === 'ArrowLeft' && index > 0) {
            inputRefs[index - 1].current?.focus();
        }
        if (e.key === 'ArrowRight' && index < 5) {
            inputRefs[index + 1].current?.focus();
        }
    };

    const handlePaste = (e) => {
        e.preventDefault();
        const pastedData = e.clipboardData.getData('text').trim();

        // Only process if it's 6 digits
        if (/^\d{6}$/.test(pastedData)) {
            const newOtp = pastedData.split('');
            setOtp(newOtp);
            inputRefs[5].current?.focus();

            // Auto-submit
            handleVerify(pastedData);
        }
    };

    const handleVerify = async (otpValue = otp.join('')) => {
        if (otpValue.length !== 6) {
            setToast({
                show: true,
                message: 'Please enter complete 6-digit OTP',
                type: 'error'
            });
            return;
        }

        setLoading(true);
        setToast({ show: false, message: '', type: 'error' });

        try {
            const response = await authService.verifyFacultyOTP(email, otpValue);

            if (response.success) {
                // Navigate to faculty dashboard
                navigate('/faculty/dashboard');
            } else {
                setToast({
                    show: true,
                    message: formatBackendError(response),
                    type: 'error'
                });
                // Clear OTP on error
                setOtp(['', '', '', '', '', '']);
                inputRefs[0].current?.focus();
            }
        } catch (error) {
            setToast({
                show: true,
                message: formatBackendError(error),
                type: 'error'
            });
            // Clear OTP on error
            setOtp(['', '', '', '', '', '']);
            inputRefs[0].current?.focus();
        } finally {
            setLoading(false);
        }
    };

    const handleResend = async () => {
        if (resendCooldown > 0 || resending) return;

        setResending(true);
        setToast({ show: false, message: '', type: 'error' });

        try {
            const response = await authService.sendFacultyOTP(email, true);

            if (response.success) {
                setToast({
                    show: true,
                    message: 'OTP sent successfully! Check your email.',
                    type: 'success'
                });
                setResendCooldown(60); // 60 second cooldown
                setOtp(['', '', '', '', '', '']);
                inputRefs[0].current?.focus();
            } else {
                if (response.wait_seconds) {
                    setResendCooldown(response.wait_seconds);
                    setToast({
                        show: true,
                        message: formatBackendError(response),
                        type: 'error'
                    });
                } else {
                    setToast({
                        show: true,
                        message: formatBackendError(response),
                        type: 'error'
                    });
                }
            }
        } catch (error) {
            if (error.wait_seconds) {
                setResendCooldown(error.wait_seconds);
            }
            setToast({
                show: true,
                message: formatBackendError(error),
                type: 'error'
            });
        } finally {
            setResending(false);
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
                    <h1 className={styles.title}>Verify Your Email</h1>
                    <p className={styles.subtitle}>
                        We've sent a 6-digit OTP to<br />
                        <strong>{email}</strong>
                    </p>
                </div>

                {/* OTP Input */}
                <motion.div
                    className={styles.otpContainer}
                    variants={otpStagger}
                    initial="hidden"
                    animate="visible"
                >
                    {otp.map((digit, index) => (
                        <motion.input
                            key={index}
                            ref={inputRefs[index]}
                            type="text"
                            maxLength={1}
                            value={digit}
                            onChange={(e) => handleChange(index, e.target.value)}
                            onKeyDown={(e) => handleKeyDown(index, e)}
                            onPaste={index === 0 ? handlePaste : undefined}
                            className={styles.otpInput}
                            disabled={loading}
                            variants={otpDigit}
                        />
                    ))}
                </motion.div>

                {/* Resend Button */}
                <div className={styles.resendSection}>
                    {resendCooldown > 0 ? (
                        <p className={styles.resendText}>
                            Resend OTP in <strong>{resendCooldown}s</strong>
                        </p>
                    ) : (
                        <button
                            onClick={handleResend}
                            className={styles.resendButton}
                            disabled={resending}
                        >
                            {resending ? 'Sending...' : 'Resend OTP'}
                        </button>
                    )}
                </div>

                {/* Loading State */}
                {loading && (
                    <motion.p
                        className={styles.loadingText}
                        {...fadeIn}
                    >
                        Verifying OTP...
                    </motion.p>
                )}
            </motion.div>
        </div>
    );
};

export default FacultyOTPVerify;
