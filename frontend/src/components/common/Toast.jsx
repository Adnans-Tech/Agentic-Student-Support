/**
 * Toast/Alert Component
 * Reusable notification component with Framer Motion animations
 */

import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { toastVariants } from '../../animations/variants';
import styles from './Toast.module.css';

const Toast = ({ message, type = 'error', show, onClose, duration = 5000 }) => {
    useEffect(() => {
        if (show && duration > 0) {
            const timer = setTimeout(() => {
                onClose();
            }, duration);

            return () => clearTimeout(timer);
        }
    }, [show, duration, onClose]);

    return (
        <AnimatePresence>
            {show && message && (
                <motion.div
                    className={`${styles.toast} ${styles[type]}`}
                    variants={toastVariants}
                    initial="hidden"
                    animate="visible"
                    exit="exit"
                    onClick={onClose}
                >
                    <div className={styles.toastContent}>
                        <span className={styles.icon}>
                            {type === 'error' && '⚠️'}
                            {type === 'success' && '✓'}
                            {type === 'info' && 'ℹ'}
                        </span>
                        <span className={styles.message}>{message}</span>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};

export default Toast;
