"""
FAQ Agent with Lang Chain & RAG
Answers student queries using semantic search over college rules
Now includes conversation history for context awareness
Enhanced with synonym mapping, comparative query handling, and natural language responses
"""
import sys
import time
sys.path.append('..')

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from config import GROQ_API_KEY
from typing import Optional, List, Dict
import re

# Performance: toggle verbose logging
DEBUG_LOGGING = False

# Performance: simple TTL cache for FAQ responses
_faq_cache = {}
_FAQ_CACHE_TTL = 300  # 5 minutes
_FAQ_CACHE_MAX_SIZE = 50

try:
    from .vector_store import VectorStoreManager
    from .chat_memory import get_chat_memory
    from .agent_data_access import get_agent_data_access
    from .agent_protocol import AgentResponse
except ImportError:
    from vector_store import VectorStoreManager
    from chat_memory import get_chat_memory
    from agent_data_access import get_agent_data_access
    from agent_protocol import AgentResponse


# =============================================================================
# QUERY ENHANCEMENT: Synonym Mapping for Better RAG Retrieval
# =============================================================================

QUERY_SYNONYMS = {
    # Placement terms
    "salary": ["package", "compensation", "ctc", "offer"],
    "package": ["salary", "compensation", "ctc"],
    
    # Department terms
    "capacity": ["seats", "intake"],
    "department": ["branch", "program", "course"],
    "branch": ["department", "program"],
    
    # Comparative terms
    "highest": ["maximum", "max", "top", "best"],
    "lowest": ["minimum", "min", "least", "worst", "smallest"],
    "more": ["most", "highest", "maximum"],
    "less": ["least", "lowest", "minimum"],
}

def expand_query_with_synonyms(query: str) -> str:
    """
    Expand query with synonyms for better RAG retrieval.
    
    Example: "highest salary" → "highest salary package compensation ctc"
    This helps vector search match even if database uses different terms.
    """
    query_lower = query.lower()
    expanded_terms = []
    
    for word, synonyms in QUERY_SYNONYMS.items():
        if word in query_lower:
            expanded_terms.extend(synonyms)
    
    if expanded_terms:
        # Add unique synonyms to query
        unique_synonyms = list(set(expanded_terms))
        return f"{query} {' '.join(unique_synonyms[:3])}"  # Limit to 3 synonyms
    return query


def format_to_natural_language(raw_response: str, query: str) -> str:
    """
    Convert RAG output to full, clear, natural language sentences.
    Transforms bullet points and data snippets into professional responses.
    """
    query_lower = query.lower()
    
    # If already looks like a sentence, return as-is
    if raw_response.strip().endswith(".") and not any(x in raw_response for x in ["\n-", "• "]):
        return raw_response
    
    # Handle "data not available" responses
    if "not available" in raw_response.lower():
        return raw_response
    
    # PLACEMENT DATA FORMATTING
    if any(word in query_lower for word in ["package", "salary", "placement", "ctc"]):
        # Extract placement info
        highest_match = re.search(r"Highest Package:?\s*INR\s*([\d\.,]+\s*LPA)\s*\(([^)]+)\)", raw_response, re.IGNORECASE)
        average_match = re.search(r"Average Package:?\s*INR\s*([\d\-–]+\s*LPA)", raw_response, re.IGNORECASE)
        
        if "highest" in query_lower and highest_match:
            amount, company = highest_match.groups()
            return f"The highest placement package at ACE Engineering College is INR {amount}, offered by {company}."
        
        if "average" in query_lower and average_match:
            amount = average_match.group(1)
            return f"The average placement package at ACE Engineering College is INR {amount}."
        
        # General placement info
        if highest_match or average_match:
            parts = []
            if highest_match:
                amount, company = highest_match.groups()
                parts.append(f"the highest package is INR {amount} from {company}")
            if average_match:
                amount = average_match.group(1)
                parts.append(f"the average package is INR {amount}")
            
            if parts:
                return f"Regarding placements at ACE Engineering College, {' and '.join(parts)}."
    
    # DEPARTMENT/CAPACITY FORMATTING
    if any(word in query_lower for word in ["department", "capacity", "seats", "intake", "branch"]):
        lines = [line.strip() for line in raw_response.split("\n") if line.strip()]
        
        # Check if it's a bulleted list
        if any(line.startswith("-") or line.startswith("•") for line in lines):
            items = []
            for line in lines:
                line = line.strip("-• ").strip()
                if line:
                    items.append(line)
            
            if items and "capacity" in query_lower or "seats" in query_lower or "intake" in query_lower:
                # Format capacity list
                return f"The intake capacities at ACE Engineering College are as follows:\n\n" + "\n".join([f"• {item}" for item in items])
            elif items:
                # Format department list
                if len(items) > 1:
                    return f"ACE Engineering College offers the following departments: {', '.join(items[:-1])}, and {items[-1]}."
                elif len(items) == 1:
                    return f"ACE Engineering College offers: {items[0]}."
    
    # Default: return as-is
    return raw_response


def handle_comparative_query(query: str, response: str) -> Optional[str]:
    """
    Handle comparative queries like "which has most/least".
    Analyzes response data and returns formatted comparison.
    """
    query_lower = query.lower()
    
    # Check if it's a comparative query
    is_comparative = any(word in query_lower for word in [
        "most", "least", "highest", "lowest", "more", "less",
        "maximum", "minimum", "which", "what"
    ])
    
    if not is_comparative:
        return None
    
    # Department capacity comparison
    if any(word in query_lower for word in ["department", "branch", "capacity", "seats", "students", "intake"]):
        # Extract capacity data from response
        capacity_pattern = r"([A-Z][A-Za-z\s&()]+):\s*(\d+)\s*seats?"
        matches = re.findall(capacity_pattern, response, re.IGNORECASE)
        
        if matches:
            # Build department capacity dict
            capacities = {}
            for dept_name, capacity_str in matches:
                dept_name = dept_name.strip()
                capacity = int(capacity_str)
                capacities[dept_name] = capacity
            
            if capacities:
                # Determine if looking for max or min
                is_max_query = any(word in query_lower for word in ["most", "highest", "maximum", "more"])
                
                if is_max_query:
                    max_dept = max(capacities.items(), key=lambda x: x[1])
                    return f"The {max_dept[0]} department has the highest intake capacity with {max_dept[1]} seats."
                else:
                    min_depts = [dept for dept, cap in capacities.items() if cap == min(capacities.values())]
                    min_capacity = min(capacities.values())
                    
                    if len(min_depts) == 1:
                        return f"The {min_depts[0]} department has the lowest intake capacity with {min_capacity} seats."
                    else:
                        dept_list = ", ".join(min_depts[:-1]) + f", and {min_depts[-1]}"
                        return f"The {dept_list} departments have the lowest intake capacity with {min_capacity} seats each."
    
    return None


class FAQAgent:
    """
    Enhanced FAQ Agent with RAG capabilities and conversation memory
    Uses vector database for semantic search over college rules
    Maintains conversation context across turns
    """
    
    def __init__(self, college_rules_file='data/college_rules.txt', llm=None):
        # Reuse shared LLM if provided, otherwise create one
        if llm is not None:
            self.llm = llm
            print("[OK] FAQ Agent reusing shared LLM instance")
        else:
            self.llm = ChatGroq(
                api_key=GROQ_API_KEY,
                model_name="llama-3.1-8b-instant",
                temperature=0.1,
                max_tokens=500
            )
        
        # Initialize vector store manager (singleton — shares ML model across agents)
        print("[INFO] Initializing vector store for RAG...")
        try:
            from .vector_store import get_vector_store_manager
        except ImportError:
            from vector_store import get_vector_store_manager
        self.vector_manager = get_vector_store_manager(rules_file=college_rules_file)
        # INCREASED k from 3 to 5 for better coverage of course queries
        self.retriever = self.vector_manager.get_retriever(k=5)
        print("[OK] Vector store ready")
        
        # Get shared chat memory instance
        self.chat_memory = get_chat_memory()
        # NATURAL CONVERSATIONAL PROMPT V3
        # Natural language, complete data, no database terminology
        self.template = """You are a friendly student support assistant for ACE Engineering College.
Respond naturally and conversationally, like a helpful college counselor.

═══════════════════════════════════════════════════════════
RESPONSE RULES
═══════════════════════════════════════════════════════════

1. USE NATURAL LANGUAGE:
   ✅ "ACE Engineering College offers 9 B.Tech programs..."
   ❌ "The database shows..." or "Data found..."
   ❌ "The following are offered at ACE Engineering College:" (too formal)

2. INCLUDE ALL ITEMS:
   If the RETRIEVED INFORMATION lists 9 courses, include ALL 9 in your response.
   Never skip or truncate items. List everything completely.

3. ANSWER FORMAT:
   - Write in complete, natural sentences
   - Be direct and informative
   - No bullet points unless listing many items
   - For lists, use natural language: "...including CSE, ECE, IT, and ME."

4. IF INFORMATION IS AVAILABLE:
   Reframe the data into a helpful, conversational response.
   
   Example - Courses Query:
   Retrieved: "B.Tech: CSE (480), CSE AI&ML (180), CSE Data Science (180), ECE (120), IT (60), CSE IoT (60), CE (60), EEE (30), ME (30)"
   Response: "ACE Engineering College offers 9 B.Tech programs: Computer Science and Engineering (CSE), CSE with AI & Machine Learning, CSE with Data Science, Electronics and Communication Engineering (ECE), Information Technology (IT), CSE with IoT, Civil Engineering, Electrical and Electronics Engineering (EEE), and Mechanical Engineering (ME). The total intake is 1,200 seats."

   Example - Departments Query:
   Retrieved: "Departments: CSE, ECE, IT, CE, EEE, ME, H&S"
   Response: "ACE Engineering College has 7 academic departments: Computer Science and Engineering (CSE), Electronics and Communication Engineering (ECE), Information Technology (IT), Civil Engineering (CE), Electrical and Electronics Engineering (EEE), Mechanical Engineering (ME), and Humanities & Sciences (H&S)."

   Example - Capacity Query:
   Retrieved: "CSE: 480, AI&ML: 180, DS: 180, ECE: 120, IT: 60, IoT: 60, CE: 60, EEE: 30, ME: 30"
   Response: "The intake capacity for each program is: CSE has 480 seats, CSE (AI & ML) and CSE (Data Science) each have 180 seats, ECE has 120 seats, IT, CSE (IoT), and Civil Engineering each have 60 seats, and EEE and ME each have 30 seats. Total intake is 1,200 students."

5. IF INFORMATION IS NOT AVAILABLE:
   Say: "I don't have that specific information. Please contact the college administration at 091333 08533 for assistance."
   
   Never say: "not available in database", "no data found", "database doesn't have"

6. STRICTLY FORBIDDEN:
   ❌ Mentioning "database", "data", "retrieved", "query"
   ❌ Adding information not in RETRIEVED INFORMATION (no M.Tech, MBA if not listed)
   ❌ Repeating the same phrase twice (e.g., "The following...The following...")
   ❌ Truncating lists (if 9 items exist, show all 9)
   ❌ Technical language or robotic responses

═══════════════════════════════════════════════════════════
RETRIEVED INFORMATION:
═══════════════════════════════════════════════════════════
{context}

═══════════════════════════════════════════════════════════
STUDENT PROFILE (if relevant):
═══════════════════════════════════════════════════════════
{student_context}

═══════════════════════════════════════════════════════════
CONVERSATION HISTORY:
═══════════════════════════════════════════════════════════
{conversation_history}

═══════════════════════════════════════════════════════════
USER'S QUESTION: {question}
═══════════════════════════════════════════════════════════

Respond naturally and completely:"""
        
        self.prompt = ChatPromptTemplate.from_template(self.template)

    # =====================================================================
    # PERFORMANCE: Simple TTL cache for FAQ responses
    # =====================================================================
    def _check_cache(self, query_key: str):
        """Check if a cached response exists and is still fresh."""
        entry = _faq_cache.get(query_key)
        if entry and (time.time() - entry['time']) < _FAQ_CACHE_TTL:
            return entry['response']
        return None

    def _store_cache(self, query_key: str, response):
        """Store a response in the cache, evicting old entries if needed."""
        if len(_faq_cache) >= _FAQ_CACHE_MAX_SIZE:
            # Evict oldest entry
            oldest_key = min(_faq_cache, key=lambda k: _faq_cache[k]['time'])
            del _faq_cache[oldest_key]
        _faq_cache[query_key] = {'response': response, 'time': time.time()}
        
    
    def _format_docs(self, docs) -> str:
        """Format retrieved documents for context"""
        return "\n\n---\n\n".join(doc.page_content for doc in docs)
    
    def _get_conversation_context(self, user_id: Optional[str], session_id: Optional[str], max_turns: int = 5) -> str:
        """
        Retrieve recent conversation history for context.
        Uses user_id for multi-tenant isolation.
        
        Args:
            user_id: User email (required for isolation)
            session_id: Session UUID
            max_turns: Maximum number of recent message pairs to include
            
        Returns:
            Formatted conversation history string
        """
        if not session_id or not user_id:
            return "(No previous conversation)"
        
        try:
            # Use the new multi-tenant method
            context = self.chat_memory.get_user_context(user_id, session_id, max_messages=max_turns * 2)
            return context if context else "(No previous conversation)"
            
        except Exception as e:
            print(f"Warning: Could not retrieve conversation history: {e}")
            return "(No previous conversation)"
    
    def _estimate_confidence(self, docs: List, context: str, llm_response: str) -> float:
        """
        Estimate confidence score based on retrieval quality
        
        Args:
            docs: Retrieved documents
            context: Formatted context string
            llm_response: LLM's final response
            
        Returns:
            Confidence score (0.0-1.0)
        """
        confidence = 0.5  # Base confidence
        
        # Factor 1: Number of retrieved documents
        if len(docs) >= 3:
            confidence += 0.2
        elif len(docs) >= 1:
            confidence += 0.1
        
        # Factor 2: Context length (more data = higher confidence)
        if len(context) > 200:
            confidence += 0.15
        elif len(context) > 100:
            confidence += 0.10
        
        # Factor 3: No "not available" phrases in response
        low_confidence_phrases = [
            "not available", "don't have", "no information",
            "not sure", "unclear", "database"
        ]
        if not any(phrase in llm_response.lower() for phrase in low_confidence_phrases):
            confidence += 0.15
        else:
            confidence -= 0.2
        
        # Cap between 0.3 and 0.95
        confidence = max(0.3, min(0.95, confidence))
        
        return confidence
    
    def process(self, user_query: str, session_id: Optional[str] = None, user_id: Optional[str] = None, clarification_count: int = 0) -> Dict:
        """
        Process a student query using RAG with data-grounded context.
        NOW RETURNS STRUCTURED AgentResponse
        
        Args:
            user_query: The student's question
            session_id: Optional session UUID
            user_id: User email for data access
            clarification_count: Number of previous clarification attempts (for escalation)
            
        Returns:
            Dict: AgentResponse with status, message, confidence, etc.
        """
        try:
            query_lower = user_query.lower()

            # PERFORMANCE: Check cache first
            cache_key = query_lower.strip()
            cached = self._check_cache(cache_key)
            if cached:
                print(f"[FAQ] Cache hit for: {user_query[:50]}")
                return cached
            
            # DETECT if user is asking about PAST INTERACTIONS
            # Only inject history if explicitly requested
            history_keywords = [
                "previous", "last time", "before", "earlier", "past",
                "what did i ask", "my history", "past conversation",
                "what i asked", "earlier query", "previous question"
            ]
            user_wants_history = any(keyword in query_lower for keyword in history_keywords)
            
            # Get conversation history ONLY if user explicitly asks
            if user_wants_history:
                conversation_history = self._get_conversation_context(user_id, session_id)
                if DEBUG_LOGGING:
                    print(f"[FAQ] User asked about past interactions - including history")
            else:
                conversation_history = "(User did not ask about past interactions - not shown)"
            
            # GET STUDENT-SPECIFIC DATA FROM DATABASE
            # CRITICAL: Do NOT inject student context for course/department queries
            # Student profiles contain section names (CSM-B) that get confused as courses
            student_context = "(No student data available)"
            
            # Exclude student context for general college info queries
            is_college_info_query = any(keyword in query_lower for keyword in [
                "course", "courses", "department", "departments", "branch", "branches",
                "program", "programs", "offered", "available", "intake", "seats",
                "placement", "placements", "package", "salary", "fee", "fees",
                "attendance", "exam", "grading", "founder", "about college"
            ])
            
            if user_id and not is_college_info_query:
                try:
                    data_access = get_agent_data_access()
                    
                    # Detect intent for targeted data retrieval
                    if "ticket" in query_lower:
                        student_context = data_access.build_agent_context(user_id, intent="ticket")
                    elif "faculty" in query_lower or "contact" in query_lower:
                        student_context = data_access.build_agent_context(user_id, intent="contact_faculty")
                    elif "approval" in query_lower or "verified" in query_lower or "login" in query_lower:
                        student_context = data_access.build_agent_context(user_id, intent="approval")
                    else:
                        student_context = data_access.build_agent_context(user_id, intent="general")
                    
                    print(f"[FAQ] Retrieved student context from database")
                except Exception as e:
                    print(f"[FAQ] Could not get student data: {e}")
            elif is_college_info_query:
                print(f"[FAQ] College info query detected - excluding student context to prevent confusion")
            
            # PLACEMENT QUERY DETECTION
            placement_keywords = [
                "placement", "placements", "placed", "recruiter", "recruiters",
                "hiring companies", "top companies", "companies visited", "company",
                "package", "packages", "salary", "salaries", "ctc", "lpa"
            ]
            is_placement_query = any(keyword in query_lower for keyword in placement_keywords)
            
            # COURSE/PROGRAM QUERY DETECTION (CRITICAL FIX)
            course_keywords = [
                "course", "courses", "program", "programs", "branch", "branches",
                "intake", "seats", "offered", "available", "department", "departments"
            ]
            is_course_query = any(keyword in query_lower for keyword in course_keywords)
            
            
            # SYNONYM EXPANSION: Enhance query with synonyms for better RAG retrieval
            enhanced_query = expand_query_with_synonyms(user_query)
            if DEBUG_LOGGING and enhanced_query != user_query:
                print(f"[FAQ] Query expanded: {enhanced_query[:80]}")
            
            # Enhanced retrieval for specific query types
            if is_course_query:
                retrieval_k = 7
            elif is_placement_query:
                retrieval_k = 5
            else:
                retrieval_k = 5
            
            # Retrieve from vector store
            if retrieval_k != 5:
                try:
                    custom_retriever = self.vector_manager.get_retriever(k=retrieval_k)
                    docs = custom_retriever.invoke(enhanced_query)
                except:
                    docs = self.retriever.invoke(enhanced_query)
            else:
                docs = self.retriever.invoke(enhanced_query)
            
            # Format context
            context = self._format_docs(docs)
            print(f"[FAQ] Retrieved {len(docs)} docs ({len(context)} chars)")
            
            if not context or len(context.strip()) <= 50:
                context = "(Database query executed - no relevant information found for this query)"
            
            # Placement fallback - only AFTER database was checked
            if is_placement_query and len(context.strip()) < 50:
                return "The requested information (placement data) is not available in the current database."
            
            # Build prompt with structured data
            prompt_value = self.prompt.invoke({
                "student_context": student_context,
                "context": context,
                "conversation_history": conversation_history,
                "question": user_query
            })
            
            # Get LLM response
            response = self.llm.invoke(prompt_value)
            
            # Parse response
            from langchain_core.output_parsers import StrOutputParser
            parser = StrOutputParser()
            llm_response = parser.invoke(response)
            
            # POST-PROCESSING: Apply enhancements
            comparative_response = handle_comparative_query(user_query, llm_response)
            if comparative_response:
                final_response = comparative_response
            else:
                final_response = format_to_natural_language(llm_response, user_query)
            
            # =========================================================
            # PHASE 3: STRUCTURED RESPONSE WITH CONFIDENCE SCORING
            # =========================================================
            
            # Estimate confidence based on retrieval quality
            confidence = self._estimate_confidence(docs, context, llm_response)
            
            # Escalation logic: After 2 failed clarifications, suggest ticket
            if clarification_count >= 2:
                return AgentResponse.create(
                    status="needs_escalation",
                    message=f"{final_response}\n\n_If this doesn't answer your question, would you like to raise a ticket for personalized assistance?_",
                    metadata={
                        "confidence": confidence,
                        "clarification_attempts": clarification_count,
                        "escalation_reason": "max_clarifications_reached"
                    }
                )
            
            # Low confidence warning
            if confidence < 0.6:
                result = AgentResponse.create(
                    status="needs_input",
                    message=f"I found some information, but I'm not fully confident.\n\n{final_response}\n\nWould you like me to connect you with administration, or can you rephrase your question?",
                    metadata={
                        "confidence": confidence,
                        "low_confidence_warning": True,
                        "rag_sources": ["college_rules.txt"]
                    },
                    next_expected="confirmation_or_rephrase"
                )
                # Don't cache low-confidence responses
                return result
            
            # High confidence success
            result = AgentResponse.create(
                status="success",
                message=final_response,
                resolved_entities={"query_type": "faq"},
                artifacts={
                    "retrieved_chunks": [doc.page_content[:200] for doc in docs[:3]],
                    "chunk_count": len(docs)
                },
                metadata={
                    "confidence": confidence,
                    "rag_sources": ["college_rules.txt"],
                    "query_enhanced": enhanced_query != user_query
                }
            )
            # Cache successful high-confidence responses
            self._store_cache(cache_key, result)
            return result
            
        except Exception as e:
            print(f"[FAQ][ERROR] {e}")
            return AgentResponse.error(
                f"I encountered an error while searching for information: {str(e)}",
                metadata={"error_type": "retrieval_failure"}
            )
    
    def reset_conversation(self, session_id: Optional[str] = None, user_id: Optional[str] = None):
        """Clear conversation history for a session (with user verification)"""
        if session_id and user_id:
            try:
                self.chat_memory.delete_session(session_id, user_id)
                print(f"🔄 Conversation history cleared for user: {user_id}, session: {session_id}")
            except Exception as e:
                print(f"Warning: Could not clear session: {e}")
        print("🔄 Conversation context reset")


if __name__ == "__main__":
    # Test the FAQ agent
    print("\n" + "=" * 60)
    print("  Testing FAQ Agent with RAG")
    print("=" * 60 + "\n")
    
    agent = FAQAgent()
    
    # Test queries
    test_queries = [
        "What is the attendance policy?",
        "How much is the hostel fee?",
        "What happens if I fail in a subject?"
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: {query}")
        response = agent.process(query)
        print(f"🤖 Response: {response}")
        print("-" * 60)
