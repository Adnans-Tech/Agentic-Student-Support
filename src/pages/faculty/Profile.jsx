/**
 * Faculty Profile — Full featured design matching Student Profile pattern
 * Sections: Profile Header + Photo, Details (view/edit), Appearance, Security
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { pageTransition, fadeInUp } from '../../animations/variants';
import { getCurrentUser } from '../../utils/auth';
import facultyService from '../../services/facultyService';
import authService from '../../services/authService';
import { useTheme } from '../../contexts/ThemeContext';
import {
    User, Mail, Hash, Building2, Briefcase, Phone, Camera, Trash2,
    Edit3, AlertCircle, Sun, Moon, Lock, Eye, EyeOff, Shield,
    MapPin, FileText, Linkedin, Github, Globe, Palette
} from 'lucide-react';
import styles from './Profile.module.css';

const API_BASE = import.meta.env.VITE_API_URL || '';

const FacultyProfile = () => {
    const user = getCurrentUser();
    const { theme, toggleTheme, toggleFacultyTheme } = useTheme();
    const fileInputRef = useRef(null);

    // Profile state
    const [profileData, setProfileData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [isEditing, setIsEditing] = useState(false);
    const [editForm, setEditForm] = useState({});
    const [saving, setSaving] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [toast, setToast] = useState(null);

    // Password state
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

    // === DATA FETCHING ===

    const fetchProfile = useCallback(async () => {
        try {
            setLoading(true);
            const data = await facultyService.getProfile();
            setProfileData(data);
            const p = data.profile || {};
            setEditForm({
                full_name: p.full_name || '',
                phone: p.phone || '',
                office_room: p.office_room || '',
                bio: p.bio || '',
                linkedin: p.linkedin || '',
                github: p.github || '',
                researchgate: p.researchgate || '',
            });


            setError(null);
        } catch (err) {
            setError(err?.error || 'Failed to load profile');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchProfile(); }, [fetchProfile]);

    // === PROFILE ACTIONS ===

    const handleSaveProfile = async () => {
        setSaving(true);
        try {
            await facultyService.updateProfile(editForm);
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
            await facultyService.uploadPhoto(file);
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
            await facultyService.deletePhoto();
            showToast('Photo removed');
            fetchProfile();
        } catch (err) {
            showToast(err?.error || 'Failed to delete photo', 'error');
        }
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
            setTimeout(() => authService.logout(), 2000);
        } catch (err) {
            showToast(err?.error || 'Failed to change password', 'error');
        } finally {
            setChangingPassword(false);
        }
    };



    const getInitials = (name) => {
        if (!name) return '?';
        return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
    };

    // === RENDER ===

    if (loading) {
        return (
            <motion.div {...pageTransition} className={styles.loading}>
                <div className={styles.spinner}></div>
                <p>Loading profile...</p>
            </motion.div>
        );
    }

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
                        <span className={styles.badge}><Hash size={12} /> {profile.employee_id || 'N/A'}</span>
                        <span className={styles.badge}><Building2 size={12} /> {profile.department}</span>
                        <span className={styles.badge}><Briefcase size={12} /> {profile.designation || 'Faculty'}</span>
                        {profile.profile_photo && (
                            <span className={`${styles.badge} ${styles.badgeDanger}`}
                                onClick={handleDeletePhoto} title="Remove photo">
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
                        {/* Editable: Full Name */}
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

                        {/* Editable: Phone */}
                        <div className={styles.fieldGroup}>
                            <label><Phone size={12} /> Phone</label>
                            {isEditing ? (
                                <input value={editForm.phone}
                                    onChange={e => setEditForm(prev => ({ ...prev, phone: e.target.value }))}
                                    placeholder="10-digit number" maxLength={10} className={styles.formInput} />
                            ) : (
                                <div className={styles.value}>{profile.phone || 'Not set'}</div>
                            )}
                        </div>

                        {/* Read-only fields */}
                        <div className={styles.fieldGroup}>
                            <label><Mail size={12} /> Email</label>
                            <div className={styles.value}>{profile.email}</div>
                        </div>
                        <div className={styles.fieldGroup}>
                            <label><Hash size={12} /> Employee ID</label>
                            <div className={styles.value}>{profile.employee_id || 'N/A'}</div>
                        </div>
                        <div className={styles.fieldGroup}>
                            <label><Building2 size={12} /> Department</label>
                            <div className={styles.value}>{profile.department}</div>
                        </div>
                        <div className={styles.fieldGroup}>
                            <label><Briefcase size={12} /> Designation</label>
                            <div className={styles.value}>{profile.designation || 'N/A'}</div>
                        </div>

                        {/* Editable: Office Room */}
                        <div className={styles.fieldGroup}>
                            <label><MapPin size={12} /> Office / Cabin</label>
                            {isEditing ? (
                                <input value={editForm.office_room}
                                    onChange={e => setEditForm(prev => ({ ...prev, office_room: e.target.value }))}
                                    placeholder="e.g. Room 204, Block A" className={styles.formInput} />
                            ) : (
                                <div className={styles.value}>{profile.office_room || 'Not set'}</div>
                            )}
                        </div>

                        {/* Editable: Links */}
                        <div className={styles.fieldGroup}>
                            <label><Linkedin size={12} /> LinkedIn</label>
                            {isEditing ? (
                                <input value={editForm.linkedin}
                                    onChange={e => setEditForm(prev => ({ ...prev, linkedin: e.target.value }))}
                                    placeholder="LinkedIn URL" className={styles.formInput} />
                            ) : (
                                <div className={styles.value}>
                                    {profile.linkedin ? <a href={profile.linkedin} target="_blank" rel="noreferrer" style={{ color: 'var(--color-primary)' }}>{profile.linkedin}</a> : 'Not set'}
                                </div>
                            )}
                        </div>
                        <div className={styles.fieldGroup}>
                            <label><Github size={12} /> GitHub</label>
                            {isEditing ? (
                                <input value={editForm.github}
                                    onChange={e => setEditForm(prev => ({ ...prev, github: e.target.value }))}
                                    placeholder="GitHub URL" className={styles.formInput} />
                            ) : (
                                <div className={styles.value}>
                                    {profile.github ? <a href={profile.github} target="_blank" rel="noreferrer" style={{ color: 'var(--color-primary)' }}>{profile.github}</a> : 'Not set'}
                                </div>
                            )}
                        </div>
                        <div className={styles.fieldGroup}>
                            <label><Globe size={12} /> ResearchGate</label>
                            {isEditing ? (
                                <input value={editForm.researchgate}
                                    onChange={e => setEditForm(prev => ({ ...prev, researchgate: e.target.value }))}
                                    placeholder="ResearchGate URL" className={styles.formInput} />
                            ) : (
                                <div className={styles.value}>
                                    {profile.researchgate ? <a href={profile.researchgate} target="_blank" rel="noreferrer" style={{ color: 'var(--color-primary)' }}>{profile.researchgate}</a> : 'Not set'}
                                </div>
                            )}
                        </div>

                        {/* Editable: Bio (full width) */}
                        <div className={styles.fieldGroupFull}>
                            <label><FileText size={12} /> Bio / Research Interests</label>
                            {isEditing ? (
                                <textarea value={editForm.bio}
                                    onChange={e => setEditForm(prev => ({ ...prev, bio: e.target.value }))}
                                    placeholder="Brief bio, research areas, expertise..."
                                    maxLength={500} className={styles.formTextarea} />
                            ) : (
                                <div className={styles.value}>{profile.bio || 'Not set'}</div>
                            )}
                        </div>
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
                </div>

                {/* Right Column */}
                <div className={styles.rightCol}>
                    {/* Appearance Card */}
                    <motion.div className={styles.card} variants={fadeInUp} initial="initial" animate="animate"
                        transition={{ delay: 0.15 }}>
                        <h3 className={styles.cardTitle}>
                            <Palette size={18} />
                            Appearance
                        </h3>
                        <div className={styles.themeSection}>
                            <p className={styles.themeLabel}>
                                Currently using <strong>{theme === 'faculty-light' ? 'Faculty Light' : theme === 'dark' ? 'Dark' : 'Light'}</strong> theme
                            </p>
                            <button className={styles.themeToggle} onClick={toggleFacultyTheme}>
                                <div className={`${styles.themeToggleTrack} ${theme === 'dark' ? styles.themeToggleDark : ''}`}>
                                    <div className={styles.themeToggleThumb}>
                                        {theme === 'faculty-light' ? <Sun size={14} /> : <Moon size={14} />}
                                    </div>
                                </div>
                                <span>{theme === 'faculty-light' ? 'Switch to Dark' : 'Switch to Faculty Light'}</span>
                            </button>
                        </div>
                    </motion.div>

                    {/* Security Card */}
                    <motion.div className={styles.card} variants={fadeInUp} initial="initial" animate="animate"
                        transition={{ delay: 0.2 }}>
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
                                    transition={{ duration: 0.25 }}>
                                    <div className={styles.fieldGroup}>
                                        <label>Current Password</label>
                                        <div className={styles.passwordInputWrapper}>
                                            <input
                                                type={showCurrentPw ? 'text' : 'password'}
                                                value={passwordForm.current}
                                                onChange={e => setPasswordForm(prev => ({ ...prev, current: e.target.value }))}
                                                placeholder="Enter current password"
                                                className={styles.formInput} />
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
                                                className={styles.formInput} />
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
                                                className={styles.formInput} />
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
                            <p className={styles.hintText}>Click "Change Password" above to update your login credentials.</p>
                        )}
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
                        exit={{ opacity: 0, y: 20 }}>
                        {toast.message}
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
};

export default FacultyProfile;
