/**
 * Student Profile — Simplified Per User Request
 * Shows: Profile photo, student details, CGPA input, theme toggle
 * Removed: Quick Actions, Daily Limits, Weekly Chart, Recent Activity
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { pageTransition, fadeInUp } from '../../animations/variants';
import { getCurrentUser } from '../../utils/auth';
import studentService from '../../services/studentService';
import authService from '../../services/authService';
import { useTheme } from '../../contexts/ThemeContext';
import {
    User, Mail, Hash, Building2, GraduationCap, Phone, Camera, Trash2,
    Edit3, AlertCircle, Sun, Moon, GraduationCap as CgpaIcon,
    Lock, Eye, EyeOff, Check, Shield
} from 'lucide-react';
import styles from './Profile.module.css';

const API_BASE = import.meta.env.VITE_API_URL || '';

const StudentProfile = () => {
    const user = getCurrentUser();
    const { theme, toggleTheme } = useTheme();
    const fileInputRef = useRef(null);

    const [profileData, setProfileData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [isEditing, setIsEditing] = useState(false);
    const [editForm, setEditForm] = useState({ full_name: '', phone: '' });
    const [saving, setSaving] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [toast, setToast] = useState(null);
    const [cgpa, setCgpa] = useState('');

    // Change Password state
    const [showChangePassword, setShowChangePassword] = useState(false);
    const [passwordForm, setPasswordForm] = useState({ current: '', newPw: '', confirm: '' });
    const [changingPassword, setChangingPassword] = useState(false);
    const [showCurrentPw, setShowCurrentPw] = useState(false);
    const [showNewPw, setShowNewPw] = useState(false);
    const [showConfirmPw, setShowConfirmPw] = useState(false);

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
        // Load CGPA from localStorage
        const key = `ace-cgpa-${user?.roll_number || 'default'}`;
        const saved = localStorage.getItem(key);
        if (saved) setCgpa(saved);
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

    const handleCgpaChange = (value) => {
        // Allow only valid CGPA values: 0-10 with up to 2 decimal places
        const num = value.replace(/[^0-9.]/g, '');
        if (num === '' || (parseFloat(num) >= 0 && parseFloat(num) <= 10 && /^\d{0,2}(\.\d{0,2})?$/.test(num))) {
            setCgpa(num);
            const key = `ace-cgpa-${user?.roll_number || 'default'}`;
            localStorage.setItem(key, num);
        }
    };

    const getInitials = (name) => {
        if (!name) return '?';
        return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
    };

    const handleChangePassword = async () => {
        if (!passwordForm.current || !passwordForm.newPw || !passwordForm.confirm) {
            showToast('All password fields are required', 'error');
            return;
        }
        if (passwordForm.newPw !== passwordForm.confirm) {
            showToast('New passwords do not match', 'error');
            return;
        }
        if (passwordForm.newPw.length < 8) {
            showToast('Password must be at least 8 characters', 'error');
            return;
        }
        setChangingPassword(true);
        try {
            const result = await authService.changePassword(
                passwordForm.current, passwordForm.newPw, passwordForm.confirm
            );
            showToast(result.message || 'Password changed successfully!');
            setPasswordForm({ current: '', newPw: '', confirm: '' });
            setShowChangePassword(false);
            // Log out after password change so user re-authenticates
            setTimeout(() => authService.logout(), 2000);
        } catch (err) {
            showToast(err?.error || 'Failed to change password', 'error');
        } finally {
            setChangingPassword(false);
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
    const photoUrl = profile.profile_photo ? `${API_BASE}${profile.profile_photo}` : null;

    return (
        <motion.div {...pageTransition} className={styles.profilePage}>
            {/* === PROFILE HEADER === */}
            <motion.div className={styles.profileHeader} variants={fadeInUp} initial="initial" animate="animate">
                <div className={styles.avatarSection}>
                    {photoUrl ? (
                        <img src={photoUrl} alt="Profile" className={styles.avatar} />
                    ) : (
                        <div className={styles.avatarPlaceholder}>
                            {getInitials(profile.full_name)}
                        </div>
                    )}
                    <input ref={fileInputRef} type="file" accept="image/jpeg,image/png"
                        onChange={handlePhotoUpload} style={{ display: 'none' }} />
                    <div className={styles.avatarOverlay}
                        onClick={() => fileInputRef.current?.click()}
                        title={uploading ? 'Uploading...' : 'Change photo'}>
                        <Camera size={18} />
                    </div>
                </div>

                <div className={styles.headerInfo}>
                    <h1>{profile.full_name}</h1>
                    <p className={styles.email}>{profile.email}</p>
                    <div className={styles.headerBadges}>
                        <span className={styles.badge}><Hash size={12} /> {profile.roll_number}</span>
                        <span className={styles.badge}><Building2 size={12} /> {profile.department}</span>
                        <span className={styles.badge}><GraduationCap size={12} /> Year {profile.year}</span>
                        {profile.profile_photo && (
                            <span className={`${styles.badge} ${styles.badgeDanger}`}
                                onClick={handleDeletePhoto} title="Remove photo" style={{ cursor: 'pointer' }}>
                                <Trash2 size={12} /> Remove Photo
                            </span>
                        )}
                    </div>
                </div>
            </motion.div>

            {/* === TWO COLUMN LAYOUT === */}
            <div className={styles.twoCol}>
                <div className={styles.leftCol}>
                {/* Profile Details Card */}
                <motion.div className={styles.card} variants={fadeInUp} initial="initial" animate="animate"
                    transition={{ delay: 0.1 }}>
                    <h3 className={styles.cardTitle}>
                        <User size={18} /> Profile Details
                        <button className={styles.editToggle} onClick={() => setIsEditing(!isEditing)}>
                            <Edit3 size={14} /> {isEditing ? 'Cancel' : 'Edit'}
                        </button>
                    </h3>

                    <div className={styles.detailsGrid}>
                        <div className={styles.fieldGroup}>
                            <label>Full Name</label>
                            {isEditing ? (
                                <input value={editForm.full_name}
                                    onChange={e => setEditForm(prev => ({ ...prev, full_name: e.target.value }))}
                                    placeholder="Your name" className={styles.formInput} />
                            ) : (
                                <div className={styles.value}>{profile.full_name}</div>
                            )}
                        </div>
                        <div className={styles.fieldGroup}>
                            <label>Phone</label>
                            {isEditing ? (
                                <input value={editForm.phone}
                                    onChange={e => setEditForm(prev => ({ ...prev, phone: e.target.value }))}
                                    placeholder="10-digit number" maxLength={10} className={styles.formInput} />
                            ) : (
                                <div className={styles.value}>{profile.phone || 'Not set'}</div>
                            )}
                        </div>
                        <div className={styles.fieldGroup}><label>Email</label><div className={styles.value}>{profile.email}</div></div>
                        <div className={styles.fieldGroup}><label>Roll Number</label><div className={styles.value}>{profile.roll_number}</div></div>
                        <div className={styles.fieldGroup}><label>Department</label><div className={styles.value}>{profile.department}</div></div>
                        <div className={styles.fieldGroup}><label>Year</label><div className={styles.value}>{profile.year}</div></div>
                    </div>

                    {isEditing && (
                        <div className={styles.editBtnRow}>
                            <button className={styles.btnSecondary} onClick={() => setIsEditing(false)}>Cancel</button>
                            <button className={styles.btnPrimary} onClick={handleSaveProfile} disabled={saving}>
                                {saving ? 'Saving...' : 'Save Changes'}
                            </button>
                        </div>
                    )}
                </motion.div>

                    {/* Change Password Card */}
                    <motion.div className={styles.card} variants={fadeInUp} initial="initial" animate="animate"
                        transition={{ delay: 0.25 }}>
                        <h3 className={styles.cardTitle}>
                            <Shield size={18} /> Security
                            <button className={styles.editToggle}
                                onClick={() => setShowChangePassword(!showChangePassword)}>
                                <Lock size={14} /> {showChangePassword ? 'Cancel' : 'Change Password'}
                            </button>
                        </h3>

                        <AnimatePresence>
                            {showChangePassword && (
                                <motion.div
                                    className={styles.changePasswordForm}
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    exit={{ opacity: 0, height: 0 }}
                                    transition={{ duration: 0.25 }}
                                >
                                    <div className={styles.fieldGroup}>
                                        <label>Current Password</label>
                                        <div className={styles.passwordInputWrapper}>
                                            <input
                                                type={showCurrentPw ? 'text' : 'password'}
                                                value={passwordForm.current}
                                                onChange={e => setPasswordForm(prev => ({ ...prev, current: e.target.value }))}
                                                placeholder="Enter current password"
                                                className={styles.formInput}
                                            />
                                            <button type="button" className={styles.eyeBtn}
                                                onClick={() => setShowCurrentPw(!showCurrentPw)}>
                                                {showCurrentPw ? <EyeOff size={16} /> : <Eye size={16} />}
                                            </button>
                                        </div>
                                    </div>
                                    <div className={styles.fieldGroup}>
                                        <label>New Password</label>
                                        <div className={styles.passwordInputWrapper}>
                                            <input
                                                type={showNewPw ? 'text' : 'password'}
                                                value={passwordForm.newPw}
                                                onChange={e => setPasswordForm(prev => ({ ...prev, newPw: e.target.value }))}
                                                placeholder="Enter new password"
                                                className={styles.formInput}
                                            />
                                            <button type="button" className={styles.eyeBtn}
                                                onClick={() => setShowNewPw(!showNewPw)}>
                                                {showNewPw ? <EyeOff size={16} /> : <Eye size={16} />}
                                            </button>
                                        </div>
                                    </div>
                                    <div className={styles.fieldGroup}>
                                        <label>Confirm New Password</label>
                                        <div className={styles.passwordInputWrapper}>
                                            <input
                                                type={showConfirmPw ? 'text' : 'password'}
                                                value={passwordForm.confirm}
                                                onChange={e => setPasswordForm(prev => ({ ...prev, confirm: e.target.value }))}
                                                placeholder="Confirm new password"
                                                className={styles.formInput}
                                            />
                                            <button type="button" className={styles.eyeBtn}
                                                onClick={() => setShowConfirmPw(!showConfirmPw)}>
                                                {showConfirmPw ? <EyeOff size={16} /> : <Eye size={16} />}
                                            </button>
                                        </div>
                                    </div>
                                    <div className={styles.editBtnRow}>
                                        <button className={styles.btnSecondary}
                                            onClick={() => { setShowChangePassword(false); setPasswordForm({ current: '', newPw: '', confirm: '' }); }}>
                                            Cancel
                                        </button>
                                        <button className={styles.btnPrimary}
                                            onClick={handleChangePassword}
                                            disabled={changingPassword}>
                                            {changingPassword ? 'Changing...' : 'Update Password'}
                                        </button>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {!showChangePassword && (
                            <p className={styles.cgpaHint}>Click "Change Password" above to update your login credentials.</p>
                        )}
                    </motion.div>


                </div>

                {/* Right Column: CGPA + Theme */}
                <div className={styles.rightCol}>
                    {/* CGPA Card */}
                    <motion.div className={styles.card} variants={fadeInUp} initial="initial" animate="animate"
                        transition={{ delay: 0.15 }}>
                        <h3 className={styles.cardTitle}>
                            <GraduationCap size={18} /> Academic Performance
                        </h3>
                        <div className={styles.cgpaSection}>
                            <label className={styles.cgpaLabel}>Current CGPA</label>
                            <div className={styles.cgpaInputWrapper}>
                                <input
                                    type="text"
                                    value={cgpa}
                                    onChange={(e) => handleCgpaChange(e.target.value)}
                                    placeholder="0.00"
                                    className={styles.cgpaInput}
                                    maxLength={5}
                                />
                                <span className={styles.cgpaMax}>/ 10</span>
                            </div>
                            <p className={styles.cgpaHint}>Enter your CGPA. It will be displayed on your dashboard.</p>
                        </div>
                    </motion.div>

                    {/* Theme Toggle Card */}
                    <motion.div className={styles.card} variants={fadeInUp} initial="initial" animate="animate"
                        transition={{ delay: 0.2 }}>
                        <h3 className={styles.cardTitle}>
                            {theme === 'light' ? <Sun size={18} /> : <Moon size={18} />}
                            Appearance
                        </h3>
                        <div className={styles.themeSection}>
                            <p className={styles.themeLabel}>
                                Currently using <strong>{theme === 'light' ? 'Light' : 'Dark'}</strong> theme
                            </p>
                            <button className={styles.themeToggle} onClick={toggleTheme}>
                                <div className={`${styles.themeToggleTrack} ${theme === 'dark' ? styles.themeToggleDark : ''}`}>
                                    <div className={styles.themeToggleThumb}>
                                        {theme === 'light' ? <Sun size={14} /> : <Moon size={14} />}
                                    </div>
                                </div>
                                <span>{theme === 'light' ? 'Switch to Dark' : 'Switch to Light'}</span>
                            </button>
                        </div>
                    </motion.div>

                </div>
            </div>

            {/* === TOAST === */}
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
