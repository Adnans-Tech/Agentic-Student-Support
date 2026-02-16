import { motion } from 'framer-motion';
import { pageTransition } from '../../animations/variants';
import { getCurrentUser } from '../../utils/auth';
import authService from '../../services/authService';

const FacultyProfile = () => {
    const user = getCurrentUser();

    return (
        <motion.div {...pageTransition} style={{ padding: '2rem' }}>
            <h1>Profile</h1>
            <div style={{ marginTop: '2rem', background: 'var(--color-bg-secondary)', padding: '1.5rem', borderRadius: 'var(--radius-lg)', maxWidth: '500px' }}>
                <p><strong>Name:</strong> {user?.name}</p>
                <p><strong>Email:</strong> {user?.email}</p>
                <p><strong>Department:</strong> {user?.department}</p>
                <p><strong>Designation:</strong> {user?.designation}</p>

                <button
                    onClick={() => authService.logout()}
                    style={{ marginTop: '1.5rem', background: 'var(--color-error)', color: 'white', padding: '0.75rem 1.5rem', borderRadius: 'var(--radius-md)', border: 'none', cursor: 'pointer' }}
                >
                    Logout
                </button>
            </div>
        </motion.div>
    );
};

export default FacultyProfile;
