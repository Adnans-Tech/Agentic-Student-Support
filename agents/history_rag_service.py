"""
History RAG Service - User-specific historical data retrieval
Manages ChromaDB vector store for emails, tickets, and faculty contacts
"""
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except Exception:
    print("[WARN] ChromaDB not available - history retrieval will be limited")
    CHROMADB_AVAILABLE = False

from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json


class HistoryRAGService:
    """
    RAG service for user-specific historical data retrieval.
    Uses ChromaDB with metadata filtering for efficient user-scoped queries.
    Falls back to in-memory storage if ChromaDB is not available.
    """
    
    def __init__(self, persist_directory="data/user_history_db"):
        """Initialize ChromaDB client and collection"""
        self.chromadb_available = CHROMADB_AVAILABLE
        
        if self.chromadb_available:
            try:
                self.client = chromadb.PersistentClient(
                    path=persist_directory,
                    settings=Settings(anonymized_telemetry=False)
                )
                
                # Create or get collection
                self.collection = self.client.get_or_create_collection(
                    name="user_actions",
                    metadata={"hnsw:space": "cosine"}
                )
                
                print(f"[OK] History RAG Service initialized with ChromaDB")
            except Exception as e:
                print(f"[WARN] ChromaDB initialization failed: {e}")
                print("[WARN] Falling back to in-memory storage")
                self.chromadb_available = False
                self._init_fallback()
        else:
            self._init_fallback()

    
    def _init_fallback(self):
        """Initialize fallback in-memory storage"""
        self.memory_store = []
        print("✓ History RAG Service initialized with fallback storage")
    
    def index_email_action(self, user_id: str, email_data: Dict) -> bool:
        """
        Index an email action to the vector store.
        
        Args:
            user_id: Student email
            email_data: Dict containing to_email, subject, body, timestamp
            
        Returns:
            bool: Success status
        """
        try:
            timestamp = email_data.get('timestamp', datetime.now().isoformat())
            
            # Create document content (natural language summary)
            content = f"""Email sent to {email_data.get('recipient_name', 'recipient')} ({email_data.get('to_email', 'unknown')}) on {timestamp[:10]}.
Subject: {email_data.get('subject', 'No subject')}
Purpose: {email_data.get('purpose', 'Not specified')}
Status: Sent successfully"""
            
            if self.chromadb_available:
                # Generate unique ID
                doc_id = f"email_{user_id}_{timestamp}".replace('@', '_').replace(':', '_').replace('.', '_')
                
                # Add to collection with metadata
                self.collection.add(
                    documents=[content],
                    metadatas=[{
                        "user_id": user_id,
                        "action_type": "email",
                        "timestamp": timestamp,
                        "recipient": email_data.get('to_email', ''),
                        "subject": email_data.get('subject', '')[:100],  # Truncate for metadata
                        "category": "communication"
                    }],
                    ids=[doc_id]
                )
            else:
                # Fallback: store in memory
                self.memory_store.append({
                    "content": content,
                    "metadata": {
                        "user_id": user_id,
                        "action_type": "email",
                        "timestamp": timestamp,
                        "recipient": email_data.get('to_email', ''),
                        "subject": email_data.get('subject', '')[:100],
                    }
                })
            
            return True
            
        except Exception as e:
            print(f"Error indexing email action: {e}")
            return False
    
    def index_ticket_action(self, user_id: str, ticket_data: Dict) -> bool:
        """
        Index a ticket action to the vector store.
        
        Args:
            user_id: Student email
            ticket_data: Dict containing ticket details
            
        Returns:
            bool: Success status
        """
        try:
            timestamp = ticket_data.get('created_at', datetime.now().isoformat())
            
            # Create document content
            content = f"""Ticket raised on {timestamp[:10]}.
Ticket ID: {ticket_data.get('ticket_id', 'Unknown')}
Category: {ticket_data.get('category', 'General')} - {ticket_data.get('sub_category', '')}
Priority: {ticket_data.get('priority', 'Medium')}
Description: {ticket_data.get('description', '')[:200]}
Status: {ticket_data.get('status', 'Open')}
Department: {ticket_data.get('department', 'General')}"""
            
            if self.chromadb_available:
                # Generate unique ID
                doc_id = f"ticket_{user_id}_{ticket_data.get('ticket_id', timestamp)}".replace('@', '_').replace(':', '_').replace('.', '_').replace('-', '_')
                
                # Add to collection
                self.collection.add(
                    documents=[content],
                    metadatas=[{
                        "user_id": user_id,
                        "action_type": "ticket",
                        "timestamp": timestamp,
                        "ticket_id": str(ticket_data.get('ticket_id', '')),
                        "category": ticket_data.get('category', '')[:50],
                        "priority": ticket_data.get('priority', 'Medium'),
                        "status": ticket_data.get('status', 'Open')
                    }],
                    ids=[doc_id]
                )
            else:
                # Fallback
                self.memory_store.append({
                    "content": content,
                    "metadata": {
                        "user_id": user_id,
                        "action_type": "ticket",
                        "timestamp": timestamp,
                        "ticket_id": str(ticket_data.get('ticket_id', '')),
                        "category": ticket_data.get('category', '')[:50],
                    }
                })
            
            return True
            
        except Exception as e:
            print(f"Error indexing ticket action: {e}")
            return False
    
    def index_faculty_contact(self, user_id: str, contact_data: Dict) -> bool:
        """
        Index a faculty contact action to the vector store.
        
        Args:
            user_id: Student email
            contact_data: Dict containing faculty contact details
            
        Returns:
            bool: Success status
        """
        try:
            timestamp = contact_data.get('timestamp', datetime.now().isoformat())
            
            # Create document content
            content = f"""Contacted faculty member on {timestamp[:10]}.
Faculty: {contact_data.get('faculty_name', 'Unknown')} ({contact_data.get('designation', '')})
Department: {contact_data.get('department', '')}
Email: {contact_data.get('faculty_email', '')}
Purpose: {contact_data.get('purpose', 'Not specified')}
Status: {contact_data.get('status', 'Sent')}"""
            
            if self.chromadb_available:
                # Generate unique ID
                doc_id = f"faculty_{user_id}_{timestamp}".replace('@', '_').replace(':', '_').replace('.', '_')
                
                # Add to collection
                self.collection.add(
                    documents=[content],
                    metadatas=[{
                        "user_id": user_id,
                        "action_type": "faculty_contact",
                        "timestamp": timestamp,
                        "faculty_email": contact_data.get('faculty_email', ''),
                        "department": contact_data.get('department', '')[:50],
                        "category": "faculty_communication"
                    }],
                    ids=[doc_id]
                )
            else:
                # Fallback
                self.memory_store.append({
                    "content": content,
                    "metadata": {
                        "user_id": user_id,
                        "action_type": "faculty_contact",
                        "timestamp": timestamp,
                        "faculty_email": contact_data.get('faculty_email', ''),
                    }
                })
            
            return True
            
        except Exception as e:
            print(f"Error indexing faculty contact: {e}")
            return False
    
    def retrieve_user_history(self, user_id: str, query: str, k: int = 5, action_type: Optional[str] = None) -> List[Dict]:
        """
        Retrieve user-specific history using semantic search.
        
        Args:
            user_id: Student email (for filtering)
            query: Natural language query
            k: Number of results to return
            action_type: Optional filter for action type (email/ticket/faculty_contact)
            
        Returns:
            List of matching documents with metadata
        """
        try:
            if self.chromadb_available:
                # Build where filter for user_id and optional action_type
                where_filter = {"user_id": user_id}
                if action_type:
                    where_filter["action_type"] = action_type
                
                # Query the collection
                results = self.collection.query(
                    query_texts=[query],
                    n_results=k,
                    where=where_filter
                )
                
                # Format results
                formatted_results = []
                if results['documents'] and len(results['documents']) > 0:
                    for i, doc in enumerate(results['documents'][0]):
                        formatted_results.append({
                            "content": doc,
                            "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                            "distance": results['distances'][0][i] if results.get('distances') else None
                        })
                
                return formatted_results
            else:
                # Fallback: simple filtering from memory
                results = []
                for item in self.memory_store:
                    if item['metadata'].get('user_id') == user_id:
                        if action_type is None or item['metadata'].get('action_type') == action_type:
                            # Simple keyword matching
                            if query.lower() in item['content'].lower():
                                results.append(item)
                
                return results[:k]
            
        except Exception as e:
            print(f"Error retrieving user history: {e}")
            return []
    
    def get_recent_actions(self, user_id: str, action_type: Optional[str] = None, days: int = 30, limit: int = 10) -> List[Dict]:
        """
        Get recent actions chronologically (not semantic search).
        
        Args:
            user_id: Student email
            action_type: Optional filter for action type
            days: Number of days to look back
            limit: Maximum number of results
            
        Returns:
            List of recent actions
        """
        try:
            # Calculate cutoff date
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Build where filter
            where_filter = {
                "$and": [
                    {"user_id": user_id},
                    {"timestamp": {"$gte": cutoff}}
                ]
            }
            
            if action_type:
                where_filter["$and"].append({"action_type": action_type})
            
            # Get all matching documents
            results = self.collection.get(
                where=where_filter,
                limit=limit
            )
            
            # Format and sort by timestamp
            formatted_results = []
            if results['documents']:
                for i, doc in enumerate(results['documents']):
                    formatted_results.append({
                        "content": doc,
                        "metadata": results['metadatas'][i] if results['metadatas'] else {},
                        "id": results['ids'][i] if results['ids'] else None
                    })
                
                # Sort by timestamp descending
                formatted_results.sort(
                    key=lambda x: x['metadata'].get('timestamp', ''),
                    reverse=True
                )
            
            return formatted_results
            
        except Exception as e:
            print(f"Error getting recent actions: {e}")
            return []
    
    def get_action_count(self, user_id: str, action_type: Optional[str] = None) -> int:
        """
        Get count of user actions.
        
        Args:
            user_id: Student email
            action_type: Optional filter for action type
            
        Returns:
            Count of actions
        """
        try:
            where_filter = {"user_id": user_id}
            if action_type:
                where_filter["action_type"] = action_type
            
            results = self.collection.get(where=where_filter)
            return len(results['ids']) if results.get('ids') else 0
            
        except Exception as e:
            print(f"Error getting action count: {e}")
            return 0


# Singleton instance
_history_rag_instance = None

def get_history_rag_service():
    """Get singleton instance of HistoryRAGService"""
    global _history_rag_instance
    if _history_rag_instance is None:
        _history_rag_instance = HistoryRAGService()
    return _history_rag_instance


if __name__ == "__main__":
    # Test the service
    print("\n" + "=" * 60)
    print("  Testing History RAG Service")
    print("=" * 60 + "\n")
    
    service = HistoryRAGService()
    
    # Test indexing
    test_email = {
        "to_email": "dr.sharma@college.edu",
        "recipient_name": "Dr. Sharma",
        "subject": "Request for Attendance Condonation",
        "purpose": "Need attendance condonation due to medical emergency",
        "timestamp": datetime.now().isoformat()
    }
    
    success = service.index_email_action("test@student.com", test_email)
    print(f"Email indexing: {'✓' if success else '✗'}")
    
    # Test retrieval
    results = service.retrieve_user_history("test@student.com", "attendance", k=3)
    print(f"\nFound {len(results)} results for 'attendance'")
    for r in results:
        print(f"  - {r['content'][:100]}...")
