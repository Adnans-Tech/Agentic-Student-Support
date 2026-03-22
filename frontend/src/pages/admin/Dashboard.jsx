/**
 * Admin Dashboard
 * Unified system stats + weekly ticket resolution trend chart, and collapsible activity feed
 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid,
    Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import {
    Users,
    GraduationCap,
    BookOpen,
    Ticket,
    CheckCircle,
    Activity,
    LogOut,
    MessageSquare,
    Send,
    TrendingUp,
    ChevronDown,
    ChevronUp
} from 'lucide-react';
import adminService from '../../services/adminService';
import styles from './Dashboard.module.css';

const fadeInUp = { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } };

/* ──── Custom Tooltip ──── */
const ChartTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
        <div className={styles.chartTooltip}>
            <div className={styles.tooltipLabel}>{label}</div>
            {payload.map((entry, i) => (
                <div key={i} className={styles.tooltipRow}>
                    <span className={styles.tooltipDot} style={{ background: entry.color }} />
                    <span className={styles.tooltipName}>{entry.name}</span>
                    <span className={styles.tooltipValue}>{entry.value}</span>
                </div>
            ))}
        </div>
    );
};

const AdminDashboard = () => {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [data, setData] = useState({
        total_students: 0,
        total_faculty: 0,
        total_departments: 0,
        open_tickets: 0,
        resolved_tickets: 0,
        recent_activity: []
    });

    // Trend chart — loaded independently
    const [trendData, setTrendData] = useState([]);
    const [trendLoading, setTrendLoading] = useState(true);

    // Collapsible activity state
    const [activityExpanded, setActivityExpanded] = useState(false);

    useEffect(() => {
        fetchDashboardData();
        fetchTicketTrends();
    }, []);

    const fetchDashboardData = async () => {
        try {
            setLoading(true);
            const res = await adminService.getDashboardStats();
            if (res.success) {
                setData(res.data);
            } else {
                setError(res.error || 'Failed to load dashboard');
            }
        } catch (err) {
            console.error('Dashboard Error:', err);
            setError('Failed to connect to server');
        } finally {
            setLoading(false);
        }
    };

    const fetchTicketTrends = async () => {
        try {
            setTrendLoading(true);
            const res = await adminService.getTicketTrends();
            if (res?.success && Array.isArray(res.data)) {
                setTrendData(res.data);
            }
        } catch (err) {
            console.error('Trend fetch error:', err);
        } finally {
            setTrendLoading(false);
        }
    };

    const formatTime = (ts) => {
        if (!ts) return '';
        const date = new Date(ts);
        const today = new Date();
        const isToday = date.getDate() === today.getDate() && date.getMonth() === today.getMonth() && date.getFullYear() === today.getFullYear();

        if (isToday) {
            return `Today, ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
        }
        return date.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    };

    const getActivityIcon = (type) => {
        switch (type) {
            case 'LOGIN': return <LogOut size={16} />;
            case 'TICKET_CREATED': return <Ticket size={16} />;
            case 'TICKET_RESOLVED': return <CheckCircle size={16} />;
            case 'CHAT_MESSAGE': return <MessageSquare size={16} />;
            case 'EMAIL_SENT': return <Send size={16} />;
            default: return <Activity size={16} />;
        }
    };

    const getActivityText = (activity) => {
        switch (activity.action_type) {
            case 'LOGIN': return <span>Logged into the system</span>;
            case 'LOGOUT': return <span>Logged out</span>;
            case 'TICKET_CREATED': return <span>Created a new ticket: <strong>{activity.details?.category || 'Support'}</strong></span>;
            case 'TICKET_UPDATED': return <span>Updated a ticket</span>;
            case 'TICKET_RESOLVED': return <span>Resolved ticket <strong>{activity.details?.ticket_id || 'N/A'}</strong></span>;
            case 'TICKET_CLOSED': return <span>Closed ticket <strong>{activity.details?.ticket_id || 'N/A'}</strong></span>;
            case 'CHAT_MESSAGE': return <span>Sent a message to the AI Assistant</span>;
            case 'EMAIL_SENT': return <span>Sent an email via AI Agent</span>;
            case 'PROFILE_UPDATED': return <span>Updated their profile</span>;
            default: return <span>{activity.action_type?.replace(/_/g, ' ') || 'Action'}</span>;
        }
    };

    /* ── Compute trend summary numbers ── */
    const trendSummary = (() => {
        if (!trendData.length) return null;
        const totalCreated = trendData.reduce((s, w) => s + (w.created || 0), 0);
        const totalResolved = trendData.reduce((s, w) => s + (w.resolved || 0), 0);
        const ratio = totalCreated > 0 ? Math.round((totalResolved / totalCreated) * 100) : 0;
        return { totalCreated, totalResolved, ratio };
    })();

    if (loading) {
        return (
            <div className={styles.loadingContainer}>
                <div className={styles.spinner} />
                <span style={{ color: 'var(--color-text-muted)', fontSize: '14px' }}>Loading admin dashboard…</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className={styles.dashboardContainer}>
                <div className={styles.errorState}>
                    <h3>Error</h3>
                    <p>{error}</p>
                    <button onClick={fetchDashboardData} style={{ marginTop: '12px', padding: '8px 16px', borderRadius: '8px' }}>Retry</button>
                </div>
            </div>
        );
    }

    return (
        <motion.div className={styles.dashboardContainer} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
            {/* Header */}
            <div className={styles.pageHeader}>
                <h1>Admin Workspace</h1>
                <p>System metrics and weekly support performance</p>
            </div>

            {/* Unified System Pulse & Trend Card */}
            <motion.div className={styles.unifiedCard} variants={fadeInUp} initial="initial" animate="animate" transition={{ delay: 0.05 }}>
                <div className={styles.unifiedHeader}>
                    <div className={styles.unifiedTitleGroup}>
                        <h2 className={styles.unifiedTitle}><TrendingUp size={20} className={styles.titleIcon} /> System Pulse & Ticket Trends</h2>
                        <span className={styles.unifiedSubtitle}>Overview of platform metrics and weekly resolution performance</span>
                    </div>
                </div>

                {/* Integrated Stats Row */}
                <div className={styles.integratedStatsRow}>
                    <div className={styles.integratedStat}>
                        <div className={`${styles.iStatIcon} ${styles.blue}`}><GraduationCap size={20} /></div>
                        <div className={styles.iStatData}>
                            <div className={styles.iStatLabel}>Total Students</div>
                            <div className={styles.iStatValue}>{data.total_students}</div>
                        </div>
                    </div>
                    <div className={styles.integratedStat}>
                        <div className={`${styles.iStatIcon} ${styles.purple}`}><Users size={20} /></div>
                        <div className={styles.iStatData}>
                            <div className={styles.iStatLabel}>Total Faculty</div>
                            <div className={styles.iStatValue}>{data.total_faculty}</div>
                        </div>
                    </div>
                    <div className={styles.integratedStat}>
                        <div className={`${styles.iStatIcon} ${styles.amber}`}><Ticket size={20} /></div>
                        <div className={styles.iStatData}>
                            <div className={styles.iStatLabel}>Open Tickets</div>
                            <div className={styles.iStatValue}>{data.open_tickets}</div>
                        </div>
                    </div>
                    <div className={styles.integratedStat}>
                        <div className={`${styles.iStatIcon} ${styles.green}`}><CheckCircle size={20} /></div>
                        <div className={styles.iStatData}>
                            <div className={styles.iStatLabel}>Resolved Tickets</div>
                            <div className={styles.iStatValue}>{data.resolved_tickets}</div>
                        </div>
                    </div>
                </div>

                {/* Chart Area */}
                <div className={styles.chartAreaWrapper}>
                    <div className={styles.chartHeaderRow}>
                        <h3 className={styles.chartTitle}>Last 8 Weeks (Created vs Resolved)</h3>
                        {trendSummary && (
                            <div className={styles.trendPills}>
                                <div className={`${styles.trendPill} ${styles.pillAmber}`}>
                                    <span className={styles.pillDot} style={{ background: '#F59E0B' }} />
                                    {trendSummary.totalCreated} created
                                </div>
                                <div className={`${styles.trendPill} ${styles.pillGreen}`}>
                                    <span className={styles.pillDot} style={{ background: '#10B981' }} />
                                    {trendSummary.totalResolved} resolved
                                </div>
                                <div className={`${styles.trendPill} ${styles.pillRatio}`}>
                                    {trendSummary.ratio}% resolution rate
                                </div>
                            </div>
                        )}
                    </div>

                    {trendLoading ? (
                        <div className={styles.chartSkeleton}>
                            <div className={styles.skeletonBar} style={{ height: '40%' }} />
                            <div className={styles.skeletonBar} style={{ height: '65%' }} />
                            <div className={styles.skeletonBar} style={{ height: '50%' }} />
                            <div className={styles.skeletonBar} style={{ height: '80%' }} />
                            <div className={styles.skeletonBar} style={{ height: '55%' }} />
                            <div className={styles.skeletonBar} style={{ height: '70%' }} />
                            <div className={styles.skeletonBar} style={{ height: '45%' }} />
                            <div className={styles.skeletonBar} style={{ height: '60%' }} />
                        </div>
                    ) : trendData.length === 0 ? (
                        <div className={styles.chartEmpty}>
                            <TrendingUp size={32} strokeWidth={1.5} />
                            <p>No ticket data available yet.</p>
                            <span>Trend data will appear once tickets are created in the system.</span>
                        </div>
                    ) : (
                        <div className={styles.chartContainer}>
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={trendData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="gradCreated" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="0%" stopColor="#F59E0B" stopOpacity={0.35} />
                                            <stop offset="95%" stopColor="#F59E0B" stopOpacity={0.02} />
                                        </linearGradient>
                                        <linearGradient id="gradResolved" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="0%" stopColor="#10B981" stopOpacity={0.35} />
                                            <stop offset="95%" stopColor="#10B981" stopOpacity={0.02} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" strokeOpacity={0.5} vertical={false} />
                                    <XAxis
                                        dataKey="week"
                                        tick={{ fill: 'var(--color-text-muted)', fontSize: 12, fontWeight: 500 }}
                                        axisLine={{ stroke: 'var(--color-border)' }}
                                        tickLine={false}
                                        dy={8}
                                    />
                                    <YAxis
                                        allowDecimals={false}
                                        tick={{ fill: 'var(--color-text-muted)', fontSize: 12 }}
                                        axisLine={false}
                                        tickLine={false}
                                        dx={-4}
                                    />
                                    <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'var(--color-border)', strokeDasharray: '4 4' }} />
                                    <Legend
                                        verticalAlign="top"
                                        align="right"
                                        iconType="circle"
                                        iconSize={8}
                                        wrapperStyle={{ fontSize: '12px', fontWeight: 500, paddingBottom: '8px', color: 'var(--color-text-secondary)' }}
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="created"
                                        name="Created"
                                        stroke="#F59E0B"
                                        strokeWidth={2.5}
                                        fill="url(#gradCreated)"
                                        dot={{ r: 4, fill: '#F59E0B', strokeWidth: 2, stroke: 'var(--card-bg)' }}
                                        activeDot={{ r: 6, strokeWidth: 2, stroke: '#F59E0B', fill: 'var(--card-bg)' }}
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="resolved"
                                        name="Resolved"
                                        stroke="#10B981"
                                        strokeWidth={2.5}
                                        fill="url(#gradResolved)"
                                        dot={{ r: 4, fill: '#10B981', strokeWidth: 2, stroke: 'var(--card-bg)' }}
                                        activeDot={{ r: 6, strokeWidth: 2, stroke: '#10B981', fill: 'var(--card-bg)' }}
                                    />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    )}
                </div>
            </motion.div>

            {/* Collapsible Global Activity Feed */}
            <motion.div className={styles.activityAccordion} variants={fadeInUp} initial="initial" animate="animate" transition={{ delay: 0.1 }}>
                <button
                    className={`${styles.accordionToggle} ${activityExpanded ? styles.expanded : ''}`}
                    onClick={() => setActivityExpanded(!activityExpanded)}
                >
                    <div className={styles.toggleLeft}>
                        <Activity size={18} className={styles.toggleIcon} />
                        <span>Global System Activity</span>
                    </div>
                    <div className={styles.toggleRight}>
                        <span className={styles.activityBadge}>{data.recent_activity.length} recent events</span>
                        {activityExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                    </div>
                </button>

                <AnimatePresence>
                    {activityExpanded && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.3, ease: 'easeInOut' }}
                            className={styles.accordionContentWrapper}
                        >
                            <div className={styles.accordionContent}>
                                <div className={styles.recentList}>
                                    {data.recent_activity.length > 0 ? data.recent_activity.map((item, idx) => (
                                        <div key={idx} className={styles.recentItem}>
                                            <div className={styles.recentIcon}>
                                                {getActivityIcon(item.action_type)}
                                            </div>
                                            <div className={styles.recentInfo}>
                                                <div className={styles.recentTitle}>
                                                    {getActivityText(item)}
                                                </div>
                                                <div className={styles.recentMeta}>
                                                    {item.student_email}
                                                </div>
                                            </div>
                                            <div className={styles.recentTime}>
                                                {formatTime(item.timestamp)}
                                            </div>
                                        </div>
                                    )) : (
                                        <div className={styles.emptyState}>No recent activity found.</div>
                                    )}
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.div>

        </motion.div>
    );
};

export default AdminDashboard;
