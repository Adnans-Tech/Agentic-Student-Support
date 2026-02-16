import { motion } from 'framer-motion';
import { pageTransition } from '../../animations/variants';
import { getCurrentUser } from '../../utils/auth';

const FacultyDashboard = () => {
    const user = getCurrentUser();

    return (
        <motion.div {...pageTransition} style={{ padding: '2rem' }}>
            <h1>Faculty Dashboard</h1>
            <p>Welcome, {user?.name}!</p>
            <p style={{ marginTop: '2rem' }}>Faculty features coming soon...</p>
        </motion.div>
    );
};

export default FacultyDashboard;
