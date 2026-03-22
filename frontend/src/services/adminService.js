import api from './api';

export const adminService = {
    // Dashboard
    getDashboardStats: async () => {
        try {
            const response = await api.get('/admin/dashboard');
            return response.data;
        } catch (error) {
            throw error;
        }
    },

    getTicketTrends: async () => {
        try {
            const response = await api.get('/admin/dashboard/ticket-trends');
            return response.data;
        } catch (error) {
            console.error('Ticket trends error:', error);
            return { success: true, data: [] };
        }
    },

    // Departments
    getDepartments: async () => {
        try {
            const response = await api.get('/admin/departments');
            return response.data;
        } catch (error) {
            throw error;
        }
    },

    // User Management
    getStudents: async (dept, query = '') => {
        try {
            const response = await api.get(`/admin/users/students`, {
                params: { dept, q: query }
            });
            return response.data;
        } catch (error) {
            throw error;
        }
    },

    getFaculty: async (dept, query = '') => {
        try {
            const response = await api.get(`/admin/users/faculty`, {
                params: { dept, q: query }
            });
            return response.data;
        } catch (error) {
            throw error;
        }
    },

    getUserProfile: async (userId) => {
        try {
            const response = await api.get(`/admin/users/${userId}`);
            return response.data;
        } catch (error) {
            throw error;
        }
    },

    toggleUserActive: async (userId) => {
        try {
            const response = await api.post(`/admin/users/${userId}/toggle-active`);
            return response.data;
        } catch (error) {
            throw error;
        }
    },

    resetPassword: async (userId, newPassword) => {
        try {
            const response = await api.post(`/admin/users/${userId}/reset-password`, {
                new_password: newPassword
            });
            return response.data;
        } catch (error) {
            throw error;
        }
    },

    // Ticket Oversight
    getTickets: async (status = 'all') => {
        try {
            const response = await api.get('/admin/tickets', {
                params: { status }
            });
            return response.data;
        } catch (error) {
            throw error;
        }
    },

    forceCloseTicket: async (ticketId) => {
        try {
            const response = await api.post(`/admin/tickets/${ticketId}/force-close`);
            return response.data;
        } catch (error) {
            throw error;
        }
    },

    // Announcements
    getAnnouncements: async () => {
        try {
            const response = await api.get('/admin/announcements');
            return response.data;
        } catch (error) {
            throw error;
        }
    },

    createAnnouncement: async (data) => {
        try {
            const response = await api.post('/admin/announcements', data);
            return response.data;
        } catch (error) {
            throw error;
        }
    },

    updateAnnouncement: async (id, data) => {
        try {
            const response = await api.put(`/admin/announcements/${id}`, data);
            return response.data;
        } catch (error) {
            throw error;
        }
    },

    deleteAnnouncement: async (id) => {
        try {
            const response = await api.delete(`/admin/announcements/${id}`);
            return response.data;
        } catch (error) {
            throw error;
        }
    },

    // Reports
    getTicketReports: async () => {
        try {
            const response = await api.get('/admin/reports/tickets');
            return response.data;
        } catch (error) {
            throw error;
        }
    },

    getEmailUsageReports: async () => {
        try {
            const response = await api.get('/admin/reports/email-usage');
            return response.data;
        } catch (error) {
            throw error;
        }
    }
};

export default adminService;
