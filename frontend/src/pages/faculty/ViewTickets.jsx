import { motion } from 'framer-motion';
import { pageTransition } from '../../animations/variants';

const ViewTickets = () => (
    <motion.div {...pageTransition} style={{ padding: '2rem' }}>
        <h1>View Tickets</h1>
        <p>Ticket management coming soon...</p>
    </motion.div>
);

export default ViewTickets;
