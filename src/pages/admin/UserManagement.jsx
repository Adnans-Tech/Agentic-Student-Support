/**
 * Admin User Management
 * Directory of all student and faculty users, enforcing a department-first search flow.
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
    Search,
    Shield,
    UserX,
    UserCheck,
    Key,
    UserCircle,
    Building2,
    Users
} from 'lucide-react';
import adminService from '../../services/adminService';
import styles from './UserManagement.module.css';

const fadeInUp = { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } };

const UserManagement = () => {
    const [activeTab, setActiveTab] = useState('students');
    const [departments, setDepartments] = useState([]);
    const [selectedDept, setSelectedDept] = useState('');
    const [searchQuery, setSearchQuery] = useState('');

    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [actionLoading, setActionLoading] = useState(null);
    const [error, setError] = useState(null);

    // Initial load: fetch departments
    useEffect(() => {
        const fetchDepts = async () => {
            try {
                const res = await adminService.getDepartments();
                if (res.success) {
                    setDepartments(res.data);
                }
            } catch (err) {
                console.error("Failed to load generic departments", err);
            }
        };
        fetchDepts();
    }, []);

    // Effect: reset search and results when tab or department changes
    useEffect(() => {
        setUsers([]);
        setError(null);
        setSearchQuery('');
        // Auto-fetch all users globally on tab/dept change implicitly
        fetchUsersForDept(selectedDept, activeTab, '');
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeTab, selectedDept]);

    const fetchUsersForDept = async (dept, tab, query) => {
        try {
            setLoading(true);
            setError(null);

            const req = tab === 'students'
                ? adminService.getStudents(dept, query)
                : adminService.getFaculty(dept, query);

            const res = await req;

            if (res.success) {
                setUsers(res.data);
            } else {
                setError(res.error || 'Failed to fetch users');
                setUsers([]);
            }
        } catch (err) {
            console.error('Search error:', err);
            setError('Failed to connect to server');
            setUsers([]);
        } finally {
            setLoading(false);
        }
    };

    const handleSearch = async (e) => {
        if (e) e.preventDefault();
        fetchUsersForDept(selectedDept, activeTab, searchQuery);
    };

    const handleToggleActive = async (userId, currentStatus) => {
        if (!window.confirm(`Are you sure you want to ${currentStatus ? 'deactivate' : 'activate'} this user account?`)) return;

        try {
            setActionLoading(userId);
            const res = await adminService.toggleUserActive(userId);
            if (res.success) {
                // Update local list
                setUsers(prev => prev.map(u =>
                    u.user_id === userId ? { ...u, is_active: res.new_status } : u
                ));
            } else {
                alert(res.error || 'Failed to toggle account status');
            }
        } catch (err) {
            console.error(err);
            alert('Server error occurred');
        } finally {
            setActionLoading(null);
        }
    };

    const handlePasswordReset = async (userId, name) => {
        const tempPass = prompt(`Enter a temporary, strong password to assign to ${name}:\n(At least 8 chars, 1 uppercase, 1 lowercase, 1 number, 1 special char)`);
        if (!tempPass) return;

        try {
            setActionLoading(`pwd-${userId}`);
            const res = await adminService.resetPassword(userId, tempPass);
            if (res.success) {
                alert(`Password successfully reset. \n\nPlease provide this temporary password to the user securely: ${tempPass}`);
            } else {
                alert(res.error || 'Failed to reset password');
            }
        } catch (err) {
            console.error(err);
            alert('Server error occurred while resetting password');
        } finally {
            setActionLoading(null);
        }
    };

    const getInitials = (name) => {
        if (!name) return 'U';
        return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
    };

    return (
        <motion.div className={styles.pageContainer} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>

            <div className={styles.pageHeader}>
                <h1>User Directory</h1>
                <p>Manage student and faculty accounts by department</p>
            </div>

            {/* Tab Navigation */}
            <div className={styles.tabRow}>
                <button
                    className={`${styles.tabBtn} ${activeTab === 'students' ? styles.activeTab : ''}`}
                    onClick={() => setActiveTab('students')}
                >
                    <Users size={16} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'text-bottom' }} />
                    Students
                </button>
                <button
                    className={`${styles.tabBtn} ${activeTab === 'faculty' ? styles.activeTab : ''}`}
                    onClick={() => setActiveTab('faculty')}
                >
                    <Building2 size={16} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'text-bottom' }} />
                    Faculty
                </button>
            </div>

            {/* Search Controls */}
            <motion.div className={styles.controlsCard} variants={fadeInUp} initial="initial" animate="animate">
                <div className={styles.controlGroup}>
                    <label>Department (Optional)</label>
                    <select
                        className={styles.deptSelect}
                        value={selectedDept}
                        onChange={(e) => setSelectedDept(e.target.value)}
                    >
                        <option value="">-- Select a Department --</option>
                        {departments.map(d => (
                            <option key={d} value={d}>{d}</option>
                        ))}
                    </select>
                </div>

                <form className={styles.controlGroup} style={{ flex: 2 }} onSubmit={handleSearch}>
                    <label>Search {activeTab === 'students' ? 'Name or Roll Number' : 'Name or Employee ID'}</label>
                    <div className={styles.searchBox}>
                        <Search className={styles.searchIcon} size={18} />
                        <input
                            type="text"
                            className={styles.searchInput}
                            placeholder={`Type to search...`}
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                </form>

                <button
                    className={styles.searchBtn}
                    onClick={handleSearch}
                    disabled={loading}
                >
                    {loading ? 'Searching...' : 'Search'}
                </button>
            </motion.div>

            {/* Error Message */}
            {error && (
                <div style={{ color: 'var(--color-error)', background: 'var(--color-error-bg)', padding: '12px 16px', borderRadius: '8px', marginBottom: '24px' }}>
                    {error}
                </div>
            )}

            {/* Results Table */}
            <motion.div className={styles.tableCard} variants={fadeInUp} initial="initial" animate="animate">
                <div className={styles.tableWrapper}>
                    <table className={styles.usersTable}>
                        <thead>
                            <tr>
                                <th>User</th>
                                <th>{activeTab === 'students' ? 'Roll Number' : 'Employee ID'}</th>
                                <th>Status</th>
                                <th>Registration</th>
                                <th>Account Role</th>
                                <th style={{ textAlign: 'right' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {!loading && users.map((user, idx) => (
                                <tr key={user.user_id || `unregistered-${user.id || idx}`}>
                                    <td>
                                        <div className={styles.userCell}>
                                            <div className={styles.userAvatar}>
                                                {getInitials(user.name)}
                                            </div>
                                            <div className={styles.userInfo}>
                                                <span className={styles.userName}>{user.name}</span>
                                                <span className={styles.userEmail}>{user.email}</span>
                                            </div>
                                        </div>
                                    </td>
                                    <td>
                                        {activeTab === 'students' ? user.roll_number : user.employee_id}
                                    </td>
                                    <td>
                                        <span className={`${styles.statusBadge} ${user.is_active ? styles.statusActive : styles.statusInactive}`}>
                                            {user.is_active ? 'Active' : 'Deactivated'}
                                        </span>
                                    </td>
                                    <td>
                                        {user.is_registered ? (
                                            <span style={{ color: '#059669', fontWeight: 500, fontSize: '13px' }}>
                                                <UserCheck size={14} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'text-bottom' }} />
                                                Registered
                                            </span>
                                        ) : (
                                            <span style={{ color: 'var(--color-text-muted)', fontWeight: 500, fontSize: '13px' }}>
                                                Unregistered
                                            </span>
                                        )}
                                    </td>
                                    <td>
                                        {user.is_admin ? (
                                            <span style={{ color: '#F59E0B', fontWeight: 600, fontSize: '12px' }}>
                                                <Shield size={12} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'middle' }} />
                                                Global Admin
                                            </span>
                                        ) : (
                                            <span style={{ color: 'var(--color-text-muted)', fontSize: '13px' }}>
                                                {activeTab === 'students' ? 'Student' : 'Faculty'}
                                            </span>
                                        )}
                                    </td>
                                    <td style={{ textAlign: 'right' }}>
                                        <div className={styles.actionGroup} style={{ justifyContent: 'flex-end' }}>
                                            <button
                                                className={styles.actionBtn}
                                                title={user.is_registered ? "Reset Password" : "Can't reset password for unregistered user"}
                                                onClick={() => handlePasswordReset(user.user_id, user.name)}
                                                disabled={!user.is_registered || actionLoading === `pwd-${user.user_id}`}
                                            >
                                                <Key size={14} />
                                            </button>

                                            {(!user.is_admin) && (
                                                <button
                                                    className={`${styles.actionBtn} ${user.is_active ? styles.danger : styles.success}`}
                                                    title={!user.is_registered ? "Account not created yet" : (user.is_active ? "Deactivate Account" : "Activate Account")}
                                                    onClick={() => handleToggleActive(user.user_id, user.is_active)}
                                                    disabled={!user.is_registered || actionLoading === user.user_id}
                                                >
                                                    {user.is_active ? <UserX size={14} /> : <UserCheck size={14} />}
                                                </button>
                                            )}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Empty & Loading States inside table card */}
                {loading && (
                    <div className={styles.emptyState}>
                        <div className={styles.loadingSpinner}></div>
                        <div style={{ marginTop: '12px' }}>Searching across {selectedDept}...</div>
                    </div>
                )}

                {!loading && users.length === 0 && !error && (
                    <div className={styles.emptyState}>
                        <div className={styles.emptyStateCol}>
                            <UserCircle size={48} className={styles.emptyIcon} />
                            <span>No users found {selectedDept ? `in ${selectedDept}` : ''} matching your search.</span>
                        </div>
                    </div>
                )}
            </motion.div>
        </motion.div>
    );
};

export default UserManagement;
