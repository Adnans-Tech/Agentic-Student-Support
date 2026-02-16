import { motion } from 'framer-motion';
import { pageTransition } from '../../animations/variants';

const EmailInbox = () => (
    <motion.div {...pageTransition} style={{ padding: '2rem' }}>
        <h1>Email Inbox</h1>
        <p>Email management coming soon...</p>
    </motion.div>
);

export default EmailInbox;
