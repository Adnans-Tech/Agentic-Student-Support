/**
 * OTP Verification Page
 * 6-digit OTP input with resend functionality and countdown
 */

import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import authService from '../../services/authService';
import { formatBackendError } from '../../utils/validators';
import { pageTransition, fadeIn, otpStagger, otpDigit } from '../../animations/variants';
import styles from './Auth.module.css';

const OTPVerification = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const email = location.state?.email;

    const [otp, setOtp] = useState(['', '', '', '', '', '']);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [countdown, setCountdown] = useState(0);
    const [resending, setResending] = useState(false);

    const inputRefs = useRef([]);

    // Redirect if no email provided
    useEffect(() => {
        if (!email) {
            navigate('/register');
        }
    }, [email, navigate]);

    // Handle countdown timer
    useEffect(() => {
        if (countdown > 0) {
            const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
            return () => clearTimeout(timer);
        }
    }, [countdown]);

    const handleChange = (index, value) => {
        if (value.length > 1) return; // Only allow single digit
        if (value && !/^\d$/.test(value)) return; // Only numbers

        const newOtp = [...otp];
        newOtp[index] = value;
        setOtp(newOtp);
        setError('');

        // Auto-focus next input
        if (value && index < 5) {
            inputRefs.current[index + 1]?.focus();
        }
    };

    const handleKeyDown = (index, e) => {
        if (e.key === 'Backspace' && !otp[index] && index > 0) {
            inputRefs.current[index - 1]?.focus();
        }
    };

    const handlePaste = (e) => {
        e.preventDefault();
        const pastedData = e.clipboardData.getData('text/plain').slice(0, 6);

        if (!/^\d+$/.test(pastedData)) return;

        const newOtp = pastedData.split('');
        while (newOtp.length < 6) newOtp.push('');
        setOtp(newOtp);

        // Focus last filled input
        inputRefs.current[Math.min(pastedData.length, 5)]?.focus();
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        const otpValue = otp.join('');

        if (otpValue.length !== 6) {
            setError('Please enter all 6 digits');
            return;
        }

        setLoading(true);

        try {
            const response = await authService.verifyOTP(email, otpValue);

            if (response.success) {
                // Success - redirect to dashboard
                navigate('/student/dashboard');
            } else {
                setError(formatBackendError(response));
                setOtp(['', '', '', '', '', '']);
                inputRefs.current[0]?.focus();
            }
        } catch (error) {
            setError(formatBackendError(error));
            setOtp(['', '', '', '', '', '']);
            inputRefs.current[0]?.focus();
        } finally {
            setLoading(false);
        }
    };

    const handleResend = async () => {
        if (countdown > 0 || resending) return;

        setResending(true);
        setError('');

        try {
            const response = await authService.sendOTP(email, true);

            if (response.success) {
                setCountdown(60); // 60 second cooldown
                setOtp(['', '', '', '', '', '']);
                inputRefs.current[0]?.focus();
            } else {
                if (response.wait_seconds) {
                    setCountdown(response.wait_seconds);
                    setError(`Please wait ${response.wait_seconds} seconds before resending`);
                } else {
                    setError(formatBackendError(response));
                }
            }
        } catch (error) {
            setError(formatBackendError(error));
        } finally {
            setResending(false);
        }
    };

    return (
        <div className={styles.authContainer}>
            <motion.div
                className={styles.authCard}
                {...pageTransition}
            >
                {/* Logo */}
                <div className={styles.logoSection}>
                    <img src="/ace_logo.png" alt="ACE Logo" className={styles.logo} />
                    <h1 className={styles.title}>Verify OTP</h1>
                    <p className={styles.subtitle}>
                        Enter the 6-digit code sent to<br />
                        <strong>{email}</strong>
                    </p>
                </div>

                {/* OTP Form */}
                <form onSubmit={handleSubmit} className={styles.form}>
                    {error && (
                        <motion.div className={styles.errorAlert} {...fadeIn}>
                            {error}
                        </motion.div>
                    )}

                    {/* OTP Inputs */}
                    <motion.div
                        className={styles.otpContainer}
                        variants={otpStagger}
                        initial="hidden"
                        animate="visible"
                    >
                        {otp.map((digit, index) => (
                            <motion.input
                                key={index}
                                ref={(el) => (inputRefs.current[index] = el)}
                                type="text"
                                inputMode="numeric"
                                maxLength={1}
                                value={digit}
                                onChange={(e) => handleChange(index, e.target.value)}
                                onKeyDown={(e) => handleKeyDown(index, e)}
                                onPaste={index === 0 ? handlePaste : undefined}
                                className={`${styles.otpDigit} ${error ? styles.otpDigitError : ''}`}
                                disabled={loading}
                                variants={otpDigit}
                            />
                        ))}
                    </motion.div>

                    {/* Submit */}
                    <motion.button
                        type="submit"
                        className={styles.submitButton}
                        disabled={loading || otp.join('').length !== 6}
                        whileHover={{ scale: loading ? 1 : 1.02 }}
                        whileTap={{ scale: loading ? 1 : 0.98 }}
                    >
                        {loading ? 'Verifying...' : 'Verify OTP'}
                    </motion.button>

                    {/* Resend OTP */}
                    <div style={{ textAlign: 'center' }}>
                        <button
                            type="button"
                            onClick={handleResend}
                            className={styles.resendButton}
                            disabled={countdown > 0 || resending}
                        >
                            {resending ? 'Resending...' : countdown > 0 ? `Resend OTP (${countdown}s)` : 'Resend OTP'}
                        </button>

                        {countdown > 0 && (
                            <p className={styles.countdown}>
                                Wait {countdown} seconds to resend
                            </p>
                        )}
                    </div>
                </form>
            </motion.div>
        </div>
    );
};

export default OTPVerification;
