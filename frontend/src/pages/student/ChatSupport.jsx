/**
 * Chat Support - Agentic Interface with Orchestrator
 * ChatGPT-like UI with autonomous routing, RAG-based memory, and confirmation-first execution
 */

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import studentService from '../../services/studentService';
import { pageTransition, staggerContainer, staggerItem } from '../../animations/variants';
import ConfirmationCard from '../../components/chat/ConfirmationCard';
import StreamingStatus from '../../components/chat/StreamingStatus';
import styles from './ChatSupport.module.css';

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

    const messagesEndRef = useRef(null);
    const dropdownRef = useRef(null);

    // Tool options
    const toolOptions = [
        { value: 'auto', label: 'Auto', icon: '✨' },
        { value: 'email', label: 'Send Email', icon: '✉️' },
        { value: 'ticket', label: 'Raise Ticket', icon: '🎫' },
        { value: 'faculty', label: 'Contact Faculty', icon: '👨‍🏫' }
    ];

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

    // Auto-scroll to bottom
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, confirmationPending, executionStatus]);

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

    const handleSendMessage = async (messageText = inputMessage) => {
        if (!messageText.trim() || confirmationPending) return;

        const userMessage = {
            id: Date.now(),
            type: 'user',
            text: messageText.trim(),
            timestamp: new Date().toISOString()
        };

        setMessages(prev => [...prev, userMessage]);
        setInputMessage('');
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
            await handleSendMessage('regenerate');
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

    return (
        <motion.div className={styles.chatPage} {...pageTransition}>
            <div className={styles.chatContainer}>
                {/* Header */}
                <div className={styles.chatHeader}>
                    <div className={styles.headerInfo}>
                        <h1 className={styles.title}>💬 Chat Support</h1>
                        <p className={styles.subtitle}>AI-powered agentic assistant</p>
                    </div>
                    <div className={styles.modeIndicator}>
                        <span className={styles.modeIcon}>{getToolIcon()}</span>
                        <span className={styles.modeText}>
                            {mode.charAt(0).toUpperCase() + mode.slice(1)} Mode
                        </span>
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
                            className={styles.chatGptInput}
                            value={inputMessage}
                            onChange={(e) => setInputMessage(e.target.value)}
                            onKeyPress={handleKeyPress}
                            placeholder="Message your AI assistant..."
                            rows={1}
                            disabled={isLoading || confirmationPending}
                        />

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
        </motion.div>
    );
};

export default ChatSupport;
