/**
 * Streaming Status Component
 * Real-time execution progress indicator
 */

import { motion } from 'framer-motion';
import styles from './StreamingStatus.module.css';

const StreamingStatus = ({ steps }) => {
    if (!steps || steps.length === 0) return null;

    const getStepIcon = (status) => {
        switch (status) {
            case 'complete':
                return '✓';
            case 'loading':
                return '⟳';
            case 'pending':
                return '○';
            case 'error':
                return '✗';
            default:
                return '○';
        }
    };

    return (
        <div className={styles.streamingStatus}>
            {steps.map((step, index) => (
                <motion.div
                    key={index}
                    className={`${styles.step} ${styles[step.status]}`}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                >
                    <span className={`${styles.stepIcon} ${step.status === 'loading' ? styles.spinning : ''}`}>
                        {getStepIcon(step.status)}
                    </span>
                    <span className={styles.stepText}>{step.text}</span>
                </motion.div>
            ))}
        </div>
    );
};

export default StreamingStatus;
