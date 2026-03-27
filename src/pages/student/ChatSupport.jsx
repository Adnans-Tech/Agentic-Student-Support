/**
 * Chat Support - Agentic Interface with Orchestrator
 * ChatGPT-like UI with autonomous routing, RAG-based memory, and confirmation-first execution
 * Includes speech-to-text via Web Speech API
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Timer, StickyNote, Calendar as CalendarIcon, ChevronDown, ChevronUp, Plus, Trash2, X } from 'lucide-react';
import studentService from '../../services/studentService';
import { pageTransition, staggerContainer, staggerItem } from '../../animations/variants';
import ConfirmationCard from '../../components/chat/ConfirmationCard';
import StreamingStatus from '../../components/chat/StreamingStatus';
import styles from './ChatSupport.module.css';

// Check for browser Speech Recognition support
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

const ChatSupport = () => {
    const [messages, setMessages] = useState([
        {
            id: 1,
            type: 'bot',
            text: "Hello! I'm your AI assistant. I can help you with college policies, send emails, raise tickets, contact faculty, and retrieve your history. What would you like to do?",
            timestamp: new Date().toISOString()
        }
    ]);
    const [inputMessage, setInputMessage] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [mode, setMode] = useState('auto');  // 'auto', 'email', 'ticket', 'faculty'
    const [showToolDropdown, setShowToolDropdown] = useState(false);
    const [sessionId, setSessionId] = useState(null);
    const [confirmationPending, setConfirmationPending] = useState(null);
    const [executionStatus, setExecutionStatus] = useState(null);

    // Offline / Local Features State
    const [activeTool, setActiveTool] = useState(null);
    const [notes, setNotes] = useState(() => localStorage.getItem('ace_notes') || '');
    const [theme, setTheme] = useState(() => localStorage.getItem('ace_theme') || 'light');

    // Calendar State
    const [calendarViewDate, setCalendarViewDate] = useState(new Date());
    const [selectedDate, setSelectedDate] = useState(new Date());
    const [calendarEvents, setCalendarEvents] = useState([]);
    const [eventPopup, setEventPopup] = useState(null); // { date, events: [...] }
    const [showAddEvent, setShowAddEvent] = useState(false);
    const [newEventTitle, setNewEventTitle] = useState('');
    const [newEventDate, setNewEventDate] = useState('');
    const [addingEvent, setAddingEvent] = useState(false);

    // Speech-to-text state
    const [isListening, setIsListening] = useState(false);
    const [speechSupported, setSpeechSupported] = useState(false);
    const [micPermission, setMicPermission] = useState('prompt'); // 'prompt', 'granted', 'denied'
    const [speechInterimText, setSpeechInterimText] = useState('');

    const messagesEndRef = useRef(null);
    const dropdownRef = useRef(null);
    const recognitionRef = useRef(null);
    const textareaRef = useRef(null);

    const quickReplies = [
        "What are the library timings?",
        "How do I reset my password?",
        "Where is the CSE department?",
        "Show my previous tickets",
        "Who is the HOD for ECE?"
    ];

    // Tool options
    const toolOptions = [
        { value: 'auto', label: 'Auto', icon: '✨' },
        { value: 'email', label: 'Send Email', icon: '✉️' },
        { value: 'ticket', label: 'Raise Ticket', icon: '🎫' },
        { value: 'faculty', label: 'Contact Faculty', icon: '👨‍🏫' }
    ];

    // Initialize Speech Recognition
    useEffect(() => {
        let silenceTimer = null;

        if (SpeechRecognition) {
            setSpeechSupported(true);
            const recognition = new SpeechRecognition();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = 'en-US';

            recognition.onresult = (event) => {
                if (silenceTimer) clearTimeout(silenceTimer);

                let interimTranscript = '';
                let finalTranscript = '';

                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        finalTranscript += transcript;
                    } else {
                        interimTranscript += transcript;
                    }
                }

                if (finalTranscript) {
                    setInputMessage(prev => {
                        const separator = prev && !prev.endsWith(' ') ? ' ' : '';
                        return prev + separator + finalTranscript;
                    });
                    setSpeechInterimText('');
                } else if (interimTranscript) {
                    setSpeechInterimText(interimTranscript);
                }

                silenceTimer = setTimeout(() => {
                    if (recognitionRef.current) {
                        try { recognitionRef.current.stop(); } catch (e) { /* ignore */ }
                    }
                    setIsListening(false);
                    setSpeechInterimText('');
                }, 2000);
            };

            recognition.onerror = (event) => {
                if (silenceTimer) clearTimeout(silenceTimer);
                console.error('Speech recognition error:', event.error);
                if (event.error === 'not-allowed') {
                    setMicPermission('denied');
                }
                setIsListening(false);
                setSpeechInterimText('');
            };

            recognition.onend = () => {
                if (silenceTimer) clearTimeout(silenceTimer);
                setIsListening(false);
                setSpeechInterimText('');
            };

            recognitionRef.current = recognition;
        }

        return () => {
            if (silenceTimer) clearTimeout(silenceTimer);
            if (recognitionRef.current) {
                try { recognitionRef.current.stop(); } catch (e) { /* ignore */ }
            }
        };
    }, []);

    // Toggle speech recognition
    const toggleListening = useCallback(() => {
        if (!recognitionRef.current) return;

        if (isListening) {
            recognitionRef.current.stop();
            setIsListening(false);
            setSpeechInterimText('');
        } else {
            try {
                recognitionRef.current.start();
                setIsListening(true);
                setMicPermission('granted');
                // Focus the textarea so user can see text appearing
                textareaRef.current?.focus();
            } catch (error) {
                console.error('Failed to start speech recognition:', error);
                // May already be running, try restart
                try {
                    recognitionRef.current.stop();
                    setTimeout(() => {
                        recognitionRef.current.start();
                        setIsListening(true);
                    }, 100);
                } catch (e) { /* ignore */ }
            }
        }
    }, [isListening]);

    // Generate session ID on mount
    useEffect(() => {
        const storedSessionId = localStorage.getItem('chat_session_id');
        if (storedSessionId) {
            setSessionId(storedSessionId);
            loadSession(storedSessionId);
        } else {
            const newSessionId = generateSessionId();
            setSessionId(newSessionId);
            localStorage.setItem('chat_session_id', newSessionId);
        }
    }, []);

    // Load calendar events on mount
    useEffect(() => {
        loadCalendarEvents();
    }, []);

    const loadCalendarEvents = async () => {
        try {
            const response = await studentService.getCalendarEvents();
            if (response.success) {
                setCalendarEvents(response.events || []);
            }
        } catch (error) {
            console.log('Could not load calendar events:', error);
        }
    };

    const handleAddCalendarEvent = async () => {
        if (!newEventTitle.trim() || !newEventDate.trim()) return;
        setAddingEvent(true);
        try {
            const response = await studentService.addCalendarEvent(newEventTitle.trim(), newEventDate);
            if (response.success) {
                setCalendarEvents(response.events || []);
                setNewEventTitle('');
                setNewEventDate('');
                setShowAddEvent(false);
            }
        } catch (error) {
            console.error('Failed to add event:', error);
        } finally {
            setAddingEvent(false);
        }
    };

    const handleDeleteCalendarEvent = async (eventId) => {
        try {
            const response = await studentService.deleteCalendarEvent(eventId);
            if (response.success) {
                setCalendarEvents(response.events || []);
                // Close popup if no events left on that date
                if (eventPopup) {
                    const remaining = (response.events || []).filter(
                        e => e.event_date === eventPopup.date
                    );
                    if (remaining.length === 0) setEventPopup(null);
                    else setEventPopup({ ...eventPopup, events: remaining });
                }
            }
        } catch (error) {
            console.error('Failed to delete event:', error);
        }
    };

    // Helper: get events for a specific date string (YYYY-MM-DD)
    const getEventsForDate = (dateStr) => {
        return calendarEvents.filter(e => e.event_date === dateStr);
    };

    // Auto-scroll to bottom
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, confirmationPending, executionStatus]);

    // Local Storage savecalls & Pomodoro logic
    useEffect(() => {
        localStorage.setItem('ace_notes', notes);
    }, [notes]);

    useEffect(() => {
        localStorage.setItem('ace_theme', theme);
    }, [theme]);



    // Calendar Logic
    const getDaysInMonth = (date) => new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
    const getFirstDayOfMonth = (date) => new Date(date.getFullYear(), date.getMonth(), 1).getDay();

    const generateCalendarGrid = () => {
        const daysInMonth = getDaysInMonth(calendarViewDate);
        const firstDay = getFirstDayOfMonth(calendarViewDate);
        const grid = [];

        // Previous month placeholders
        const prevMonthDate = new Date(calendarViewDate.getFullYear(), calendarViewDate.getMonth(), 0);
        const prevMonthDays = prevMonthDate.getDate();
        for (let i = firstDay - 1; i >= 0; i--) {
            grid.push({ day: prevMonthDays - i, isCurrentMonth: false });
        }

        // Current month days
        for (let i = 1; i <= daysInMonth; i++) {
            grid.push({ day: i, isCurrentMonth: true });
        }

        // Next month placeholders
        const remainder = grid.length % 7;
        if (remainder !== 0) {
            for (let i = 1; i <= 7 - remainder; i++) {
                grid.push({ day: i, isCurrentMonth: false });
            }
        }

        return grid;
    };

    const handleNextMonth = () => {
        setCalendarViewDate(new Date(calendarViewDate.getFullYear(), calendarViewDate.getMonth() + 1, 1));
    };

    const handlePrevMonth = () => {
        setCalendarViewDate(new Date(calendarViewDate.getFullYear(), calendarViewDate.getMonth() - 1, 1));
    };

    const exportChat = () => {
        const chatText = messages.map(m => `[${new Date(m.timestamp).toLocaleTimeString()}] ${m.type.toUpperCase()}: ${m.text}`).join('\n\n');
        const blob = new Blob([chatText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chat-export-${new Date().toISOString().split('T')[0]}.txt`;
        a.click();
    };

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setShowToolDropdown(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const generateSessionId = () => {
        return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    };

    const loadSession = async (sid) => {
        try {
            const response = await studentService.getChatSession(sid);
            if (response.success && response.messages && response.messages.length > 0) {
                // Convert saved messages to display format
                const loadedMessages = response.messages.map(msg => ({
                    id: msg.id,
                    type: msg.role === 'user' ? 'user' : 'bot',
                    text: msg.content,
                    timestamp: msg.timestamp
                }));
                setMessages(loadedMessages);
            }
        } catch (error) {
            console.log('Could not load session:', error);
            // Continue with fresh session
        }
    };

    const handleSendMessage = async (messageText = inputMessage, force = false) => {
        const trimmedMessage = messageText.trim();
        const lowerMessage = trimmedMessage.toLowerCase();
        
        // Define keywords that should always be allowed to bypass confirmation pending
        const isFlowControl = ['regenerate', 'cancel', 'reset', 'restart'].includes(lowerMessage);
        
        if (!trimmedMessage || (!force && confirmationPending && !isFlowControl)) return;
        
        // If it's a flow control command, clear any pending confirmation to allow fresh response
        if (isFlowControl && confirmationPending) {
            setConfirmationPending(null);
        }

        // Stop listening if active when sending
        if (isListening && recognitionRef.current) {
            recognitionRef.current.stop();
            setIsListening(false);
            setSpeechInterimText('');
        }

        const userMessage = {
            id: Date.now(),
            type: 'user',
            text: messageText.trim(),
            timestamp: new Date().toISOString()
        };

        setMessages(prev => [...prev, userMessage]);
        setInputMessage('');
        // Resets height logic in case it expanded
        if (textareaRef.current) {
            textareaRef.current.style.height = '24px';
        }
        setIsLoading(true);
        setExecutionStatus(null);

        try {
            const response = await studentService.sendChatMessage(
                messageText.trim(),
                mode,
                sessionId
            );

            // Handle different response types
            if (response.type === 'clarification_request') {
                // Bot asking for more info
                const botMessage = {
                    id: Date.now() + 1,
                    type: 'bot',
                    text: response.content,
                    timestamp: new Date().toISOString()
                };
                setMessages(prev => [...prev, botMessage]);
            } else if (response.type === 'email_preview') {
                // Email preview ready - show editable preview
                setConfirmationPending(response.content);
            } else if (response.type === 'ticket_preview') {
                // Ticket preview ready - show editable preview
                setConfirmationPending(response.content);
            } else if (response.type === 'confirmation_request') {
                // Show confirmation card
                setConfirmationPending(response.content);
            } else if (response.type === 'information') {
                // Add bot response
                const botMessage = {
                    id: Date.now() + 1,
                    type: 'bot',
                    text: response.content,
                    timestamp: new Date().toISOString()
                };
                setMessages(prev => [...prev, botMessage]);
            } else if (response.type === 'error') {
                const errorMessage = {
                    id: Date.now() + 1,
                    type: 'bot',
                    text: response.content || 'I encountered an error. Please try again.',
                    timestamp: new Date().toISOString()
                };
                setMessages(prev => [...prev, errorMessage]);
            }

            // Sync calendar if response includes calendar_events
            if (response.calendar_events) {
                setCalendarEvents(response.calendar_events);
            }

        } catch (error) {
            const errorMessage = {
                id: Date.now() + 1,
                type: 'bot',
                text: 'Sorry, I encountered an error. Please try again.',
                timestamp: new Date().toISOString()
            };
            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleConfirm = async (editedDraft) => {
        if (!confirmationPending) return;

        // Handle regenerate action — send as chat message, not confirmation
        if (editedDraft?.regenerate) {
            setConfirmationPending(null);
            await handleSendMessage('regenerate', true);
            return;
        }

        setIsLoading(true);

        // Show execution status
        setExecutionStatus([
            { text: 'Preparing...', status: 'loading' }
        ]);

        try {
            // Simulate streaming status updates
            setTimeout(() => {
                setExecutionStatus([
                    { text: 'Preparing...', status: 'complete' },
                    { text: 'Executing action...', status: 'loading' }
                ]);
            }, 500);

            // Add edited_draft to action_data if provided
            const actionData = { ...confirmationPending };
            if (editedDraft) {
                actionData.edited_draft = editedDraft;
            }

            const result = await studentService.confirmChatAction(
                sessionId,
                true,
                actionData
            );

            if (result.success) {
                setExecutionStatus([
                    { text: 'Preparing...', status: 'complete' },
                    { text: 'Executing action...', status: 'complete' },
                    { text: result.message || 'Action completed ✓', status: 'complete' }
                ]);

                // Add success message
                setTimeout(() => {
                    const successMessage = {
                        id: Date.now(),
                        type: 'bot',
                        text: result.message || 'Action completed successfully!',
                        timestamp: new Date().toISOString()
                    };
                    setMessages(prev => [...prev, successMessage]);
                    setConfirmationPending(null);
                    setExecutionStatus(null);
                }, 1500);
            } else {
                setExecutionStatus([
                    { text: 'Preparing...', status: 'complete' },
                    { text: 'Executing action...', status: 'error' },
                    { text: result.error || 'Action failed', status: 'error' }
                ]);

                setTimeout(() => {
                    const errorMessage = {
                        id: Date.now(),
                        type: 'bot',
                        text: `Failed: ${result.error || 'Unknown error'}`,
                        timestamp: new Date().toISOString()
                    };
                    setMessages(prev => [...prev, errorMessage]);
                    setConfirmationPending(null);
                    setExecutionStatus(null);
                }, 2000);
            }

        } catch (error) {
            setExecutionStatus([
                { text: 'Preparing...', status: 'complete' },
                { text: 'Executing action...', status: 'error' },
                { text: 'Failed to execute', status: 'error' }
            ]);

            setTimeout(() => {
                const errorMessage = {
                    id: Date.now(),
                    type: 'bot',
                    text: 'Failed to execute action. Please try again.',
                    timestamp: new Date().toISOString()
                };
                setMessages(prev => [...prev, errorMessage]);
                setConfirmationPending(null);
                setExecutionStatus(null);
            }, 2000);
        } finally {
            setIsLoading(false);
        }
    };

    const handleCancel = () => {
        const cancelMessage = {
            id: Date.now(),
            type: 'bot',
            text: 'Action cancelled. How else can I help you?',
            timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, cancelMessage]);
        setConfirmationPending(null);
    };

    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    };

    const getToolIcon = () => {
        const tool = toolOptions.find(t => t.value === mode);
        return tool ? tool.icon : '✨';
    };

    // Combined input display (typed + interim speech)
    const displayPlaceholder = isListening
        ? '🎙️ Listening... speak now'
        : 'Message your AI assistant...';

    return (
        <motion.div className={styles.chatPage} {...pageTransition}>
            <div className={styles.chatLayoutGrid}>
                {/* ---------- MAIN CHAT COLUMN ---------- */}
                <div className={styles.chatMainColumn}>
                    {/* Header */}
                    <div className={styles.chatHeader}>
                        <div className={styles.headerInfo}>
                            <h1 className={styles.title}>💬 Chat Support</h1>
                            <p className={styles.subtitle}>AI-powered agentic assistant</p>
                        </div>
                        <div className={styles.headerActions}>
                            <div className={styles.modeIndicator}>
                                <span className={styles.modeIcon}>{getToolIcon()}</span>
                                <span className={styles.modeText}>
                                    {mode.charAt(0).toUpperCase() + mode.slice(1)} Mode
                                </span>
                            </div>

                            <button className={styles.iconButton} onClick={exportChat} title="Export Chat">
                                📥
                            </button>
                        </div>
                    </div>

                    {/* Messages Area */}
                    <div className={styles.messagesArea}>
                        <AnimatePresence>
                            {messages.map((message, index) => (
                                <motion.div
                                    key={message.id}
                                    className={`${styles.messageWrapper} ${styles[message.type]}`}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0 }}
                                    transition={{ duration: 0.3 }}
                                >
                                    <div className={styles.messageBubble}>
                                        <p className={styles.messageText}>{message.text}</p>
                                        <span className={styles.messageTime}>
                                            {new Date(message.timestamp).toLocaleTimeString('en-US', {
                                                hour: '2-digit',
                                                minute: '2-digit'
                                            })}
                                        </span>
                                    </div>
                                </motion.div>
                            ))}
                        </AnimatePresence>

                        {/* Confirmation Card */}
                        {confirmationPending && !executionStatus && (
                            <ConfirmationCard
                                action={confirmationPending.action}
                                summary={confirmationPending.summary}
                                details={confirmationPending.preview || confirmationPending.params}
                                preview={confirmationPending.preview}
                                onConfirm={handleConfirm}
                                onCancel={handleCancel}
                            />
                        )}

                        {/* Execution Status */}
                        {executionStatus && (
                            <StreamingStatus steps={executionStatus} />
                        )}

                        {/* Loading Indicator */}
                        {isLoading && !confirmationPending && !executionStatus && (
                            <motion.div
                                className={`${styles.messageWrapper} ${styles.bot}`}
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                            >
                                <div className={styles.messageBubble}>
                                    <div className={styles.typingIndicator}>
                                        <span></span>
                                        <span></span>
                                        <span></span>
                                    </div>
                                </div>
                            </motion.div>
                        )}

                        <div ref={messagesEndRef} />
                    </div>

                    {/* Input Area - ChatGPT Style */}
                    <div className={styles.inputArea}>
                        {/* Interim speech text preview */}
                        <AnimatePresence>
                            {isListening && speechInterimText && (
                                <motion.div
                                    className={styles.speechPreview}
                                    initial={{ opacity: 0, y: 5 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: 5 }}
                                >
                                    <span className={styles.speechPreviewIcon}>🎙️</span>
                                    <span className={styles.speechPreviewText}>{speechInterimText}</span>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Quick Replies */}
                        <div className={styles.quickReplies}>
                            {quickReplies.map((reply, i) => (
                                <button
                                    key={i}
                                    className={styles.replyChip}
                                    onClick={() => handleSendMessage(reply)}
                                    disabled={isLoading || confirmationPending}
                                >
                                    {reply}
                                </button>
                            ))}
                        </div>

                        <div className={styles.chatGptInputWrapper}>
                            {/* Tool Selector (Left) */}
                            <div className={styles.toolSelectorContainer} ref={dropdownRef}>
                                <button
                                    className={styles.toolSelectorButton}
                                    onClick={() => setShowToolDropdown(!showToolDropdown)}
                                    disabled={isLoading || confirmationPending}
                                >
                                    <span className={styles.toolIcon}>{getToolIcon()}</span>
                                </button>

                                {showToolDropdown && (
                                    <motion.div
                                        className={styles.toolDropdown}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, y: 10 }}
                                    >
                                        {toolOptions.map(tool => (
                                            <button
                                                key={tool.value}
                                                className={`${styles.toolOption} ${mode === tool.value ? styles.active : ''}`}
                                                onClick={() => {
                                                    setMode(tool.value);
                                                    setShowToolDropdown(false);
                                                }}
                                            >
                                                <span className={styles.toolIcon}>{tool.icon}</span>
                                                <span className={styles.toolLabel}>{tool.label}</span>
                                                {mode === tool.value && <span className={styles.checkmark}>✓</span>}
                                            </button>
                                        ))}
                                    </motion.div>
                                )}
                            </div>

                            {/* Text Input */}
                            <textarea
                                ref={textareaRef}
                                className={`${styles.chatGptInput} ${isListening ? styles.listeningInput : ''}`}
                                value={inputMessage}
                                onChange={(e) => {
                                    setInputMessage(e.target.value);
                                    e.target.style.height = 'auto';
                                    e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
                                    if (e.target.value === '') e.target.style.height = '24px';
                                }}
                                onKeyPress={handleKeyPress}
                                placeholder={displayPlaceholder}
                                rows={1}
                                disabled={isLoading || confirmationPending}
                            />

                            {/* Mic Button */}
                            {speechSupported && (
                                <motion.button
                                    className={`${styles.micButton} ${isListening ? styles.micActive : ''}`}
                                    onClick={toggleListening}
                                    disabled={isLoading || confirmationPending}
                                    whileHover={{ scale: 1.1 }}
                                    whileTap={{ scale: 0.9 }}
                                    title={isListening ? 'Stop listening' : 'Start voice input'}
                                >
                                    {isListening ? (
                                        <svg className={styles.micIconSvg} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
                                        </svg>
                                    ) : (
                                        <svg className={styles.micIconSvg} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                                            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                                            <line x1="12" y1="19" x2="12" y2="23" />
                                            <line x1="8" y1="23" x2="16" y2="23" />
                                        </svg>
                                    )}
                                    {/* Pulse rings when active */}
                                    {isListening && (
                                        <>
                                            <span className={styles.micPulseRing} />
                                            <span className={`${styles.micPulseRing} ${styles.micPulseRingDelay}`} />
                                        </>
                                    )}
                                </motion.button>
                            )}

                            {/* Mic permission denied notice */}
                            {micPermission === 'denied' && (
                                <span className={styles.micDenied} title="Microphone blocked. Enable it in browser settings.">
                                    🚫
                                </span>
                            )}

                            {/* Send Button */}
                            <motion.button
                                className={styles.sendButton}
                                onClick={() => handleSendMessage()}
                                disabled={!inputMessage.trim() || isLoading || confirmationPending}
                                whileHover={{ scale: 1.05 }}
                                whileTap={{ scale: 0.95 }}
                            >
                                <span className={styles.sendIcon}>↑</span>
                            </motion.button>
                        </div>
                    </div>
                </div>

                {/* ---------- WIDGETS COLUMN ---------- */}
                <div className={styles.widgetsColumn}>

                    <div className={styles.widgetCard}>
                        <div className={styles.widgetHeader}>
                            <h3 className={styles.widgetTitle}>
                                <StickyNote size={18} color="#facc15" /> Private Notes
                            </h3>
                        </div>
                        <textarea
                            className={styles.widgetTextarea}
                            placeholder="Jot down quick notes here... (auto-saves)"
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                        />
                    </div>

                    <div className={`${styles.widgetCard} ${styles.calendarWidgetWrapper}`}>

                        {/* Calendar Header */}
                        <div className={styles.calendarFullHeader}>
                            <span className={styles.calendarFullDateSelected}>
                                {selectedDate.toLocaleDateString('en-US', { weekday: 'long', day: 'numeric', month: 'long' })}
                            </span>
                            <button
                                className={styles.calendarAddBtn}
                                onClick={() => setShowAddEvent(!showAddEvent)}
                                title="Add event"
                            >
                                {showAddEvent ? <X size={14} /> : <Plus size={14} />}
                            </button>
                        </div>

                        {/* Add Event Form */}
                        <AnimatePresence>
                            {showAddEvent && (
                                <motion.div
                                    className={styles.calendarAddEventForm}
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: 'auto', opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    transition={{ duration: 0.2 }}
                                >
                                    <input
                                        type="text"
                                        className={styles.addEventInput}
                                        placeholder="Event name"
                                        value={newEventTitle}
                                        onChange={(e) => setNewEventTitle(e.target.value)}
                                        onKeyPress={(e) => e.key === 'Enter' && handleAddCalendarEvent()}
                                    />
                                    <input
                                        type="date"
                                        className={styles.addEventInput}
                                        value={newEventDate}
                                        onChange={(e) => setNewEventDate(e.target.value)}
                                    />
                                    <button
                                        className={styles.addEventSubmitBtn}
                                        onClick={handleAddCalendarEvent}
                                        disabled={!newEventTitle.trim() || !newEventDate.trim() || addingEvent}
                                    >
                                        {addingEvent ? 'Adding...' : 'Add Event'}
                                    </button>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Calendar Body */}
                        <div className={styles.calendarBodyBox}>
                            <div className={styles.calendarMonthCtrl}>
                                <span className={styles.calendarCurrentMonthSpan}>
                                    {calendarViewDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                                </span>
                                <div className={styles.calendarArrows}>
                                    <button onClick={handlePrevMonth}><ChevronUp size={16} /></button>
                                    <button onClick={handleNextMonth}><ChevronDown size={16} /></button>
                                </div>
                            </div>

                            <div className={styles.calendarGrid}>
                                <div className={styles.calendarWeekRow}>
                                    <span>Su</span><span>Mo</span><span>Tu</span><span>We</span><span>Th</span><span>Fr</span><span>Sa</span>
                                </div>
                                <div className={styles.calendarDaysGrid}>
                                    {generateCalendarGrid().map((item, index) => {
                                        const isSelected = item.isCurrentMonth && item.day === selectedDate.getDate() &&
                                            calendarViewDate.getMonth() === selectedDate.getMonth() &&
                                            calendarViewDate.getFullYear() === selectedDate.getFullYear();

                                        // Build date string for event lookup
                                        const dateStr = item.isCurrentMonth
                                            ? `${calendarViewDate.getFullYear()}-${String(calendarViewDate.getMonth() + 1).padStart(2, '0')}-${String(item.day).padStart(2, '0')}`
                                            : null;
                                        const dayEvents = dateStr ? getEventsForDate(dateStr) : [];
                                        const hasEvents = dayEvents.length > 0;

                                        return (
                                            <button
                                                key={index}
                                                className={`
                                                    ${styles.calendarDayBtn} 
                                                    ${!item.isCurrentMonth ? styles.calendarDayOutside : ''} 
                                                    ${isSelected ? styles.calendarDaySelected : ''}
                                                    ${hasEvents ? styles.calendarDayHasEvent : ''}
                                                `}
                                                onClick={() => {
                                                    if (item.isCurrentMonth) {
                                                        const clickedDate = new Date(calendarViewDate.getFullYear(), calendarViewDate.getMonth(), item.day);
                                                        setSelectedDate(clickedDate);
                                                        if (hasEvents) {
                                                            setEventPopup({ date: dateStr, events: dayEvents });
                                                        } else {
                                                            setEventPopup(null);
                                                        }
                                                    }
                                                }}
                                            >
                                                <span>{item.day}</span>
                                                {hasEvents && <span className={styles.calendarEventDot} />}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>

                        {/* Event Popup */}
                        <AnimatePresence>
                            {eventPopup && (
                                <motion.div
                                    className={styles.calendarEventPopup}
                                    initial={{ opacity: 0, y: 8 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: 8 }}
                                    transition={{ duration: 0.2 }}
                                >
                                    <div className={styles.eventPopupHeader}>
                                        <span className={styles.eventPopupTitle}>
                                            📅 Events on {new Date(eventPopup.date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                                        </span>
                                        <button className={styles.eventPopupClose} onClick={() => setEventPopup(null)}>
                                            <X size={14} />
                                        </button>
                                    </div>
                                    <div className={styles.eventPopupList}>
                                        {eventPopup.events.map(ev => (
                                            <div key={ev.id} className={styles.calendarEventItem}>
                                                <span className={styles.eventItemTitle}>{ev.title}</span>
                                                <button
                                                    className={styles.eventDeleteBtn}
                                                    onClick={() => handleDeleteCalendarEvent(ev.id)}
                                                    title="Delete event"
                                                >
                                                    <Trash2 size={13} />
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                    </div>

                </div>
            </div>
        </motion.div>
    );
};

export default ChatSupport;
