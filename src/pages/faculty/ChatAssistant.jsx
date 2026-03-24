/**
 * ChatAssistant.jsx — Faculty Assistant
 * Full feature parity with student chat:
 *  - ConfirmationCard for email edit/regenerate/send
 *  - Web Speech API speech-to-text (identical to ChatSupport.jsx)
 *  - Typing indicator, quick-prompt chips, session management
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { Bot, Send, RotateCcw, Sparkles } from 'lucide-react';
import ConfirmationCard from '../../components/chat/ConfirmationCard';
import facultyService from '../../services/facultyService';
import styles from './ChatAssistant.module.css';

// ─── Speech Recognition (same pattern as ChatSupport.jsx) ────────────────────
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

// ─── Session helpers ──────────────────────────────────────────────────────────
const SESSION_KEY = 'faculty_assistant_session_id';

function getSessionId() {
    let id = sessionStorage.getItem(SESSION_KEY);
    if (!id) {
        id = crypto.randomUUID();
        sessionStorage.setItem(SESSION_KEY, id);
    }
    return id;
}

function resetSessionId() {
    const id = crypto.randomUUID();
    sessionStorage.setItem(SESSION_KEY, id);
    return id;
}

function formatTime(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// ─── Quick prompts ────────────────────────────────────────────────────────────
const QUICK_PROMPTS = [
    { label: '📋 My tickets', text: 'Show all tickets in my department' },
    { label: '🎓 Student lookup', text: 'List all students with name ' },
    { label: '📧 Email history', text: 'Show my email history' },
    { label: '✉️ Compose email', text: 'Send an email to ' },
];

const WELCOME_MSG = {
    id: 0,
    role: 'bot',
    text:
        "👋 Hello! I'm your Faculty Assistant.\n\n" +
        "I can help you with:\n" +
        "• 🎓 Student record lookups (presence, email, name search)\n" +
        "• 🎫 Ticket inbox and resolution\n" +
        "• 📧 Email drafting, editing and sending\n\n" +
        "Type a question or use a quick prompt below.",
    ts: new Date(),
};

// ─── Message component ────────────────────────────────────────────────────────
function Message({ msg }) {
    const isUser = msg.role === 'user';
    return (
        <div className={`${styles.messageWrapper} ${isUser ? styles.user : styles.bot}`}>
            {!isUser && (
                <div className={styles.botAvatar}>
                    <Bot size={16} />
                </div>
            )}
            <div className={`${styles.bubble} ${isUser ? styles.userBubble : styles.botBubble}`}>
                <p className={styles.messageText}>{msg.text}</p>
                <span className={styles.messageTime}>{formatTime(msg.ts)}</span>
            </div>
        </div>
    );
}

// ─── Typing indicator ─────────────────────────────────────────────────────────
function TypingIndicator() {
    return (
        <div className={`${styles.messageWrapper} ${styles.bot}`}>
            <div className={styles.botAvatar}><Bot size={16} /></div>
            <div className={`${styles.bubble} ${styles.botBubble}`}>
                <div className={styles.typingDots}>
                    <span /><span /><span />
                </div>
            </div>
        </div>
    );
}

// ─── Mic SVG icons ────────────────────────────────────────────────────────────
const MicIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round" width="18" height="18">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" y1="19" x2="12" y2="23" />
        <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
);

const StopIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round" width="18" height="18">
        <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
    </svg>
);

// ─── Main component ───────────────────────────────────────────────────────────
export default function ChatAssistant() {
    const [messages, setMessages] = useState([WELCOME_MSG]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId, setSessionId] = useState(getSessionId);

    // Email ConfirmationCard state (mirrors student chat)
    const [confirmationPending, setConfirmationPending] = useState(null);

    // Speech-to-text
    const [isListening, setIsListening] = useState(false);
    const [speechSupported, setSpeechSupported] = useState(false);
    const [micPermission, setMicPermission] = useState('prompt');
    const [speechInterimText, setSpeechInterimText] = useState('');

    const bottomRef = useRef(null);
    const textareaRef = useRef(null);
    const recognitionRef = useRef(null);

    // ── Speech Recognition setup ──────────────────────────────────────────────
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
                    setInput(prev => {
                        const sep = prev && !prev.endsWith(' ') ? ' ' : '';
                        return prev + sep + finalTranscript;
                    });
                    setSpeechInterimText('');
                } else if (interimTranscript) {
                    setSpeechInterimText(interimTranscript);
                }

                silenceTimer = setTimeout(() => {
                    if (recognitionRef.current) {
                        try { recognitionRef.current.stop(); } catch (_) { /* ignore */ }
                    }
                    setIsListening(false);
                    setSpeechInterimText('');
                }, 2000);
            };

            recognition.onerror = (event) => {
                if (silenceTimer) clearTimeout(silenceTimer);
                if (event.error === 'not-allowed') setMicPermission('denied');
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
            try { recognitionRef.current?.stop(); } catch (_) { /* ignore */ }
        };
    }, []);

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
                textareaRef.current?.focus();
            } catch (err) {
                try {
                    recognitionRef.current.stop();
                    setTimeout(() => { recognitionRef.current.start(); setIsListening(true); }, 100);
                } catch (_) { }
            }
        }
    }, [isListening]);

    // ── Auto-scroll ───────────────────────────────────────────────────────────
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isLoading, confirmationPending]);

    useEffect(() => {
        textareaRef.current?.focus();
    }, []);

    // ── Send message ──────────────────────────────────────────────────────────
    const sendMessage = useCallback(async (text) => {
        const trimmed = (text !== undefined ? text : input).trim();
        if (!trimmed || isLoading || confirmationPending) return;

        if (isListening && recognitionRef.current) {
            recognitionRef.current.stop();
            setIsListening(false);
            setSpeechInterimText('');
        }

        const userMsg = { id: Date.now(), role: 'user', text: trimmed, ts: new Date() };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        if (textareaRef.current) textareaRef.current.style.height = '24px';
        setIsLoading(true);

        try {
            const result = await facultyService.sendMessage(trimmed, sessionId);

            if (result.type === 'email_preview' && result.content) {
                // Show ConfirmationCard (same as student chat)
                setConfirmationPending({ ...result.content, _sessionId: sessionId });
                setMessages(prev => [...prev, {
                    id: Date.now() + 1, role: 'bot',
                    text: result.response || '📧 Email draft ready — review below.',
                    ts: new Date(),
                }]);
            } else if (result.type === 'ticket_resolve_preview' && result.content) {
                // Show ConfirmationCard for ticket resolution
                setConfirmationPending({ ...result.content, _sessionId: sessionId });
                setMessages(prev => [...prev, {
                    id: Date.now() + 1, role: 'bot',
                    text: result.response || '📋 Resolution note ready — review below.',
                    ts: new Date(),
                }]);
            } else {
                setMessages(prev => [...prev, {
                    id: Date.now() + 1, role: 'bot',
                    text: result.response || "I didn't get a response. Please try again.",
                    ts: new Date(),
                }]);
            }
        } catch (err) {
            setMessages(prev => [...prev, {
                id: Date.now() + 1, role: 'bot',
                text: `⚠️ ${err?.error || err?.message || 'Something went wrong. Please try again.'}`,
                ts: new Date(),
            }]);
        } finally {
            setIsLoading(false);
            setTimeout(() => textareaRef.current?.focus(), 100);
        }
    }, [input, isLoading, confirmationPending, isListening, sessionId]);

    // ── ConfirmationCard handlers ─────────────────────────────────────────────
    const handleConfirmEmail = async (editedDraft) => {
        if (!confirmationPending) return;
        const sid = confirmationPending._sessionId || sessionId;

        if (editedDraft?.regenerate) {
            try {
                const result = await facultyService.confirmEmail(sid, false, null, true);
                if (result.type === 'email_preview' && result.content) {
                    setConfirmationPending({ ...result.content, _sessionId: sid });
                }
            } catch (err) {
                console.error('Regenerate failed:', err);
            }
            return;
        }

        const edited = editedDraft
            ? { subject: editedDraft.subject, body: editedDraft.body }
            : null;

        try {
            const result = await facultyService.confirmEmail(sid, true, edited, false);
            setConfirmationPending(null);
            setMessages(prev => [...prev, {
                id: Date.now(), role: 'bot',
                text: result.success
                    ? (result.message || '✅ Email sent!')
                    : `❌ ${result.message || result.error || 'Failed to send email.'}`,
                ts: new Date(),
            }]);
        } catch (err) {
            setConfirmationPending(null);
            setMessages(prev => [...prev, {
                id: Date.now(), role: 'bot',
                text: `❌ ${err?.error || 'Failed to send email.'}`,
                ts: new Date(),
            }]);
        }
    };

    const handleCancelEmail = async () => {
        const sid = confirmationPending?._sessionId || sessionId;
        try { await facultyService.confirmEmail(sid, false, null, false); } catch (_) { }
        setConfirmationPending(null);
        setMessages(prev => [...prev, {
            id: Date.now(), role: 'bot',
            text: '🚫 Email cancelled. Draft discarded.',
            ts: new Date(),
        }]);
    };

    // ── Ticket Resolution ConfirmationCard handlers ───────────────────────────
    const handleConfirmResolve = async (editedDraft) => {
        if (!confirmationPending) return;
        const sid = confirmationPending._sessionId || sessionId;

        if (editedDraft?.regenerate) {
            try {
                const result = await facultyService.confirmResolve(sid, false, null, true);
                if (result.type === 'ticket_resolve_preview' && result.content) {
                    setConfirmationPending({ ...result.content, _sessionId: sid });
                }
            } catch (err) {
                console.error('Regenerate resolve failed:', err);
            }
            return;
        }

        // editedDraft may contain { resolution_note } if user edited the note
        const editedNote = editedDraft?.body || editedDraft?.resolution_note || null;

        try {
            const result = await facultyService.confirmResolve(sid, true, editedNote, false);
            setConfirmationPending(null);
            setMessages(prev => [...prev, {
                id: Date.now(), role: 'bot',
                text: result.success
                    ? (result.message || '✅ Ticket resolved!')
                    : `❌ ${result.message || result.error || 'Failed to resolve ticket.'}`,
                ts: new Date(),
            }]);
        } catch (err) {
            setConfirmationPending(null);
            setMessages(prev => [...prev, {
                id: Date.now(), role: 'bot',
                text: `❌ ${err?.error || 'Failed to resolve ticket.'}`,
                ts: new Date(),
            }]);
        }
    };

    const handleCancelResolve = async () => {
        const sid = confirmationPending?._sessionId || sessionId;
        try { await facultyService.confirmResolve(sid, false, null, false); } catch (_) { }
        setConfirmationPending(null);
        setMessages(prev => [...prev, {
            id: Date.now(), role: 'bot',
            text: '🚫 Ticket resolution cancelled.',
            ts: new Date(),
        }]);
    };

    // ── New session ───────────────────────────────────────────────────────────
    const handleNewSession = () => {
        const newId = resetSessionId();
        setSessionId(newId);
        setMessages([{ ...WELCOME_MSG, id: Date.now(), ts: new Date() }]);
        setInput('');
        setConfirmationPending(null);
        textareaRef.current?.focus();
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    const canSend = input.trim().length > 0 && !isLoading && !confirmationPending;
    const displayPlaceholder = isListening
        ? '🎙️ Listening… speak now'
        : 'Ask about students, tickets, or compose an email…';

    return (
        <div className={styles.page}>
            {/* Header */}
            <header className={styles.header}>
                <div className={styles.headerLeft}>
                    <div className={styles.headerIcon}><Sparkles size={20} /></div>
                    <div>
                        <h1 className={styles.headerTitle}>Faculty Assistant</h1>
                        <p className={styles.headerSub}>AI-powered · Student Records · Tickets · Email</p>
                    </div>
                </div>
                <button className={styles.resetBtn} onClick={handleNewSession} title="New conversation">
                    <RotateCcw size={16} /><span>New Chat</span>
                </button>
            </header>

            {/* Chat body */}
            <div className={styles.chatBody}>
                {messages.map((msg) => (
                    <Message key={msg.id} msg={msg} />
                ))}

                {/* ConfirmationCard for email draft or ticket resolution */}
                {confirmationPending && (
                    <ConfirmationCard
                        action={confirmationPending.action}
                        summary={confirmationPending.summary}
                        details={confirmationPending.preview}
                        preview={confirmationPending.preview}
                        onConfirm={
                            confirmationPending.action === 'ticket_resolve_preview'
                                ? handleConfirmResolve
                                : handleConfirmEmail
                        }
                        onCancel={
                            confirmationPending.action === 'ticket_resolve_preview'
                                ? handleCancelResolve
                                : handleCancelEmail
                        }
                    />
                )}

                {isLoading && !confirmationPending && <TypingIndicator />}
                <div ref={bottomRef} />
            </div>

            {/* Input area */}
            <div className={styles.inputSection}>
                {messages.length <= 1 && !confirmationPending && (
                    <div className={styles.chips}>
                        {QUICK_PROMPTS.map((p) => (
                            <button
                                key={p.label}
                                className={styles.chip}
                                onClick={() => { setInput(p.text); textareaRef.current?.focus(); }}
                                disabled={isLoading}
                            >
                                {p.label}
                            </button>
                        ))}
                    </div>
                )}

                {/* Interim speech preview */}
                {isListening && speechInterimText && (
                    <div className={styles.speechPreview}>
                        <span className={styles.speechIcon}>🎙️</span>
                        <span className={styles.speechText}>{speechInterimText}</span>
                    </div>
                )}

                <div className={styles.inputRow}>
                    <textarea
                        ref={textareaRef}
                        className={`${styles.textarea} ${isListening ? styles.listeningInput : ''}`}
                        value={input}
                        onChange={(e) => {
                            setInput(e.target.value);
                            e.target.style.height = 'auto';
                            e.target.style.height = Math.min(e.target.scrollHeight, 180) + 'px';
                            if (!e.target.value) e.target.style.height = '24px';
                        }}
                        onKeyDown={handleKeyDown}
                        placeholder={displayPlaceholder}
                        rows={1}
                        id="faculty-chat-input"
                        aria-label="Faculty assistant message"
                        disabled={isLoading || !!confirmationPending}
                    />

                    {/* Mic button */}
                    {speechSupported && (
                        <button
                            className={`${styles.micBtn} ${isListening ? styles.micActive : ''}`}
                            onClick={toggleListening}
                            disabled={isLoading || !!confirmationPending}
                            title={isListening ? 'Stop listening' : 'Voice input'}
                            aria-label={isListening ? 'Stop voice input' : 'Start voice input'}
                        >
                            {isListening ? <StopIcon /> : <MicIcon />}
                            {isListening && (
                                <>
                                    <span className={styles.pulseRing} />
                                    <span className={`${styles.pulseRing} ${styles.pulseDelay}`} />
                                </>
                            )}
                        </button>
                    )}

                    {micPermission === 'denied' && (
                        <span className={styles.micDenied} title="Microphone blocked — enable in browser settings">🚫</span>
                    )}

                    <button
                        className={styles.sendBtn}
                        onClick={() => sendMessage()}
                        disabled={!canSend}
                        aria-label="Send message"
                    >
                        <Send size={18} />
                    </button>
                </div>

                <p className={styles.hint}>Enter to send · Shift+Enter for new line</p>
            </div>
        </div>
    );
}
