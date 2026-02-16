# ACE College Support System

AI-powered student support system for ACE Engineering College, Ghatkesar. Provides intelligent chat support, ticket management, faculty contact, and email generation using LangChain, LangGraph, and Groq LLM.

## Features

- **🤖 Chat Support**: AI-powered FAQ agent with RAG (Retrieval-Augmented Generation) using college knowledge base
- **🎫 Ticket Management**: Raise and track support tickets with email notifications
- **📧 Email Agent**: AI-assisted email composition with tone and length customization
- **👨‍🏫 Faculty Contact**: Direct faculty communication with rate limiting and quota management
- **🔀 Orchestrator Agent**: LangGraph-based intelligent routing for multi-turn conversations
- **🔐 Authentication**: Student and faculty login with JWT and OTP verification

## Tech Stack

### Backend
- **Python 3.8+** with Flask
- **LangChain** + **LangGraph** for agentic workflows
- **Groq LLM** (Llama 3.1) for natural language processing
- **FAISS** for vector storage and semantic search
- **SQLite** for user data, tickets, and chat memory
- **SendGrid** for email delivery

### Frontend
- **React 19** with React Router
- **Vite** for fast development
- **Framer Motion** for animations
- **Lucide Icons** for UI

## Quick Start

### Prerequisites
- Python 3.8 or higher
- Node.js 18 or higher
- Groq API key ([Get one here](https://console.groq.com/keys))
- SendGrid API key ([Get one here](https://app.sendgrid.com/settings/api_keys))

### Installation

1. **Clone and navigate to project**
   ```bash
   cd "c:\Users\mohd adnan\Desktop\agents"
   ```

2. **Set up environment variables**
   ```bash
   copy .env.example .env
   ```
   Edit `.env` and add your API keys:
   ```
   GROQ_API_KEY=your_groq_api_key_here
   SENDGRID_API_KEY=your_sendgrid_api_key_here
   NOTIFICATION_EMAIL_FROM=your_email@example.com
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install frontend dependencies**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

5. **Start the application**
   ```bash
   start.bat
   ```

   This will:
   - Start the backend server on `http://localhost:5000`
   - Start the frontend on `http://localhost:5173`
   - Automatically open your browser

## Manual Startup (Alternative)

If you prefer to start servers separately:

**Backend**:
```bash
python app.py
```

**Frontend**:
```bash
cd frontend
npm run dev
```

## Project Structure

```
agents/
├── app.py                      # Main Flask application (35 endpoints)
├── config.py                   # Configuration and environment variables
├── auth_utils.py               # JWT authentication utilities
├── start.bat                   # Single-command startup script
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (DO NOT COMMIT)
├── .env.example                # Environment template
├── college_rules.txt           # College knowledge base (263 lines)
│
├── agents/                     # AI agents and services
│   ├── faq_agent.py           # RAG-based FAQ agent
│   ├── orchestrator_agent.py  # LangGraph routing agent
│   ├── email_agent.py         # Email generation agent
│   ├── ticket_agent.py        # Ticket management
│   ├── vector_store.py        # FAISS vector database manager
│   ├── chat_memory.py         # Conversation history management
│   └── faculty_db.py          # Faculty database service
│
├── data/                       # SQLite databases and vector storage
│   ├── students.db            # Student authentication
│   ├── faculty.db             # Faculty data
│   ├── tickets.db             # Support tickets
│   ├── chat_memory.db         # Chat sessions
│   └── vectordb/              # FAISS vector store
│
└── frontend/                   # React frontend
    ├── src/
    │   ├── pages/             # Student/Faculty dashboards
    │   ├── components/        # Reusable UI components
    │   └── services/          # API integration
    ├── package.json
    └── vite.config.js
```

## Key APIs

### Student Authentication
- `POST /api/auth/student/register` - Register new student
- `POST /api/auth/student/login` - Student login
- `POST /api/auth/send-otp` - Send OTP for verification

### Chat & FAQ
- `POST /api/chat/orchestrator` - Main chat endpoint (LangGraph routing)
- `POST /api/faq` - Direct FAQ agent queries
- `POST /api/chat/reset` - Clear conversation history

### Ticket Management
- `GET /api/tickets/categories` - Get ticket categories
- `POST /api/tickets/create` - Create support ticket
- `GET /api/tickets/student/<email>` - Get student's tickets

### Faculty Contact
- `GET /api/faculty/departments` - Get all departments
- `GET /api/faculty/list?department=CSE` - Get faculty by department
- `POST /api/faculty/send-email` - Send email to faculty

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | ✅ Yes | Groq API key for LLM inference |
| `SENDGRID_API_KEY` | ✅ Yes | SendGrid API for email delivery |
| `JWT_SECRET_KEY` | ⚠️ Recommended | Secret key for JWT (change in production!) |
| `NOTIFICATION_EMAIL_FROM` | ⚠️ Recommended | Sender email address |
| `FRONTEND_URL` | No | Frontend URL for CORS (default: localhost:5173) |

## Features in Detail

### Chat Support (Orchestrator Agent)
- **Intent Classification**: Automatically detects if user wants FAQ, raise ticket, or contact faculty
- **Multi-turn Conversations**: Maintains context across messages
- **Conversational Ticket Raising**: Asks clarifying questions before creating tickets
- **Faculty Identification**: Intelligently matches faculty based on department and name

### FAQ Agent (RAG)
- **Semantic Search**: Uses FAISS vector database for college rules
- **Context-Aware**: Remembers previous conversation for follow-up questions
- **Natural Responses**: Groq LLM generates friendly, conversational answers

### Ticket System
- **Category-based**: Academic, Technical, Administrative, Hostel, Transport
- **SLA Tracking**: 24-48 hour response times
- **Email Notifications**: Automatic confirmation emails
- **Duplicate Prevention**: Checks for open tickets in same category

## Deployment Preparation

### For Production Deployment:

1. **Update environment variables**
   - Generate strong `JWT_SECRET_KEY`
   - Use production email addresses
   - Set `FRONTEND_URL` to your domain

2. **Database Setup**
   - Consider migrating to PostgreSQL for production
   - Set up regular backups for SQLite databases
   - Implement database migrations

3. **Security**
   - Enable HTTPS
   - Set up proper CORS policies
   - Implement rate limiting
   - Add input validation and sanitization

4. **Vector Database** (Optional Future Enhancement)
   - See `VECTOR_DB_INTEGRATION.md` for Chroma DB migration guide
   - Current FAISS setup works well for static college rules

5. **Monitoring**
   - Add logging for all API endpoints
   - Set up error tracking (e.g., Sentry)
   - Monitor API usage and quotas

## Development

### Running Tests
```bash
# Backend tests (if implemented)
python -m pytest

# Frontend tests
cd frontend
npm test
```

### Code Structure Guidelines
- **Agents**: All AI agents in `agents/` directory
- **Database**: All SQLite databases in `data/` directory
- **Frontend**: React components in `frontend/src/`
- **Configuration**: Environment-based config in `config.py`

## Troubleshooting

### "Module not found" error
```bash
pip install -r requirements.txt
```

### "API key not found" error
Ensure `.env` file exists and contains valid API keys

### Frontend not connecting to backend
Verify backend is running on `http://localhost:5000` and frontend on `http://localhost:5173`

### Vector store initialization error
Delete `data/vectordb/` and restart - it will rebuild automatically from `college_rules.txt`

## Future Enhancements

- [ ] Faculty dashboard for ticket management
- [ ] Admin panel for system configuration
- [ ] Chroma DB integration for chat memory (see `VECTOR_DB_INTEGRATION.md`)
- [ ] Multi-language support
- [ ] Voice input for chat
- [ ] Mobile app (React Native)
- [ ] Analytics dashboard

## License

Private - ACE Engineering College Internal Use Only

## Support

For issues or questions:
- Contact: 091333 08533
- Email: mohdadnan2k4@gmail.com

---

**Last Updated**: January 2026  
**Version**: 1.0.0  
**Status**: Production Ready ✅
