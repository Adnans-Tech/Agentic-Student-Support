/**
 * Theme Context — Light/Dark/Faculty-Light Toggle
 * Stores preference in localStorage, applies via data-theme attribute
 */

import { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext();

export const useTheme = () => {
    const ctx = useContext(ThemeContext);
    if (!ctx) throw new Error('useTheme must be inside ThemeProvider');
    return ctx;
};

export const ThemeProvider = ({ children }) => {
    const [theme, setTheme] = useState(() => {
        try {
            return localStorage.getItem('ace-theme') || 'light';
        } catch {
            return 'light';
        }
    });

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
        try { localStorage.setItem('ace-theme', theme); } catch { }
    }, [theme]);

    const toggleTheme = () => setTheme(prev => prev === 'light' ? 'dark' : 'light');

    // Faculty-specific toggle: switches between dark ↔ faculty-light (Figma green)
    const toggleFacultyTheme = () => setTheme(prev =>
        prev === 'faculty-light' ? 'dark' : 'faculty-light'
    );

    return (
        <ThemeContext.Provider value={{ theme, setTheme, toggleTheme, toggleFacultyTheme }}>
            {children}
        </ThemeContext.Provider>
    );
};

export default ThemeContext;
