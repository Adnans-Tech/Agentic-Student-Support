/**
 * Admin Announcements Manager
 * Allows creating, editing, and deleting global broadcast announcements.
 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Megaphone, Plus, Edit2, Trash2, X, AlertCircle } from 'lucide-react';
import adminService from '../../services/adminService';
import styles from './Announcements.module.css';

const fadeInUp = { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } };

const Announcements = () => {
    const [announcements, setAnnouncements] = useState([]);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(null);

    // Modal State
    const [showModal, setShowModal] = useState(false);
    const [editingId, setEditingId] = useState(null);
    const [formData, setFormData] = useState({
        title: '',
        body: '',
        target: 'all',
        is_active: 1
    });

    useEffect(() => {
        fetchAnnouncements();
    }, []);

    const fetchAnnouncements = async () => {
        try {
            setLoading(true);
            const res = await adminService.getAnnouncements();
            if (res.success) {
                setAnnouncements(res.data);
            } else {
                alert(res.error || 'Failed to fetch announcements');
            }
        } catch (err) {
            console.error(err);
            alert('Server error loading announcements');
        } finally {
            setLoading(false);
        }
    };

    const handleOpenCreate = () => {
        setFormData({ title: '', body: '', target: 'all', is_active: 1 });
        setEditingId(null);
        setShowModal(true);
    };

    const handleOpenEdit = (announcement) => {
        setFormData({
            title: announcement.title,
            body: announcement.body,
            target: announcement.target,
            is_active: announcement.is_active
        });
        setEditingId(announcement.id);
        setShowModal(true);
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Delete this announcement permanently?')) return;

        try {
            setActionLoading(id);
            const res = await adminService.deleteAnnouncement(id);
            if (res.success) {
                setAnnouncements(prev => prev.filter(a => a.id !== id));
            } else {
                alert(res.error || 'Failed to delete');
            }
        } catch (err) {
            console.error(err);
            alert('Server error deleting announcement');
        } finally {
            setActionLoading(null);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        if (!formData.title.trim() || !formData.body.trim()) {
            alert('Title and body are required.');
            return;
        }

        try {
            setActionLoading('submit');

            if (editingId) {
                const res = await adminService.updateAnnouncement(editingId, formData);
                if (res.success) {
                    setAnnouncements(prev => prev.map(a => a.id === editingId ? { ...a, ...formData } : a));
                    setShowModal(false);
                } else {
                    alert(res.error || 'Update failed');
                }
            } else {
                const res = await adminService.createAnnouncement(formData);
                if (res.success) {
                    // Assuming the create API returns the new ID, but typically we can just refetch or rely on returned object
                    fetchAnnouncements();
                    setShowModal(false);
                } else {
                    alert(res.error || 'Creation failed');
                }
            }
        } catch (err) {
            console.error(err);
            alert('Server error saving announcement');
        } finally {
            setActionLoading(null);
        }
    };

    const formatDate = (dateString) => {
        if (!dateString) return '';
        return new Date(dateString).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
    };

    return (
        <motion.div className={styles.pageContainer} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>

            <div className={styles.pageHeader}>
                <div className={styles.headerTitle}>
                    <h1>Announcements</h1>
                    <p>Broadcast messages to students, faculty, or both</p>
                </div>
                <button className={styles.addBtn} onClick={handleOpenCreate}>
                    <Plus size={18} /> New Announcement
                </button>
            </div>

            {loading ? (
                <div className={styles.fullPageLoader}>
                    <div className={styles.spinner} />
                </div>
            ) : (
                <motion.div className={styles.grid} variants={fadeInUp} initial="initial" animate="animate">
                    {announcements.length === 0 && (
                        <div className={styles.emptyState}>
                            <Megaphone size={48} style={{ opacity: 0.3, marginBottom: '16px' }} />
                            <h3>No Announcements</h3>
                            <p>Click "New Announcement" to broadcast a message.</p>
                        </div>
                    )}

                    {announcements.map(announcement => (
                        <div
                            key={announcement.id}
                            className={`${styles.announcementCard} ${!announcement.is_active ? styles.inactive : ''}`}
                        >
                            <div className={`${styles.statusStrip} ${announcement.is_active ? styles.active : styles.inactive}`} />

                            <div className={styles.cardHeader}>
                                <h3 className={styles.cardTitle}>{announcement.title}</h3>
                            </div>

                            <div className={styles.cardMeta}>
                                <span className={`${styles.targetBadge} ${styles[announcement.target || ''] || ''}`}>
                                    {(announcement.target || 'all').toUpperCase()}
                                </span>
                                <span>· {formatDate(announcement.created_at)}</span>
                            </div>

                            <div className={styles.cardBody}>
                                {announcement.body}
                            </div>

                            <div className={styles.cardActions}>
                                <button
                                    className={styles.actionBtn}
                                    onClick={() => handleOpenEdit(announcement)}
                                    disabled={actionLoading !== null}
                                >
                                    <Edit2 size={14} /> Edit
                                </button>
                                <button
                                    className={`${styles.actionBtn} ${styles.danger}`}
                                    onClick={() => handleDelete(announcement.id)}
                                    disabled={actionLoading === announcement.id}
                                >
                                    <Trash2 size={14} /> Delete
                                </button>
                            </div>
                        </div>
                    ))}
                </motion.div>
            )}

            {/* Create/Edit Modal */}
            <AnimatePresence>
                {showModal && (
                    <motion.div
                        className={styles.modalOverlay}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                    >
                        <motion.div
                            className={styles.modalContent}
                            initial={{ scale: 0.95, y: 20 }}
                            animate={{ scale: 1, y: 0 }}
                            exit={{ scale: 0.95, y: 20 }}
                        >
                            <div className={styles.modalHeader}>
                                <h2>{editingId ? 'Edit Announcement' : 'New Announcement'}</h2>
                                <button className={styles.closeBtn} onClick={() => setShowModal(false)}>
                                    <X size={20} />
                                </button>
                            </div>

                            <form onSubmit={handleSubmit}>
                                <div className={styles.modalBody}>
                                    <div className={styles.formGroup}>
                                        <label>Title</label>
                                        <input
                                            type="text"
                                            className={styles.formInput}
                                            value={formData.title}
                                            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                                            placeholder="E.g., System Maintenance"
                                            required
                                        />
                                    </div>

                                    <div className={styles.formGroup}>
                                        <label>Target Audience</label>
                                        <select
                                            className={styles.formSelect}
                                            value={formData.target}
                                            onChange={(e) => setFormData({ ...formData, target: e.target.value })}
                                        >
                                            <option value="all">Everyone (Students & Faculty)</option>
                                            <option value="student">Students Only</option>
                                            <option value="faculty">Faculty Only</option>
                                        </select>
                                    </div>

                                    <div className={styles.formGroup}>
                                        <label>Message Body</label>
                                        <textarea
                                            className={styles.formTextarea}
                                            value={formData.body}
                                            onChange={(e) => setFormData({ ...formData, body: e.target.value })}
                                            placeholder="Enter announcement details..."
                                            required
                                        />
                                    </div>

                                    {editingId && (
                                        <label className={styles.formCheckbox}>
                                            <input
                                                type="checkbox"
                                                checked={formData.is_active === 1}
                                                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked ? 1 : 0 })}
                                            />
                                            Show to users (Active)
                                        </label>
                                    )}
                                </div>

                                <div className={styles.modalFooter}>
                                    <button
                                        type="button"
                                        className={styles.btnCancel}
                                        onClick={() => setShowModal(false)}
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        type="submit"
                                        className={styles.btnSubmit}
                                        disabled={actionLoading === 'submit'}
                                    >
                                        {actionLoading === 'submit' ? 'Saving...' : (editingId ? 'Save Changes' : 'Broadcast')}
                                    </button>
                                </div>
                            </form>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

        </motion.div>
    );
};

export default Announcements;
