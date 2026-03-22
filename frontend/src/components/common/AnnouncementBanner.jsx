import { useState, useEffect } from 'react';
import { Megaphone, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import api from '../../services/api';
import styles from './AnnouncementBanner.module.css';

/**
 * AnnouncementBanner
 * Fetches and displays active announcements at the top of the interface.
 * Users can dismiss them locally.
 */
const AnnouncementBanner = () => {
    const [announcements, setAnnouncements] = useState([]);
    const [loading, setLoading] = useState(true);
    const [dismissedIds, setDismissedIds] = useState(() => {
        try {
            const saved = localStorage.getItem('ace_dismissed_announcements');
            return saved ? JSON.parse(saved) : [];
        } catch (e) {
            return [];
        }
    });

    useEffect(() => {
        const fetchAnnouncements = async () => {
            try {
                // The endpoint automatically filters by role (student vs faculty)
                // because of the require_auth decorator and get_active_announcements logic
                const response = await api.get('/announcements/active');
                if (response.data?.success && response.data?.data) {
                    setAnnouncements(response.data.data);
                }
            } catch (error) {
                console.error('Failed to fetch active announcements', error);
            } finally {
                setLoading(false);
            }
        };

        fetchAnnouncements();
    }, []);

    const handleDismiss = (id) => {
        const newDismissed = [...dismissedIds, id];
        setDismissedIds(newDismissed);
        try {
            localStorage.setItem('ace_dismissed_announcements', JSON.stringify(newDismissed));
        } catch (e) {
            console.error('Could not save to localStorage', e);
        }
    };

    if (loading) {
        return <div className={styles.skeleton}></div>;
    }

    // Filter out locally dismissed ones
    const visibleAnnouncements = announcements.filter(a => !dismissedIds.includes(a.id));

    if (visibleAnnouncements.length === 0) {
        return null;
    }

    return (
        <div className={styles.bannerContainer}>
            <AnimatePresence>
                {visibleAnnouncements.map((ann, idx) => (
                    <motion.div
                        key={ann.id}
                        className={styles.banner}
                        initial={{ opacity: 0, y: -10, height: 0 }}
                        animate={{ opacity: 1, y: 0, height: 'auto' }}
                        exit={{ opacity: 0, height: 0, scale: 0.95, marginBottom: 0, overflow: 'hidden' }}
                        transition={{ duration: 0.3 }}
                    >
                        <Megaphone className={styles.bannerIcon} size={20} />

                        <div className={styles.bannerContent}>
                            <h4 className={styles.bannerTitle}>{ann.title}</h4>
                            <p className={styles.bannerBody}>{ann.body}</p>
                        </div>

                        <button
                            className={styles.closeBtn}
                            onClick={() => handleDismiss(ann.id)}
                            title="Dismiss announcement"
                        >
                            <X size={16} />
                        </button>
                    </motion.div>
                ))}
            </AnimatePresence>
        </div>
    );
};

export default AnnouncementBanner;
