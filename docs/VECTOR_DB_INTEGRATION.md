# Chroma DB Integration Guide

## Current State

The ACE College Support System currently uses:
- **FAISS** for vector storage of `college_rules.txt` (semantic search for FAQ agent)
- **SQLite** for chat memory and conversation history

## Why Chroma DB is Not Yet Integrated

Per project requirements, Chroma DB integration is **future-ready** but not currently enabled. The system is designed to work without it for now.

## Where Chroma DB Should Be Integrated (Future)

### 1. Chat Memory Storage
**File**: `agents/chat_memory.py`

**Current Implementation**: Uses SQLite for storing conversation history
**Future Migration**: Replace SQLite backend with Chroma DB for:
- Better semantic search over conversation history
- Efficient retrieval of contextually similar past conversations
- Metadata-based filtering (user_id, session_id, timestamps)

**Integration Points**:
```python
# agents/chat_memory.py
# Replace SQLite connection with ChromaDB client
import chromadb
client = chromadb.PersistentClient(path="data/chat_memory_db")
collection = client.get_or_create_collection("chat_history")
```

### 2. User History RAG Service
**File**: `agents/history_rag_service.py`

**Current Implementation**: Likely uses SQLite or in-memory storage
**Future Migration**: Use Chroma DB for:
- Student ticket history semantic search
- Faculty interaction history retrieval
- Email request pattern matching

**Integration Points**:
```python
# agents/history_rag_service.py
# Add Chroma collection for user interaction history
history_collection = client.get_or_create_collection("user_history")
```

### 3. Optional: Replace FAISS with Chroma
**File**: `agents/vector_store.py`

**Current**: FAISS for college rules (works well)
**Future Option**: Migrate to Chroma DB for unified vector storage

**Pros**: Single database for all embeddings, easier deployment
**Cons**: FAISS is faster for static data

## Migration Checklist

When Chroma DB access is provided:

- [ ] Install/update `chromadb` package
- [ ] Update `requirements.txt` with Chroma DB version
- [ ] Migrate `chat_memory.py` to use Chroma collections
- [ ] Update `history_rag_service.py` to use Chroma for user history
- [ ] Test conversation context retrieval with Chroma backend
- [ ] (Optional) Migrate FAISS college rules to Chroma
- [ ] Update environment variables if Chroma requires remote connection
- [ ] Test semantic search performance vs. SQLite/FAISS
- [ ] Update deployment documentation

## Environment Variables (Future)

If using Chroma Cloud or remote instance:
```bash
# .env
CHROMA_HOST=localhost
CHROMA_PORT=8000
CHROMA_AUTH_TOKEN=your_token_here  # if authentication required
```

## Notes

- Current architecture is **modular** - switching to Chroma requires minimal code changes
- FAISS vector store for college rules should remain unless performance issues arise
- Chroma DB is better for **dynamic, growing datasets** (chat logs, user history)
- FAISS is better for **static, read-heavy datasets** (college rules)

## Architecture Decision

**Recommended Hybrid Approach**:
- Keep FAISS for `college_rules.txt` (static data)
- Use Chroma DB for chat memory and user history (dynamic, growing data)
- This gives best performance and simplicity

---

Last Updated: January 2026
Status: Future Integration (Not Yet Implemented)
