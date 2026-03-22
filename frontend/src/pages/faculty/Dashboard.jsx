/**
 * Faculty Dashboard — Phase 1
 * Stats cards, 7-day activity chart, recent tickets/emails, weekly timetable
 */

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Ticket, Mail, CheckCircle, TrendingUp,
    Calendar, Edit3, AlertCircle,
} from 'lucide-react';
import facultyService from '../../services/facultyService';
import styles from './Dashboard.module.css';

// === TIMETABLE CONSTANTS ===
const DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
const TIMINGS = [
    { label: '09:30-10:20', type: 'period' },
    { label: '10:20-11:10', type: 'period' },
    { label: 'Break', name: 'B\nR\nE\nA\nK', type: 'break' },
    { label: '11:20-12:10', type: 'period' },
    { label: '12:10-01:00', type: 'period' },
    { label: 'Lunch', name: 'L\nU\nN\nC\nH', type: 'break' },
    { label: '02:00-02:50', type: 'period' },
    { label: '02:50-03:40', type: 'period' },
    { label: '03:40-04:30', type: 'period' },
];

const fadeInUp = { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } };

const FacultyDashboard = () => {
    // --- State ---
    const [loading, setLoading] = useState(true);
    const [stats, setStats] = useState({});
    const [trend, setTrend] = useState([]);
    const [recentTickets, setRecentTickets] = useState([]);
    const [recentEmails, setRecentEmails] = useState([]);
    const [timetable, setTimetable] = useState({});
    const [activeTab, setActiveTab] = useState('tickets');

    // Timetable editing
    const [isEditing, setIsEditing] = useState(false);
    const [editingCell, setEditingCell] = useState(null);
    const [cellForm, setCellForm] = useState({ subject: '', class: '' });
    const [saving, setSaving] = useState(false);
    const [toast, setToast] = useState(null);

    // --- Fetch Data ---
    const fetchDashboard = useCallback(async () => {
        try {
            setLoading(true);
            const data = await facultyService.getDashboardData();
            if (data.success) {
                setStats(data.stats || {});
                setTrend(data.trend || []);
                setRecentTickets(data.recent_tickets || []);
                setRecentEmails(data.recent_emails || []);
                setTimetable(data.timetable || {});
            }
        } catch (err) {
            console.error('Dashboard fetch error:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

    // --- Toast helper ---
    const showToast = (message, type = 'success') => {
        setToast({ message, type });
        setTimeout(() => setToast(null), 3000);
    };

    // --- Timetable Editing ---
    const handleCellClick = (day, periodIndex) => {
        if (!isEditing) return;
        const cellData = timetable[day]?.[periodIndex] || { subject: '', class: '' };
        setEditingCell({ day, periodIndex });
        setCellForm({ subject: cellData.subject || '', class: cellData.class || '' });
    };

    const handleSaveCell = () => {
        if (!editingCell) return;
        const { day, periodIndex } = editingCell;
        setTimetable(prev => ({
            ...prev,
            [day]: { ...(prev[day] || {}), [periodIndex]: { ...cellForm } }
        }));
        setEditingCell(null);
        setCellForm({ subject: '', class: '' });
    };

    const handleCancelCellEdit = () => {
        setEditingCell(null);
        setCellForm({ subject: '', class: '' });
    };

    const handleSaveTimetable = async () => {
        try {
            setSaving(true);
            await facultyService.saveTimetable(timetable);
            showToast('Timetable saved successfully!');
            setIsEditing(false);
        } catch (err) {
            showToast('Failed to save timetable', 'error');
        } finally {
            setSaving(false);
        }
    };

    // --- Chart helpers ---
    const maxChartVal = Math.max(1, ...trend.map(d => Math.max(d.tickets, d.emails)));

    const getDayLabel = (dateStr) => {
        const d = new Date(dateStr + 'T00:00:00');
        return ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][d.getDay()];
    };

    const getStatusClass = (status) => {
        if (!status) return 'sent';
        const s = status.toLowerCase();
        if (s.includes('open') || s.includes('progress')) return 'open';
        if (s.includes('resolved')) return 'resolved';
        if (s.includes('closed')) return 'closed';
        return 'sent';
    };

    const formatTime = (ts) => {
        if (!ts) return '';
        try {
            const d = new Date(ts);
            return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
        } catch { return ''; }
    };

    // --- Render ---
    if (loading) {
        return (
            <div className={styles.loadingContainer}>
                <div className={styles.spinner} />
                <span style={{ color: 'var(--color-text-muted)', fontSize: '14px' }}>Loading dashboard…</span>
            </div>
        );
    }

    return (
        <motion.div className={styles.dashboardContainer} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
            {/* Header */}
            <div className={styles.pageHeader}>
                <h1>Faculty Dashboard</h1>
                <p>Overview of your teaching activity and schedule</p>
            </div>

            {/* Stats Cards */}
            <motion.div className={styles.statsGrid} variants={fadeInUp} initial="initial" animate="animate" transition={{ delay: 0.05 }}>
                <div className={styles.statCard}>
                    <div className={`${styles.statIconBox} ${styles.amber}`}><Ticket size={22} /></div>
                    <div className={styles.statInfo}>
                        <h4>Open Tickets</h4>
                        <div className={styles.statValue}>{stats.open_tickets ?? 0}</div>
                        <div className={styles.statSub}>{stats.tickets_today ?? 0} created today</div>
                    </div>
                </div>
                <div className={styles.statCard}>
                    <div className={`${styles.statIconBox} ${styles.green}`}><CheckCircle size={22} /></div>
                    <div className={styles.statInfo}>
                        <h4>Resolved (7d)</h4>
                        <div className={styles.statValue}>{stats.resolved_7d ?? 0}</div>
                        <div className={styles.statSub}>Last 7 days</div>
                    </div>
                </div>
                <div className={styles.statCard}>
                    <div className={`${styles.statIconBox} ${styles.blue}`}><Mail size={22} /></div>
                    <div className={styles.statInfo}>
                        <h4>Total Emails</h4>
                        <div className={styles.statValue}>{stats.unread_emails ?? 0}</div>
                        <div className={styles.statSub}>{stats.emails_today ?? 0} received today</div>
                    </div>
                </div>
                <div className={styles.statCard}>
                    <div className={`${styles.statIconBox} ${styles.purple}`}><TrendingUp size={22} /></div>
                    <div className={styles.statInfo}>
                        <h4>Today's Activity</h4>
                        <div className={styles.statValue}>{(stats.tickets_today ?? 0) + (stats.emails_today ?? 0)}</div>
                        <div className={styles.statSub}>Tickets + Emails</div>
                    </div>
                </div>
            </motion.div>

            {/* Chart + Recent */}
            <motion.div className={styles.dualPanel} variants={fadeInUp} initial="initial" animate="animate" transition={{ delay: 0.1 }}>
                {/* 7-Day Activity Chart */}
                <div className={styles.card}>
                    <div className={styles.cardTitle}>
                        <TrendingUp size={16} /> Weekly Activity
                    </div>
                    <div className={styles.chartArea}>
                        {trend.map((day, i) => (
                            <div key={i} className={styles.chartBar}>
                                <div className={styles.barGroup}>
                                    <div className={`${styles.bar} ${styles.tickets}`}
                                        style={{ height: `${(day.tickets / maxChartVal) * 140}px` }} />
                                    <div className={`${styles.bar} ${styles.emails}`}
                                        style={{ height: `${(day.emails / maxChartVal) * 140}px` }} />
                                </div>
                                <span className={styles.chartLabel}>{getDayLabel(day.date)}</span>
                            </div>
                        ))}
                    </div>
                    <div className={styles.chartLegend}>
                        <div className={styles.legendItem}><span className={`${styles.legendDot} ${styles.green}`} /> Tickets</div>
                        <div className={styles.legendItem}><span className={`${styles.legendDot} ${styles.blue}`} /> Emails</div>
                    </div>
                </div>

                {/* Recent Activity */}
                <div className={styles.card}>
                    <div className={styles.cardTitle}>Recent Updates</div>
                    <div className={styles.tabRow}>
                        <button className={`${styles.tabBtn} ${activeTab === 'tickets' ? styles.activeTab : ''}`}
                            onClick={() => setActiveTab('tickets')}>Tickets</button>
                        <button className={`${styles.tabBtn} ${activeTab === 'emails' ? styles.activeTab : ''}`}
                            onClick={() => setActiveTab('emails')}>Emails</button>
                    </div>
                    <div className={styles.recentList}>
                        {activeTab === 'tickets' ? (
                            recentTickets.length > 0 ? recentTickets.map((t, i) => (
                                <div key={i} className={styles.recentItem}>
                                    <span className={`${styles.recentDot} ${styles[getStatusClass(t.status)]}`} />
                                    <div className={styles.recentInfo}>
                                        <div className={styles.recentTitle}>{t.ticket_id} — {t.category}</div>
                                        <div className={styles.recentMeta}>{t.student_email} · {formatTime(t.created_at)}</div>
                                    </div>
                                    <span className={`${styles.recentBadge} ${styles[getStatusClass(t.status)]}`}>{t.status}</span>
                                </div>
                            )) : <div className={styles.emptyState}>No recent tickets</div>
                        ) : (
                            recentEmails.length > 0 ? recentEmails.map((e, i) => (
                                <div key={i} className={styles.recentItem}>
                                    <span className={`${styles.recentDot} ${styles[getStatusClass(e.status)]}`} />
                                    <div className={styles.recentInfo}>
                                        <div className={styles.recentTitle}>{e.subject}</div>
                                        <div className={styles.recentMeta}>{e.student_name} · {formatTime(e.timestamp)}</div>
                                    </div>
                                    <span className={`${styles.recentBadge} ${styles[getStatusClass(e.status)]}`}>{e.status}</span>
                                </div>
                            )) : <div className={styles.emptyState}>No recent emails</div>
                        )}
                    </div>
                </div>
            </motion.div>

            {/* Timetable */}
            <motion.div className={`${styles.card} ${styles.timetableSection}`}
                variants={fadeInUp} initial="initial" animate="animate" transition={{ delay: 0.15 }}>
                <div className={styles.timetableHeader}>
                    <div className={styles.cardTitle} style={{ margin: 0 }}>
                        <Calendar size={18} /> Faculty Timetable
                    </div>
                    {!isEditing && (
                        <button className={styles.addEventBtn} onClick={() => setIsEditing(true)}>
                            <Edit3 size={16} /> Edit Timetable
                        </button>
                    )}
                    {isEditing && (
                        <div className={styles.ttEditBtnRow}>
                            <button className={styles.btnSecondary} onClick={() => setIsEditing(false)}>Cancel</button>
                            <button className={styles.btnPrimary} onClick={handleSaveTimetable} disabled={saving}>
                                {saving ? 'Saving…' : 'Save Timetable'}
                            </button>
                        </div>
                    )}
                </div>

                {isEditing && (
                    <div className={styles.editHint}>
                        <AlertCircle size={14} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'middle' }} />
                        Click on any period cell to edit its class / subject.
                    </div>
                )}

                <div className={styles.timetableTableWrapper}>
                    <table className={styles.timetableTable}>
                        <thead>
                            <tr>
                                <th className={styles.timeHeader}>DAY/TIME</th>
                                {TIMINGS.map((time, index) => (
                                    <th key={index} className={styles.timeColHeader}>{time.label}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {DAYS.map((day) => (
                                <tr key={day}>
                                    <td className={styles.dayCol}>{day}</td>
                                    {TIMINGS.map((time, index) => {
                                        if (time.type === 'break') {
                                            if (day === DAYS[0]) {
                                                return (
                                                    <td key={index} rowSpan={DAYS.length} className={styles.breakCol}>
                                                        {time.name.split('\n').map((char, i) => <div key={i}>{char}</div>)}
                                                    </td>
                                                );
                                            }
                                            return null;
                                        }

                                        const cellData = timetable[day]?.[index] || { subject: '', class: '' };
                                        const isCellEditing = editingCell?.day === day && editingCell?.periodIndex === index;
                                        const hasData = cellData.subject || cellData.class;

                                        return (
                                            <td key={index}
                                                className={`${styles.periodCol} ${isEditing ? styles.editableCell : ''}`}
                                                onClick={() => handleCellClick(day, index)}>
                                                {isCellEditing ? (
                                                    <div className={styles.cellEditor} onClick={e => e.stopPropagation()}>
                                                        <input className={styles.cellInput} placeholder="Subject"
                                                            value={cellForm.subject}
                                                            onChange={e => setCellForm(prev => ({ ...prev, subject: e.target.value }))}
                                                            autoFocus />
                                                        <input className={styles.cellInput} placeholder="Class"
                                                            value={cellForm.class}
                                                            onChange={e => setCellForm(prev => ({ ...prev, class: e.target.value }))} />
                                                        <div className={styles.cellActions}>
                                                            <button className={styles.cellBtnSave} onClick={handleSaveCell}>✓</button>
                                                            <button className={styles.cellBtnCancel} onClick={handleCancelCellEdit}>✕</button>
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <div className={styles.cellContent}>
                                                        {hasData ? (
                                                            <>
                                                                <div className={styles.cellSubject}>{cellData.subject}</div>
                                                                <div className={styles.cellClass}>{cellData.class}</div>
                                                            </>
                                                        ) : (
                                                            <div className={styles.cellEmpty}>-</div>
                                                        )}
                                                    </div>
                                                )}
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </motion.div>

            {/* Toast */}
            <AnimatePresence>
                {toast && (
                    <motion.div className={`${styles.toast} ${styles[toast.type]}`}
                        initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 20 }}>
                        {toast.message}
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
};

export default FacultyDashboard;
