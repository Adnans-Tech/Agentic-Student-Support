# ACE ASSIST — AI-Powered College Support System

> 🎓 An intelligent multi-agent support system for ACE Engineering College, Ghatkesar.
> Built with LangGraph, LangChain, Groq LLM, and React — deployed on Vercel + Supabase.

🌐 **Live Demo**: [ACE ASSIST](https://agentic-multiagentsupportsystem-a77zw4wgg-adnans-techs-projects.vercel.app/login)

---

## Features

- **🤖 AI Chat Support** — Intelligent FAQ agent with RAG over the college knowledge base
- **🎫 Ticket Management** — Raise, track, and resolve support tickets with email notifications
- **📧 Email Agent** — AI-assisted email composition with tone and length customization
- **👨‍🏫 Faculty Contact** — Direct faculty email with rate limiting and quota management
- **🧭 Multi-Agent Orchestrator** — LangGraph-powered routing for complex, multi-turn conversations
- **🎓 Student Dashboard** — Profile, tickets, email history, and AI chat
- **👩‍💼 Faculty Dashboard** — View assigned tickets, manage email inbox, and AI assistant
- **🛡️ Admin Panel** — User directory, ticket oversight, announcements, and reports
- **🔐 Authentication** — JWT-based login for Students, Faculty, and Admins (with optional OTP)

---

## Tech Stack

### Backend

| Technology | Purpose |
|---|---|
| Python 3.10+ + Flask | REST API server |
| LangChain + LangGraph | Multi-agent orchestration |
| Groq LLM (Llama 3.1) | Natural language processing |
| Supabase (PostgreSQL) | Cloud database (production) |
| SQLite | Local development fallback |
| Pinecone | Cloud vector database |
| Upstash Redis | Serverless chat memory |
| SendGrid | Transactional email delivery |
| Vercel | Cloud deployment platform |

### Frontend

| Technology | Purpose |
|---|---|
| React 19 + Vite | UI framework |
| React Router v7 | Client-side routing |
| Framer Motion | Animations and transitions |
| Recharts | Data visualization and charts |
| Lucide Icons | Icon library |
| CSS Modules | Component-scoped styling |

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Node.js 18 or higher
- [Groq API key](https://console.groq.com/keys)
- [SendGrid API key](https://app.sendgrid.com/settings/api_keys)
- [Supabase account](https://supabase.com) (for production database)

### 1. Clone the repository

```bash
git clone https://github.com/Adnans-Tech/Agentic-Student-Support.git
cd Agentic-Student-Support
```

### 2. Set up environment variables

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and fill in your API keys. See [Environment Variables](#environment-variables) below for details.

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install frontend dependencies

```bash
npm install
```

### 5. Run locally

**Backend** (in one terminal):
```bash
python -m flask --app api/index run --port 5000
```

**Frontend** (in another terminal):
```bash
npm run dev
```

The app will be available at:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:5000

> **Note**: For local development, set `USE_POSTGRES=false` in your `.env` to use SQLite automatically.

---

## Project Structure

```
Agentic-Student-Support/
│
├── api/
│   └── index.py                       # Flask app & all API routes (Vercel entry point)
│
├── agents/                            # AI agent modules
│   ├── orchestrator_agent.py          # LangGraph student routing agent
│   ├── faculty_orchestrator_agent.py  # LangGraph faculty routing agent
│   ├── faq_agent.py                   # RAG-based FAQ agent
│   ├── email_agent.py                 # Email composition agent
│   ├── ticket_agent.py                # Ticket management logic
│   ├── ticket_db.py                   # Ticket database operations
│   ├── faculty_db.py                  # Faculty database operations
│   ├── student_records_repo.py        # Student records repository
│   ├── chat_memory.py                 # Chat session management
│   ├── vector_store.py                # Vector store interface
│   ├── agent_data_access.py           # Shared data access layer
│   ├── agent_protocol.py              # Agent communication protocol
│   ├── deduplication.py               # Duplicate message detection
│   ├── email_request_service.py       # Email request handler
│   ├── history_rag_service.py         # Conversation history RAG
│   ├── flow_pause.py                  # Conversation flow control
│   ├── ticket_config.py               # Ticket categories & config
│   ├── turn_logging.py                # Conversation turn logger
│   └── db_utils.py                    # Shared DB utilities
│
├── core/                              # Core configuration
│   ├── config.py                      # App-wide settings and API key loading
│   └── db_config.py                   # DB connection factory (Supabase / SQLite)
│
├── services/                          # Business logic services
│   ├── profile_service.py             # Student profile operations
│   ├── faculty_profile_service.py     # Faculty profile operations
│   ├── activity_service.py            # Activity and analytics tracking
│   ├── stats_service.py               # System statistics
│   └── limits_service.py              # Rate limiting service
│
├── utils/                             # Utilities
│   └── auth_utils.py                  # JWT authentication helpers
│
├── data/                              # Static data files
│   ├── college_rules.txt              # College knowledge base (used for RAG)
│   └── ACE data.xlsx                  # Staff/student seed data for import
│
├── docs/                              # Documentation
│   ├── RAG_Algorithm_Report.txt       # RAG system technical report
│   ├── RAG_Pipeline_Flow.png          # RAG pipeline diagram
│   ├── RAG_System_Architecture.png    # System architecture diagram
│   └── VECTOR_DB_INTEGRATION.md       # Vector DB migration guide
│
├── scripts/                           # Utility & maintenance scripts
│   ├── fix_pg_columns.py              # PostgreSQL schema migration helper
│   └── archive/                       # One-time migration scripts (reference only)
│
├── tests/                             # Test suite
│   └── test_orchestrator.py           # Orchestrator agent tests
│
├── src/                               # React frontend source
│   ├── pages/
│   │   ├── admin/                     # Admin dashboard (Dashboard, UserManagement, etc.)
│   │   ├── faculty/                   # Faculty dashboard (Dashboard, Profile, etc.)
│   │   ├── student/                   # Student dashboard (ChatSupport, Tickets, etc.)
│   │   └── auth/                      # Login & Registration pages
│   ├── components/                    # Reusable React components
│   ├── services/                      # Frontend API clients
│   ├── contexts/                      # React context providers
│   ├── layouts/                       # Page layout components
│   ├── styles/                        # Global stylesheets
│   └── utils/                         # Frontend utility functions
│
├── public/                            # Static public assets
├── .env.example                       # Environment variable template ← copy to .env
├── requirements.txt                   # Python dependencies
├── package.json                       # Node.js dependencies
├── vercel.json                        # Vercel deployment configuration
└── index.html                         # Frontend HTML entry point
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | ✅ Yes | Groq LLM API key |
| `SENDGRID_API_KEY` | ✅ Yes | SendGrid email API key |
| `DATABASE_URL` | ✅ Production | Supabase PostgreSQL connection string |
| `JWT_SECRET_KEY` | ⚠️ Recommended | Secret key for JWT tokens (use a strong random string) |
| `NOTIFICATION_EMAIL_FROM` | ⚠️ Recommended | Verified sender email address |
| `USE_POSTGRES` | ⚠️ Recommended | `true` for Supabase (production), `false` for SQLite (local dev) |
| `SUPABASE_DB_URL_POOLER` | No | Supabase pooler URL (recommended for Vercel) |
| `FRONTEND_URL` | No | Frontend URL for CORS (default: `http://localhost:5173`) |
| `ENABLE_OTP` | No | Enable OTP email verification (default: `false`) |
| `CHAT_MEMORY_BACKEND` | No | Chat memory backend: `sqlite` or `redis` (default: `sqlite`) |

---

## Deployment (Vercel)

This project is pre-configured for Vercel via `vercel.json`.

1. **Fork or push** this repository to GitHub
2. **Import** the project at [vercel.com/new](https://vercel.com/new)
3. **Add all environment variables** in the Vercel project dashboard
4. **Deploy** — Vercel builds the React frontend and deploys the Flask backend as serverless functions

> ⚠️ **Important**: Set `USE_POSTGRES=true` and provide a valid `DATABASE_URL` from Supabase.
> SQLite is **not supported** on Vercel's read-only filesystem.

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/student/register` | Register a new student |
| `POST` | `/api/auth/student/login` | Student login |
| `POST` | `/api/auth/faculty/login` | Faculty login |
| `POST` | `/api/auth/send-otp` | Send OTP for verification |

### Chat & FAQ

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/chat/orchestrator` | Main student AI chat (LangGraph) |
| `POST` | `/api/faculty/chat` | Faculty AI assistant |
| `POST` | `/api/faq` | Direct FAQ query |
| `POST` | `/api/chat/reset` | Reset conversation history |

### Ticket Management

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/tickets/categories` | Get ticket categories |
| `POST` | `/api/tickets/create` | Create a support ticket |
| `GET` | `/api/tickets/student/<email>` | Get a student's tickets |
| `GET` | `/api/tickets/faculty/<email>` | Get faculty-assigned tickets |

### Faculty

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/faculty/departments` | List all departments |
| `GET` | `/api/faculty/list` | Get faculty by department |
| `POST` | `/api/faculty/send-email` | Send email to a faculty member |

---

## Troubleshooting

**`Module not found` error**
```bash
pip install -r requirements.txt
```

**`API key not found` error**
Ensure `.env` exists and contains valid keys. Copy `.env.example` to `.env` and fill in the values.

**Frontend not connecting to backend**
Make sure the backend is running on `http://localhost:5000` and the frontend on `http://localhost:5173`.

**Postgres connection failed on Vercel**
- Set `USE_POSTGRES=true` in your Vercel environment variables.
- Ensure `DATABASE_URL` is your Supabase connection string.
- Try setting `SUPABASE_DB_URL_POOLER` to the "Transaction" pooler URL from Supabase settings.

**Vector store / Pinecone error**
Ensure `PINECONE_API_KEY` is set in your environment.

---

## License

Private — ACE Engineering College, Ghatkesar — Internal Use Only

---

## Contact

- **Email**: mohdadnan2k4@gmail.com
- **GitHub**: [Adnans-Tech](https://github.com/Adnans-Tech)

---

*ACE ASSIST — Empowering students with intelligent support* 🎓
