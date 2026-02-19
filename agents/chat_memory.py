"""
Production Chat Memory with ChromaDB and Upstash Redis
Supports multi-tenant conversation storage with proper user isolation

Storage Backends:
1. ChromaDB - Persistent semantic search for conversation history
2. Upstash Redis - Fast serverless session cache (recommended for production)
3. PostgreSQL - Production database (when USE_POSTGRES=true)
4. SQLite - Local development fallback

Set CHAT_MEMORY_BACKEND environment variable:
- "chromadb" - Uses ChromaDB for persistent vector storage
- "upstash" - Uses Upstash Redis (serverless, recommended)
- "redis" - Uses self-hosted Redis
- "sqlite" - Uses SQLite (default, development)

Note: If USE_POSTGRES=true in .env, PostgreSQL is used regardless of CHAT_MEMORY_BACKEND
"""
import os
import sys
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from abc import ABC, abstractmethod

# Import db_config for PostgreSQL dual-backend support
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_config import (
    get_db_connection,
    get_placeholder,
    is_postgres,
    get_dict_cursor
)

# Try to import ChromaDB
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except Exception:
    CHROMADB_AVAILABLE = False
    print("[WARN] ChromaDB not available. Using fallback backend.")

# Try to import Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class ChatMemoryBackend(ABC):
    """Abstract base class for chat memory storage"""
    
    @abstractmethod
    def save_message(self, user_id: str, session_id: str, role: str, content: str,
                     intent: Optional[str] = None, selected_agent: Optional[str] = None,
                     metadata: Optional[Dict] = None) -> bool:
        pass
    
    @abstractmethod
    def get_session_history(self, session_id: str, user_id: str, limit: int = 50) -> List[Dict]:
        pass
    
    @abstractmethod
    def get_user_context(self, user_id: str, session_id: str, max_messages: int = 10) -> str:
        pass
    
    @abstractmethod
    def search_conversation(self, user_id: str, query: str, limit: int = 5) -> List[Dict]:
        pass
    
    @abstractmethod
    def delete_session(self, session_id: str, user_id: str) -> bool:
        pass


class ChromaDBChatMemory(ChatMemoryBackend):
    """
    ChromaDB-based chat memory with multi-tenant support.
    Each user's conversations are isolated via user_id metadata filtering.
    Uses semantic search for finding relevant past conversations.
    """
    
    def __init__(self, persist_directory: str = "data/chat_memory_db"):
        """
        Initialize ChromaDB chat memory.
        
        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        self.persist_directory = persist_directory
        
        try:
            # Create persistent client
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Create or get conversation collection
            self.collection = self.client.get_or_create_collection(
                name="chat_conversations",
                metadata={"hnsw:space": "cosine"}
            )
            
            self.available = True
            print(f"[OK] ChromaDB Chat Memory initialized (path: {persist_directory})")
            
        except Exception as e:
            print(f"[ERROR] ChromaDB initialization failed: {e}")
            self.available = False
    
    def _generate_doc_id(self, user_id: str, session_id: str, timestamp: str) -> str:
        """Generate unique document ID"""
        clean_id = f"{user_id}_{session_id}_{timestamp}"
        return clean_id.replace('@', '_').replace(':', '_').replace('.', '_').replace('-', '_')[:100]
    
    def save_message(self, user_id: str, session_id: str, role: str, content: str,
                     intent: Optional[str] = None, selected_agent: Optional[str] = None,
                     metadata: Optional[Dict] = None) -> bool:
        """
        Save a chat message with user isolation.
        
        Args:
            user_id: User email (for isolation)
            session_id: Session UUID
            role: 'user' or 'bot'
            content: Message content
            intent: Detected intent
            selected_agent: Agent that handled the message
            metadata: Additional metadata
        """
        if not self.available:
            return False
        
        # GUARD 1: Skip if content is None or empty
        if content is None or (isinstance(content, str) and content.strip() == ""):
            print(f"[CHAT_MEMORY] Skipped empty/null message in ChromaDB (role={role})")
            return True
        
        # GUARD 2: Skip system/control messages
        if role and role.lower() == "system":
            print(f"[CHAT_MEMORY] Skipped system message in ChromaDB")
            return True
        
        try:
            timestamp = datetime.utcnow().isoformat()
            doc_id = self._generate_doc_id(user_id, session_id, timestamp)
            
            # Create document with role prefix for clarity
            document = f"[{role.upper()}] {content}"
            
            # Build metadata with user isolation
            meta = {
                "user_id": user_id,
                "session_id": session_id,
                "role": role,
                "timestamp": timestamp,
                "intent": intent or "",
                "selected_agent": selected_agent or "",
                "created_date": timestamp[:10]  # For date filtering
            }
            
            # Add any additional metadata
            if metadata:
                for key, value in metadata.items():
                    if isinstance(value, (str, int, float, bool)):
                        meta[key] = value
                    elif isinstance(value, (dict, list)):
                        # JSON encode complex types so they can be stored
                        try:
                            meta[key] = json.dumps(value)
                        except (TypeError, ValueError):
                            meta[key] = str(value)
            
            # Add to collection
            self.collection.add(
                documents=[document],
                metadatas=[meta],
                ids=[doc_id]
            )
            
            return True
            
        except Exception as e:
            print(f"ChromaDB save error: {e}")
            return False
    
    def get_session_history(self, session_id: str, user_id: str, limit: int = 50) -> List[Dict]:
        """
        Get conversation history for a specific session.
        Ensures user isolation via user_id filter.
        
        Args:
            session_id: Session UUID
            user_id: User email (required for isolation)
            limit: Maximum messages to retrieve
        """
        if not self.available:
            return []
        
        try:
            # Query with both session_id AND user_id for security
            results = self.collection.get(
                where={
                    "$and": [
                        {"session_id": {"$eq": session_id}},
                        {"user_id": {"$eq": user_id}}
                    ]
                },
                limit=limit
            )
            
            if not results['ids']:
                return []
            
            # Format results
            messages = []
            for i, doc_id in enumerate(results['ids']):
                meta = results['metadatas'][i]
                content = results['documents'][i]
                
                # Remove role prefix from content
                if content.startswith("[USER] "):
                    content = content[7:]
                elif content.startswith("[BOT] "):
                    content = content[6:]
                
                # Parse JSON-encoded metadata fields back to dicts
                parsed_meta = {}
                for key, value in meta.items():
                    if key in ['extracted_slots', 'faculty_matches', 'resolved_faculty'] and isinstance(value, str):
                        try:
                            parsed_meta[key] = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            parsed_meta[key] = value
                    else:
                        parsed_meta[key] = value
                
                messages.append({
                    "id": doc_id,
                    "user_id": meta.get("user_id"),
                    "session_id": meta.get("session_id"),
                    "role": meta.get("role"),
                    "content": content,
                    "intent": meta.get("intent"),
                    "selected_agent": meta.get("selected_agent"),
                    "timestamp": meta.get("timestamp"),
                    "metadata": parsed_meta  # Include full metadata for flow state
                })
            
            # Sort by timestamp
            messages.sort(key=lambda x: x.get("timestamp", ""))
            
            return messages[-limit:]  # Return last N messages
            
        except Exception as e:
            print(f"ChromaDB retrieval error: {e}")
            return []
    
    def get_user_context(self, user_id: str, session_id: str, max_messages: int = 10) -> str:
        """
        Get formatted conversation context for LLM prompt.
        
        Args:
            user_id: User email
            session_id: Session UUID
            max_messages: Maximum messages to include
        
        Returns:
            Formatted conversation string for LLM context
        """
        messages = self.get_session_history(session_id, user_id, limit=max_messages)
        
        if not messages:
            return "(No previous conversation)"
        
        # Format for LLM
        context_lines = []
        for msg in messages[-max_messages:]:
            role_label = "Student" if msg["role"] == "user" else "Assistant"
            content = msg["content"]
            
            # Truncate long messages
            if len(content) > 300:
                content = content[:300] + "..."
            
            context_lines.append(f"{role_label}: {content}")
        
        return "\n".join(context_lines) if context_lines else "(No previous conversation)"
    
    def search_conversation(self, user_id: str, query: str, limit: int = 5) -> List[Dict]:
        """
        Semantic search across user's conversation history.
        Finds relevant past messages using vector similarity.
        
        Args:
            user_id: User email (for isolation)
            query: Natural language query
            limit: Maximum results
        
        Returns:
            List of relevant messages with similarity scores
        """
        if not self.available:
            return []
        
        try:
            # Query with user isolation
            results = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where={"user_id": {"$eq": user_id}}
            )
            
            if not results['documents'] or not results['documents'][0]:
                return []
            
            # Format results
            formatted = []
            for i, doc in enumerate(results['documents'][0]):
                meta = results['metadatas'][0][i]
                distance = results['distances'][0][i] if results.get('distances') else None
                
                # Remove role prefix
                content = doc
                if content.startswith("[USER] "):
                    content = content[7:]
                elif content.startswith("[BOT] "):
                    content = content[6:]
                
                formatted.append({
                    "content": content,
                    "role": meta.get("role"),
                    "session_id": meta.get("session_id"),
                    "timestamp": meta.get("timestamp"),
                    "similarity": 1 - distance if distance else None
                })
            
            return formatted
            
        except Exception as e:
            print(f"ChromaDB search error: {e}")
            return []
    
    def get_user_sessions(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get list of sessions for a user"""
        if not self.available:
            return []
        
        try:
            results = self.collection.get(
                where={"user_id": {"$eq": user_id}},
                limit=100  # Capped from 1000 — prevents excessive memory usage
            )
            
            if not results['metadatas']:
                return []
            
            # Group by session_id
            sessions = {}
            for meta in results['metadatas']:
                session_id = meta.get("session_id")
                if session_id not in sessions:
                    sessions[session_id] = {
                        "session_id": session_id,
                        "last_timestamp": meta.get("timestamp"),
                        "message_count": 1
                    }
                else:
                    sessions[session_id]["message_count"] += 1
                    if meta.get("timestamp", "") > sessions[session_id]["last_timestamp"]:
                        sessions[session_id]["last_timestamp"] = meta.get("timestamp")
            
            # Sort by last timestamp
            sorted_sessions = sorted(
                sessions.values(),
                key=lambda x: x.get("last_timestamp", ""),
                reverse=True
            )
            
            return sorted_sessions[:limit]
            
        except Exception as e:
            print(f"ChromaDB sessions error: {e}")
            return []
    
    def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete all messages in a session (with user verification)"""
        if not self.available:
            return False
        
        try:
            # Get IDs to delete (with user verification)
            results = self.collection.get(
                where={
                    "$and": [
                        {"session_id": {"$eq": session_id}},
                        {"user_id": {"$eq": user_id}}
                    ]
                }
            )
            
            if results['ids']:
                self.collection.delete(ids=results['ids'])
            
            return True
            
        except Exception as e:
            print(f"ChromaDB delete error: {e}")
            return False
    
    def clear_user_history(self, user_id: str) -> bool:
        """Clear all conversation history for a user"""
        if not self.available:
            return False
        
        try:
            results = self.collection.get(
                where={"user_id": {"$eq": user_id}}
            )
            
            if results['ids']:
                self.collection.delete(ids=results['ids'])
            
            return True
            
        except Exception as e:
            print(f"ChromaDB clear error: {e}")
            return False


class UpstashRedisChatMemory(ChatMemoryBackend):
    """
    Upstash Redis chat memory - serverless, production-ready.
    Uses REST API for serverless compatibility.
    Perfect for Vercel, AWS Lambda, etc.
    """
    
    def __init__(self, url: str = None, token: str = None, ttl_hours: int = 48):
        """
        Initialize Upstash Redis chat memory.
        
        Args:
            url: Upstash Redis REST URL (or UPSTASH_REDIS_REST_URL env var)
            token: Upstash Redis REST token (or UPSTASH_REDIS_REST_TOKEN env var)
            ttl_hours: Time-to-live for sessions
        """
        self.url = url or os.getenv("UPSTASH_REDIS_REST_URL")
        self.token = token or os.getenv("UPSTASH_REDIS_REST_TOKEN")
        self.ttl_seconds = ttl_hours * 3600
        
        if not self.url or not self.token:
            print("[WARN] Upstash Redis not configured. Set UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN")
            self.available = False
            return
        
        try:
            # Use Upstash Redis REST client
            from upstash_redis import Redis
            self.client = Redis(url=self.url, token=self.token)
            
            # Test connection
            self.client.ping()
            self.available = True
            print("[OK] Upstash Redis Chat Memory initialized (serverless)")
            
        except ImportError:
            print("[WARN] upstash-redis not installed. Install with: pip install upstash-redis")
            self.available = False
        except Exception as e:
            print(f"[ERROR] Upstash Redis connection failed: {e}")
            self.available = False
    
    def _session_key(self, user_id: str, session_id: str) -> str:
        """Generate user-isolated session key"""
        return f"chat:user:{user_id}:session:{session_id}"
    
    def _user_sessions_key(self, user_id: str) -> str:
        """Generate key for tracking user's sessions"""
        return f"chat:user:{user_id}:sessions"
    
    def save_message(self, user_id: str, session_id: str, role: str, content: str,
                     intent: Optional[str] = None, selected_agent: Optional[str] = None,
                     metadata: Optional[Dict] = None) -> bool:
        if not self.available:
            return False
        
        # GUARD 1: Skip if content is None or empty
        if content is None or (isinstance(content, str) and content.strip() == ""):
            print(f"[CHAT_MEMORY] Skipped empty/null message in Upstash (role={role})")
            return True
        
        # GUARD 2: Skip system/control messages
        if role and role.lower() == "system":
            print(f"[CHAT_MEMORY] Skipped system message in Upstash")
            return True
        
        try:
            message = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "session_id": session_id,
                "role": role,
                "content": content,
                "intent": intent,
                "selected_agent": selected_agent,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            }
            
            # Add to session list (user-isolated key)
            session_key = self._session_key(user_id, session_id)
            self.client.rpush(session_key, json.dumps(message))
            self.client.expire(session_key, self.ttl_seconds)
            
            # Track session
            sessions_key = self._user_sessions_key(user_id)
            self.client.sadd(sessions_key, session_id)
            self.client.expire(sessions_key, self.ttl_seconds * 7)
            
            return True
            
        except Exception as e:
            print(f"Upstash save error: {e}")
            return False
    
    def get_session_history(self, session_id: str, user_id: str, limit: int = 50) -> List[Dict]:
        if not self.available:
            return []
        
        try:
            session_key = self._session_key(user_id, session_id)
            messages_json = self.client.lrange(session_key, -limit, -1)
            
            messages = []
            for msg_json in messages_json:
                if isinstance(msg_json, str):
                    msg = json.loads(msg_json)
                else:
                    msg = msg_json
                messages.append(msg)
            
            return messages
            
        except Exception as e:
            print(f"Upstash retrieval error: {e}")
            return []
    
    def get_user_context(self, user_id: str, session_id: str, max_messages: int = 10) -> str:
        messages = self.get_session_history(session_id, user_id, limit=max_messages)
        
        if not messages:
            return "(No previous conversation)"
        
        context_lines = []
        for msg in messages[-max_messages:]:
            role_label = "Student" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")
            if len(content) > 300:
                content = content[:300] + "..."
            context_lines.append(f"{role_label}: {content}")
        
        return "\n".join(context_lines) if context_lines else "(No previous conversation)"
    
    def search_conversation(self, user_id: str, query: str, limit: int = 5) -> List[Dict]:
        """Basic keyword search (Redis doesn't support semantic search)"""
        if not self.available:
            return []
        
        # Get all user sessions and search
        try:
            sessions_key = self._user_sessions_key(user_id)
            session_ids = self.client.smembers(sessions_key)
            
            results = []
            query_lower = query.lower()
            
            for session_id in session_ids:
                messages = self.get_session_history(session_id, user_id, limit=100)
                for msg in messages:
                    if query_lower in msg.get("content", "").lower():
                        results.append(msg)
                        if len(results) >= limit:
                            return results
            
            return results[:limit]
            
        except Exception as e:
            print(f"Upstash search error: {e}")
            return []
    
    def delete_session(self, session_id: str, user_id: str) -> bool:
        if not self.available:
            return False
        
        try:
            session_key = self._session_key(user_id, session_id)
            self.client.delete(session_key)
            
            sessions_key = self._user_sessions_key(user_id)
            self.client.srem(sessions_key, session_id)
            
            return True
            
        except Exception as e:
            print(f"Upstash delete error: {e}")
            return False
    
    def get_user_sessions(self, user_id: str, limit: int = 10) -> List[Dict]:
        if not self.available:
            return []
        
        try:
            sessions_key = self._user_sessions_key(user_id)
            session_ids = list(self.client.smembers(sessions_key))[:limit]
            
            sessions = []
            for session_id in session_ids:
                messages = self.get_session_history(session_id, user_id, limit=1)
                if messages:
                    sessions.append({
                        "session_id": session_id,
                        "last_timestamp": messages[-1].get("timestamp"),
                        "message_count": self.client.llen(self._session_key(user_id, session_id))
                    })
            
            return sorted(sessions, key=lambda x: x.get("last_timestamp", ""), reverse=True)
            
        except Exception as e:
            print(f"Upstash sessions error: {e}")
            return []


class SQLiteChatMemory(ChatMemoryBackend):
    """SQLite fallback for development (local storage)"""
    
    # Constants for retry logic
    MAX_RETRIES = 5
    RETRY_DELAY = 0.2
    
    def __init__(self, db_path: str = "data/chat_memory.db"):
        import sqlite3
        import time as time_module
        self.db_path = db_path
        self.sqlite3 = sqlite3
        self.time = time_module
        
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._initialize_database()
        self.available = True
        print(f"[OK] SQLite Chat Memory initialized ({db_path}) - WAL mode enabled")
    
    def _get_connection(self):
        """Get database connection with WAL mode and timeout"""
        conn = self.sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn
    
    def _initialize_database(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    intent TEXT,
                    selected_agent TEXT,
                    metadata TEXT,
                    timestamp TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_session ON chat_messages(user_id, session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON chat_messages(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON chat_messages(session_id)")
            
            conn.commit()
        finally:
            conn.close()
    
    def _execute_with_retry(self, operation, *args, **kwargs):
        """Execute a database operation with retry logic for lock errors"""
        last_error = None
        delay = self.RETRY_DELAY
        
        for attempt in range(self.MAX_RETRIES):
            conn = None
            try:
                conn = self._get_connection()
                result = operation(conn, *args, **kwargs)
                conn.commit()
                print(f"[CHAT_MEMORY] Database operation successful")
                return result
            except self.sqlite3.OperationalError as e:
                last_error = e
                error_msg = str(e).lower()
                
                if "locked" in error_msg or "busy" in error_msg:
                    if conn:
                        try:
                            conn.rollback()
                        except:
                            pass
                    
                    if attempt < self.MAX_RETRIES - 1:
                        print(f"[CHAT_MEMORY] Database locked, retrying in {delay:.2f}s (attempt {attempt + 1}/{self.MAX_RETRIES})")
                        self.time.sleep(delay)
                        delay *= 1.5
                        continue
                else:
                    raise
            except Exception:
                if conn:
                    try:
                        conn.rollback()
                    except:
                        pass
                raise
            finally:
                if conn:
                    try:
                        conn.close()
                    except:
                        pass
        
        print(f"[CHAT_MEMORY] All {self.MAX_RETRIES} retries exhausted")
        raise last_error
    
    def save_message(self, user_id: str, session_id: str, role: str, content: str,
                     intent: Optional[str] = None, selected_agent: Optional[str] = None,
                     metadata: Optional[Dict] = None) -> bool:
        
        # GUARD 1: Skip if content is None or empty
        if content is None or (isinstance(content, str) and content.strip() == ""):
            print(f"[CHAT_MEMORY] Skipped empty/null message (role={role}, intent={intent})")
            return True  # Return success to not block the flow
        
        # GUARD 2: Skip system/control messages that are not real conversation
        if role and role.lower() == "system":
            print(f"[CHAT_MEMORY] Skipped system message (not persisting control events)")
            return True
        
        # GUARD 3: Ensure content is a valid string
        if not isinstance(content, str):
            try:
                content = str(content)
            except Exception:
                print(f"[CHAT_MEMORY] Skipped message with invalid content type: {type(content)}")
                return True
        
        def _do_save(conn):
            cursor = conn.cursor()
            timestamp = datetime.utcnow().isoformat()
            
            cursor.execute("""
                INSERT INTO chat_messages (user_id, session_id, role, content, intent, selected_agent, metadata, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, session_id, role, content, intent, selected_agent,
                  json.dumps(metadata) if metadata else None, timestamp))
            return True
        
        try:
            return self._execute_with_retry(_do_save)
        except Exception as e:
            print(f"SQLite save error: {e}")
            return False
    
    def get_session_history(self, session_id: str, user_id: str, limit: int = 50) -> List[Dict]:
        try:
            conn = self._get_connection()
            conn.row_factory = self.sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM chat_messages
                WHERE session_id = ? AND user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (session_id, user_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            messages = []
            for row in rows:
                # Parse metadata JSON if present
                metadata = None
                if row["metadata"]:
                    try:
                        metadata = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
                    except (json.JSONDecodeError, TypeError):
                        metadata = {}
                
                messages.append({
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "session_id": row["session_id"],
                    "role": row["role"],
                    "content": row["content"],
                    "intent": row["intent"],
                    "selected_agent": row["selected_agent"],
                    "timestamp": row["timestamp"],
                    "metadata": metadata  # CRITICAL: Include metadata for flow state
                })
            
            return messages
            
        except Exception as e:
            print(f"SQLite retrieval error: {e}")
            return []
    
    def get_user_context(self, user_id: str, session_id: str, max_messages: int = 10) -> str:
        messages = self.get_session_history(session_id, user_id, limit=max_messages)
        
        if not messages:
            return "(No previous conversation)"
        
        context_lines = []
        for msg in messages[-max_messages:]:
            role_label = "Student" if msg["role"] == "user" else "Assistant"
            content = msg["content"]
            if len(content) > 300:
                content = content[:300] + "..."
            context_lines.append(f"{role_label}: {content}")
        
        return "\n".join(context_lines) if context_lines else "(No previous conversation)"
    
    def search_conversation(self, user_id: str, query: str, limit: int = 5) -> List[Dict]:
        try:
            conn = self._get_connection()
            conn.row_factory = self.sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM chat_messages
                WHERE user_id = ? AND content LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, f"%{query}%", limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            print(f"SQLite search error: {e}")
            return []
    
    def delete_session(self, session_id: str, user_id: str) -> bool:
        def _do_delete(conn):
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM chat_messages WHERE session_id = ? AND user_id = ?
            """, (session_id, user_id))
            return True
        
        try:
            return self._execute_with_retry(_do_delete)
        except Exception as e:
            print(f"SQLite delete error: {e}")
            return False
    
    def get_user_sessions(self, user_id: str, limit: int = 10) -> List[Dict]:
        try:
            conn = self._get_connection()
            conn.row_factory = self.sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT session_id, MAX(timestamp) as last_timestamp, COUNT(*) as message_count
                FROM chat_messages
                WHERE user_id = ?
                GROUP BY session_id
                ORDER BY last_timestamp DESC
                LIMIT ?
            """, (user_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            print(f"SQLite sessions error: {e}")
            return []


class PostgreSQLChatMemory(ChatMemoryBackend):
    """PostgreSQL-based chat memory with multi-tenant support.
    Uses db_config for connection management.
    Activated when USE_POSTGRES=true in .env
    """
    
    def __init__(self):
        try:
            # Test connection
            conn = get_db_connection('chat')
            conn.close()
            self.available = True
            print("[OK] PostgreSQL Chat Memory initialized")
        except Exception as e:
            print(f"[ERROR] PostgreSQL Chat Memory initialization failed: {e}")
            self.available = False
    
    def save_message(self, user_id: str, session_id: str, role: str, content: str,
                     intent: Optional[str] = None, selected_agent: Optional[str] = None,
                     metadata: Optional[Dict] = None) -> bool:
        """Save a chat message with user isolation"""
        if not self.available:
            return False
        
        # GUARD: Skip empty/null/system messages
        if content is None or (isinstance(content, str) and content.strip() == ""):
            print(f"[CHAT_MEMORY] Skipped empty/null message in PostgreSQL (role={role})")
            return True
        
        if role and role.lower() == "system":
            print(f"[CHAT_MEMORY] Skipped system message in PostgreSQL")
            return True
        
        try:
            conn = get_db_connection('chat')
            cursor = conn.cursor()
            timestamp = datetime.utcnow().isoformat()
            
            cursor.execute("""
                INSERT INTO chat_messages (user_id, session_id, role, content, intent, selected_agent, metadata, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, session_id, role, content, intent, selected_agent,
                  json.dumps(metadata) if metadata else None, timestamp))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"PostgreSQL chat save error: {e}")
            return False
    
    def get_session_history(self, session_id: str, user_id: str, limit: int = 50) -> List[Dict]:
        """Get conversation history for a specific session"""
        if not self.available:
            return []
        
        try:
            conn = get_db_connection('chat')
            cursor = get_dict_cursor(conn)
            
            cursor.execute("""
                SELECT * FROM chat_messages
                WHERE session_id = %s AND user_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (session_id, user_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            messages = []
            for row in rows:
                # Parse metadata JSON if present
                metadata = None
                if row.get("metadata"):
                    try:
                        raw_meta = row["metadata"]
                        metadata = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
                    except (json.JSONDecodeError, TypeError):
                        metadata = {}
                
                messages.append({
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "session_id": row["session_id"],
                    "role": row["role"],
                    "content": row["content"],
                    "intent": row["intent"],
                    "selected_agent": row["selected_agent"],
                    "timestamp": str(row["timestamp"]) if row["timestamp"] else None,
                    "metadata": metadata  # CRITICAL: Include metadata for flow state
                })
            
            return messages
            
        except Exception as e:
            print(f"PostgreSQL chat retrieval error: {e}")
            return []
    
    def get_user_context(self, user_id: str, session_id: str, max_messages: int = 10) -> str:
        """Get formatted conversation context for LLM prompt"""
        messages = self.get_session_history(session_id, user_id, limit=max_messages)
        
        if not messages:
            return "(No previous conversation)"
        
        context_lines = []
        for msg in messages[-max_messages:]:
            role_label = "Student" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")
            if len(content) > 300:
                content = content[:300] + "..."
            context_lines.append(f"{role_label}: {content}")
        
        return "\n".join(context_lines) if context_lines else "(No previous conversation)"
    
    def search_conversation(self, user_id: str, query: str, limit: int = 5) -> List[Dict]:
        """Basic keyword search (PostgreSQL doesn't support semantic search without extensions)"""
        if not self.available:
            return []
        
        try:
            conn = get_db_connection('chat')
            cursor = get_dict_cursor(conn)
            
            cursor.execute("""
                SELECT * FROM chat_messages
                WHERE user_id = %s AND LOWER(content) LIKE %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (user_id, f"%{query.lower()}%", limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            print(f"PostgreSQL chat search error: {e}")
            return []
    
    def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete all messages in a session (with user verification)"""
        if not self.available:
            return False
        
        try:
            conn = get_db_connection('chat')
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM chat_messages
                WHERE session_id = %s AND user_id = %s
            """, (session_id, user_id))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"PostgreSQL chat delete error: {e}")
            return False
    
    def get_user_sessions(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get list of sessions for a user"""
        if not self.available:
            return []
        
        try:
            conn = get_db_connection('chat')
            cursor = get_dict_cursor(conn)
            
            cursor.execute("""
                SELECT session_id, MAX(timestamp) as last_timestamp, COUNT(*) as message_count
                FROM chat_messages
                WHERE user_id = %s
                GROUP BY session_id
                ORDER BY last_timestamp DESC
                LIMIT %s
            """, (user_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            print(f"PostgreSQL chat sessions error: {e}")
            return []


class ChatMemory:
    """
    Unified Chat Memory with automatic backend selection.
    Multi-tenant with proper user isolation.
    
    Environment Variables:
    - CHAT_MEMORY_BACKEND: "chromadb", "upstash", "redis", or "sqlite"
    - UPSTASH_REDIS_REST_URL: Upstash Redis URL
    - UPSTASH_REDIS_REST_TOKEN: Upstash Redis token
    """
    
    def __init__(self):
        backend_type = os.getenv("CHAT_MEMORY_BACKEND", "chromadb").lower()
        
        self.backend: ChatMemoryBackend = None
        
        # PRIORITY: Use PostgreSQL when USE_POSTGRES=true (database migration support)
        if is_postgres():
            self.backend = PostgreSQLChatMemory()
            if self.backend.available:
                print("[OK] Using PostgreSQL for chat memory (dual-backend mode)")
            else:
                print("[WARN] PostgreSQL unavailable, falling back to other backends")
                self.backend = None
        
        # Try ChromaDB (recommended for semantic search)
        if self.backend is None and backend_type == "chromadb":
            if CHROMADB_AVAILABLE:
                self.backend = ChromaDBChatMemory()
                if self.backend.available:
                    print("[OK] Using ChromaDB for chat memory (persistent, semantic search)")
                else:
                    self.backend = None
            else:
                print("[WARN] ChromaDB not available")
        
        # Try Upstash Redis (serverless)
        if self.backend is None and backend_type in ["upstash", "redis"]:
            upstash_url = os.getenv("UPSTASH_REDIS_REST_URL")
            if upstash_url:
                self.backend = UpstashRedisChatMemory()
                if self.backend.available:
                    print("[OK] Using Upstash Redis for chat memory (serverless)")
                else:
                    self.backend = None
        
        # Fallback to SQLite
        if self.backend is None:
            print("[WARN] Using SQLite fallback for chat memory (local development only)")
            self.backend = SQLiteChatMemory()
    
    def create_session_id(self) -> str:
        """Generate a new unique session ID"""
        return str(uuid.uuid4())
    
    def save_message(self, user_id: str, session_id: str, role: str, content: str,
                     intent: Optional[str] = None, selected_agent: Optional[str] = None,
                     metadata: Optional[Dict] = None, action_executed: Optional[Dict] = None) -> bool:
        """Save a message with user isolation
        
        Args:
            user_id: User email for isolation
            session_id: Session UUID
            role: 'user' or 'bot'
            content: Message content
            intent: Detected intent
            selected_agent: Agent that handled the message
            metadata: Additional metadata dict (preferred)
            action_executed: Legacy parameter for action data
        """
        # GUARD: Skip empty/null/system messages at the top level
        if content is None or (isinstance(content, str) and content.strip() == ""):
            print(f"[CHAT_MEMORY] Skipped empty/null message via wrapper (role={role})")
            return True  # Return success to avoid blocking
        
        if role and role.lower() == "system":
            print(f"[CHAT_MEMORY] Skipped system message via wrapper")
            return True
        
        # Merge metadata - support both old and new parameter styles
        final_metadata = metadata if metadata else {}
        if action_executed:
            final_metadata["action_executed"] = action_executed
        
        return self.backend.save_message(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            intent=intent,
            selected_agent=selected_agent,
            metadata=final_metadata if final_metadata else None
        )
    
    def save_turn(self, user_id: str, session_id: str, user_message: str, bot_response: str, metadata: Optional[Dict] = None) -> bool:
        """
        Save a full conversation turn (User + Bot)
        """
        # Save user message
        success_user = self.save_message(
            user_id=user_id,
            session_id=session_id,
            role="user",
            content=user_message,
            metadata=metadata
        )
        
        # Save bot response - using "assistant" role for consistency with orchestrator state loading
        success_bot = self.save_message(
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            content=bot_response,
            metadata=metadata
        )
        
        return success_user and success_bot
    
    def get_session_history(self, session_id: str, user_id: str = None, limit: int = 50) -> List[Dict]:
        """
        Get session history with user isolation.
        
        Args:
            session_id: Session UUID
            user_id: User email (required for security)
            limit: Maximum messages
        """
        if user_id is None:
            print("[WARN] Warning: get_session_history called without user_id - this is a security risk")
            return []
        
        return self.backend.get_session_history(session_id, user_id, limit)
    
    def get_user_context(self, user_id: str, session_id: str, max_messages: int = 10) -> str:
        """Get formatted conversation context for LLM"""
        return self.backend.get_user_context(user_id, session_id, max_messages)
    
    def get_recent_context(self, session_id: str, max_messages: int = 10, user_id: str = None) -> str:
        """Backward compatible method"""
        if user_id:
            return self.backend.get_user_context(user_id, session_id, max_messages)
        return "(No context - user_id required)"
    
    def search_conversation(self, user_id: str, query: str, limit: int = 5) -> List[Dict]:
        """Search user's conversation history"""
        return self.backend.search_conversation(user_id, query, limit)
    
    def delete_session(self, session_id: str, user_id: str = None) -> bool:
        """Delete session with user verification"""
        if user_id is None:
            print("[WARN] Warning: delete_session called without user_id")
            return False
        return self.backend.delete_session(session_id, user_id)
    
    def get_user_sessions(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get list of user's sessions"""
        if hasattr(self.backend, 'get_user_sessions'):
            return self.backend.get_user_sessions(user_id, limit)
        return []


# Singleton instance
_chat_memory_instance = None

def get_chat_memory() -> ChatMemory:
    """Get singleton instance of ChatMemory"""
    global _chat_memory_instance
    if _chat_memory_instance is None:
        _chat_memory_instance = ChatMemory()
    return _chat_memory_instance


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Testing Multi-Tenant Chat Memory")
    print("=" * 60 + "\n")
    
    memory = ChatMemory()
    
    # Test with two different users
    user1 = "student1@ace.edu"
    user2 = "student2@ace.edu"
    
    session1 = memory.create_session_id()
    session2 = memory.create_session_id()
    
    # User 1 conversation
    memory.save_message(user1, session1, "user", "What is the attendance policy?")
    memory.save_message(user1, session1, "bot", "You need 75% minimum attendance.")
    memory.save_message(user1, session1, "user", "What if it drops below?")
    
    # User 2 conversation (should be isolated)
    memory.save_message(user2, session2, "user", "How much is the hostel fee?")
    memory.save_message(user2, session2, "bot", "Hostel fee is ₹45,000 per year.")
    
    # Verify isolation
    print(f"User 1 context:\n{memory.get_user_context(user1, session1)}\n")
    print(f"User 2 context:\n{memory.get_user_context(user2, session2)}\n")
    
    # User 1 should NOT see User 2's messages
    user1_history = memory.get_session_history(session1, user1)
    print(f"User 1 messages: {len(user1_history)}")
    
    # Try to access User 2's session as User 1 (should return empty)
    cross_access = memory.get_session_history(session2, user1)
    print(f"Cross-user access (should be 0): {len(cross_access)}")
