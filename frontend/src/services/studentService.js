/**
 * Student Service
 * Handles all student-related API calls
 */

import api from './api';

const studentService = {
    // === DASHBOARD STATS ===

    async getStats() {
        try {
            const response = await api.get('/student/stats');
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to fetch stats' };
        }
    },

    // === FAQ/CHAT ===

    async sendChatMessage(message, mode = 'auto', sessionId) {
        try {
            const response = await api.post('/chat/orchestrator', {
                message,
                mode,
                session_id: sessionId
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to send message' };
        }
    },

    async confirmChatAction(sessionId, confirmed, actionData) {
        try {
            const response = await api.post('/chat/confirm-action', {
                session_id: sessionId,
                confirmed,
                action_data: actionData
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to confirm action' };
        }
    },

    async getChatSession(sessionId) {
        try {
            const response = await api.get(`/chat/session/${sessionId}`);
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to retrieve session' };
        }
    },

    async editChatEmail(sessionId, emailDraft) {
        try {
            const response = await api.post('/chat/edit-email', {
                session_id: sessionId,
                email_draft: emailDraft
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to edit email draft' };
        }
    },

    async resetChat() {
        try {
            const response = await api.post('/reset');
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to reset chat' };
        }
    },

    // === EMAIL ===

    async generateEmailPreview(data) {
        try {
            const response = await api.post('/email', {
                ...data,
                preview_mode: true
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to generate preview' };
        }
    },

    async sendEmail(data) {
        try {
            const response = await api.post('/email', {
                ...data,
                preview_mode: false
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to send email' };
        }
    },

    // === TICKETS ===

    async getTicketCategories() {
        try {
            const response = await api.get('/tickets/categories');
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to fetch categories' };
        }
    },

    async checkDuplicateTicket(email, category) {
        try {
            const response = await api.get('/tickets/check-duplicate', {
                params: { email, category }
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to check duplicate' };
        }
    },

    async createTicket(data) {
        try {
            const response = await api.post('/tickets/create', data);
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to create ticket' };
        }
    },

    async getStudentTickets(email) {
        try {
            const response = await api.get(`/tickets/student/${email}`);
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to fetch tickets' };
        }
    },

    async closeTicket(ticketId) {
        try {
            const response = await api.post(`/tickets/close/${ticketId}`);
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to close ticket' };
        }
    },

    async closeAllTickets() {
        try {
            const response = await api.post('/tickets/close-all');
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to close tickets' };
        }
    },

    // === FACULTY CONTACT ===

    async getDepartments() {
        try {
            const response = await api.get('/faculty/departments');
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to fetch departments' };
        }
    },

    async getFacultyList(department) {
        try {
            const response = await api.get('/faculty/list', {
                params: { department }
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to fetch faculty' };
        }
    },

    async checkEmailQuota(email) {
        try {
            const response = await api.get('/faculty/check-quota', {
                params: { email }
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to check quota' };
        }
    },

    async sendFacultyEmail(data) {
        try {
            const response = await api.post('/faculty/send-email', data);
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to send email' };
        }
    },

    async getEmailHistory(email) {
        try {
            const response = await api.get('/faculty/email-history', {
                params: { email }
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to fetch history' };
        }
    },

    // === PROFILE (v1) ===

    async getProfile() {
        try {
            const response = await api.get('/v1/student/profile');
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to fetch profile' };
        }
    },

    async updateProfile(data) {
        try {
            const response = await api.put('/v1/student/profile', data);
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to update profile' };
        }
    },

    async uploadPhoto(file) {
        try {
            const formData = new FormData();
            formData.append('photo', file);
            const response = await api.post('/v1/student/profile/photo', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to upload photo' };
        }
    },

    async deletePhoto() {
        try {
            const response = await api.delete('/v1/student/profile/photo');
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to delete photo' };
        }
    },
};

export default studentService;
