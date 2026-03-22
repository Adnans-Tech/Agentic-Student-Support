/**
 * Faculty Service
 * Handles all faculty-specific API calls (profile, photo, calendar)
 */

import api from './api';

const facultyService = {
    // === DASHBOARD ===

    async getDashboardData() {
        try {
            const response = await api.get('/v1/faculty/dashboard');
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to fetch dashboard data' };
        }
    },

    async saveTimetable(timetable) {
        try {
            const response = await api.put('/v1/faculty/profile', { timetable });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to save timetable' };
        }
    },

    // === PROFILE ===

    async getProfile() {
        try {
            const response = await api.get('/v1/faculty/profile');
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to fetch profile' };
        }
    },

    async updateProfile(data) {
        try {
            const response = await api.put('/v1/faculty/profile', data);
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to update profile' };
        }
    },

    async uploadPhoto(file) {
        try {
            const formData = new FormData();
            formData.append('photo', file);
            const response = await api.post('/v1/faculty/profile/photo', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to upload photo' };
        }
    },

    async deletePhoto() {
        try {
            const response = await api.delete('/v1/faculty/profile/photo');
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to delete photo' };
        }
    },

    // === CALENDAR ===

    async getCalendarEvents(month, year) {
        try {
            const params = {};
            if (month) params.month = month;
            if (year) params.year = year;
            const response = await api.get('/v1/faculty/calendar', { params });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to fetch calendar events' };
        }
    },

    async addCalendarEvent(data) {
        try {
            const response = await api.post('/v1/faculty/calendar', data);
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to add event' };
        }
    },

    async updateCalendarEvent(eventId, data) {
        try {
            const response = await api.put(`/v1/faculty/calendar/${eventId}`, data);
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to update event' };
        }
    },

    async deleteCalendarEvent(eventId) {
        try {
            const response = await api.delete(`/v1/faculty/calendar/${eventId}`);
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to delete event' };
        }
    },

    // === TICKETS (Phase 2) ===

    async getTickets() {
        try {
            const response = await api.get('/v1/faculty/tickets');
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to fetch tickets' };
        }
    },

    async getTicket(ticketId) {
        try {
            const response = await api.get(`/v1/faculty/tickets/${ticketId}`);
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to fetch ticket' };
        }
    },

    async resolveTicket(ticketId, resolutionNote) {
        try {
            const response = await api.post(`/v1/faculty/tickets/${ticketId}/resolve`, {
                resolution_note: resolutionNote
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to resolve ticket' };
        }
    },

    async notifyStudent(ticketId, data) {
        try {
            const response = await api.post(`/v1/faculty/tickets/${ticketId}/notify`, data);
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to notify student' };
        }
    },

    // === EMAILS (Phase 2) ===

    async getEmails(filter = 'all') {
        try {
            const response = await api.get('/v1/faculty/emails', { params: { filter } });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to fetch emails' };
        }
    },

    async getEmail(emailId) {
        try {
            const response = await api.get(`/v1/faculty/emails/${emailId}`);
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to fetch email details' };
        }
    },

    async replyEmail(emailId, data) {
        try {
            const response = await api.post(`/v1/faculty/emails/${emailId}/reply`, data);
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to process email reply' };
        }
    },

    // === FACULTY ASSISTANT CHAT ===

    /**
     * Send a message to the Faculty Orchestrator.
     * @param {string} message - User's chat message
     * @param {string} sessionId - Unique session identifier
     * @returns {Promise<{ response: string, intent: string, session_id: string }>}
     */
    async sendMessage(message, sessionId) {
        try {
            const response = await api.post('/chat/faculty-orchestrator', {
                message,
                session_id: sessionId,
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Faculty assistant unavailable' };
        }
    },

    /**
     * Confirm, cancel, or regenerate an email draft from the ConfirmationCard.
     * @param {string} sessionId
     * @param {boolean} confirmed - true to send
     * @param {Object|null} editedDraft - { subject, body } if user edited
     * @param {boolean} regenerate - true to regenerate body
     */
    async confirmEmail(sessionId, confirmed, editedDraft = null, regenerate = false) {
        try {
            const response = await api.post('/chat/faculty-orchestrator/confirm-email', {
                session_id: sessionId,
                confirmed,
                edited_draft: editedDraft,
                regenerate,
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to process email action' };
        }
    },

    /**
     * Confirm, cancel, or regenerate a ticket resolution from the ConfirmationCard.
     * @param {string} sessionId
     * @param {boolean} confirmed - true to resolve
     * @param {string|null} editedNote - edited resolution note text
     * @param {boolean} regenerate - true to regenerate note
     */
    async confirmResolve(sessionId, confirmed, editedNote = null, regenerate = false) {
        try {
            const response = await api.post('/chat/faculty-orchestrator/confirm-resolve', {
                session_id: sessionId,
                confirmed,
                edited_note: editedNote,
                regenerate,
            });
            return response.data;
        } catch (error) {
            throw error.response?.data || { error: 'Failed to process ticket resolution' };
        }
    },
};

export default facultyService;
