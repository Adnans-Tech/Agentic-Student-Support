/**
 * Axios API Client Configuration
 * Handles all HTTP requests to the Flask backend
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api';

// Create axios instance
const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    withCredentials: true,
});

// Request interceptor - Add auth token to requests
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('ace_auth_token');

        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }

        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Response interceptor - Handle errors globally
api.interceptors.response.use(
    (response) => {
        return response;
    },
    (error) => {
        // Handle specific error cases
        if (error.response) {
            switch (error.response.status) {
                case 401:
                    // Unauthorized - clear token and redirect to login
                    localStorage.removeItem('ace_auth_token');
                    localStorage.removeItem('ace_user');
                    window.location.href = '/login';
                    break;

                case 403:
                    // Forbidden - user doesn't have permission
                    console.error('Permission denied');
                    break;

                case 429:
                    // Rate limited
                    console.error('Too many requests. Please try again later.');
                    break;

                case 500:
                    // Server error
                    console.error('Server error. Please try again.');
                    break;

                default:
                    console.error('An error occurred:', error.response.data);
            }
        } else if (error.request) {
            // Request made but no response received
            console.error('Network error. Please check your connection.');
        } else {
            // Something else happened
            console.error('Error:', error.message);
        }

        return Promise.reject(error);
    }
);

export default api;
