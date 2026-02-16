import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { pageTransition, staggerContainer, staggerItem, fadeInUp } from '../../animations/variants';
import { getCurrentUser } from '../../utils/auth';
import studentService from '../../services/studentService';
import authService from '../../services/authService';
import {
    User, Mail, Hash, Building2, GraduationCap, Phone, Camera, Trash2,
    Ticket, CheckCircle, Clock, Send, Edit3, LogOut, MessageSquare,
    Activity, BarChart3, Shield, AlertCircle, X
} from 'lucide-react';
import styles from './Profile.module.css';
import { useNavigate } from 'react-router-dom';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const StudentProfile = () => {
    const navigate = useNavigate();
    const user = getCurrentUser();
    const fileInputRef = useRef(null);

    const [profileData, setProfileData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [isEditing, setIsEditing] = useState(false);
    const [editForm, setEditForm] = useState({ full_name: '', phone: '' });
    const [saving, setSaving] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [toast, setToast] = useState(null);

    const showToast = useCallback((message, type = 'success') => {
        setToast({ message, type });
        setTimeout(() => setToast(null), 3000);
    }, []);

    const fetchProfile = useCallback(async () => {
        try {
            setLoading(true);
            const data = await studentService.getProfile();
            setProfileData(data);
            setEditForm({
                full_name: data.profile?.full_name || '',
                phone: data.profile?.phone || ''
            });
            setError(null);
        } catch (err) {
            console.error('Profile fetch error:', err);
            setError(err?.error || 'Failed to load profile');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchProfile();
    }, [fetchProfile]);

    const handleSaveProfile = async () => {
        setSaving(true);
        try {
            await studentService.updateProfile(editForm);
            setIsEditing(false);
            showToast('Profile updated successfully');
            fetchProfile();
        } catch (err) {
            showToast(err?.error || 'Failed to update profile', 'error');
        } finally {
            setSaving(false);
        }
    };

    const handlePhotoUpload = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        // Client-side validation
        const validTypes = ['image/jpeg', 'image/png', 'image/jpg'];
        if (!validTypes.includes(file.type)) {
            showToast('Only JPEG and PNG files are allowed', 'error');
            return;
        }
        if (file.size > 2 * 1024 * 1024) {
            showToast('File size must be less than 2MB', 'error');
            return;
        }

        setUploading(true);
        try {
            await studentService.uploadPhoto(file);
            showToast('Photo updated successfully');
            fetchProfile();
        } catch (err) {
            showToast(err?.error || 'Failed to upload photo', 'error');
        } finally {
            setUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const handleDeletePhoto = async () => {
        try {
            await studentService.deletePhoto();
            showToast('Photo removed');
            fetchProfile();
        } catch (err) {
            showToast(err?.error || 'Failed to delete photo', 'error');
        }
    };

    const getInitials = (name) => {
        if (!name) return '?';
        return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
    };

    const getActivityDotClass = (type) => {
        if (type?.includes('TICKET')) return styles.ticket;
        if (type?.includes('EMAIL')) return styles.email;
        if (type?.includes('PROFILE') || type?.includes('PHOTO')) return styles.profile;
        return styles.login;
    };

    const getLimitColor = (remaining, max) => {
        const pct = remaining / max;
        if (pct > 0.5) return styles.green;
        if (pct > 0.2) return styles.yellow;
        return styles.red;
    };

    const formatTimestamp = (ts) => {
        if (!ts) return 'Never';
        try {
            const d = new Date(ts);
            const now = new Date();
            const diff = now - d;
            if (diff < 60000) return 'Just now';
            if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
            if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
            return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
        } catch {
            return ts;
        }
    };

    // Loading state
    if (loading) {
        return (
            <motion.div {...pageTransition} className={styles.loading}>
                <div className={styles.spinner}></div>
                <p>Loading profile...</p>
            </motion.div>
        );
    }

    // Error state
    if (error) {
        return (
            <motion.div {...pageTransition} className={styles.error}>
                <AlertCircle size={48} />
                <p>{error}</p>
                <button className={styles.btnPrimary} onClick={fetchProfile}>Retry</button>
            </motion.div>
        );
    }

    const profile = profileData?.profile || {};
    const stats = profileData?.stats || {};
    const limits = profileData?.limits || {};
    const weeklyChart = profileData?.weekly_chart || [];
    const recentActivity = profileData?.recent_activity || [];

    const photoUrl = profile.profile_photo
        ? `${API_BASE}${profile.profile_photo}`
        : null;

    return (
        <motion.div
            {...pageTransition}
            className={styles.profilePage}
        >
            {/* === PROFILE HEADER === */}
            <motion.div
                className={styles.profileHeader}
                variants={fadeInUp}
                initial="initial"
                animate="animate"
            >
                <div className={styles.avatarSection}>
                    {photoUrl ? (
                        <img src={photoUrl} alt="Profile" className={styles.avatar} />
                    ) : (
                        <div className={styles.avatarPlaceholder}>
                            {getInitials(profile.full_name)}
                        </div>
                    )}
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/jpeg,image/png"
                        onChange={handlePhotoUpload}
                        style={{ display: 'none' }}
                    />
                    <div
                        className={styles.avatarOverlay}
                        onClick={() => fileInputRef.current?.click()}
                        title={uploading ? 'Uploading...' : 'Change photo'}
                    >
                        <Camera />
                    </div>
                </div>

                <div className={styles.headerInfo}>
                    <h1>{profile.full_name}</h1>
                    <p className={styles.email}>{profile.email}</p>
                    <div className={styles.headerBadges}>
                        <span className={styles.badge}>
                            <Hash size={12} /> {profile.roll_number}
                        </span>
                        <span className={styles.badge}>
                            <Building2 size={12} /> {profile.department}
                        </span>
                        <span className={styles.badge}>
                            <GraduationCap size={12} /> Year {profile.year}
                        </span>
                        {profile.profile_photo && (
                            <span
                                className={styles.badge}
                                style={{ cursor: 'pointer', background: 'rgba(239,68,68,0.15)', color: '#ef4444', borderColor: 'rgba(239,68,68,0.2)' }}
                                onClick={handleDeletePhoto}
                                title="Remove photo"
                            >
                                <Trash2 size={12} /> Remove Photo
                            </span>
                        )}
                    </div>
                </div>

                <div style={{ position: 'absolute', top: '1rem', right: '1rem' }}>
                    <button className={styles.logoutBtn} onClick={() => authService.logout()}>
                        <LogOut size={14} /> Logout
                    </button>
                </div>
            </motion.div>

            {/* === COMPLETION BAR === */}
            <motion.div
                className={styles.completionBar}
                variants={fadeInUp}
                initial="initial"
                animate="animate"
                transition={{ delay: 0.1 }}
            >
                <div className={styles.completionLabel}>
                    <span>Profile Completion</span>
                    <span>{profile.completion_pct || 0}%</span>
                </div>
                <div className={styles.completionTrack}>
                    <div
                        className={styles.completionFill}
                        style={{ width: `${profile.completion_pct || 0}%` }}
                    ></div>
                </div>
            </motion.div>

            {/* === STATS CARDS === */}
            <motion.div
                className={styles.statsGrid}
                variants={staggerContainer}
                initial="initial"
                animate="animate"
            >
                <motion.div className={styles.statCard} variants={staggerItem}>
                    <div className={`${styles.statIcon} ${styles.tickets}`}>
                        <Ticket size={22} />
                    </div>
                    <div>
                        <div className={styles.statValue}>{stats.tickets_total || 0}</div>
                        <div className={styles.statLabel}>Total Tickets</div>
                    </div>
                </motion.div>

                <motion.div className={styles.statCard} variants={staggerItem}>
                    <div className={`${styles.statIcon} ${styles.open}`}>
                        <Clock size={22} />
                    </div>
                    <div>
                        <div className={styles.statValue}>{stats.tickets_open || 0}</div>
                        <div className={styles.statLabel}>Open Tickets</div>
                    </div>
                </motion.div>

                <motion.div className={styles.statCard} variants={staggerItem}>
                    <div className={`${styles.statIcon} ${styles.closed}`}>
                        <CheckCircle size={22} />
                    </div>
                    <div>
                        <div className={styles.statValue}>{stats.tickets_closed || 0}</div>
                        <div className={styles.statLabel}>Resolved</div>
                    </div>
                </motion.div>

                <motion.div className={styles.statCard} variants={staggerItem}>
                    <div className={`${styles.statIcon} ${styles.emails}`}>
                        <Send size={22} />
                    </div>
                    <div>
                        <div className={styles.statValue}>{stats.emails_total || 0}</div>
                        <div className={styles.statLabel}>Emails Sent</div>
                    </div>
                </motion.div>
            </motion.div>

            {/* === TWO COLUMN: DETAILS + LIMITS === */}
            <div className={styles.twoCol}>
                {/* Profile Details Card */}
                <motion.div
                    className={styles.card}
                    variants={fadeInUp}
                    initial="initial"
                    animate="animate"
                    transition={{ delay: 0.2 }}
                >
                    <h3>
                        <User size={18} /> Profile Details
                        <button
                            className={styles.editToggle}
                            onClick={() => setIsEditing(!isEditing)}
                        >
                            {isEditing ? 'Cancel' : 'Edit'}
                        </button>
                    </h3>

                    <div className={styles.detailsGrid}>
                        <div className={styles.fieldGroup}>
                            <label>Full Name</label>
                            {isEditing ? (
                                <input
                                    value={editForm.full_name}
                                    onChange={e => setEditForm(prev => ({ ...prev, full_name: e.target.value }))}
                                    placeholder="Your name"
                                />
                            ) : (
                                <div className={styles.value}>{profile.full_name}</div>
                            )}
                        </div>

                        <div className={styles.fieldGroup}>
                            <label>Phone</label>
                            {isEditing ? (
                                <input
                                    value={editForm.phone}
                                    onChange={e => setEditForm(prev => ({ ...prev, phone: e.target.value }))}
                                    placeholder="10-digit number"
                                    maxLength={10}
                                />
                            ) : (
                                <div className={styles.value}>{profile.phone || 'Not set'}</div>
                            )}
                        </div>

                        <div className={styles.fieldGroup}>
                            <label>Email</label>
                            <div className={styles.value}>{profile.email}</div>
                        </div>

                        <div className={styles.fieldGroup}>
                            <label>Roll Number</label>
                            <div className={styles.value}>{profile.roll_number}</div>
                        </div>

                        <div className={styles.fieldGroup}>
                            <label>Department</label>
                            <div className={styles.value}>{profile.department}</div>
                        </div>

                        <div className={styles.fieldGroup}>
                            <label>Year</label>
                            <div className={styles.value}>{profile.year}</div>
                        </div>
                    </div>

                    {isEditing && (
                        <div className={styles.editBtnRow}>
                            <button className={styles.btnSecondary} onClick={() => setIsEditing(false)}>
                                Cancel
                            </button>
                            <button
                                className={styles.btnPrimary}
                                onClick={handleSaveProfile}
                                disabled={saving}
                            >
                                {saving ? 'Saving...' : 'Save Changes'}
                            </button>
                        </div>
                    )}
                </motion.div>

                {/* Limits & Quick Actions Card */}
                <motion.div
                    style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}
                    variants={fadeInUp}
                    initial="initial"
                    animate="animate"
                    transition={{ delay: 0.25 }}
                >
                    {/* Daily Limits */}
                    <div className={styles.card}>
                        <h3><Shield size={18} /> Daily Limits</h3>
                        <div className={styles.limitRow}>
                            <div className={styles.limitInfo}>
                                <span>Emails Today</span>
                                <span>{limits.emails_remaining || 0} / {limits.emails_max || 5} remaining</span>
                            </div>
                            <div className={styles.limitBar}>
                                <div
                                    className={`${styles.limitFill} ${getLimitColor(limits.emails_remaining, limits.emails_max)}`}
                                    style={{ width: `${((limits.emails_remaining || 0) / (limits.emails_max || 5)) * 100}%` }}
                                ></div>
                            </div>
                        </div>
                        <div className={styles.limitRow}>
                            <div className={styles.limitInfo}>
                                <span>Tickets Today</span>
                                <span>{limits.tickets_remaining || 0} / {limits.tickets_max || 3} remaining</span>
                            </div>
                            <div className={styles.limitBar}>
                                <div
                                    className={`${styles.limitFill} ${getLimitColor(limits.tickets_remaining, limits.tickets_max)}`}
                                    style={{ width: `${((limits.tickets_remaining || 0) / (limits.tickets_max || 3)) * 100}%` }}
                                ></div>
                            </div>
                        </div>
                    </div>

                    {/* Quick Actions */}
                    <div className={styles.card}>
                        <h3><Activity size={18} /> Quick Actions</h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            <button className={styles.actionBtn} onClick={() => navigate('/student/chat')}>
                                <MessageSquare /> Chat Support
                            </button>
                            <button className={styles.actionBtn} onClick={() => navigate('/student/tickets')}>
                                <Ticket /> Raise Ticket
                            </button>
                            <button className={styles.actionBtn} onClick={() => navigate('/student/email')}>
                                <Mail /> Send Email
                            </button>
                        </div>
                    </div>
                </motion.div>
            </div>

            {/* === TWO COLUMN: CHART + ACTIVITY === */}
            <div className={styles.twoCol}>
                {/* Weekly Activity Chart */}
                <motion.div
                    className={styles.card}
                    variants={fadeInUp}
                    initial="initial"
                    animate="animate"
                    transition={{ delay: 0.3 }}
                >
                    <h3><BarChart3 size={18} /> Weekly Activity</h3>
                    <div className={styles.chartContainer}>
                        {weeklyChart.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={weeklyChart} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                                    <XAxis
                                        dataKey="date"
                                        tick={{ fill: '#94a3b8', fontSize: 11 }}
                                        tickFormatter={d => {
                                            const date = new Date(d + 'T00:00:00');
                                            return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
                                        }}
                                    />
                                    <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} allowDecimals={false} />
                                    <Tooltip
                                        contentStyle={{
                                            background: '#1e1e2e',
                                            border: '1px solid rgba(99,102,241,0.3)',
                                            borderRadius: '8px',
                                            color: '#e2e8f0'
                                        }}
                                    />
                                    <Legend wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }} />
                                    <Bar dataKey="emails" fill="#ec4899" radius={[4, 4, 0, 0]} name="Emails" />
                                    <Bar dataKey="tickets" fill="#818cf8" radius={[4, 4, 0, 0]} name="Tickets" />
                                </BarChart>
                            </ResponsiveContainer>
                        ) : (
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--color-text-tertiary)' }}>
                                No activity data yet
                            </div>
                        )}
                    </div>
                </motion.div>

                {/* Recent Activity Timeline */}
                <motion.div
                    className={styles.card}
                    variants={fadeInUp}
                    initial="initial"
                    animate="animate"
                    transition={{ delay: 0.35 }}
                >
                    <h3><Clock size={18} /> Recent Activity</h3>
                    <div className={styles.timeline}>
                        {recentActivity.length > 0 ? (
                            recentActivity.slice(0, 8).map((item, i) => (
                                <motion.div
                                    key={i}
                                    className={styles.timelineItem}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.05 * i }}
                                >
                                    <div className={`${styles.timelineDot} ${getActivityDotClass(item.type)}`}></div>
                                    <div className={styles.timelineContent}>
                                        <p>{item.description}</p>
                                        <span>{formatTimestamp(item.timestamp)}</span>
                                    </div>
                                </motion.div>
                            ))
                        ) : (
                            <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--color-text-tertiary)' }}>
                                No recent activity
                            </div>
                        )}
                    </div>
                </motion.div>
            </div>

            {/* === TOAST NOTIFICATION === */}
            <AnimatePresence>
                {toast && (
                    <motion.div
                        className={`${styles.toast} ${styles[toast.type]}`}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 20 }}
                    >
                        {toast.message}
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
};

export default StudentProfile;
