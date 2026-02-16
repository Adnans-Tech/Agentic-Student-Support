"""
Orchestrator Agent - Production-Grade Agentic Decision System
=============================================================
Implements a 12-step canonical execution pipeline using LangGraph.

Architecture:
- IntentType Enum for deterministic routing
- Confidence-aware classification (threshold: 0.6)
- Self-resolution before escalation
- Preview → Edit → Confirm pipelines
- Absolute RAG enforcement for academic queries
"""
import sys
sys.path.append('..')

from enum import Enum
from typing import TypedDict, List, Dict, Optional, Any
from dataclasses import dataclass, field
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from config import GROQ_API_KEY, DEFAULT_FACULTY_EMAIL
import json
import re
import hashlib

# Governance services
from services.limits_service import LimitsService
from services.activity_service import ActivityService, ActivityType

try:
    from .history_rag_service import get_history_rag_service
    from .chat_memory import get_chat_memory
    from .faq_agent import FAQAgent
    from .email_agent import EmailAgent
    from .ticket_agent import TicketAgent
    from .faculty_db import FacultyDatabase
    from .agent_data_access import get_agent_data_access
    from .ticket_config import CATEGORIES
    # Phase 1 utilities
    from .agent_protocol import AgentResponse, safe_agent_call, compact_state_summary
    from .deduplication import check_duplicate, cache_response
    from .flow_pause import pause_flow, resume_flow, has_paused_flow, clear_flow, update_session_activity, check_session_timeout
    from .turn_logging import log_turn
except ImportError:
    from history_rag_service import get_history_rag_service
    from chat_memory import get_chat_memory
    from faq_agent import FAQAgent
    from email_agent import EmailAgent
    from ticket_agent import TicketAgent
    from faculty_db import FacultyDatabase
    from agent_data_access import get_agent_data_access
    from ticket_config import CATEGORIES
    # Phase 1 utilities
    from agent_protocol import AgentResponse, safe_agent_call, compact_state_summary
    from deduplication import check_duplicate, cache_response
    from flow_pause import pause_flow, resume_flow, has_paused_flow, clear_flow, update_session_activity, check_session_timeout
    from turn_logging import log_turn



# =============================================================================
# COLLEGE CONTACT CONFIGURATION
# =============================================================================

COLLEGE_CONTACT_NUMBER = "091333 08533"
COLLEGE_CONTACT_HOURS = "9:30 AM - 4:30 PM, Monday-Saturday"
MAX_SESSION_MESSAGES = 50  # Suggest refresh after this many messages

# Keywords that trigger contact number suggestion
CONTACT_SUGGESTED_KEYWORDS = {
    "admission", "admissions", "apply", "application", "enroll", "enrollment",
    "placement", "placements", "job", "recruit", "recruiting",
    "fee", "fees", "payment", "scholarship", "scholarships",
    "transfer", "migration", "document", "documents", "certificate",
    "procedure", "process", "official", "confirmation",
    "grievance", "complaint", "urgent", "emergency",
    "rules", "regulation", "policy", "policies"
}


# =============================================================================
# INTENT ENUM - Deterministic routing via enums (no string-based logic)
# =============================================================================

class IntentType(Enum):
    """All possible user intents - used for deterministic routing"""
    # RAG/Information Queries
    COLLEGE_RAG_QUERY = "college_rag_query"
    ACADEMIC_PROGRAM_QUERY = "academic_program_query"
    
    # Ticket Flow
    ISSUE_DESCRIPTION = "issue_description"
    TICKET_CREATE = "ticket_create"
    TICKET_STATUS = "ticket_status"
    TICKET_ACTIVE = "ticket_active"
    TICKET_RESOLVED = "ticket_resolved"
    TICKET_CLOSE = "ticket_close"
    
    # Email/Faculty Flow
    FACULTY_CONTACT = "faculty_contact"
    EMAIL_ACTION = "email_action"
    
    # History
    RETRIEVE_HISTORY = "retrieve_history"
    
    # General
    GENERAL_CHAT = "general_chat"
    UNKNOWN = "unknown"
    
    # Special - Sensitive complaints
    SENSITIVE_COMPLAINT = "sensitive_complaint"


class UserRole(Enum):
    """User roles for permission-based routing"""
    STUDENT = "student"
    FACULTY = "faculty"
    ADMIN = "admin"
    UNKNOWN = "unknown"


# =============================================================================
# DATA CLASSES - Structured results
# =============================================================================

@dataclass
class IntentResult:
    """Result of intent classification"""
    intent: IntentType
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    is_multi_intent: bool = False
    secondary_intent: Optional[IntentType] = None


@dataclass
class ValidationResult:
    """Result of validation checks"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ResolutionResult:
    """Result of self-resolution attempt"""
    resolved: bool
    response: str
    policy_references: List[str] = field(default_factory=list)
    needs_escalation: bool = False


# =============================================================================
# SHORT-TERM MEMORY - Explicit session memory (NOT ChromaDB)
# =============================================================================

class ShortTermMemory(TypedDict):
    """Minimal short-term memory for follow-up resolution"""
    last_intent: Optional[str]
    last_unresolved_goal: Optional[str]
    last_ticket_id: Optional[str]
    last_referenced_entity: Optional[str]
    last_faculty_id: Optional[str]


class ConversationState(TypedDict):
    """Per-session conversation state for context continuity"""
    current_intent: Optional[str]
    current_step: Optional[str]  # e.g., "awaiting_faculty", "awaiting_purpose"
    filled_slots: Dict[str, Any]
    pending_questions: List[str]
    last_action: Optional[str]
    conversation_summary: Optional[str]
    turns_in_current_flow: int


# =============================================================================
# AGENT STATE - LangGraph state structure
# =============================================================================

class AgentState(TypedDict):
    """State for the orchestrator agent - flows through LangGraph nodes"""
    # Core identifiers
    user_id: str
    session_id: str
    user_message: str
    user_role: str
    
    # Student profile
    student_profile: Optional[Dict]
    
    # Intent classification
    intent: str
    intent_enum: Optional[IntentType]
    confidence: float
    entities: Dict[str, Any]
    is_multi_intent: bool
    secondary_intent: Optional[str]
    reasoning: str
    
    # Flow control
    requires_clarification: bool
    clarification_question: Optional[str]
    active_flow: Optional[str]
    contact_faculty_step: Optional[str]
    
    # NEW: Follow-up question tracking
    pending_question: Optional[str]  # Question system is waiting for answer to
    expected_response_type: Optional[str]  # Type of response expected (e.g., "faculty_name", "confirmation")
    clarification_context: Dict[str, Any]  # Context for clarification questions
    
    # Action data
    extracted_slots: Dict[str, Any]
    confirmation_pending: bool
    confirmation_data: Optional[Dict]
    email_draft: Optional[Dict]
    pending_action_data: Optional[Dict]
    
    # Resolution
    self_resolution_attempted: bool
    self_resolution_response: Optional[str]
    awaiting_resolution_feedback: bool
    
    # Validation
    validation_passed: bool
    validation_errors: List[str]
    
    # Output
    final_response: Optional[str]
    selected_agent: str
    execution_plan: Optional[str]
    
    # Memory
    short_term_memory: ShortTermMemory
    conversation_state: ConversationState
    last_bot_response: Optional[str]
    
    # Ticket flow state
    ticket_step: Optional[str]  # 'awaiting_category', 'awaiting_description', 'preview'
    mode: str
    query_type: Optional[str]
    force_rag: bool
    
    # Faculty flow
    resolved_faculty: Optional[Dict]
    faculty_matches: Optional[List[Dict]]


# =============================================================================
# CONFIDENCE THRESHOLDS & SLOT SCHEMAS
# =============================================================================

# Confidence thresholds for intent routing
CONFIDENCE_HIGH = 0.8      # Execute directly
CONFIDENCE_MEDIUM = 0.5    # Ask clarification
CONFIDENCE_LOW = 0.5       # Fallback to general chat
CONFIDENCE_THRESHOLD = 0.7 # Threshold for requiring clarification (used in ambiguity detection)

# Slot schemas for each intent
INTENT_SLOT_SCHEMAS = {
    "email_action": {
        "required": ["faculty_name", "purpose"],
        "optional": ["subject"],
        "prompts": {
            "faculty_name": "Sure! Which faculty member would you like to email? Please provide their name.",
            "purpose": "What would you like to say in your email?"
        }
    },
    "faculty_contact": {
        "required": ["faculty_name", "message"],
        "optional": ["urgency"],
        "prompts": {
            "faculty_name": "Which faculty member would you like to contact?",
            "message": "What would you like to communicate?"
        }
    },
    "ticket_create": {
        "required": ["category", "description"],
        "optional": ["priority"],
        "prompts": {
            "category": "Please select a category for your ticket:",
            "description": "Please describe your issue in detail."
        }
    }
}

# Professional response templates
RESPONSE_TEMPLATES = {
    "email_confirmation": "Yes, I can help you send an email! {question}",
    "ticket_confirmation": "Of course! I'll help you raise a ticket. {question}",
    "general_greeting": "👋 Hello! I'm your ACE College assistant. I can help you with college policies, tickets, and faculty contact. What do you need?"
}


# =============================================================================
# REQUIRED FIELDS & ACTION INTENTS (CRITICAL FOR FOLLOW-UP CONTROL)
# =============================================================================

# Email validation regex - simple and permissive
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# Required fields for action intents (follow-ups allowed ONLY for these)
# Maps intent to list of required field names
REQUIRED_FIELDS = {
    "send_email": ["contact_type", "recipient", "purpose"],
    "raise_ticket": ["category", "description"]
}

# Intents that require follow-up questions (all others answer directly)
# CRITICAL: Only these intents can trigger follow-up questions
ACTION_INTENTS = {
    IntentType.EMAIL_ACTION,
    IntentType.FACULTY_CONTACT,
    IntentType.TICKET_CREATE,
    IntentType.ISSUE_DESCRIPTION,
    IntentType.SENSITIVE_COMPLAINT
}

# Intents that should NEVER trigger follow-up questions
INFORMATIONAL_INTENTS = {
    IntentType.COLLEGE_RAG_QUERY,
    IntentType.ACADEMIC_PROGRAM_QUERY,
    IntentType.TICKET_STATUS,
    IntentType.RETRIEVE_HISTORY,
    IntentType.GENERAL_CHAT
}


def check_missing_fields(intent: str, filled_slots: Dict[str, Any]) -> List[str]:
    """
    Check which required fields are missing for an action intent.
    
    Args:
        intent: The intent name (e.g., 'send_email', 'raise_ticket')
        filled_slots: Dictionary of currently filled slots
        
    Returns:
        List of missing field names
    """
    # Map intent enum values to REQUIRED_FIELDS keys
    intent_mapping = {
        "email_action": "send_email",
        "faculty_contact": "send_email",
        "ticket_create": "raise_ticket",
        "issue_description": "raise_ticket",
        "sensitive_complaint": "raise_ticket"
    }
    
    mapped_intent = intent_mapping.get(intent, intent)
    required = REQUIRED_FIELDS.get(mapped_intent, [])
    
    missing = []
    for field in required:
        # Check various possible slot names for each field
        if field == "recipient":
            # Recipient can be faculty (resolved_faculty) or external email
            has_faculty = filled_slots.get("resolved_faculty") or filled_slots.get("faculty_name")
            has_email = filled_slots.get("recipient_email")
            if not has_faculty and not has_email:
                missing.append(field)
        elif field == "contact_type":
            if not filled_slots.get("email_type") and not filled_slots.get("contact_type"):
                missing.append(field)
        elif field == "purpose":
            if not filled_slots.get("purpose") and not filled_slots.get("body"):
                missing.append(field)
        elif field == "category":
            if not filled_slots.get("category"):
                missing.append(field)
        elif field == "description":
            if not filled_slots.get("description"):
                missing.append(field)
        else:
            if field not in filled_slots or not filled_slots[field]:
                missing.append(field)
    
    return missing


def get_next_missing_field_prompt(intent: str, missing_fields: List[str], filled_slots: Dict[str, Any]) -> str:
    """
    Get the prompt for the next missing field (ask ONE at a time).
    
    Returns:
        Prompt string for the first missing field
    """
    if not missing_fields:
        return None
    
    next_field = missing_fields[0]
    
    prompts = {
        "contact_type": (
            "📧 **Email Assistant**\n\n"
            "Who would you like to send an email to?\n\n"
            "1️⃣ **Faculty Member** - I'll search our faculty database\n"
            "2️⃣ **External Contact** (friend, classmate, etc.)\n\n"
            "Please reply with **1** or **2**:"
        ),
        "recipient": (
            "Please provide the **recipient's email address**:"
            if filled_slots.get("email_type") == "external" or filled_slots.get("contact_type") == "external"
            else "Which **faculty member** would you like to email?\n\nPlease provide their name (e.g., 'Dr. Sharma', 'Prof. Kumar'):"
        ),
        "purpose": (
            "What would you like to say in your email?\n\n"
            "Please describe the purpose or message:"
        ),
        "category": (
            "📋 **Support Ticket**\n\n"
            "Please select a category for your ticket:\n\n"
            + "\n".join([f"{i+1}. {cat}" for i, cat in enumerate(list(CATEGORIES.keys()))])
        ),
        "description": (
            "Please describe your issue in detail:"
        )
    }
    
    return prompts.get(next_field, f"Please provide the {next_field}:")


# =============================================================================
# ORCHESTRATOR AGENT CLASS
# =============================================================================

class OrchestratorAgent:
    """
    Production-grade orchestrator implementing 12-step agentic pipeline.
    
    Pipeline Steps:
    1. Receive message
    2. Intent classification (with confidence)
    3. User role identification
    4. Entity extraction
    5. Ambiguity detection
    6. Self-resolution check
    7. Confirmation requirement check
    8. Execution plan creation
    9. Execute agent
    10. Output validation
    11. Policy compliance
    12. Response + memory update
    """
    
    def __init__(self):
        """Initialize orchestrator with LLM and agents"""
        # Initialize LLM for classification
        self.llm = ChatGroq(
            api_key=GROQ_API_KEY,
            model_name="llama-3.1-8b-instant",
            temperature=0.2
        )
        
        # Initialize downstream agents (REUSED - no modifications)
        self.faq_agent = FAQAgent()
        self.email_agent = EmailAgent()
        self.ticket_agent = TicketAgent()
        self.faculty_db = FacultyDatabase()
        
        # Initialize services
        self.history_rag = get_history_rag_service()
        self.chat_memory = get_chat_memory()
        self.data_access = get_agent_data_access()
        
        # Build LangGraph
        self.graph = self._build_graph()
        
        print("[OK] Orchestrator Agent initialized with 12-step pipeline")
    
    # =========================================================================
    # LANGGRAPH CONSTRUCTION
    # =========================================================================
    
    def _build_graph(self) -> StateGraph:
        """Build the 12-step LangGraph state machine"""
        workflow = StateGraph(AgentState)
        
        # Add nodes for each pipeline step
        workflow.add_node("classify_intent", self._node_classify_intent)
        workflow.add_node("identify_role", self._node_identify_role)
        workflow.add_node("extract_entities", self._node_extract_entities)
        workflow.add_node("detect_ambiguity", self._node_detect_ambiguity)
        workflow.add_node("check_self_resolution", self._node_check_self_resolution)
        workflow.add_node("check_confirmation", self._node_check_confirmation)
        workflow.add_node("create_execution_plan", self._node_create_execution_plan)
        workflow.add_node("execute_agent", self._node_execute_agent)
        workflow.add_node("validate_output", self._node_validate_output)
        workflow.add_node("generate_response", self._node_generate_response)
        workflow.add_node("clarify", self._node_clarify)
        workflow.add_node("handle_faculty_flow", self._node_handle_faculty_flow)
        workflow.add_node("handle_ticket_flow", self._node_handle_ticket_flow)
        
        # Set entry point
        workflow.set_entry_point("classify_intent")
        
        # Define edges
        workflow.add_edge("classify_intent", "identify_role")
        workflow.add_edge("identify_role", "extract_entities")
        workflow.add_edge("extract_entities", "detect_ambiguity")
        
        # Conditional: ambiguity detection
        workflow.add_conditional_edges(
            "detect_ambiguity",
            self._route_after_ambiguity,
            {
                "clarify": "clarify",
                "check_self_resolution": "check_self_resolution"
            }
        )
        
        # Conditional: self-resolution check
        workflow.add_conditional_edges(
            "check_self_resolution",
            self._route_after_self_resolution,
            {
                "execute_agent": "execute_agent",  # ADDED: For FAQ and History agents
                "generate_response": "generate_response",
                "check_confirmation": "check_confirmation",
                "handle_faculty_flow": "handle_faculty_flow",
                "handle_ticket_flow": "handle_ticket_flow"
            }
        )
        
        # Conditional: confirmation check
        workflow.add_conditional_edges(
            "check_confirmation",
            self._route_after_confirmation_check,
            {
                "generate_response": "generate_response",
                "create_execution_plan": "create_execution_plan"
            }
        )
        
        workflow.add_edge("create_execution_plan", "execute_agent")
        workflow.add_edge("execute_agent", "validate_output")
        workflow.add_edge("validate_output", "generate_response")
        
        # Terminal edges
        workflow.add_edge("clarify", END)
        workflow.add_edge("generate_response", END)
        workflow.add_edge("handle_faculty_flow", END)
        workflow.add_edge("handle_ticket_flow", END)
        
        return workflow.compile()
    
    # =========================================================================
    # ROUTING FUNCTIONS
    # =========================================================================
    
    def _route_after_ambiguity(self, state: AgentState) -> str:
        """Route after ambiguity detection"""
        if state.get("requires_clarification"):
            return "clarify"
        return "check_self_resolution"
    
    def _route_after_self_resolution(self, state: AgentState) -> str:
        """
        Route after self-resolution check.
        
        HIGH-LEVEL INTENT MAPPING:
        - FAQ: college_rag_query, academic_program_query → FAQ Agent
        - EMAIL: email_action → Email Agent
        - FACULTY: faculty_contact → Faculty Flow → Email Agent
        - TICKET: issue_description, ticket_create, sensitive_complaint → Ticket Agent
        """
        intent = state.get("intent_enum")
        
        print(f"[ROUTE] After self-resolution: intent={intent.value if intent else 'None'}")
        
        # =====================================================================
        # FAQ QUERIES → FAQ Agent (CRITICAL FIX)
        # Route to execute_agent to use FAQ agent with RAG search
        # =====================================================================
        if intent in [IntentType.COLLEGE_RAG_QUERY, IntentType.ACADEMIC_PROGRAM_QUERY]:
            state["selected_agent"] = "faq"
            state["force_rag"] = True
            print(f"[ROUTE] → FAQ Agent (execute_agent)")
            return "execute_agent"
        
        # =====================================================================
        # EMAIL/FACULTY QUERIES → Faculty Flow
        # =====================================================================
        if intent in [IntentType.FACULTY_CONTACT, IntentType.EMAIL_ACTION]:
            print(f"[ROUTE] → Faculty Flow (handle_faculty_flow)")
            return "handle_faculty_flow"
        
        # =====================================================================
        # TICKET QUERIES → Ticket Flow
        # =====================================================================
        if intent in [IntentType.ISSUE_DESCRIPTION, IntentType.TICKET_CREATE, 
                      IntentType.TICKET_STATUS, IntentType.TICKET_CLOSE,
                      IntentType.SENSITIVE_COMPLAINT]:
            print(f"[ROUTE] → Ticket Flow (handle_ticket_flow)")
            return "handle_ticket_flow"
        
        # =====================================================================
        # HISTORY RETRIEVAL → Execute Agent
        # =====================================================================
        if intent == IntentType.RETRIEVE_HISTORY:
            state["selected_agent"] = "history"
            print(f"[ROUTE] → History Agent (execute_agent)")
            return "execute_agent"
        
        # Default: check if confirmation needed
        print(f"[ROUTE] → Default (check_confirmation)")
        return "check_confirmation"
    
    def _route_after_confirmation_check(self, state: AgentState) -> str:
        """Route after confirmation check"""
        if state.get("confirmation_pending"):
            return "generate_response"
        return "create_execution_plan"
    
    # =========================================================================
    # NODE 1: INTENT CLASSIFICATION
    # =========================================================================
    
    # =========================================================================
    # HELPER: STATE MANAGEMENT
    # =========================================================================

    def _reset_flow_state(self, state: AgentState) -> None:
        """
        Aggressively clear all flow-related state to prevent artifacts from leaking.
        """
        print(f"[FLOW] 🧹 RESETTING FLOW STATE")
        state["active_flow"] = None
        state["contact_faculty_step"] = None
        state["ticket_step"] = None
        state["email_draft"] = None
        state["extracted_slots"] = {}
        state["pending_question"] = None
        state["expected_response_type"] = None
        state["faculty_matches"] = None
        state["resolved_faculty"] = None
        state["confirmation_pending"] = False
        state["confirmation_data"] = None
        state["clarification_context"] = {}

    def _is_intent_compatible(self, new_intent: IntentType, active_flow: str) -> bool:
        """Check if the new intent is compatible with the active flow (continuation)."""
        if not active_flow:
            return True
            
        # Email flow compatibilities
        if active_flow in ["email", "contact_faculty"]:
            return new_intent in [
                IntentType.EMAIL_ACTION, 
                IntentType.FACULTY_CONTACT, 
                IntentType.GENERAL_CHAT, # "yes", "ok" often classified as general
                IntentType.UNKNOWN,       # unambiguous input often unknown
                # Allow these because LLM often misclassifies purpose text as FAQ/Ticket
                IntentType.COLLEGE_RAG_QUERY,
                IntentType.ACADEMIC_PROGRAM_QUERY,
                IntentType.TICKET_CREATE
            ]
            
        # Ticket flow compatibilities
        if active_flow == "ticket":
            return new_intent in [
                IntentType.TICKET_CREATE, 
                IntentType.ISSUE_DESCRIPTION,
                IntentType.GENERAL_CHAT,
                IntentType.UNKNOWN
            ]
            
        return False

    # =========================================================================
    # NODE 1: INTENT CLASSIFICATION
    # =========================================================================
    
    def _node_classify_intent(self, state: AgentState) -> AgentState:
        """Classify user intent with confidence score using LangChain"""
        user_message = state["user_message"]
        # Import re locally to fix Python 3.14 scoping issue in generator expressions
        import re as re_module
        
        mode = state.get("mode", "auto")
        msg_lower = user_message.lower().strip()
        
        print(f"[PIPELINE][1] Intent Classification: '{user_message[:50]}...'")

        # 1. ALWAYS classify the intent first (Re-evaluation)
        # We need to know what the user wants NOW, regardless of previous state
        intent_result = self._llm_classify_intent(user_message)
        new_intent = intent_result.intent
        confidence = intent_result.confidence
        
        print(f"[INTENT] Classified: {new_intent.value} (conf={confidence:.2f})")

        # 2. Check for manual "Game Changers" (Cancel, Stop)
        # These keywords immediately kill any active flow
        CANCEL_KEYWORDS = ["cancel", "stop", "abort", "forget it", "never mind", "quit", "exit"]
        is_cancel = any(kw in msg_lower for kw in CANCEL_KEYWORDS) and len(msg_lower) < 20

        active_flow = state.get("active_flow")
        
        # 3. Decision Logic: Continue Flow vs. Switch Intent
        if active_flow:
            # A. User wants to cancel
            if is_cancel:
                print(f"[FLOW] Cancellation detected - resetting {active_flow}")
                self._reset_flow_state(state)
                state["intent"] = IntentType.GENERAL_CHAT.value
                state["intent_enum"] = IntentType.GENERAL_CHAT
                state["final_response"] = "Action cancelled. How else can I help?"
                return state

            # B. Complaint Priority (Critical Fix)
            # If user has a complaint, it MUST override email flow
            # BUT: Do NOT override if we are waiting for email purpose text —
            # "ask for 2 day leave" gets misclassified as TICKET_CREATE
            is_complaint = new_intent in [IntentType.TICKET_CREATE, IntentType.SENSITIVE_COMPLAINT] and confidence > 0.7
            is_awaiting_email_input = state.get("expected_response_type") in [
                "email_purpose", "faculty_name", "faculty_selection",
                "email_confirmation", "recipient_email", "recipient_name",
                "editing_subject", "editing_body", "editing_recipient_email"
            ]
            if is_complaint and active_flow != "ticket" and not is_awaiting_email_input:
                 print(f"[FLOW] 🚨 Complaint detected during {active_flow} flow - FORCED SWITCH to ticket")
                 self._reset_flow_state(state)
                 # Fall through to standard handling below to set up ticket intent
            elif is_complaint and is_awaiting_email_input:
                 print(f"[FLOW] Ticket intent detected but suppressed — email flow is awaiting '{state.get('expected_response_type')}'")

            # C. Strong Intent Switch
            # If new intent is High Confidence AND Incompatible with current flow -> Reset
            # BUT: Protect against short numeric inputs (e.g. "1", "2") or very short phrases
            # getting misclassified as unrelated intents during an active flow.
            is_short_input = len(msg_lower) < 5 or (len(msg_lower) < 10 and msg_lower.replace(".","").isdigit())
            
            if confidence > 0.85 and not self._is_intent_compatible(new_intent, active_flow) and not state.get("expected_response_type") and not is_short_input:
                 print(f"[FLOW] Strong intent switch detected ({new_intent.value}) - resetting {active_flow}")
                 self._reset_flow_state(state)
                 # Fall through to standard handling
            
            # D. Otherwise, assume Flow Continuation
            else:
                print(f"[FLOW] Continuing active flow: {active_flow}")
                
                # ... Restore original Flow Logic ...
                # Use the existing step-based logic for continuity
                contact_step = state.get("contact_faculty_step")
                ticket_step = state.get("ticket_step")
                current_step = contact_step if active_flow in ["email", "contact_faculty"] else ticket_step
                
                # Derive expected_response_type from step (SINGLE SOURCE OF TRUTH)
                # Map flow steps to their expected response types
                step_to_expected_type = {
                    # Email/Faculty flow steps
                    "awaiting_type_selection": "email_type_selection",
                    "awaiting_recipient_email": "recipient_email",
                    "awaiting_recipient_name": "recipient_name",
                    "awaiting_faculty": "faculty_name",
                    "awaiting_selection": "faculty_selection",
                    "awaiting_purpose": "email_purpose",
                    "preview": "email_confirmation",
                    "editing_subject": "editing_subject",
                    "editing_body": "editing_body",
                    "editing_recipient_email": "editing_recipient_email",
                    # Ticket flow steps
                    "awaiting_category": "category_selection",
                    "awaiting_description": None,
                    "awaiting_confirmation": "ticket_confirmation"
                }
                
                 # Also map expected types to slots
                response_type_to_slot = {
                    "email_type_selection": "email_type",
                    "recipient_email": "recipient_email",
                    "recipient_name": "recipient_name",
                    "faculty_name": "faculty_name",
                    "faculty_selection": "resolved_faculty",
                    "email_purpose": "purpose",
                    "email_confirmation": "email_action",
                    "editing_subject": "editing_subject",
                    "editing_body": "editing_body",
                    "editing_recipient_email": "editing_recipient_email",
                    "category_selection": "category",
                    "ticket_confirmation": "confirmed",
                    "sensitive_confirmation": "confirmed"
                }

                derived_expected_type = step_to_expected_type.get(current_step)
                
                # Check sensitive complaint special case
                stored_expected_type = state.get("expected_response_type")
                if active_flow == "sensitive_complaint" and stored_expected_type == "sensitive_confirmation":
                     derived_expected_type = "sensitive_confirmation"

                if derived_expected_type:
                    # Sync expected type
                    state["expected_response_type"] = derived_expected_type
                    
                    # Check if slot is already filled
                    slot_name = response_type_to_slot.get(derived_expected_type, derived_expected_type)
                    extracted_slots = state.get("extracted_slots", {})
                    
                    if slot_name in extracted_slots and extracted_slots[slot_name]:
                        print(f"[FLOW] Slot '{slot_name}' already filled - proceeding")
                        state["expected_response_type"] = None
                    else:
                        print(f"[FLOW] Handing over to follow-up handler for {derived_expected_type}")
                        return self._handle_followup_response(state)
                
                # If no expected type, or slot filled, we continue. 
                # BUT we must ensure 'intent' is NOT overwritten by the LLM result if we are continuing flow
                # Re-assign the active intent? No, just return state with current intent?
                # Actually, the loop will call the next node based on active flow.
                # Just return strict state.
                return state

        # 4. Standard Classification Handling (No Active Flow OR Reset Triggered)
        state["intent"] = new_intent.value
        state["intent_enum"] = new_intent
        state["confidence"] = confidence
        state["is_multi_intent"] = intent_result.is_multi_intent
        state["secondary_intent"] = intent_result.secondary_intent.value if intent_result.secondary_intent else None
        state["reasoning"] = intent_result.reasoning

        # CAPABILITY QUESTION DETECTION (BLOCKS ACTION INTENT - HIGHEST PRIORITY)
        # Must come BEFORE email/ticket intent detection to intercept capability questions
        # These are informational queries about what the bot CAN do, not action requests
        capability_patterns = [
            r"can you (send|email|contact|raise|create|help)",
            r"do you (send|email|contact|raise|create)",
            r"are you (able|capable)",
            r"what can you do",
            r"how do i (send|contact|raise)"
        ]
        
        is_capability_question = any(re_module.search(pattern, msg_lower) for pattern in capability_patterns)
        
        if is_capability_question and confidence > 0.8: # Only if LLM also thinks it's action/general
            # Double check: is it a specific request?
            # "Can you send email to X" -> Action
            # "Can you send emails?" -> Capability
            # "Can you send emails to faculty" -> Capability (vague target)
            has_specific_target = any(word in msg_lower for word in [" to @", ".com", ".in", " to dr", " to prof"])
            has_vague_target = any(word in msg_lower for word in ["to faculty", "to professor", "to teacher", "emails?", "tickets?"])
            
            # It's a capability question if no specific target OR has vague/plural target
            if not has_specific_target or has_vague_target:
                print(f"[INTENT] Capability question detected - providing guidance")
                state["intent"] = IntentType.GENERAL_CHAT.value
                state["intent_enum"] = IntentType.GENERAL_CHAT
                state["confidence"] = 0.95
                state["reasoning"] = "Capability question - user asking about features"
                state["requires_clarification"] = False

        return state
    def _llm_classify_intent(self, user_message: str) -> IntentResult:
        """Use LangChain for structured intent classification with improved prompt"""
        
        classification_prompt = ChatPromptTemplate.from_template("""
You are an intent classifier for a college student support system.

Classify the user message into ONE of these intents:

**INFORMATIONAL INTENTS (FAQ):**
- college_rag_query: Questions about college (courses, founder, policies, fees, facilities, departments, rules)
- academic_program_query: Questions about specific programs, branches, seats, intake

**ACTION INTENTS:**
- email_action: Wants to send an email (may not specify recipient yet)
- faculty_contact: Wants to contact/email a specific faculty member
- ticket_create: EXPLICIT request to raise/create a ticket or complaint
- ticket_status: Asking about existing ticket status or history
- ticket_close: Wants to close a ticket

**PROBLEM INTENTS:**
- issue_description: User describing a problem (NOT explicitly asking to raise ticket)

**OTHER:**
- retrieve_history: Asking about past tickets, emails, or conversations
- general_chat: General greeting, thanks, or off-topic conversation
- unknown: Cannot determine intent with reasonable confidence

🚨 CRITICAL RULES FOR FAQ vs TICKET DISTINCTION:

1. **INFORMATIONAL QUESTIONS = FAQ** (NOT ticket)
   - "What courses are offered?" → college_rag_query
   - "Who is the founder of ACE?" → college_rag_query
   - "Could you explain ACE founder?" → college_rag_query
   - "Any info on courses?" → college_rag_query
   - "Details about placements?" → college_rag_query
   - "What are the attendance rules?" → college_rag_query
   - "Tell me about fees" → college_rag_query

2. **PROBLEM DESCRIPTION = issue_description** (NOT ticket_create)
   - "My WiFi is not working" → issue_description
   - "I have a problem with hostel" → issue_description
   - "The library is closed" → issue_description

3. **EXPLICIT TICKET REQUEST = ticket_create** (ONLY these)
   - "Raise a ticket" → ticket_create
   - "Create a complaint" → ticket_create
   - "I want to file a complaint" → ticket_create
   - "Submit a ticket about WiFi" → ticket_create

4. **EMAIL/FACULTY = Separate intents**
   - "Contact professor Kumar" → faculty_contact
   - "Send an email" → email_action

CONFIDENCE CALIBRATION:
- 0.9-1.0: Extremely clear intent with explicit keywords
- 0.7-0.9: Clear intent, unambiguous
- 0.5-0.7: Probable intent, some ambiguity
- 0.3-0.5: Uncertain, multiple possible intents
- 0.0-0.3: Cannot determine intent

EXAMPLES:
- "What are all the courses offered?" → college_rag_query (confidence: 0.95)
- "Who is the founder of ACE?" → college_rag_query (confidence: 0.92)
- "Could you explain ACE founder?" → college_rag_query (confidence: 0.88)
- "My WiFi is not working" → issue_description (confidence: 0.85)
- "I want to raise a ticket about WiFi" → ticket_create (confidence: 0.95)
- "Can you help me contact my professor?" → faculty_contact (confidence: 0.85)

**PLACEMENT & SALARY QUERIES** (These are FAQ, NOT tickets):
- "What is the highest package?" → college_rag_query (confidence: 0.95)
- "highest salary" → college_rag_query (confidence: 0.92)
- "average package" → college_rag_query (confidence: 0.93)
- "placement statistics" → college_rag_query (confidence: 0.94)
- "which companies recruit?" → college_rag_query (confidence: 0.90)
- "tell me about placements" → college_rag_query (confidence: 0.92)

**COMPARATIVE QUERIES** (These are analytical FAQ questions):
- "which department has more students?" → college_rag_query (confidence: 0.88)
- "which department has the most capacity?" → college_rag_query (confidence: 0.88)
- "which has least capacity?" → college_rag_query (confidence: 0.85)
- "which branch has highest intake?" → college_rag_query (confidence: 0.87)

**CAPABILITY QUESTIONS** (These are general_chat, NOT actions):
- "Can you send emails?" → general_chat (confidence: 0.95)
- "Can you raise a ticket?" → general_chat (confidence: 0.95)
- "Do you send emails?" → general_chat (confidence: 0.92)
- "Are you able to contact faculty?" → general_chat (confidence: 0.90)
- "Can you help me?" → general_chat (confidence: 0.85)

vs

**ACTION REQUESTS** (These are actions, NOT capability questions):
- "Send an email to Dr. Kumar" → email_action (confidence: 0.95)
- "I want to raise a ticket" → ticket_create (confidence: 0.95)
- "Email my friend John" → email_action (confidence: 0.90)
- "Raise a ticket about WiFi" → ticket_create (confidence: 0.92)

**OTHER EXAMPLES**:
- "I want to send an email" → email_action (confidence: 0.80)
- "I need help" → unknown (confidence: 0.25) - too vague
- "Hello" → general_chat (confidence: 0.95)

User message: {message}

Respond in JSON:
{{
    "intent": "intent_name",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation",
    "is_multi_intent": false,
    "secondary_intent": null
}}
""")
        
        try:
            chain = classification_prompt | self.llm | JsonOutputParser()
            result = chain.invoke({"message": user_message})
            
            intent_str = result.get("intent", "unknown")
            try:
                intent = IntentType(intent_str)
            except ValueError:
                intent = IntentType.UNKNOWN
            
            return IntentResult(
                intent=intent,
                confidence=float(result.get("confidence", 0.5)),
                reasoning=result.get("reasoning", ""),
                is_multi_intent=result.get("is_multi_intent", False),
                secondary_intent=IntentType(result["secondary_intent"]) if result.get("secondary_intent") else None
            )
        except Exception as e:
            print(f"[PIPELINE][1] Classification error: {e}")
            return IntentResult(
                intent=IntentType.UNKNOWN,
                confidence=0.0,
                reasoning=f"Classification failed: {str(e)}"
            )
    
    # =========================================================================
    # MISSING NODE METHODS (FIX: Prevent runtime crashes)
    # =========================================================================
    
    def _node_identify_role(self, state: AgentState) -> AgentState:
        """Identify user role - currently just passes through"""
        print(f"[PIPELINE][2] Role Identification: {state.get('user_role', 'student')}")
        # Role is already set from student_profile or defaults to 'student'
        return state
    
    def _node_extract_entities(self, state: AgentState) -> AgentState:
        """Extract entities from user message - currently just passes through"""
        print(f"[PIPELINE][3] Entity Extraction: {state.get('entities', {})}")
        # Entities are extracted during intent classification
        return state
    
    def _node_detect_ambiguity(self, state: AgentState) -> AgentState:
        """
        Detect if intent is ambiguous and requires clarification.
        
        DEFENSIVE FALLBACK: If CONFIDENCE_THRESHOLD is not defined, uses 0.7 as default.
        This prevents NameError crashes in the LangGraph pipeline.
        """
        print(f"[PIPELINE][4] Ambiguity Detection")
        
        # Defensive fallback for CONFIDENCE_THRESHOLD
        try:
            threshold = CONFIDENCE_THRESHOLD
        except NameError:
            print(f"[PIPELINE][4] WARNING: CONFIDENCE_THRESHOLD not defined, using default 0.7")
            threshold = 0.7
        
        confidence = state.get("confidence", 0.0)
        intent = state.get("intent_enum")
        
        print(f"[PIPELINE][4] Confidence: {confidence:.2f}, Threshold: {threshold}")
        
        # Check if clarification is needed
        if confidence < threshold and intent not in [IntentType.GENERAL_CHAT, IntentType.UNKNOWN]:
            print(f"[PIPELINE][4] Low confidence detected - marking for clarification")
            state["requires_clarification"] = True
            
            # Generate clarification question
            intent_result = IntentResult(
                intent=intent,
                confidence=confidence,
                reasoning=state.get("reasoning", "")
            )
            state["clarification_question"] = self._generate_clarification_question(
                intent_result,
                state["user_message"]
            )
        else:
            print(f"[PIPELINE][4] Confidence sufficient - no clarification needed")
            state["requires_clarification"] = False
        
        return state
    
    def _generate_clarification_question(self, intent_result: IntentResult, user_message: str) -> str:
        """Generate contextual clarification question based on low-confidence intent"""
        
        # If intent is completely unknown
        if intent_result.intent == IntentType.UNKNOWN or intent_result.confidence < 0.3:
            return (
                "I'd like to help you! Could you please clarify what you need?\n\n"
                "I can help you with:\n"
                "• **College information** (policies, fees, courses)\n"
                "• **Raising a support ticket** for issues\n"
                "• **Contacting faculty members**\n"
                "• **Checking ticket status**\n\n"
                "What would you like to do?"
            )
        
        # If we have a guess but low confidence, ask for confirmation
        intent_confirmations = {
            IntentType.ISSUE_DESCRIPTION: (
                "It sounds like you're experiencing an issue. "
                "Would you like me to:\n"
                "1. **Help you resolve it** (I'll suggest solutions)\n"
                "2. **Raise a support ticket** for you\n"
                "3. **Contact a faculty member** about this\n\n"
                "Please choose an option or tell me more."
            ),
            IntentType.EMAIL_ACTION: (
                "I can help you send an email! "
                "Are you trying to:\n"
                "1. **Contact a faculty member**\n"
                "2. **Send a general email**\n\n"
                "Please let me know who you'd like to contact."
            ),
            IntentType.FACULTY_CONTACT: (
                "I can help you contact a faculty member. "
                "Could you please tell me:\n"
                "• **Which faculty member** you'd like to contact?\n"
                "• **What you'd like to discuss** with them?"
            ),
            IntentType.TICKET_CREATE: (
                "I can help you raise a support ticket. "
                "Could you please describe the issue you're facing in more detail?"
            ),
            IntentType.COLLEGE_RAG_QUERY: (
                "I can help you with college information. "
                "Could you be more specific about what you'd like to know?\n\n"
                "For example:\n"
                "• Attendance policies\n"
                "• Fee structure\n"
                "• Course details\n"
                "• Exam schedules"
            )
        }
        
        return intent_confirmations.get(
            intent_result.intent,
            "I'm not quite sure I understand. Could you please rephrase or provide more details?"
        )
    
    # =========================================================================
    # FOLLOW-UP RESPONSE HANDLING (CRITICAL FIX)
    # =========================================================================
    
    def _handle_followup_response(self, state: AgentState) -> AgentState:
        """
        Handles user replies when the system is waiting for a specific response.
        This MUST bypass intent classification to maintain flow determinism.
        
        This is called when expected_response_type is set, indicating the system
        is waiting for a specific type of response from the user.
        """
        expected_type = state.get("expected_response_type")
        user_message = state["user_message"]
        active_flow = state.get("active_flow")
        
        print(f"[FLOW] Handling follow-up response")
        print(f"[FLOW] Expected type: {expected_type}")
        print(f"[FLOW] Active flow: {active_flow}")
        print(f"[FLOW] User message: {user_message[:100]}")
        
        # Validate the user's response
        is_valid, extracted_value = self._validate_user_response(expected_type, user_message, state)
        
        if is_valid:
            print(f"[FLOW] Validation SUCCESS: {expected_type} = {extracted_value}")
            
            # Update extracted slots
            slots = state.get("extracted_slots", {})
            
            # Map expected_response_type to slot name
            slot_mapping = {
                "faculty_name": "faculty_name",
                "category_selection": "category",
                "email_purpose": "purpose",
                "ticket_confirmation": "confirmed",
                "sensitive_confirmation": "confirmed",
                "clarification_choice": "clarification_choice",
                # Email flow slot mappings
                "email_type_selection": "email_type",
                "recipient_email": "recipient_email",
                "recipient_name": "recipient_name",
                "faculty_selection": "resolved_faculty",
                "email_confirmation": "email_action"
            }
            
            slot_name = slot_mapping.get(expected_type, expected_type)
            if extracted_value is not None:
                slots[slot_name] = extracted_value
                state["extracted_slots"] = slots
                print(f"[FLOW] Slot filled: {slot_name} = {extracted_value}")
            
            # Increment conversation turn counter
            conv_state = state.get("conversation_state", {})
            if isinstance(conv_state, dict):
                conv_state["turns_in_current_flow"] = conv_state.get("turns_in_current_flow", 0) + 1
                state["conversation_state"] = conv_state
            
            # Clear pending state (ONLY on success)
            state["pending_question"] = None
            state["expected_response_type"] = None
            
            # CRITICAL FIX: Advance email flow step based on completed expected_type
            if active_flow in ["email", "contact_faculty"]:
                flow_step_advancement = {
                    "email_type_selection": (
                        "awaiting_faculty" if extracted_value == "faculty"
                        else "awaiting_purpose" if extracted_value == "external_with_email"
                        else "awaiting_recipient_email"
                    ),
                    "recipient_email": "awaiting_recipient_name",
                    "recipient_name": "awaiting_purpose",
                    "faculty_name": "awaiting_faculty",  # Re-enter faculty flow for search
                    "faculty_selection": "awaiting_purpose",
                    "email_purpose": "preview",
                    "email_confirmation": None,  # Handled separately in flow
                    "editing_subject": "preview",  # Return to preview after edit
                    "editing_body": "preview",
                    "editing_recipient_email": "preview",
                }
                next_step = flow_step_advancement.get(expected_type)
                if next_step:
                    state["contact_faculty_step"] = next_step
                    # If external_with_email, also update active_flow
                    if extracted_value == "external_with_email":
                        state["active_flow"] = "email"
                        slots = state.get("extracted_slots", {})
                        slots["email_type"] = "external"
                        state["extracted_slots"] = slots
                    print(f"[FLOW] Advanced step to: {next_step}")
            
            # Continue the active flow
            if active_flow:
                print(f"[FLOW] Advancing flow: {active_flow}")
                return self._continue_active_flow(state)
            else:
                # No active flow - this shouldn't happen, but handle gracefully
                print(f"[FLOW] WARNING: No active flow set, proceeding with normal classification")
                state["intent"] = IntentType.GENERAL_CHAT.value
                state["intent_enum"] = IntentType.GENERAL_CHAT
                state["confidence"] = 0.5
                return state
        
        else:
            # Validation failed - re-ask the question
            print(f"[FLOW] Validation FAILED for {expected_type}")
            
            # Track retry count
            retry_count = state.get("clarification_context", {}).get("retry_count", 0) + 1
            clarification_context = state.get("clarification_context", {})
            clarification_context["retry_count"] = retry_count
            state["clarification_context"] = clarification_context
            
            print(f"[FLOW] Retry {retry_count}/3")
            
            if retry_count >= 3:
                # Max retries reached - cancel flow
                print(f"[FLOW] Max retries reached, cancelling flow")
                state["active_flow"] = None
                state["expected_response_type"] = None
                state["pending_question"] = None
                state["extracted_slots"] = {}
                state["final_response"] = (
                    "I'm having trouble understanding your response. "
                    "Let's start over. How can I help you today?"
                )
                state["selected_agent"] = "orchestrator"
                return state
            
            # Re-ask with examples
            state["final_response"] = self._generate_retry_message(expected_type, user_message, state)
            state["selected_agent"] = "orchestrator"
            # Keep expected_response_type and pending_question for next attempt
            return state
    
    def _validate_user_response(
        self,
        expected_type: str,
        user_message: str,
        state: AgentState
    ) -> tuple[bool, any]:
        """
        Centralized validator for user responses based on expected_response_type.
        
        Returns:
            (True, extracted_value) if valid
            (False, None) if invalid
        """
        msg_lower = user_message.lower().strip()
        
        # Faculty name validation — accept any text >= 2 chars
        # The actual DB search happens downstream in _node_handle_faculty_flow
        if expected_type == "faculty_name":
            if len(user_message.strip()) >= 2:
                return (True, user_message.strip())
            return (False, None)
        
        # Category selection validation
        elif expected_type == "category_selection":
            from .ticket_config import CATEGORIES
            categories = list(CATEGORIES.keys())
            
            # Try numeric selection
            if msg_lower.replace(".", "").isdigit():
                try:
                    idx = int(msg_lower.replace(".", "")) - 1
                    if 0 <= idx < len(categories):
                        return (True, categories[idx])
                except:
                    pass
            
            # Try text matching
            for cat in categories:
                if cat.lower() in msg_lower or msg_lower in cat.lower():
                    return (True, cat)
            
            return (False, None)
        
        # Confirmation validation (yes/no)
        elif expected_type == "confirmation":
            if msg_lower in ["yes", "y", "confirm", "ok", "okay", "sure"]:
                return (True, True)
            elif msg_lower in ["no", "n", "cancel", "nope"]:
                return (True, False)
            return (False, None)
        
        # Ticket confirmation validation (explicit submit)
        elif expected_type == "ticket_confirmation":
            if msg_lower in ["submit", "yes", "confirm", "create"]:
                return (True, True)
            elif msg_lower in ["edit", "change", "modify"]:
                return (True, "edit")
            elif msg_lower in ["cancel", "abort", "stop"]:
                return (True, "cancel")
            return (False, None)
        
        # Sensitive complaint confirmation
        elif expected_type == "sensitive_confirmation":
            if msg_lower in ["yes", "confirm", "proceed", "create", "submit"]:
                return (True, True)
            elif msg_lower in ["no", "cancel", "not now"]:
                return (True, False)
            return (False, None)
        
        # Email purpose validation
        elif expected_type == "email_purpose":
            if len(user_message.strip()) >= 5:  # At least 5 characters
                return (True, user_message.strip())
            return (False, None)
        
        # Clarification choice validation
        elif expected_type == "clarification_choice":
            if any(word in msg_lower for word in ["faq", "question", "information", "know"]):
                return (True, "faq")
            elif any(word in msg_lower for word in ["ticket", "issue", "problem", "complaint"]):
                return (True, "ticket")
            elif any(word in msg_lower for word in ["faculty", "professor", "teacher", "contact", "email"]):
                return (True, "faculty")
            return (False, None)
        
        # EMAIL FLOW: Email type selection (1=faculty, 2=external)
        elif expected_type == "email_type_selection":
            if msg_lower in ["1", "faculty", "professor", "teacher"]:
                return (True, "faculty")
            elif msg_lower in ["2", "external", "friend", "other", "classmate"]:
                return (True, "external")
            
            # SMART DETECTION: Check if user provided a bare email address
            import re
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            email_match = re.search(email_pattern, user_message)
            if email_match:
                extracted_email = email_match.group(0).lower()
                # Store email in slots for immediate use
                slots = state.get("extracted_slots", {})
                slots["recipient_email"] = extracted_email
                state["extracted_slots"] = slots
                print(f"[FLOW] Email detected in type_selection reply: {extracted_email}")
                return (True, "external_with_email")
            
            # Try to detect faculty name directly
            result = self.faculty_db.search_faculty(name=user_message)
            if result.get("matches"):
                return (True, "faculty_name:" + user_message)
            return (False, None)
        
        # EMAIL FLOW: Recipient email validation
        elif expected_type == "recipient_email":
            import re
            # Use simple, permissive email regex (defined at module level)
            # First try the entire input as an email
            if re.match(EMAIL_REGEX, user_message.strip()):
                return (True, user_message.strip().lower())
            
            # Try to extract email from sentence (e.g., "send to john@gmail.com")
            email_extract_pattern = r'[^@\s]+@[^@\s]+\.[^@\s]+'
            match = re.search(email_extract_pattern, user_message)
            if match:
                extracted_email = match.group(0).lower()
                print(f"[FLOW] Extracted email from message: {extracted_email}")
                # Also try to extract purpose from the rest of the message
                purpose_match = re.search(r'(?:asking|about|regarding|for|to)\s+(.+)', user_message, re.IGNORECASE)
                if purpose_match:
                    state["extracted_slots"]["inferred_purpose"] = purpose_match.group(1).strip()
                    print(f"[FLOW] Also extracted inferred purpose: {state['extracted_slots']['inferred_purpose']}")
                return (True, extracted_email)
            return (False, None)
        
        # EMAIL FLOW: Recipient name validation
        elif expected_type == "recipient_name":
            if len(user_message.strip()) >= 2:  # At least 2 characters for a name
                return (True, user_message.strip().title())
            return (False, None)
        
        # EMAIL FLOW: Faculty selection from list
        elif expected_type == "faculty_selection":
            matches = state.get("faculty_matches") or []
            # Try numeric selection
            try:
                selection = int(msg_lower.replace(".", "").strip()) - 1
                if 0 <= selection < len(matches):
                    return (True, matches[selection])
            except ValueError:
                pass
            # Try matching by designation or department
            for m in matches:
                if msg_lower in m.get("designation", "").lower() or msg_lower in m.get("department", "").lower():
                    return (True, m)
            return (False, None)
        
        # EMAIL FLOW: Email confirmation (send/edit/cancel)
        elif expected_type == "email_confirmation":
            if msg_lower in ["send", "yes", "confirm", "ok", "send it"]:
                return (True, "send")
            elif msg_lower in ["edit subject", "change subject", "subject"]:
                return (True, "edit_subject")
            elif msg_lower in ["edit body", "change body", "body", "edit"]:
                return (True, "edit_body")
            elif msg_lower in ["edit email", "change email", "change recipient", "edit recipient"]:
                return (True, "edit_recipient_email")
            elif msg_lower in ["cancel", "abort", "stop", "no"]:
                return (True, "cancel")
            return (False, None)
        
        # EMAIL FLOW: Editing subject (accept any text)
        elif expected_type == "editing_subject":
            if len(user_message.strip()) >= 3:
                return (True, user_message.strip())
            return (False, None)
        
        # EMAIL FLOW: Editing body (accept any text)
        elif expected_type == "editing_body":
            if len(user_message.strip()) >= 5:
                return (True, user_message.strip())
            return (False, None)
        
        # EMAIL FLOW: Editing recipient email
        elif expected_type == "editing_recipient_email":
            import re
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            email_match = re.search(email_pattern, user_message)
            if email_match:
                return (True, email_match.group(0).lower())
            return (False, None)
        
        # Unknown expected type - fail validation
        print(f"[FLOW] WARNING: Unknown expected_response_type: {expected_type}")
        return (False, None)
    
    def _generate_retry_message(self, expected_type: str, user_message: str, state: AgentState) -> str:
        """Generate helpful retry message with examples when validation fails"""
        
        retry_messages = {
            "faculty_name": (
                "I couldn't find that faculty member. Please provide:\n"
                "• Full name (e.g., 'Dr. Kumar')\n"
                "• Department (e.g., 'Computer Science')\n"
                "• Or say 'cancel' to stop"
            ),
            "category_selection": (
                "Please select a valid category:\n"
                "• Reply with the **number** (e.g., '1' or '3')\n"
                "• Or reply with the **category name**\n"
                "• Or say 'cancel' to stop"
            ),
            "confirmation": (
                "Please reply with:\n"
                "• **'yes'** to confirm\n"
                "• **'no'** to decline"
            ),
            "ticket_confirmation": (
                "⚠️ **Please choose an action:**\n"
                "• Reply **'submit'** or **'yes'** to create this ticket\n"
                "• Reply **'edit'** to modify the ticket\n"
                "• Reply **'cancel'** to cancel"
            ),
            "sensitive_confirmation": (
                "I need a clear response to proceed.\n\n"
                "Would you like me to raise an urgent support ticket?\n"
                "Please reply **'yes'** to proceed or **'no'** to cancel."
            ),
            "email_purpose": (
                "Please describe the purpose of your email in a few words.\n"
                "For example: 'Request for project extension' or 'Query about exam schedule'"
            ),
            "clarification_choice": (
                "I can help you with:\n"
                "• **College information** (say 'faq' or 'information')\n"
                "• **Raising a support ticket** (say 'ticket' or 'issue')\n"
                "• **Contacting faculty** (say 'faculty' or 'contact')\n\n"
                "What would you like to do?"
            ),
            # EMAIL FLOW retry messages
            "email_type_selection": (
                "Please choose who to email:\n\n"
                "1️⃣ **Faculty Member** - I'll search our database\n"
                "2️⃣ **External Contact** (friend, classmate)\n\n"
                "Reply with **1** or **2**, or type the faculty member's name."
            ),
            "recipient_email": (
                "❌ That doesn't look like a valid email address.\n\n"
                "Please enter a valid email (e.g., john@gmail.com):\n"
                "Or say **'cancel'** to stop."
            ),
            "recipient_name": (
                "Please enter the recipient's name (at least 2 characters):\n"
                "This will be used in the email greeting."
            ),
            "faculty_selection": (
                "Please select a faculty member:\n"
                "• Enter the **number** (e.g., '1' or '2')\n"
                "• Or specify their **department/designation**\n"
                "• Or say **'cancel'** to stop."
            ),
            "email_confirmation": (
                "Please choose an option:\n\n"
                "• **Send** - Send this email\n"
                "• **Edit Subject** - Modify the subject line\n"
                "• **Edit Body** - Modify the email content\n"
                "• **Cancel** - Cancel this email"
            )
        }
        
        return retry_messages.get(
            expected_type,
            f"I didn't understand '{user_message}'. Please try again or say 'cancel' to stop."
        )
    
    def _continue_active_flow(self, state: AgentState) -> AgentState:
        """Continue an active flow without reclassification"""
        active_flow = state["active_flow"]
        user_message = state["user_message"].strip()
        msg_lower = user_message.lower()
        
        # Show correct step based on flow type
        flow_step = state.get("contact_faculty_step") if active_flow in ["email", "contact_faculty"] else state.get("ticket_step")
        print(f"[PIPELINE][1] Continuing active flow: {active_flow}, step: {flow_step}, slots: {list(state.get('extracted_slots', {}).keys())}")
        
        if active_flow == "contact_faculty":
            state["intent"] = IntentType.FACULTY_CONTACT.value
            state["intent_enum"] = IntentType.FACULTY_CONTACT
        elif active_flow == "email":
            # External email flow
            state["intent"] = IntentType.EMAIL_ACTION.value
            state["intent_enum"] = IntentType.EMAIL_ACTION
        elif active_flow == "ticket":
            state["intent"] = IntentType.TICKET_CREATE.value
            state["intent_enum"] = IntentType.TICKET_CREATE
            
            # Check if user is selecting a category
            ticket_step = state.get("ticket_step", "")
            if ticket_step == "awaiting_category":
                categories = list(CATEGORIES.keys())
                selected_category = None
                
                # Try numeric selection first (1-10)
                try:
                    # Strip any punctuation like "1." -> "1"
                    clean_msg = "".join(c for c in user_message if c.isdigit())
                    if clean_msg:
                        selection = int(clean_msg)
                        if 1 <= selection <= len(categories):
                            selected_category = categories[selection - 1]
                except (ValueError, UnboundLocalError):
                    # Not a number - try text matching
                    for cat in categories:
                        cat_lower = cat.lower()
                        # Exact match or substring match
                        if cat_lower == msg_lower or msg_lower in cat_lower or cat_lower in msg_lower:
                            selected_category = cat
                            break
                    
                    # Also try keyword matching
                    if not selected_category:
                        keyword_map = {
                            "academic": "Academic Support",
                            "exam": "Examinations",
                            "fee": "Fees & Finance",
                            "finance": "Fees & Finance",
                            "payment": "Fees & Finance",
                            "it": "IT Support",
                            "computer": "IT Support",
                            "wifi": "IT Support",
                            "internet": "IT Support",
                            "hostel": "Hostel & Transport",
                            "transport": "Hostel & Transport",
                            "bus": "Hostel & Transport",
                            "certificate": "Certificates",
                            "health": "Health & Counseling",
                            "counseling": "Health & Counseling",
                            "library": "Library",
                            "book": "Library",
                            "placement": "Placements & Internships",
                            "internship": "Placements & Internships",
                            "job": "Placements & Internships"
                        }
                        for keyword, cat in keyword_map.items():
                            if keyword in msg_lower:
                                selected_category = cat
                                break
                
                if selected_category:
                    slots = state.get("extracted_slots", {})
                    slots["category"] = selected_category
                    state["extracted_slots"] = slots
                    state["ticket_step"] = "preview"
                    print(f"[PIPELINE][1] Category selected: {selected_category}")
                else:
                    # Invalid - keep step as awaiting_category
                    print(f"[PIPELINE][1] Invalid category input: {user_message}")
                    
        elif active_flow == "email":
            state["intent"] = IntentType.EMAIL_ACTION.value
            state["intent_enum"] = IntentType.EMAIL_ACTION
        
        state["confidence"] = 1.0
        state["requires_clarification"] = False
        return state
    
    def _handle_manual_mode(self, state: AgentState, mode: str) -> AgentState:
        """Handle manual mode selection - initializes flow for the selected mode"""
        mode_mapping = {
            "email": IntentType.EMAIL_ACTION,
            "ticket": IntentType.TICKET_CREATE,
            "faculty": IntentType.FACULTY_CONTACT
        }
        state["intent_enum"] = mode_mapping.get(mode, IntentType.UNKNOWN)
        state["intent"] = state["intent_enum"].value
        state["confidence"] = 1.0
        
        # ENHANCEMENT: Initialize email flow when mode is explicitly selected
        if mode == "email":
            print(f"[MANUAL_MODE] Email mode selected - initializing email flow")
            state["active_flow"] = "email"
            state["contact_faculty_step"] = "init"
            state["extracted_slots"] = {}
        elif mode == "faculty":
            print(f"[MANUAL_MODE] Faculty mode selected - initializing faculty flow")
            state["active_flow"] = "contact_faculty"
            state["contact_faculty_step"] = "awaiting_faculty"
            state["extracted_slots"] = {"email_type": "faculty"}
        elif mode == "ticket":
            print(f"[MANUAL_MODE] Ticket mode selected - initializing ticket flow")
            state["active_flow"] = "ticket"
            state["ticket_step"] = "awaiting_category"
            state["extracted_slots"] = {}
        
        return state
    
    # =========================================================================
    # NODE 2: ROLE IDENTIFICATION
    # =========================================================================
    
    def _node_identify_role(self, state: AgentState) -> AgentState:
        """Identify user role from auth payload or database"""
        user_id = state["user_id"]
        
        # First: Check if role in student_profile (from auth payload)
        profile = state.get("student_profile", {})
        if profile and profile.get("role"):
            state["user_role"] = profile["role"]
            print(f"[PIPELINE][2] Role from auth: {state['user_role']}")
            return state
        
        # Fallback: Query database
        try:
            student = self.data_access.get_student_profile(user_id)
            if student:
                state["user_role"] = UserRole.STUDENT.value
            else:
                # Check faculty table
                faculty = self.faculty_db.search_faculty(name=user_id.split("@")[0])
                if faculty.get("matches"):
                    state["user_role"] = UserRole.FACULTY.value
                else:
                    state["user_role"] = UserRole.UNKNOWN.value
        except:
            state["user_role"] = UserRole.STUDENT.value  # Default
        
        print(f"[PIPELINE][2] Role: {state['user_role']}")
        return state
    
    # =========================================================================
    # NODE 3: ENTITY EXTRACTION
    # =========================================================================
    
    def _node_extract_entities(self, state: AgentState) -> AgentState:
        """Extract entities from user message"""
        user_message = state["user_message"]
        intent = state.get("intent_enum")
        
        entities = state.get("entities", {})
        
        # Extract ticket ID if mentioned
        ticket_match = re.search(r'#?(\d{6,})', user_message)
        if ticket_match:
            entities["ticket_id"] = ticket_match.group(1)
        
        # Extract faculty name patterns
        faculty_patterns = [
            r"(?:Dr\.?|Prof\.?|Mr\.?|Mrs\.?|Ms\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"([A-Z][a-z]+)\s+(?:ma'am|sir|madam)",
            r"(?:contact|email|message)\s+([A-Z][a-z]+)"
        ]
        for pattern in faculty_patterns:
            match = re.search(pattern, user_message, re.IGNORECASE)
            if match:
                entities["faculty_name"] = match.group(1)
                break
        
        # Extract category keywords for tickets
        if intent in [IntentType.ISSUE_DESCRIPTION, IntentType.TICKET_CREATE]:
            for category in CATEGORIES.keys():
                if category.lower() in user_message.lower():
                    entities["category"] = category
                    break
        
        state["entities"] = entities
        print(f"[PIPELINE][3] Entities: {list(entities.keys())}")
        return state
    
    # =========================================================================
    # NODE 4: AMBIGUITY DETECTION
    # =========================================================================
    
    def _node_detect_ambiguity(self, state: AgentState) -> AgentState:
        """Detect if clarification is needed"""
        confidence = state.get("confidence", 0.0)
        is_multi = state.get("is_multi_intent", False)
        intent = state.get("intent_enum")
        
        # Low confidence
        if confidence < CONFIDENCE_THRESHOLD:
            state["requires_clarification"] = True
            state["clarification_question"] = self._generate_clarification_question(state)
            print(f"[PIPELINE][4] Low confidence ({confidence:.2f}) - requesting clarification")
            return state
        
        # Multi-intent
        if is_multi:
            state["requires_clarification"] = True
            secondary = state.get("secondary_intent", "")
            state["clarification_question"] = (
                f"I noticed you might have multiple requests. "
                f"Let me help with '{intent.value}' first. Is that okay?"
            )
            print(f"[PIPELINE][4] Multi-intent detected - handling primary first")
        
        # Unknown intent
        if intent == IntentType.UNKNOWN:
            state["requires_clarification"] = True
            state["clarification_question"] = (
                "I'm not sure what you need help with. Could you please clarify if you want to:\n"
                "• Ask a question about college policies\n"
                "• Raise a support ticket\n"
                "• Contact a faculty member\n"
                "• Check your ticket status"
            )
        
        return state
    
    def _generate_clarification_question(self, state: AgentState) -> str:
        """Generate appropriate clarification question"""
        intent = state.get("intent_enum", IntentType.UNKNOWN)
        
        if intent == IntentType.ISSUE_DESCRIPTION:
            return "I understand you're facing an issue. Would you like me to:\n• Try to help resolve it now\n• Raise a support ticket for you"
        
        if intent == IntentType.FACULTY_CONTACT:
            return "Which faculty member would you like to contact? Please provide their name or department."
        
        return (
            "Could you please clarify what you'd like help with?\n"
            "• Ask about college policies/fees\n"
            "• Report an issue\n"
            "• Contact faculty\n"
            "• Check ticket status"
        )
    
    # =========================================================================
    # NODE 5: SELF-RESOLUTION CHECK
    # =========================================================================
    
    def _node_check_self_resolution(self, state: AgentState) -> AgentState:
        """Attempt self-resolution before escalation"""
        intent = state.get("intent_enum")
        user_message = state["user_message"]
        
        # Skip self-resolution for sensitive complaints
        if intent == IntentType.SENSITIVE_COMPLAINT:
            state["self_resolution_attempted"] = False
            print(f"[PIPELINE][5] Skipping self-resolution for sensitive complaint")
            return state
        
        # For issue_description, attempt self-resolution
        if intent == IntentType.ISSUE_DESCRIPTION:
            result = self._attempt_self_resolution(user_message, state)
            state["self_resolution_attempted"] = True
            state["self_resolution_response"] = result.response
            
            if result.resolved:
                state["final_response"] = result.response + (
                    "\n\nDid this resolve your issue? If not, I can help you raise a support ticket."
                )
                state["awaiting_resolution_feedback"] = True
            else:
                state["awaiting_resolution_feedback"] = False
            
            print(f"[PIPELINE][5] Self-resolution attempted: {result.resolved}")
            return state
        
        # RAG queries - always use database
        if intent in [IntentType.COLLEGE_RAG_QUERY, IntentType.ACADEMIC_PROGRAM_QUERY]:
            state["force_rag"] = True
            print(f"[PIPELINE][5] Forcing RAG for academic query")
        
        return state
    
    def _attempt_self_resolution(self, issue: str, state: AgentState) -> ResolutionResult:
        """Attempt to resolve issue using RAG + policies"""
        try:
            # Search for relevant policies
            response = self.faq_agent.process(
                user_query=issue,
                session_id=state.get("session_id"),
                user_id=state.get("user_id")
            )
            
            # Check if response contains useful information
            if response and len(response) > 50 and "not available" not in response.lower():
                return ResolutionResult(
                    resolved=True,
                    response=response,
                    policy_references=["college_rules.txt"]
                )
            
            return ResolutionResult(
                resolved=False,
                response="I couldn't find a specific policy for this issue.",
                needs_escalation=True
            )
        except Exception as e:
            print(f"[PIPELINE][5] Self-resolution error: {e}")
            return ResolutionResult(
                resolved=False,
                response="Unable to search policies at this time.",
                needs_escalation=True
            )
    
    # =========================================================================
    # NODE 6: CONFIRMATION CHECK
    # =========================================================================
    
    def _node_check_confirmation(self, state: AgentState) -> AgentState:
        """Check if action requires confirmation"""
        intent = state.get("intent_enum")
        
        # Actions requiring confirmation
        confirmation_required = [
            IntentType.EMAIL_ACTION,
            IntentType.FACULTY_CONTACT,
            IntentType.TICKET_CREATE
        ]
        
        if intent in confirmation_required:
            state["confirmation_pending"] = True
            print(f"[PIPELINE][6] Confirmation required for {intent.value}")
        
        return state
    
    # =========================================================================
    # NODE 7: EXECUTION PLAN
    # =========================================================================
    
    def _node_create_execution_plan(self, state: AgentState) -> AgentState:
        """Create explicit execution plan"""
        intent = state.get("intent_enum")
        
        plan_mapping = {
            IntentType.COLLEGE_RAG_QUERY: "faq_agent.process()",
            IntentType.ACADEMIC_PROGRAM_QUERY: "data_access.get_all_courses()",
            IntentType.TICKET_STATUS: "data_access.get_student_tickets()",
            IntentType.RETRIEVE_HISTORY: "data_access.get_recent_chat_history()",
            IntentType.GENERAL_CHAT: "llm.generate_response()"
        }
        
        state["execution_plan"] = plan_mapping.get(intent, "generate_response")
        state["selected_agent"] = intent.value if intent else "unknown"
        
        print(f"[PIPELINE][7] Plan: {state['execution_plan']}")
        return state
    
    # =========================================================================
    # NODE 8: EXECUTE AGENT
    # =========================================================================
    
    def _node_execute_agent(self, state: AgentState) -> AgentState:
        """Execute exactly one downstream agent"""
        intent = state.get("intent_enum")
        user_message = state["user_message"]
        user_id = state["user_id"]
        session_id = state.get("session_id", "")
        
        print(f"[PIPELINE][8] Executing agent for: {intent}")
        
        try:
            # =====================================================================
            # FAQ QUERIES - Use FAQ Agent with RAG (CRITICAL FIX)
            # Route both COLLEGE_RAG_QUERY and ACADEMIC_PROGRAM_QUERY to FAQ agent
            # =====================================================================
            if intent in [IntentType.COLLEGE_RAG_QUERY, IntentType.ACADEMIC_PROGRAM_QUERY]:
                print(f"[PIPELINE][8] Routing to FAQ Agent with RAG search")
                response = self.faq_agent.process(
                    user_query=user_message,
                    session_id=session_id,
                    user_id=user_id
                )
                
                print(f"[PIPELINE][8] FAQ Agent response length: {len(response)} chars")
                print(f"[PIPELINE][8] FAQ Agent response preview: {response[:100]}...")
                
                # CRITICAL FIX: Don't override FAQ agent response
                # Trust the FAQ agent to return appropriate responses
                state["final_response"] = response
            
            # TICKET STATUS
            elif intent == IntentType.TICKET_STATUS:
                try:
                    tickets = self.data_access.get_student_tickets(user_id, limit=5)
                    counts = self.data_access.get_active_ticket_count(user_id)
                except Exception as db_err:
                    print(f"[EXECUTE] Database error fetching tickets: {db_err}")
                    state["final_response"] = "I'm having trouble accessing the ticket database right now. Please try again later."
                    return state
                
                if tickets:
                    ticket_lines = []
                    for t in tickets:
                        ticket_lines.append(
                            f"• **#{t['ticket_id']}** [{t['status']}] - {t['category']}: {t['description']}"
                        )
                    state["final_response"] = (
                        f"📋 **Your Tickets** ({counts['total']} total, {counts['open']} open):\n\n"
                        + "\n".join(ticket_lines)
                    )
                else:
                    state["final_response"] = "You don't have any tickets yet. Would you like to raise one?"
            
            # HISTORY RETRIEVAL
            elif intent == IntentType.RETRIEVE_HISTORY:
                history = self.data_access.get_recent_chat_history(user_id, limit=10)
                if history:
                    state["final_response"] = "Here's your recent conversation history."
                else:
                    state["final_response"] = "No previous conversation history found."
            
            # GENERAL CHAT
            elif intent == IntentType.GENERAL_CHAT:
                # Check if this is a capability question (from reasoning)
                reasoning = state.get("reasoning", "").lower()
                is_capability = "capability" in reasoning or "asking about features" in reasoning or "capabilities" in reasoning
                
                if is_capability:
                    # Generate contextual capability response
                    state["final_response"] = self._generate_capability_response(user_message)
                else:
                    # Standard greeting
                    state["final_response"] = (
                        "Hello! I'm your ACE College support assistant. I can help you with:\n"
                        "• College policies and information\n"
                        "• Raising support tickets\n"
                        "• Contacting faculty members\n"
                        "• Checking your ticket status\n\n"
                        "How can I assist you today?"
                    )
            
            else:
                state["final_response"] = "I'm processing your request."
                
        except Exception as e:
            print(f"[PIPELINE][8] Execution error: {e}")
            import traceback
            traceback.print_exc()
            state["final_response"] = "I encountered an error processing your request. Please try again."
        
        return state
    
    def _generate_capability_response(self, user_message: str) -> str:
        """Generate contextual response for capability questions like 'can you send emails?'"""
        msg_lower = user_message.lower()
        
        # Detect which capability is being asked about
        if any(kw in msg_lower for kw in ["email", "mail", "send"]):
            return (
                "Yes! I can help you **send emails**. Here's how:\n\n"
                "• Just say something like: *\"Send an email to friend@gmail.com asking about the project\"*\n"
                "• I'll generate a professional email body and show you a preview before sending\n"
                "• You can edit the subject, body, or cancel before sending\n\n"
                "Would you like to send an email now?"
            )
        elif any(kw in msg_lower for kw in ["ticket", "complaint", "raise", "issue"]):
            return (
                "Yes! I can help you **raise support tickets**. Here's how:\n\n"
                "• Say: *\"Raise a ticket about WiFi not working\"* or *\"I have a complaint\"*\n"
                "• I'll guide you through selecting a category and describing your issue\n"
                "• You'll get a ticket number to track your request\n\n"
                "Would you like to raise a ticket now?"
            )
        elif any(kw in msg_lower for kw in ["faculty", "professor", "teacher", "contact"]):
            return (
                "Yes! I can help you **contact faculty members**. Here's how:\n\n"
                "• Say: *\"Contact Professor Kumar\"* or *\"Email Dr. Sharma\"*\n"
                "• I'll search our faculty database and send an email on your behalf\n\n"
                "Would you like to contact a faculty member now?"
            )
        else:
            return (
                "I can help you with several things:\n\n"
                "📚 **College Information** — Ask about courses, fees, policies, placements\n"
                "📧 **Send Emails** — Send emails to faculty or anyone else\n"
                "🎫 **Raise Tickets** — Report issues and track resolutions\n"
                "👨‍🏫 **Contact Faculty** — Reach out to professors directly\n"
                "📋 **Ticket Status** — Check status of your existing tickets\n\n"
                "Just tell me what you need!"
            )
    
    # =========================================================================
    # NODE 9: VALIDATE OUTPUT
    # =========================================================================
    
    def _node_validate_output(self, state: AgentState) -> AgentState:
        """Validate output and permissions"""
        errors = []
        
        # Validate ticket access
        if state.get("entities", {}).get("ticket_id"):
            ticket_id = state["entities"]["ticket_id"]
            try:
                ticket = self.data_access.get_ticket_status(ticket_id, state["user_id"])
                if not ticket:
                    errors.append(f"Ticket #{ticket_id} not found or access denied")
            except Exception as db_err:
                print(f"[VALIDATE] Database error checking ticket: {db_err}")
                errors.append(f"Could not verify ticket #{ticket_id} — database temporarily unavailable")
        
        # Validate faculty exists
        if state.get("resolved_faculty"):
            faculty_id = state["resolved_faculty"].get("faculty_id")
            if faculty_id:
                faculty = self.faculty_db.get_faculty_by_id(faculty_id)
                if not faculty:
                    errors.append("Faculty member not found in database")
        
        state["validation_passed"] = len(errors) == 0
        state["validation_errors"] = errors
        
        if errors:
            print(f"[PIPELINE][9] Validation errors: {errors}")
        
        return state
    
    # =========================================================================
    # NODE 10: GENERATE RESPONSE
    # =========================================================================
    
    def _node_generate_response(self, state: AgentState) -> AgentState:
        """Generate final response"""
        
        # If validation failed
        if not state.get("validation_passed", True):
            errors = state.get("validation_errors", [])
            state["final_response"] = f"Unable to complete request: {'; '.join(errors)}"
            return state
        
        # Response already set by execute_agent
        if state.get("final_response"):
            print(f"[PIPELINE][10] Response ready: {len(state['final_response'])} chars")
            return state
        
        # Default response
        state["final_response"] = "I've processed your request."
        return state
    
    # =========================================================================
    # NODE: CLARIFY
    # =========================================================================
    
    def _node_clarify(self, state: AgentState) -> AgentState:
        """Generate clarification response"""
        question = state.get("clarification_question", 
                            "Could you please provide more details?")
        state["final_response"] = question
        state["selected_agent"] = "clarification"
        return state
    
    # =========================================================================
    # NODE: FACULTY FLOW
    # =========================================================================
    
    def _node_handle_faculty_flow(self, state: AgentState) -> AgentState:
        """
        Handle multi-step faculty/email contact flow.
        
        Supports two email types:
        1. Faculty Email: Search faculty DB, ask for name/designation if ambiguous
        2. External Email: Ask for recipient email address directly
        
        Flow Steps:
        - init: Determine email type (faculty vs external)
        - awaiting_faculty: Collect faculty name from user
        - awaiting_selection: Disambiguate multiple faculty matches
        - awaiting_recipient_email: Collect external recipient email
        - awaiting_recipient_name: Collect external recipient name
        - awaiting_purpose: Collect email purpose/message
        - preview: Show generated email for confirmation
        - editing_subject/editing_body: Handle edits
        """
        user_message = state["user_message"]
        msg_lower = user_message.lower().strip()
        step = state.get("contact_faculty_step", "init")
        slots = state.get("extracted_slots", {})
        
        print(f"[EMAIL_FLOW] Step: {step}, Message: '{user_message[:50]}...'")
        print(f"[EMAIL_FLOW] Slots: {slots}")
        
        # =====================================================================
        # CRITICAL FIX: AUTO-ADVANCE STEP BASED ON ALREADY-FILLED SLOTS
        # This prevents the flow from getting stuck when slots are already filled
        # =====================================================================
        if step == "init" or step == "awaiting_type_selection":
            # If email_type is already filled, advance to the appropriate next step
            if slots.get("email_type"):
                email_type = slots.get("email_type")
                print(f"[EMAIL_FLOW] Auto-advancing: email_type already set to '{email_type}'")
                
                if email_type == "external":
                    # External email flow
                    if slots.get("recipient_email"):
                        if slots.get("purpose") or slots.get("body"):
                            # All required fields present - go to preview
                            step = "preview"
                            state["contact_faculty_step"] = "preview"
                            print(f"[EMAIL_FLOW] Auto-advancing to preview (all external fields filled)")
                        elif slots.get("recipient_name"):
                            step = "awaiting_purpose"
                            state["contact_faculty_step"] = "awaiting_purpose"
                            print(f"[EMAIL_FLOW] Auto-advancing to awaiting_purpose")
                        else:
                            step = "awaiting_recipient_name"
                            state["contact_faculty_step"] = "awaiting_recipient_name"
                            print(f"[EMAIL_FLOW] Auto-advancing to awaiting_recipient_name")
                    else:
                        step = "awaiting_recipient_email"
                        state["contact_faculty_step"] = "awaiting_recipient_email"
                        print(f"[EMAIL_FLOW] Auto-advancing to awaiting_recipient_email")
                else:
                    # Faculty email flow
                    if slots.get("resolved_faculty") or slots.get("faculty_name"):
                        if slots.get("purpose") or slots.get("body"):
                            step = "preview"
                            state["contact_faculty_step"] = "preview"
                            print(f"[EMAIL_FLOW] Auto-advancing to preview (all faculty fields filled)")
                        else:
                            step = "awaiting_purpose"
                            state["contact_faculty_step"] = "awaiting_purpose"
                            print(f"[EMAIL_FLOW] Auto-advancing to awaiting_purpose")
                    else:
                        step = "awaiting_faculty"
                        state["contact_faculty_step"] = "awaiting_faculty"
                        print(f"[EMAIL_FLOW] Auto-advancing to awaiting_faculty")
        
        # =====================================================================
        # STEP: INIT - Determine email type (faculty vs external)
        # =====================================================================
        if step == "init" or step is None:
            import re
            
            # =====================================================================
            # PRIORITY 1: Check for email address in the message FIRST
            # If found, auto-route to external flow (skip Faculty/External question)
            # =====================================================================
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            email_match = re.search(email_pattern, user_message)
            
            if email_match:
                extracted_email = email_match.group(0).lower()
                print(f"[EMAIL_FLOW] Email detected in message: {extracted_email} — auto-routing to external flow")
                
                slots["email_type"] = "external"
                slots["recipient_email"] = extracted_email
                state["active_flow"] = "email"
                
                # Try to extract purpose from message
                purpose_patterns = [
                    r"(?:ask(?:ing)?|tell(?:ing)?|request(?:ing)?|remind(?:ing)?)\s+(?:him|her|them)?\s*(?:to)?\s*(.+?)(?:$|\.)",
                    r"(?:about|regarding)\s+(.+?)(?:$|\.)",
                    r"(?:email|mail|send)\s+.+?@.+?\s+(.+?)(?:$|\.)",
                ]
                purpose = None
                for pattern in purpose_patterns:
                    purpose_match = re.search(pattern, user_message, re.IGNORECASE)
                    if purpose_match:
                        purpose_text = purpose_match.group(1).strip()
                        # Remove the email address from purpose if it leaked in
                        purpose_text = re.sub(email_pattern, '', purpose_text).strip()
                        if len(purpose_text) > 10:
                            purpose = purpose_text
                            break
                
                if purpose:
                    slots["purpose"] = purpose
                    print(f"[EMAIL_FLOW] Extracted purpose: {purpose}")
                
                # Try to derive recipient name from email prefix
                email_prefix = extracted_email.split('@')[0]
                # Clean up: remove numbers, dots, underscores
                clean_name = re.sub(r'[0-9._]+', ' ', email_prefix).strip().title()
                
                state["extracted_slots"] = slots
                
                if purpose:
                    # Have both email and purpose — skip to preview directly
                    profile = state.get("student_profile", {})
                    student_name = profile.get("full_name", "Student")
                    
                    # Sanitize purpose for email body generation
                    sanitized_purpose = purpose
                    for prefix in ["send email to", "email to", "email about", "about"]:
                        if sanitized_purpose.lower().startswith(prefix):
                            sanitized_purpose = sanitized_purpose[len(prefix):].strip()
                    
                    subject = self.email_agent.generate_email_subject(sanitized_purpose)
                    if len(subject) < 5 or subject.lower().startswith(("send", "email", "write")):
                        words = sanitized_purpose.split()[:6]
                        subject = f"Regarding: {' '.join(words).capitalize()}"
                    
                    recipient_display = clean_name if len(clean_name) > 1 else "Sir/Madam"
                    body = self.email_agent.generate_email_body(
                        purpose=sanitized_purpose,
                        recipient_name=recipient_display,
                        student_name=student_name
                    )
                    
                    state["email_draft"] = {
                        "to": extracted_email,
                        "to_name": recipient_display,
                        "subject": subject,
                        "body": body
                    }
                    state["contact_faculty_step"] = "preview"
                    state["expected_response_type"] = "email_confirmation"
                    state["pending_question"] = "email_confirmation"
                    state["final_response"] = (
                        f"📧 **Email Preview:**\n\n"
                        f"**To:** {recipient_display} ({extracted_email})\n"
                        f"**Subject:** {subject}\n\n"
                        f"---\n{body}\n---\n\n"
                        "**Choose an option:**\n"
                        "• **Send** - Send this email\n"
                        "• **Edit Email** - Change the recipient email address\n"
                        "• **Edit Subject** - Modify the subject line\n"
                        "• **Edit Body** - Modify the email content\n"
                        "• **Cancel** - Cancel this email"
                    )
                else:
                    # Have email but no purpose — ask for purpose
                    state["contact_faculty_step"] = "awaiting_purpose"
                    state["expected_response_type"] = "email_purpose"
                    state["pending_question"] = "email_purpose"
                    state["final_response"] = (
                        f"📧 Got it! Sending to: **{extracted_email}**\n\n"
                        "What would you like to say in the email? Please describe the **purpose**:"
                    )
                return state
            
            # =====================================================================
            # PRIORITY 2: Keyword-based detection (faculty vs external)
            # =====================================================================
            faculty_keywords = ["faculty", "professor", "teacher", "ma'am", "sir", "dr.", "hod", "dean", "prof"]
            external_keywords = ["friend", "classmate", "colleague", "someone", "external", "other"]
            
            is_faculty_request = any(kw in msg_lower for kw in faculty_keywords)
            is_external_request = any(kw in msg_lower for kw in external_keywords)
            
            faculty_name_patterns = [
                r"(?:Dr\.?|Prof\.?|Mr\.?|Mrs\.?|Ms\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                r"([A-Z][a-z]+)\s+(?:ma'am|sir|madam)"
            ]
            has_faculty_name = any(re.search(p, user_message, re.IGNORECASE) for p in faculty_name_patterns)
            
            if is_faculty_request or has_faculty_name:
                print(f"[EMAIL_FLOW] Detected: FACULTY email request")
                slots["email_type"] = "faculty"
                state["extracted_slots"] = slots
                state["contact_faculty_step"] = "awaiting_faculty"
                state["active_flow"] = "contact_faculty"
                step = "awaiting_faculty"
            elif is_external_request:
                print(f"[EMAIL_FLOW] Detected: EXTERNAL email request")
                slots["email_type"] = "external"
                state["extracted_slots"] = slots
                state["active_flow"] = "email"
                state["contact_faculty_step"] = "awaiting_recipient_email"
                state["expected_response_type"] = "recipient_email"
                state["pending_question"] = "recipient_email"
                state["final_response"] = (
                    "📧 **Email Assistant**\n\n"
                    "I'll help you send an email.\n\n"
                    "Please provide the **recipient's email address**:"
                )
                return state
            else:
                # No email address and no clear keywords — ask for recipient email directly
                # instead of asking Faculty/External (simpler flow)
                print(f"[EMAIL_FLOW] No email detected — asking for recipient email and purpose")
                state["active_flow"] = "email"
                state["contact_faculty_step"] = "awaiting_recipient_email"
                state["expected_response_type"] = "recipient_email"
                state["pending_question"] = "recipient_email"
                state["final_response"] = (
                    "📧 **Email Assistant**\n\n"
                    "I'll help you send an email.\n\n"
                    "Please provide the **recipient's email address**:\n\n"
                    "*If you'd like to email a faculty member, just say 'contact faculty' or 'email professor [name]'.*"
                )
                return state
        
        # =====================================================================
        # STEP: TYPE SELECTION - User choosing faculty vs external
        # =====================================================================
        if step == "awaiting_type_selection":
            if msg_lower in ["1", "faculty", "professor", "teacher"]:
                slots["email_type"] = "faculty"
                state["extracted_slots"] = slots
                state["contact_faculty_step"] = "awaiting_faculty"
                state["active_flow"] = "contact_faculty"
                state["expected_response_type"] = None
                state["pending_question"] = None
                state["final_response"] = (
                    "Great! Which **faculty member** would you like to email?\n\n"
                    "Please provide their name (e.g., 'Dr. Sharma', 'Prof. Kumar', 'HOD CSE'):"
                )
                return state
            elif msg_lower in ["2", "external", "friend", "other", "classmate"]:
                slots["email_type"] = "external"
                state["extracted_slots"] = slots
                state["contact_faculty_step"] = "awaiting_recipient_email"
                state["active_flow"] = "email"
                state["expected_response_type"] = "recipient_email"
                state["pending_question"] = "recipient_email"
                state["final_response"] = (
                    "Sure! Please provide the **recipient's email address**:"
                )
                return state
            else:
                # =====================================================================
                # SMART DETECTION: Check if message contains an email address
                # If so, route to external email flow instead of faculty search
                # =====================================================================
                import re
                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                email_match = re.search(email_pattern, user_message)
                
                if email_match:
                    # User provided an email address - route to external flow
                    extracted_email = email_match.group(0)
                    print(f"[EMAIL_FLOW] Detected email in message: {extracted_email}")
                    
                    # Try to extract purpose from message (everything after the email or key phrases)
                    purpose_patterns = [
                        r'(?:ask(?:ing)?|tell(?:ing)?|request(?:ing)?|remind|about|regarding|for|to)\s+(?:him|her|them)?\s*(?:to\s+)?(.+?)$',
                        r'and\s+(.+?)$',
                    ]
                    purpose = None
                    for pattern in purpose_patterns:
                        purpose_match = re.search(pattern, user_message, re.IGNORECASE)
                        if purpose_match:
                            purpose = purpose_match.group(1).strip()
                            if len(purpose) > 5:  # Meaningful purpose
                                break
                            purpose = None
                    
                    # Try to extract recipient name
                    name_patterns = [
                        r'(?:email|mail|send)\s+(?:to\s+)?(?:my\s+)?(?:friend\s+)?([A-Za-z]+)',
                        r'(?:to\s+)([A-Za-z]+)\s+(?:having|with|at)',
                    ]
                    recipient_name = None
                    for pattern in name_patterns:
                        name_match = re.search(pattern, user_message, re.IGNORECASE)
                        if name_match:
                            name = name_match.group(1).strip()
                            if name.lower() not in ['my', 'the', 'a', 'an', 'friend', 'him', 'her']:
                                recipient_name = name.title()
                                break
                    
                    # Set up external email flow with extracted data
                    slots["email_type"] = "external"
                    slots["recipient_email"] = extracted_email
                    if recipient_name:
                        slots["recipient_name"] = recipient_name
                    if purpose:
                        slots["inferred_purpose"] = purpose
                    
                    state["extracted_slots"] = slots
                    state["active_flow"] = "email"
                    
                    # Determine next step based on what we have
                    if purpose:
                        # We have email and purpose - can go to preview
                        state["contact_faculty_step"] = "generating_preview"
                        state["expected_response_type"] = None
                        state["pending_question"] = None
                        
                        # Generate email draft with proper sanitization
                        recipient_display = recipient_name or extracted_email.split('@')[0].title()
                        
                        # Apply INVARIANT 7 & 8: Sanitize purpose and generate quality subject
                        sanitized_purpose = purpose
                        for prefix in ["send email to", "email to", "email about", "about"]:
                            if sanitized_purpose.lower().startswith(prefix):
                                sanitized_purpose = sanitized_purpose[len(prefix):].strip()
                        
                        # Generate subject - ensure quality
                        subject = self.email_agent.generate_email_subject(sanitized_purpose)
                        if len(subject) < 5 or subject.lower().startswith(("send", "email", "write")):
                            words = sanitized_purpose.split()[:6]
                            subject = f"Regarding: {' '.join(words).capitalize()}"
                        
                        # Generate proper body using LLM
                        profile = state.get("student_profile", {})
                        student_name = profile.get("full_name", "Student")
                        body = self.email_agent.generate_email_body(
                            purpose=sanitized_purpose,
                            recipient_name=recipient_display,
                            student_name=student_name
                        )
                        
                        state["email_draft"] = {
                            "to": extracted_email,
                            "to_name": recipient_display,
                            "subject": subject,
                            "body": body
                        }
                        state["contact_faculty_step"] = "preview"
                        state["final_response"] = (
                            f"📧 **Email Preview:**\n\n"
                            f"**To:** {recipient_display} ({extracted_email})\n"
                            f"**Subject:** {subject}\n\n"
                            f"---\n{body}\n---\n\n"
                            "**Choose an option:**\n"
                            "• **Send** - Send this email\n"
                            "• **Edit Email** - Change the recipient email address\n"
                            "• **Edit Subject** - Modify the subject line\n"
                            "• **Edit Body** - Modify the email content\n"
                            "• **Cancel** - Cancel this email"
                        )
                        state["expected_response_type"] = "email_confirmation"
                        state["pending_question"] = "email_confirmation"
                    else:
                        # Have email but need purpose
                        state["contact_faculty_step"] = "awaiting_purpose"
                        state["expected_response_type"] = "email_purpose"
                        state["pending_question"] = "email_purpose"
                        state["final_response"] = (
                            f"Great! I'll send an email to **{extracted_email}**.\n\n"
                            "What would you like to say in the email? Please describe the purpose:"
                        )
                    return state
                
                # No email found - try faculty search as fallback
                try:
                    result = self.faculty_db.search_faculty(name=user_message)
                    matches = result.get("matches", [])
                except Exception as e:
                    print(f"[EMAIL_FLOW] Faculty search error: {e}")
                    matches = []
                
                if matches:
                    slots["email_type"] = "faculty"
                    state["extracted_slots"] = slots
                    state["contact_faculty_step"] = "awaiting_faculty"
                    # Fall through to handle faculty matching
                    step = "awaiting_faculty"
                else:
                    state["final_response"] = (
                        "I didn't understand that. Please reply with:\n\n"
                        "• **1** for Faculty Member\n"
                        "• **2** for External Contact\n\n"
                        "Or type the faculty member's name directly, or provide an email address."
                    )
                    return state
        
        # =====================================================================
        # STEP: AWAITING FACULTY - Collect and search faculty name
        # =====================================================================
        if step == "awaiting_faculty":
            # Try to extract faculty name from entities first
            faculty_name = state.get("entities", {}).get("faculty_name")
            
            # If no entity extracted, use the user message as the name
            if not faculty_name:
                # Check for common patterns — improved to capture multi-word names
                import re
                patterns = [
                    # "send email to prof./dr. Abdul Kalam" — capture everything after the honorific
                    r"(?:email|contact|message|send)\s+(?:an?\s+)?(?:email\s+)?(?:to\s+)?(?:prof(?:essor)?\.?|dr\.?|mr\.?|mrs\.?|ms\.?)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)",
                    # "email Abdul Kalam" — capture name after action verb (no honorific)
                    r"(?:email|contact|message|send)\s+(?:an?\s+)?(?:email\s+)?(?:to\s+)?([A-Z][a-z]+(?:\s+[A-Za-z]+)*)",
                    # Fallback: just use the whole message cleaned up
                ]
                for pattern in patterns:
                    match = re.search(pattern, user_message, re.IGNORECASE)
                    if match:
                        extracted_name = match.group(1).strip()
                        # Remove trailing noise: (faculty), referring, asking, etc.
                        extracted_name = re.sub(r'\s*\(.*\).*$', '', extracted_name)
                        extracted_name = re.sub(r'\s+(?:referring|asking|about|regarding|for|that|send|this|from|sir|mam|madam)\b.*$', '', extracted_name, flags=re.IGNORECASE)
                        skip_words = ["my", "the", "a", "an", "friend", "someone", "email", "send", "to", "professor", "sir", "madam"]
                        if extracted_name.lower() not in skip_words and len(extracted_name) > 1:
                            faculty_name = extracted_name
                            print(f"[EMAIL_FLOW] Extracted faculty name: {faculty_name}")
                            break
                
                # Final fallback: clean the entire message as a name
                if not faculty_name:
                    cleaned = user_message.strip()
                    for noise in ["send", "email", "to", "an", "a", "professor", "prof", "dr", "contact", "message", "sir", "mam", "madam", "(faculty)", "faculty"]:
                        cleaned = re.sub(r'\b' + re.escape(noise) + r'\b', '', cleaned, flags=re.IGNORECASE)
                    cleaned = re.sub(r'\s*\(.*\)', '', cleaned).strip()
                    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                    if len(cleaned) > 1:
                        faculty_name = cleaned
                        print(f"[EMAIL_FLOW] Fallback faculty name extraction: {faculty_name}")
            
            if faculty_name:
                result = self.faculty_db.search_faculty(name=faculty_name)
                matches = result.get("matches", [])
                
                if len(matches) == 1:
                    # Single match - proceed
                    state["resolved_faculty"] = matches[0]
                    state["contact_faculty_step"] = "awaiting_purpose"
                    state["expected_response_type"] = "email_purpose"
                    state["pending_question"] = "email_purpose"
                    state["extracted_slots"]["email_type"] = "faculty"
                    state["final_response"] = (
                        f"✅ Found: **{matches[0]['name']}**\n"
                        f"📍 {matches[0]['designation']}, {matches[0]['department']}\n"
                        f"📧 {matches[0]['email']}\n\n"
                        "What would you like to say in your email? (I'll generate a professional message for you)"
                    )
                elif len(matches) > 1:
                    # Multiple matches - ask for designation/department to disambiguate
                    options = "\n".join([
                        f"{i+1}. **{m['name']}** - {m['designation']}, {m['department']}"
                        for i, m in enumerate(matches[:5])
                    ])
                    state["faculty_matches"] = matches
                    state["contact_faculty_step"] = "awaiting_selection"
                    state["expected_response_type"] = "faculty_selection"
                    state["pending_question"] = "faculty_selection"
                    state["final_response"] = (
                        f"I found multiple faculty members matching '{faculty_name}':\n\n"
                        f"{options}\n\n"
                        "Please reply with the **number** of your choice, or specify the **designation/department**:"
                    )
                else:
                    # No match - ask again with helpful hints
                    state["final_response"] = (
                        f"❌ I couldn't find a faculty member named '**{faculty_name}**'.\n\n"
                        "Please try:\n"
                        "• A different spelling of the name\n"
                        "• Just the first or last name\n"
                        "• Include designation (e.g., 'Dr. Kumar', 'Prof. Sharma')\n\n"
                        "Or type **'list'** to see all available faculty members."
                    )
            else:
                # No name extracted - prompt for it
                state["final_response"] = (
                    "📧 **Faculty Email Assistant**\n\n"
                    "Which faculty member would you like to email?\n\n"
                    "Please provide their **name** (e.g., 'Dr. Rajesh', 'Prof. Sharma', 'HOD CSE'):"
                )
            return state
        
        # =====================================================================
        # STEP: AWAITING SELECTION - Disambiguate faculty
        # =====================================================================
        elif step == "awaiting_selection":
            matches = state.get("faculty_matches", [])
            
            # Try numeric selection
            try:
                selection = int(msg_lower.replace(".", "").strip()) - 1
                if 0 <= selection < len(matches):
                    state["resolved_faculty"] = matches[selection]
                    state["contact_faculty_step"] = "awaiting_purpose"
                    state["expected_response_type"] = "email_purpose"
                    state["pending_question"] = "email_purpose"
                    state["faculty_matches"] = None
                    selected = matches[selection]
                    state["final_response"] = (
                        f"✅ Selected: **{selected['name']}** ({selected['designation']})\n\n"
                        "What would you like to say in your email?"
                    )
                    return state
            except ValueError:
                pass
            
            # Try matching by designation or department
            for m in matches:
                if msg_lower in m.get("designation", "").lower() or msg_lower in m.get("department", "").lower():
                    state["resolved_faculty"] = m
                    state["contact_faculty_step"] = "awaiting_purpose"
                    state["expected_response_type"] = "email_purpose"
                    state["pending_question"] = "email_purpose"
                    state["final_response"] = (
                        f"✅ Selected: **{m['name']}** ({m['designation']})\n\n"
                        "What would you like to say in your email?"
                    )
                    return state
            
            state["final_response"] = (
                "I didn't understand that. Please enter the **number** from the list above,\n"
                "or specify the faculty's **department/designation** to help me identify them."
            )
            return state
        
        # =====================================================================
        # STEP: AWAITING RECIPIENT EMAIL (External emails only)
        # =====================================================================
        elif step == "awaiting_recipient_email":
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            
            if re.match(email_pattern, msg_lower):
                slots["recipient_email"] = msg_lower
                state["extracted_slots"] = slots
                state["contact_faculty_step"] = "awaiting_recipient_name"
                state["expected_response_type"] = "recipient_name"
                state["pending_question"] = "recipient_name"
                state["final_response"] = (
                    f"📧 Got it: **{msg_lower}**\n\n"
                    "What is the **recipient's name**? (This will be used in the greeting)"
                )
            else:
                state["final_response"] = (
                    "❌ That doesn't look like a valid email address.\n\n"
                    "Please enter a valid email (e.g., john@gmail.com):"
                )
            return state
        
        # =====================================================================
        # STEP: AWAITING RECIPIENT NAME (External emails only)
        # =====================================================================
        elif step == "awaiting_recipient_name":
            recipient_name = user_message.strip().title()  # Capitalize properly
            slots["recipient_name"] = recipient_name
            state["extracted_slots"] = slots
            state["contact_faculty_step"] = "awaiting_purpose"
            state["expected_response_type"] = "email_purpose"
            state["pending_question"] = "email_purpose"
            state["final_response"] = (
                f"📧 Recipient: **{recipient_name}** ({slots.get('recipient_email', '')})\n\n"
                "What would you like to say in your email?\n"
                "(Describe the purpose and I'll generate a professional email for you)"
            )
            return state
        

        elif step == "awaiting_purpose":
            # Capture purpose and show preview
            slots["purpose"] = user_message
            state["extracted_slots"] = slots
            
            profile = state.get("student_profile", {})
            student_name = profile.get("full_name", "Student")
            
            # Determine recipient info based on email type
            email_type = slots.get("email_type", "faculty")
            
            if email_type == "faculty":
                faculty = state.get("resolved_faculty", {})
                recipient_email = faculty.get("email", "")
                recipient_name = faculty.get("name", "Faculty")
            else:
                # External email
                recipient_email = slots.get("recipient_email", "")
                recipient_name = slots.get("recipient_name", "")
            
            # Generate email preview using LLM
            # =================================================================
            # INVARIANT 7: EMAIL_BODY_SANITIZATION
            #   - Email body must be clean, human-written prose
            #   - MUST strip command text (e.g., "send email to X about Y")
            #   - MUST remove system/meta language
            #   - MUST NOT contain prompt instructions or repetitive text
            #
            # INVARIANT 8: SUBJECT_QUALITY
            #   - Subject must be meaningful and intent-based
            #   - MUST NOT be a person's name alone
            #   - MUST NOT be raw user command text
            # =================================================================
            
            # Sanitize purpose: extract actual message intent, not command structure
            purpose_text = user_message
            # Remove command prefixes
            for prefix in ["send email to", "email to", "email about", "write email about", 
                          "send an email to", "send email about", "compose email about"]:
                if purpose_text.lower().startswith(prefix):
                    purpose_text = purpose_text[len(prefix):].strip()
            
            # Remove recipient mentions from purpose (e.g., "my friend about meeting" -> "meeting")
            import re
            purpose_text = re.sub(r'^(?:my\s+)?(?:friend|professor|teacher|faculty|sir|mam)\s+(?:about|regarding|for)\s+', '', purpose_text, flags=re.IGNORECASE)
            purpose_text = re.sub(r'^(?:about|regarding|for)\s+', '', purpose_text, flags=re.IGNORECASE)
            
            # If purpose is too short after cleanup, use original
            if len(purpose_text.strip()) < 5:
                purpose_text = user_message
            
            subject = self.email_agent.generate_email_subject(purpose_text)
            
            # INVARIANT 8: Validate subject quality
            # Subject should not be just a name or raw command
            subject_lower = subject.lower().strip()
            invalid_subject_patterns = [
                r'^(dear|hi|hello|hey)\s+\w+$',  # Greetings only
                r'^(send|email|write|compose)\s+',  # Command verbs
                r'^[a-z]+\s+(sir|mam|madam)$',  # Just "X sir"
            ]
            is_invalid_subject = any(re.match(pattern, subject_lower) for pattern in invalid_subject_patterns)
            
            if is_invalid_subject or len(subject) < 5:
                # Generate a better subject from purpose
                words = purpose_text.split()[:6]
                subject = " ".join(words).capitalize()
                if not subject.endswith(("?", ".", "!")):
                    subject = f"Regarding: {subject}"
                print(f"[EMAIL] Subject regenerated due to quality check: {subject}")
            
            body = self.email_agent.generate_email_body(
                purpose=purpose_text,  # Use sanitized purpose
                recipient_name=recipient_name,
                student_name=student_name
            )
            
            # SANITIZATION: Remove any meta-text that leaked into body
            meta_patterns = [
                r'\[.*?\]',  # [anything in brackets]
                r'\{.*?\}',  # {anything in braces}
                r'(?i)note:.*?(\n|$)',  # Note: ...
                r'(?i)instruction:.*?(\n|$)',  # Instruction: ...
                r'(?i)system:.*?(\n|$)',  # System: ...
            ]
            for pattern in meta_patterns:
                body = re.sub(pattern, '', body)
            
            # Clean up excessive whitespace
            body = re.sub(r'\n{3,}', '\n\n', body)
            body = body.strip()
            
            state["email_draft"] = {
                "to": recipient_email,
                "to_name": recipient_name,
                "subject": subject,
                "body": body,
                "editable": True
            }
            state["contact_faculty_step"] = "preview"
            state["confirmation_pending"] = True
            state["expected_response_type"] = "email_confirmation"
            state["pending_question"] = "email_confirmation"
            state["final_response"] = (
                f"📧 **Email Preview:**\n\n"
                f"**To:** {recipient_name} ({recipient_email})\n"
                f"**Subject:** {subject}\n\n"
                f"---\n{body}\n---\n\n"
                "**Choose an option:**\n"
                "• **Send** - Send this email\n"
                "• **Edit Email** - Change the recipient email address\n"
                "• **Edit Subject** - Modify the subject line\n"
                "• **Edit Body** - Modify the email content\n"
                "• **🔄 Regenerate** - Regenerate the email with same details\n"
                "• **Cancel** - Cancel this email"
            )
        
        elif step == "preview":
            # Handle preview confirmation: Send, Edit Subject, Edit Body, Cancel
            msg_lower = user_message.lower().strip()
            
            # Set expected response type if not already set
            if not state.get("expected_response_type"):
                state["expected_response_type"] = "email_confirmation"
                state["pending_question"] = "Confirm email send"
            
            # Validate response type
            # Validate response type
            if state.get("expected_response_type") == "email_confirmation":
                draft = state.get("email_draft")
                
                # RECOVERY: If draft is missing in preview step, regenerate or fallback
                # FIX for AttributeError: 'NoneType' object has no attribute 'get'
                if not draft:
                    print("[EMAIL] ⚠️ Draft missing in preview step - attempting recovery")
                    recipient_email = state.get("extracted_slots", {}).get("recipient_email")
                    purpose = state.get("extracted_slots", {}).get("purpose")
                    
                    if recipient_email and purpose:
                        # We have enough to regenerate
                        print("[EMAIL] Recovering from slots...")
                        # Fallback to previous step to regenerate
                        state["contact_faculty_step"] = "awaiting_purpose" 
                        return self._node_handle_faculty_flow(state)
                    else:
                        print("[EMAIL] Cannot recover - missing slots. Resetting flow.")
                        state["final_response"] = (
                            "❌ I lost track of the email details. Let's start over.\n\n"
                            "Who would you like to email?"
                        )
                        state["active_flow"] = None
                        state["contact_faculty_step"] = None
                        state["email_draft"] = None
                        return state
                
                # SEND EMAIL
                if msg_lower in ["send", "yes", "confirm", "ok"]:
                    # =====================================================================
                    # EXECUTION GATE: Check required fields before allowing send
                    # =====================================================================
                    missing = []
                    if not draft.get("to"):
                        missing.append("recipient email")
                    if not draft.get("subject"):
                        missing.append("subject")
                    if not draft.get("body"):
                        missing.append("body")
                    
                    if missing:
                        print(f"[EXECUTION_GATE] Email blocked - missing: {missing}")
                        state["final_response"] = (
                            f"❌ Cannot send email - missing required information:\n\n"
                            f"• **{', '.join(missing)}**\n\n"
                            "Please provide the missing information."
                        )
                        state["selected_agent"] = "orchestrator"
                        return state
                    
                    # All fields present - proceed with sending
                    # =================================================================
                    # CRITICAL SYSTEM INVARIANTS - VIOLATION WILL CAUSE FAILURE
                    # =================================================================
                    # INVARIANT 4: PREVIEW_BEFORE_SEND
                    #   - send_email() MUST only be called from preview-confirmed state
                    #   - No fallback, error path, or agent may bypass confirmation
                    #
                    # INVARIANT 5: EMAIL_IMMUTABILITY  
                    #   - The email address used for sending MUST exactly match
                    #     the user-confirmed value from preview
                    #   - Never normalize, guess, correct, or replace emails
                    #
                    # INVARIANT 6: EXPLICIT_CONFIRMATION
                    #   - User must explicitly confirm with "send", "yes", "confirm", "ok"
                    #   - No auto-send on any other input
                    # =================================================================
                    
                    # GUARD: Verify we are in preview-confirmed state
                    if step != "preview" or state.get("expected_response_type") != "email_confirmation":
                        print(f"⛔ INVARIANT VIOLATION: send_email called outside preview-confirmed state")
                        print(f"   Current step: {step}, expected_response_type: {state.get('expected_response_type')}")
                        state["final_response"] = "❌ Cannot send email: Invalid state. Please start over."
                        return state
                    
                    # GUARD: Verify confirmation was explicit
                    if msg_lower not in ["send", "yes", "confirm", "ok"]:
                        print(f"⛔ INVARIANT VIOLATION: Non-explicit confirmation: '{msg_lower}'")
                        state["final_response"] = "❌ Cannot send email: Explicit confirmation required."
                        return state
                    
                    # ASSERTION: Email immutability - get user-confirmed email
                    user_confirmed_email = state.get("extracted_slots", {}).get("recipient_email", "")
                    preview_email = draft.get("to", "")
                    
                    # INVARIANT CHECK: sent email MUST match preview email MUST match user-confirmed
                    if preview_email != user_confirmed_email and user_confirmed_email:
                        print(f"⛔ EMAIL IMMUTABILITY VIOLATION: preview={preview_email}, confirmed={user_confirmed_email}")
                        # Use the user-confirmed email, not any mutated version
                        draft["to"] = user_confirmed_email
                        state["email_draft"] = draft
                        print(f"   Restored to user-confirmed email: {user_confirmed_email}")
                    
                    send_to_email = draft.get("to", "")
                    send_subject = draft.get("subject", "")
                    send_body = draft.get("body", "")
                    
                    print(f"[EMAIL] SENDING - to: {send_to_email}, subject: {send_subject[:50]}...")
                    print(f"[EMAIL] Confirmation: {msg_lower} (explicit: ✓)")
                    
                    try:
                        result = self.email_agent.send_email(
                            to_email=send_to_email,
                            subject=send_subject,
                            body=send_body
                        )
                        
                        if result.get("success"):
                            # CRITICAL: Clear all email state after successful send
                            # FIX: Use None instead of {} — empty dict is truthy and causes stale state detection
                            state["active_flow"] = None
                            state["contact_faculty_step"] = None
                            state["extracted_slots"] = {}
                            state["email_draft"] = None
                            state["expected_response_type"] = None
                            state["pending_question"] = None
                            state["resolved_faculty"] = None
                            state["faculty_matches"] = None
                            state["clarification_context"] = {}
                            
                            state["final_response"] = (
                                f"✅ **Email sent successfully to {draft.get('to_name', 'recipient')}!**\n\n"
                                "How else can I help you?"
                            )
                            state["selected_agent"] = "orchestrator"
                            print("[EMAIL] Email sent successfully - state cleared")
                        else:
                            state["final_response"] = (
                                f"❌ Failed to send email: {result.get('message', 'Unknown error')}\n\n"
                                "Would you like to try again? Reply 'yes' or 'cancel'."
                            )
                    except Exception as e:
                        print(f"[EMAIL] Error sending email: {e}")
                        state["final_response"] = (
                            "❌ An error occurred while sending the email.\n\n"
                            "Would you like to try again? Reply 'yes' or 'cancel'."
                        )
                    return state
                
                # REGENERATE EMAIL (NEW)
                elif msg_lower in ["regenerate", "regenerate email", "regen", "redo"]:
                    print(f"[EMAIL] Regenerating email with same parameters")
                    slots = state.get("extracted_slots", {})
                    # Go back to awaiting_purpose step but re-use the existing purpose
                    purpose = slots.get("purpose", "")
                    if purpose:
                        state["contact_faculty_step"] = "awaiting_purpose"
                        state["email_draft"] = None
                        state["expected_response_type"] = None
                        state["pending_question"] = None
                        # Re-enter the purpose step with the original purpose text
                        state["user_message"] = purpose
                        return self._node_handle_faculty_flow(state)
                    else:
                        state["final_response"] = (
                            "I couldn't find the original email purpose. "
                            "Please describe what you'd like to say in the email:"
                        )
                        state["contact_faculty_step"] = "awaiting_purpose"
                        state["email_draft"] = None
                        return state
                
                # EDIT SUBJECT
                elif msg_lower in ["edit subject", "change subject", "edit"]:
                    state["contact_faculty_step"] = "editing_subject"
                    state["expected_response_type"] = "email_subject_edit"
                    state["pending_question"] = "Enter new subject"
                    state["final_response"] = (
                        "📝 **Editing Subject**\n\n"
                        f"Current subject: {draft.get('subject', '')}\n\n"
                        "Please enter the new subject line:"
                    )
                    return state
                
                # EDIT BODY
                elif msg_lower in ["edit body", "change body", "edit message"]:
                    state["contact_faculty_step"] = "editing_body"
                    state["expected_response_type"] = "email_body_edit"
                    state["pending_question"] = "Enter new body"
                    state["final_response"] = (
                        "📝 **Editing Email Body**\n\n"
                        f"Current body:\n{draft.get('body', '')}\n\n"
                        "Please enter the new email body:"
                    )
                    return state
                
                # EDIT RECIPIENT EMAIL (NEW)
                elif msg_lower in ["edit email", "change email", "edit recipient", "change recipient"]:
                    state["contact_faculty_step"] = "editing_recipient_email"
                    state["expected_response_type"] = "recipient_email_edit"
                    state["pending_question"] = "Enter new recipient email"
                    state["final_response"] = (
                        "📝 **Editing Recipient Email**\n\n"
                        f"Current email: {draft.get('to', '')}\n\n"
                        "Please enter the new recipient's email address:"
                    )
                    return state
                
                # CANCEL
                elif msg_lower in ["cancel", "abort", "stop", "no"]:
                    # Clear all email state
                    # FIX: Use None instead of {} — empty dict is truthy and causes stale state detection
                    state["active_flow"] = None
                    state["contact_faculty_step"] = None
                    state["extracted_slots"] = {}
                    state["email_draft"] = None
                    state["expected_response_type"] = None
                    state["pending_question"] = None
                    state["resolved_faculty"] = None
                    state["faculty_matches"] = None
                    state["clarification_context"] = {}
                    
                    state["final_response"] = "✅ Email cancelled. How else can I help you?"
                    state["selected_agent"] = "orchestrator"
                    print("[EMAIL] Email cancelled - state cleared")
                    return state
                
                else:
                    # Invalid response - re-show preview with clear options
                    state["final_response"] = (
                        f"**Email Preview:**\n\n"
                        f"**To:** {draft.get('to_name', '')} ({draft.get('to', '')})\n"
                        f"**Subject:** {draft.get('subject', '')}\n\n"
                        f"{draft.get('body', '')}\n\n"
                        "⚠️ **Please choose an action:**\n"
                        "• Reply **'send'** or **'yes'** to send this email\n"
                        "• Reply **'edit email'** to change the recipient\n"
                        "• Reply **'edit subject'** to change the subject\n"
                        "• Reply **'edit body'** to change the message\n"
                        "• Reply **'cancel'** to cancel"
                    )
                    return state
        
        elif step == "editing_subject":
            # User provided new subject
            draft = state.get("email_draft", {})
            draft["subject"] = user_message.strip()
            state["email_draft"] = draft
            state["contact_faculty_step"] = "preview"
            state["expected_response_type"] = "email_confirmation"
            state["pending_question"] = "Confirm email send"
            
            state["final_response"] = (
                f"**Updated Email Preview:**\n\n"
                f"**To:** {draft.get('to_name', '')} ({draft.get('to', '')})\n"
                f"**Subject:** {draft.get('subject', '')}\n\n"
                f"{draft.get('body', '')}\n\n"
                "Choose an option:\n"
                "• **Send** - Send the email\n"
                "• **Edit Email** - Change recipient\n"
                "• **Edit Subject** - Modify subject again\n"
                "• **Edit Body** - Modify the message\n"
                "• **Cancel** - Cancel this email"
            )
            return state
        
        elif step == "editing_body":
            # User provided new body
            draft = state.get("email_draft", {})
            draft["body"] = user_message.strip()
            state["email_draft"] = draft
            state["contact_faculty_step"] = "preview"
            state["expected_response_type"] = "email_confirmation"
            state["pending_question"] = "Confirm email send"
            
            state["final_response"] = (
                f"**Updated Email Preview:**\n\n"
                f"**To:** {draft.get('to_name', '')} ({draft.get('to', '')})\n"
                f"**Subject:** {draft.get('subject', '')}\n\n"
                f"{draft.get('body', '')}\n\n"
                "Choose an option:\n"
                "• **Send** - Send the email\n"
                "• **Edit Email** - Change recipient\n"
                "• **Edit Subject** - Modify the subject\n"
                "• **Edit Body** - Modify message again\n"
                "• **Cancel** - Cancel this email"
            )
            return state
        
        elif step == "editing_recipient_email":
            # User provided new recipient email
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            
            if re.match(email_pattern, user_message.lower().strip()):
                draft = state.get("email_draft", {})
                new_email = user_message.strip()
                draft["to"] = new_email
                # Also update extracted_slots
                slots = state.get("extracted_slots", {})
                slots["recipient_email"] = new_email
                state["extracted_slots"] = slots
                state["email_draft"] = draft
                state["contact_faculty_step"] = "preview"
                state["expected_response_type"] = "email_confirmation"
                state["pending_question"] = "Confirm email send"
                
                state["final_response"] = (
                    f"✅ **Updated Email Preview:**\n\n"
                    f"**To:** {draft.get('to_name', '')} ({draft.get('to', '')})\n"
                    f"**Subject:** {draft.get('subject', '')}\n\n"
                    f"{draft.get('body', '')}\n\n"
                    "Choose an option:\n"
                    "• **Send** - Send the email\n"
                    "• **Edit Email** - Change recipient again\n"
                    "• **Edit Subject** - Modify the subject\n"
                    "• **Edit Body** - Modify the message\n"
                    "• **Cancel** - Cancel this email"
                )
            else:
                state["final_response"] = (
                    "❌ That doesn't look like a valid email address.\n\n"
                    "Please enter a valid email (e.g., john@gmail.com):"
                )
            return state
        
        state["selected_agent"] = "contact_faculty"
        return state
    
    # =========================================================================
    # NODE: TICKET FLOW
    # =========================================================================
    
    def _node_handle_ticket_flow(self, state: AgentState) -> AgentState:
        """Handle ticket creation flow with self-resolution"""
        intent = state.get("intent_enum")
        user_message = state["user_message"]
        slots = state.get("extracted_slots", {})
        ticket_step = state.get("ticket_step", "start")
        
        print(f"[PIPELINE] Ticket flow: intent={intent}, step={ticket_step}, slots={list(slots.keys())}")
        
        # HANDLE TICKET STEP STATE MACHINE
        # Check if we're in an active flow and handle the current step
        if ticket_step == "awaiting_category" and slots.get("category"):
            # Category was selected in _continue_active_flow, now show preview
            description = slots.get("description", user_message)
            return self._prepare_ticket_creation(state, description)
        
        if ticket_step == "preview":
            # Handle preview actions: submit, edit, cancel
            msg_lower = user_message.lower().strip()
            
            # Set expected response type if not already set
            if not state.get("expected_response_type"):
                state["expected_response_type"] = "ticket_confirmation"
                state["pending_question"] = "Confirm ticket submission"
            
            # Validate response type
            if state.get("expected_response_type") == "ticket_confirmation":
                # EXPLICIT CONFIRMATION REQUIRED (not broad keyword matching)
                if msg_lower in ["submit", "yes", "confirm", "create"]:
                    # =====================================================================
                    # EXECUTION GATE: Check required fields before allowing submission
                    # =====================================================================
                    missing = check_missing_fields("raise_ticket", slots)
                    if missing:
                        print(f"[EXECUTION_GATE] Ticket blocked - missing fields: {missing}")
                        state["final_response"] = (
                            f"❌ Cannot create ticket - missing required information:\n\n"
                            f"• **{', '.join(missing)}**\n\n"
                            f"Please provide the missing information."
                        )
                        state["selected_agent"] = "orchestrator"
                        return state
                    
                    # All fields present - proceed with ticket creation
                    state["confirmation_pending"] = True
                    state["confirmation_data"] = {
                        "action": "ticket_preview",
                        "ticket_data": {
                            "category": slots.get("category", "Other"),
                            "description": slots.get("description", ""),
                            "priority": slots.get("priority", "Medium")
                        }
                    }
                    state["final_response"] = (
                        "✅ **Creating your ticket...**\n\n"
                        "Your ticket is being submitted. You'll receive a ticket ID shortly."
                    )
                    state["selected_agent"] = "ticket"
                    state["expected_response_type"] = None  # Clear pending state
                    state["pending_question"] = None
                    return state
                
                elif msg_lower in ["edit", "change", "modify"]:
                    # Allow editing - reset to category selection
                    slots["category"] = None
                    state["extracted_slots"] = slots
                    state["ticket_step"] = "awaiting_category"
                    state["expected_response_type"] = None
                    state["pending_question"] = None
                    description = slots.get("description", "")
                    return self._prepare_ticket_creation(state, description)
                
                elif msg_lower in ["cancel", "abort", "stop"]:
                    # Cancel the ticket
                    state["active_flow"] = None
                    state["ticket_step"] = None
                    state["extracted_slots"] = {}
                    state["expected_response_type"] = None
                    state["pending_question"] = None
                    state["final_response"] = "✅ Ticket creation cancelled. How else can I help you?"
                    state["selected_agent"] = "orchestrator"
                    return state
                
                else:
                    # Invalid response - re-ask with clear options
                    description = slots.get("description", "")
                    state["final_response"] = (
                        f"**Ticket Preview:**\n\n"
                        f"**Category:** {slots.get('category', 'Not selected')}\n"
                        f"**Description:** {description[:200]}{'...' if len(description) > 200 else ''}\n"
                        f"**Priority:** {slots.get('priority', 'Medium')}\n\n"
                        "⚠️ **Please choose an action:**\n"
                        "• Reply **'submit'** or **'yes'** to create this ticket\n"
                        "• Reply **'edit'** to modify the ticket\n"
                        "• Reply **'cancel'** to cancel"
                    )
                    return state
            
            # Fallback - repeat preview
            description = slots.get("description", "")
            return self._prepare_ticket_creation(state, description)
        
        # SENSITIVE COMPLAINT - Empathetic response with confirmation required
        if intent == IntentType.SENSITIVE_COMPLAINT:
            # Check if user is confirming ticket creation
            if state.get("expected_response_type") == "sensitive_confirmation":
                msg_lower = user_message.lower().strip()
                
                # FIX: Use word-level matching instead of exact match
                # This allows "yes raise a ticket", "yes please", etc.
                confirm_words = ["yes", "confirm", "proceed", "create", "submit", "raise", "ticket"]
                user_words = set(msg_lower.split())
                is_confirmed = bool(user_words & {"yes", "confirm", "proceed", "create", "submit"}) or \
                               ("raise" in user_words and "ticket" in user_words)
                
                if is_confirmed:
                    # User confirmed - create urgent ticket
                    slots["category"] = "Other"
                    slots["sub_category"] = "Complaint"
                    slots["priority"] = "Urgent"
                    slots["description"] = state.get("clarification_context", {}).get("original_message", user_message)
                    slots["is_sensitive"] = True
                    
                    state["extracted_slots"] = slots
                    state["confirmation_pending"] = True
                    state["confirmation_data"] = {
                        "action": "ticket_preview",
                        "ticket_data": slots,
                        "read_only": True  # Cannot edit sensitive complaints
                    }
                    state["final_response"] = (
                        "✅ **Creating Urgent Support Ticket**\n\n"
                        "Your ticket has been created with **Urgent** priority and will be handled confidentially.\n\n"
                        f"**Description:** {slots['description'][:200]}{'...' if len(slots['description']) > 200 else ''}\n\n"
                        "A support representative will contact you shortly. Your safety and well-being are our priority."
                    )
                    state["selected_agent"] = "ticket"
                    state["expected_response_type"] = None  # Clear pending state
                    state["pending_question"] = None
                    # FIX: Clear stale email state to prevent email_preview from appearing
                    state["email_draft"] = None
                    state["contact_faculty_step"] = None
                    state["active_flow"] = None
                    return state
                
                elif msg_lower in ["no", "cancel", "not now"]:
                    # User declined - offer alternatives
                    state["final_response"] = (
                        "I understand. If you'd prefer to discuss this differently, I can:\n\n"
                        "• **Connect you with a counselor** (say 'counselor')\n"
                        "• **Provide emergency contacts** (say 'emergency')\n"
                        "• **Help you with something else** (tell me what you need)\n\n"
                        "Your privacy and comfort are important to us."
                    )
                    state["active_flow"] = None
                    state["expected_response_type"] = None
                    state["pending_question"] = None
                    return state
                
                else:
                    # Invalid response - re-ask
                    state["final_response"] = (
                        "I need a clear response to proceed.\n\n"
                        "Would you like me to raise an urgent support ticket?\n"
                        "Please reply **'yes'** to proceed or **'no'** to cancel."
                    )
                    return state
            
            # First time seeing sensitive complaint - show empathetic message
            # FIX: Clear ALL stale email/flow state before entering sensitive complaint flow
            # This prevents stale email_draft from corrupting the sensitive complaint response
            state["email_draft"] = None
            state["contact_faculty_step"] = None
            state["faculty_matches"] = None
            state["resolved_faculty"] = None
            state["confirmation_data"] = None
            state["confirmation_pending"] = False
            
            state["active_flow"] = "sensitive_complaint"
            state["expected_response_type"] = "sensitive_confirmation"
            state["pending_question"] = "Confirm urgent ticket creation for sensitive issue"
            state["clarification_context"] = {
                "original_message": user_message,
                "intent": "sensitive_complaint"
            }
            
            state["final_response"] = (
                "🛡️ **I'm sorry to hear you're experiencing this.**\n\n"
                "Your safety and well-being are very important to us. "
                "This appears to be a sensitive matter that requires immediate attention.\n\n"
                "**I can raise an urgent support ticket** that will be:\n"
                "• Handled **confidentially** by our support team\n"
                "• Marked as **Urgent** priority\n"
                "• Reviewed by trained professionals\n\n"
                "**Would you like me to proceed with creating this ticket?**\n\n"
                "Reply **'yes'** to create the ticket, or **'no'** if you'd prefer to handle this differently."
            )
            state["selected_agent"] = "orchestrator"
            return state
        
        # ISSUE DESCRIPTION - Attempt self-resolution first
        if intent == IntentType.ISSUE_DESCRIPTION:
            if state.get("awaiting_resolution_feedback"):
                # Check if user said it didn't help
                if any(word in user_message.lower() for word in ["no", "didn't", "not resolved", "help more"]):
                    # Proceed to ticket creation
                    return self._prepare_ticket_creation(state, user_message)
                elif any(word in user_message.lower() for word in ["yes", "thank", "solved", "resolved"]):
                    state["final_response"] = "Great! I'm glad I could help. Is there anything else you need?"
                    state["active_flow"] = None
                    return state
            
            # First time - show self-resolution
            if state.get("self_resolution_response"):
                state["final_response"] = state["self_resolution_response"]
                state["awaiting_resolution_feedback"] = True
                state["active_flow"] = "ticket"
                return state
        
        # TICKET CREATE - Direct to creation flow
        if intent == IntentType.TICKET_CREATE:
            return self._prepare_ticket_creation(state, user_message)
        
        # TICKET STATUS - Show tickets
        if intent == IntentType.TICKET_STATUS:
            tickets = self.data_access.get_student_tickets(state["user_id"], limit=5)
            if tickets:
                ticket_lines = [
                    f"• **#{t['ticket_id']}** [{t['status']}] - {t['description'][:50]}"
                    for t in tickets
                ]
                state["final_response"] = "📋 **Your Recent Tickets:**\n\n" + "\n".join(ticket_lines)
            else:
                state["final_response"] = "You don't have any tickets. Would you like to raise one?"
            state["selected_agent"] = "ticket"
            return state
        
        # TICKET CLOSE - Close tickets immediately
        if intent == IntentType.TICKET_CLOSE:
            entities = state.get("entities", {})
            user_id = state["user_id"]
            
            if entities.get("close_all"):
                # Close all open tickets
                result = self.ticket_agent.close_all_tickets(user_id)
                
                if result.get("success"):
                    count = result.get("count", 0)
                    if count == 0:
                        state["final_response"] = (
                            "📋 **No Open Tickets**\n\n"
                            "You don't have any open tickets to close."
                        )
                    else:
                        state["final_response"] = (
                            f"✅ **Tickets Closed Successfully**\n\n"
                            f"All **{count}** of your open tickets have been closed.\n\n"
                            "If you need further assistance, feel free to raise a new ticket."
                        )
                else:
                    state["final_response"] = (
                        f"❌ **Unable to Close Tickets**\n\n"
                        f"{result.get('error', 'An error occurred. Please try again.')}"
                    )
            else:
                # Close specific ticket
                ticket_id = entities.get("ticket_id")
                if ticket_id:
                    result = self.ticket_agent.close_ticket(ticket_id, user_id)
                    
                    if result.get("success"):
                        state["final_response"] = (
                            f"✅ **Ticket Closed**\n\n"
                            f"Ticket **#{ticket_id}** has been closed successfully.\n\n"
                            "If you need further assistance, feel free to raise a new ticket."
                        )
                    else:
                        state["final_response"] = (
                            f"❌ **Unable to Close Ticket**\n\n"
                            f"{result.get('error', 'An error occurred. Please try again.')}"
                        )
                else:
                    state["final_response"] = (
                        "❓ **Which Ticket?**\n\n"
                        "Please specify which ticket you'd like to close:\n"
                        "• Say 'close ticket #ACE-1234' for a specific ticket\n"
                        "• Say 'close all my tickets' to close all open tickets"
                    )
            
            state["selected_agent"] = "ticket"
            return state
        
        state["selected_agent"] = "ticket"
        return state
    
    def _prepare_ticket_creation(self, state: AgentState, description: str) -> AgentState:
        """Prepare ticket creation with category selection"""
        slots = state.get("extracted_slots", {})
        
        # Check if category already selected
        if slots.get("category"):
            # Show preview
            state["confirmation_pending"] = True
            state["confirmation_data"] = {
                "action": "ticket_preview",
                "ticket_data": {
                    "category": slots["category"],
                    "description": description,
                    "priority": slots.get("priority", "Medium")
                }
            }
            state["final_response"] = (
                f"**Ticket Preview:**\n\n"
                f"**Category:** {slots['category']}\n"
                f"**Description:** {description[:200]}{'...' if len(description) > 200 else ''}\n"
                f"**Priority:** {slots.get('priority', 'Medium')}\n\n"
                "Would you like to:\n"
                "• **Edit** - Modify the ticket\n"
                "• **Submit** - Create this ticket\n"
                "• **Cancel** - Cancel"
            )
        else:
            # Ask for category
            categories = list(CATEGORIES.keys())
            cat_list = "\n".join([f"{i+1}. {cat}" for i, cat in enumerate(categories)])
            state["final_response"] = (
                f"I'll help you create a support ticket for: *{description[:100]}*\n\n"
                f"Please select a category:\n\n{cat_list}\n\n"
                "Reply with the number of your choice."
            )
            slots["description"] = description
            state["extracted_slots"] = slots
            state["active_flow"] = "ticket"
            state["ticket_step"] = "awaiting_category"
        
        return state
    
    # =========================================================================
    # HELPER METHODS: Contact Suggestions & Session Management
    # =========================================================================
    
    def _should_suggest_contact(self, state: AgentState) -> bool:
        """
        Determine if college contact should be suggested based on query sensitivity.
        
        Args:
            state: Current agent state
            
        Returns:
            True if contact should be suggested, False otherwise
        """
        # FIX: Don't suggest contact during active structured flows (email, ticket, faculty)
        # This prevents noise during multi-step flows
        active_flow = state.get("active_flow")
        if active_flow in ["email", "ticket", "contact_faculty"]:
            return False
        
        query_text = state["user_message"].lower()
        response_text = state.get("final_response", "").lower()
        
        # Check for sensitive keywords in query or response
        has_sensitive_keyword = any(
            keyword in query_text or keyword in response_text
            for keyword in CONTACT_SUGGESTED_KEYWORDS
        )
        
        # Check if it's a sensitive intent type
        sensitive_intents = [
            IntentType.COLLEGE_RAG_QUERY,
            IntentType.ACADEMIC_PROGRAM_QUERY,
            IntentType.SENSITIVE_COMPLAINT,
            IntentType.ISSUE_DESCRIPTION
        ]
        is_sensitive_intent = state.get("intent_enum") in sensitive_intents
        
        # Don't suggest if contact already present in response
        contact_already_present = COLLEGE_CONTACT_NUMBER in state.get("final_response", "")
        
        # Suggest if sensitive AND not already present
        should_suggest = (has_sensitive_keyword or is_sensitive_intent) and not contact_already_present
        
        if should_suggest:
            print(f"[CONTACT] Contact suggestion triggered - keywords: {has_sensitive_keyword}, intent: {is_sensitive_intent}")
        
        return should_suggest
    
    def _add_contact_suggestion(self, response: str) -> str:
        """
        Append college contact information to response.
        
        Args:
            response: Original response text
            
        Returns:
            Response with contact information appended
        """
        return (
            f"{response}\n\n"
            f"---\n\n"
            f"📞 **For official confirmation or detailed assistance:**\n"
            f"**ACE Engineering College**\n"
            f"Contact: **{COLLEGE_CONTACT_NUMBER}**\n"
            f"*(Available: {COLLEGE_CONTACT_HOURS})*"
        )
    
    def _add_refresh_suggestion(self, response: str) -> str:
        """
        Add refresh suggestion when session reaches message limit.
        
        Args:
            response: Original response text
            
        Returns:
            Response with refresh suggestion appended
        """
        return (
            f"{response}\n\n"
            f"---\n\n"
            f"💡 **Session Tip:** You've reached {MAX_SESSION_MESSAGES} messages in this chat session. "
            f"For optimal performance, consider refreshing the page to start a new session. "
            f"Your previous conversations are saved and accessible anytime!"
        )
    
    # =========================================================================
    # PUBLIC API: process_message
    # =========================================================================
    
    def process_message(
        self,
        user_message: str,
        user_id: str,
        session_id: str,
        mode: str = "auto",
        student_profile: Optional[Dict] = None
    ) -> Dict:
        """
        Main entry point for processing user messages.
        
        Args:
            user_message: User's input message
            user_id: Student email
            session_id: Session UUID
            mode: 'auto', 'email', 'ticket', or 'faculty'
            student_profile: Optional student data
            
        Returns:
            Dict with response type and content
        """
        print(f"\n{'='*60}")
        print(f"[ORCHESTRATOR] Processing: '{user_message[:50]}...'")
        print(f"{'='*60}")
        
        # =====================================================================
        # PHASE 2: Session Management & Deduplication
        # =====================================================================
        
        # 1. Update session activity timestamp
        update_session_activity(session_id)
        
        # 2. Check for session timeout (30 min inactivity)
        if check_session_timeout(session_id):
            print(f"[SESSION] Session timed out, restarting fresh")
            # Session expired, all paused flows cleared automatically
        
        # 3. Initialize turn logging metadata (will complete at end)
        turn_metadata = {
            "user_id": user_id,
            "session_id": session_id,
            "user_message": user_message,
            "intent": None,
            "routing_decision": None,
            "agent_called": None,
            "agent_status": None,
            "validation_outcome": None,
            "side_effects": [],
            "bot_response": None
        }
        
        # Retrieve short-term memory and active flow from session
        short_term_memory: ShortTermMemory = {
            "last_intent": None,
            "last_unresolved_goal": None,
            "last_ticket_id": None,
            "last_referenced_entity": None,
            "last_faculty_id": None
        }
        
        active_flow = None
        extracted_slots = {}
        contact_faculty_step = None
        ticket_step = None
        faculty_matches = None
        resolved_faculty = None
        email_draft = None
        last_bot_response = None
        conversation_state = {}
        
        # New metadata fields for better state tracking
        pending_question = None
        expected_response_type = None
        clarification_context = {}

        
        try:
            # Retrieve last 25 messages for context (user preference: understand from last 5 interactions)
            # This provides ~5 user-bot interaction pairs for context understanding
            session_history = self.chat_memory.get_session_history(session_id, user_id, limit=50)
            history_count = len(session_history) if session_history else 0
            print(f"[DEBUG] Session history retrieved: {history_count} messages")
            
            # Check if session is approaching limit
            session_needs_refresh = history_count >= MAX_SESSION_MESSAGES
            
            if session_history:
                # IMPROVED: Merge state from all messages (prefer latest non-null)
                # Process messages in reverse order (newest first)
                # CRITICAL FIX: Track when a flow was completed/cancelled to prevent
                # stale email_draft/resolved_faculty from resurrecting
                email_flow_was_cleared = False
                
                for msg in reversed(session_history):
                    if msg.get("role") == "bot":
                        metadata = msg.get("metadata", {})
                        print(f"[DEBUG] Bot message metadata type: {type(metadata)}, content: {str(metadata)[:200]}")
                        
                        # Parse metadata if it's a JSON string
                        if isinstance(metadata, str):
                            try:
                                metadata = json.loads(metadata)
                            except:
                                metadata = {}
                        
                        # CRITICAL: Detect flow completion/cancellation
                        # If we already found an active_flow but this older message has it cleared,
                        # it means the flow was completed/cancelled at some point
                        if "active_flow" in metadata and not metadata.get("active_flow"):
                            if active_flow or email_flow_was_cleared:
                                # Flow was explicitly cleared in history — do NOT merge older email state
                                pass
                            else:
                                email_flow_was_cleared = True
                                print(f"[DEBUG] Flow completion detected — stopping email state merge from older messages")
                        
                        # IMPROVED: Merge state fields (prefer latest non-null)
                        # Active flow
                        if metadata.get("active_flow") and not active_flow:
                            active_flow = metadata["active_flow"]
                            print(f"[DEBUG] Retrieved active_flow: {active_flow}")
                        
                        # Extracted slots (merge all slots, prefer latest)
                        # GUARD: Don't merge email-related slots from completed flows
                        if metadata.get("extracted_slots") and not email_flow_was_cleared:
                            for k, v in metadata["extracted_slots"].items():
                                if v and (k not in extracted_slots or not extracted_slots[k]):
                                    extracted_slots[k] = v
                            print(f"[DEBUG] Merged extracted_slots: {extracted_slots}")
                        
                        # Flow steps
                        if metadata.get("contact_faculty_step") and not contact_faculty_step:
                            contact_faculty_step = metadata["contact_faculty_step"]
                            print(f"[DEBUG] Retrieved contact_faculty_step: {contact_faculty_step}")
                        
                        if metadata.get("ticket_step") and not ticket_step:
                            ticket_step = metadata["ticket_step"]
                            print(f"[DEBUG] Retrieved ticket_step: {ticket_step}")
                        
                        # NEW: Pending question and expected response type
                        if metadata.get("pending_question") and not pending_question:
                            pending_question = metadata["pending_question"]
                            print(f"[DEBUG] Retrieved pending_question: {pending_question}")
                        
                        if metadata.get("expected_response_type") and not expected_response_type:
                            expected_response_type = metadata["expected_response_type"]
                            print(f"[DEBUG] Retrieved expected_response_type: {expected_response_type}")
                        
                        # NEW: Clarification context
                        if metadata.get("clarification_context") and not clarification_context:
                            clarification_context = metadata["clarification_context"]
                        
                        # Faculty-related state — GUARD against stale data
                        if not email_flow_was_cleared:
                            if metadata.get("faculty_matches") and not faculty_matches:
                                faculty_matches = metadata["faculty_matches"]
                            
                            if metadata.get("resolved_faculty") and not resolved_faculty:
                                resolved_faculty = metadata["resolved_faculty"]
                            
                            # Email draft
                            if metadata.get("email_draft") and not email_draft:
                                email_draft = metadata["email_draft"]
                        
                        # Short-term memory
                        if metadata.get("last_intent") and not short_term_memory["last_intent"]:
                            short_term_memory["last_intent"] = metadata["last_intent"]
                        
                        # Conversation state
                        if metadata.get("conversation_state") and not conversation_state:
                            conversation_state = metadata["conversation_state"]
                        
                        # Get last bot response for context
                        if not last_bot_response:
                            last_bot_response = msg.get("content", "")
        except Exception as e:
            print(f"[WARN] Could not retrieve session: {e}")
        
        # =====================================================================
        # FIX: POST-RECONSTRUCTION VALIDATION
        # Clear stale expected_response_type if the corresponding slot is already filled
        # This prevents infinite follow-up loops from resurrecting old questions
        # =====================================================================
        if expected_response_type:
            response_type_to_slot = {
                "email_type_selection": "email_type",
                "recipient_email": "recipient_email",
                "recipient_name": "recipient_name",
                "faculty_name": "faculty_name",
                "faculty_selection": "resolved_faculty",
                "email_purpose": "purpose",
                "email_confirmation": "email_action",
                "category_selection": "category",
                "ticket_confirmation": "confirmed",
                "sensitive_confirmation": "confirmed",
                "clarification_choice": "clarification_choice"
            }
            slot_name = response_type_to_slot.get(expected_response_type, expected_response_type)
            
            if slot_name in extracted_slots and extracted_slots[slot_name]:
                print(f"[DEBUG] STALE STATE DETECTED: Slot '{slot_name}' already filled, clearing expected_response_type='{expected_response_type}'")
                expected_response_type = None
                pending_question = None
        
        # =====================================================================
        # CRITICAL FIX: Clear stale email_draft BEFORE graph invoke
        # If user's message looks like a NEW query (not email continuation), clear all email state
        # This prevents FAQ queries from returning stale email previews
        # =====================================================================
        msg_lower = user_message.lower().strip()
        
        # Keywords that indicate a NEW query (not email flow continuation)
        FAQ_RESET_INDICATORS = [
            "course", "courses", "college", "department", "fee", "policy", "rules",
            "timing", "placement", "hostel", "library", "founder", "what is", "what are",
            "how many", "list", "is there", "are there", "tell me", "capacity"
        ]
        
        # Keywords that indicate email flow (do NOT reset for these)
        EMAIL_FLOW_KEYWORDS = [
            "send", "email", "mail", "yes", "no", "confirm", "cancel", "edit",
            "subject", "body", "@gmail", "@yahoo", "@outlook", "@"
        ]
        
        is_faq_query = any(kw in msg_lower for kw in FAQ_RESET_INDICATORS)
        is_email_related = any(kw in msg_lower for kw in EMAIL_FLOW_KEYWORDS) or "@" in msg_lower
        
        # If query looks like FAQ and NOT email-related, clear ALL stale email/flow state
        if is_faq_query and not is_email_related:
            if email_draft or active_flow:
                print(f"[PRE-GRAPH] FAQ query detected, clearing stale email/flow state: email_draft={bool(email_draft)}, active_flow={active_flow}")
                email_draft = None
                active_flow = None
                contact_faculty_step = None
                ticket_step = None
                extracted_slots = {}
                pending_question = None
                expected_response_type = None
                clarification_context = {}
                faculty_matches = None
                resolved_faculty = None
        
        # =====================================================================
        # CRITICAL FIX: Clear stale email state on NEW email intents
        # If user's message contains email action keywords (send email, write email, etc.)
        # AND there's a stale active email flow from previous conversation,
        # CLEAR ALL email state to extract fresh data from CURRENT message only
        # This prevents old email addresses/subjects/bodies from being reused
        # =====================================================================
        NEW_EMAIL_INTENT_KEYWORDS = [
            "send email", "send an email", "send a email", "send mail",
            "write email", "write an email", "write a mail",
            "compose email", "draft email", "email to",
            "send email to", "send an email to", "write email to",
            "email prof", "email dr", "email faculty", "email professor",
            "i want to send email", "i want to email"
        ]
        
        # Check if this is a NEW email intent (not a continuation like "yes", "confirm", etc.)
        is_new_email_intent = any(kw in msg_lower for kw in NEW_EMAIL_INTENT_KEYWORDS)
        
        # Continuation keywords that should NOT trigger reset
        EMAIL_CONTINUATION_KEYWORDS = [
            "yes", "no", "confirm", "cancel", "edit", "change", "okay", "ok",
            "subject", "body", "that's correct", "looks good", "send it"
        ]
        is_email_continuation = any(kw in msg_lower for kw in EMAIL_CONTINUATION_KEYWORDS) and len(msg_lower) < 50
        
        # If this is a NEW email intent AND not a continuation response, clear stale email state
        if is_new_email_intent and not is_email_continuation:
            if email_draft or active_flow in ["contact_faculty", "email"] or extracted_slots:
                print(f"[PRE-GRAPH] NEW EMAIL INTENT detected, clearing stale email state to extract fresh data")
                print(f"[PRE-GRAPH] Clearing: email_draft={bool(email_draft)}, active_flow={active_flow}, extracted_slots={extracted_slots}")
                
                # Clear ALL email-related state
                email_draft = None
                
                # Only clear email flow, preserve ticket flow if active
                if active_flow in ["contact_faculty", "email"]:
                    active_flow = None
                    contact_faculty_step = None
                    extracted_slots = {}  # Clear ALL slots for fresh extraction
                    pending_question = None
                    expected_response_type = None
                    faculty_matches = None
                    resolved_faculty = None
                    
                print(f"[PRE-GRAPH] Email state cleared successfully - fresh extraction will occur from current message")
        
        print(f"[DEBUG] Final state before graph invoke:")
        print(f"  - active_flow: {active_flow}")
        print(f"  - ticket_step: {ticket_step}")
        print(f"  - extracted_slots: {extracted_slots}")
        print(f"  - pending_question: {pending_question}")
        print(f"  - expected_response_type: {expected_response_type}")
        print(f"  - email_draft: {bool(email_draft) if email_draft else 'None'}")
        
        
        # Initialize state
        initial_state: AgentState = {
            "user_id": user_id,
            "session_id": session_id,
            "user_message": user_message,
            "user_role": student_profile.get("role", "student") if student_profile else "student",
            "student_profile": student_profile,
            "intent": "",
            "intent_enum": None,
            "confidence": 0.0,
            "entities": {},
            "is_multi_intent": False,
            "secondary_intent": None,
            "reasoning": "",
            "requires_clarification": False,
            "clarification_question": None,
            "active_flow": active_flow,
            "contact_faculty_step": contact_faculty_step,
            "ticket_step": ticket_step,
            # NEW: Follow-up question tracking
            "pending_question": pending_question,
            "expected_response_type": expected_response_type,
            "clarification_context": clarification_context,
            "extracted_slots": extracted_slots,
            "confirmation_pending": False,
            "confirmation_data": None,
            "email_draft": email_draft,
            "pending_action_data": None,
            "self_resolution_attempted": False,
            "self_resolution_response": None,
            "awaiting_resolution_feedback": False,
            "validation_passed": True,
            "validation_errors": [],
            "final_response": None,
            "selected_agent": "",
            "execution_plan": None,
            "short_term_memory": short_term_memory,
            "conversation_state": conversation_state,
            "last_bot_response": last_bot_response,
            "mode": mode,
            "query_type": None,
            "force_rag": False,
            "resolved_faculty": resolved_faculty,
            "faculty_matches": faculty_matches
        }
        
        # Run the LangGraph pipeline
        final_state = self.graph.invoke(initial_state)
        
        # Prepare response
        response_type = "information"
        response_content = final_state.get("final_response", "Request processed.")
        
        # =====================================================================
        # FIX: Post-processing safeguard — clear stale email_draft if intent is
        # not email-related. This prevents cascading stale state issues.
        # =====================================================================
        current_intent_enum = final_state.get("intent_enum")
        email_intents = [IntentType.EMAIL_ACTION, IntentType.FACULTY_CONTACT]
        
        if final_state.get("email_draft") and current_intent_enum not in email_intents:
            print(f"[POST-PROCESSING] Clearing stale email_draft — current intent is {current_intent_enum}, not email-related")
            final_state["email_draft"] = None
        
        if final_state.get("requires_clarification"):
            response_type = "clarification_request"
        elif final_state.get("email_draft") and current_intent_enum in email_intents:
            # Only show email preview if the CURRENT intent is email-related
            response_type = "email_preview"
            response_content = final_state.get("confirmation_data") or {
                "preview": final_state["email_draft"],
                "action": "email_preview"
            }
        elif final_state.get("confirmation_pending"):
            response_type = "confirmation_request"
            response_content = final_state.get("confirmation_data") or {
                "message": final_state.get("final_response"),
                "action": "confirm"
            }
        
        # POST-PROCESSING: Add contact suggestion and refresh warning
        # This happens AFTER all agent processing is complete
        
        # 1. Add college contact suggestion for sensitive queries
        if self._should_suggest_contact(final_state):
            final_state["final_response"] = self._add_contact_suggestion(
                final_state.get("final_response", "")
            )
            print(f"[CONTACT] College contact appended to response")
        
        # 2. Add refresh suggestion if session is at message limit
        if session_needs_refresh:
            final_state["final_response"] = self._add_refresh_suggestion(
                final_state.get("final_response", "")
            )
            print(f"[SESSION] Refresh suggestion appended - session at {history_count} messages")
        
        # Save to memory with conversation state
        current_step = final_state.get("ticket_step") or final_state.get("contact_faculty_step")
        turns = conversation_state.get("turns_in_current_flow", 0) + 1 if final_state.get("active_flow") else 0
        
        # =====================================================================
        # PHASE 2: Compact State Persistence (Lightweight Storage)
        # =====================================================================
        # Instead of saving full state, use compact summary
        metadata = compact_state_summary(final_state)
        
        # Add conversation state for compatibility
        metadata["conversation_state"] = {
            "current_intent": final_state.get("intent"),
            "current_step": current_step,
            "filled_slots": metadata.get("active_slots", {}),
            "last_action": final_state.get("selected_agent"),
            "turns_in_current_flow": turns
        }
        
        print(f"[DEBUG] Saving compact metadata: active_flow={metadata.get('active_flow')}, expected_response_type={metadata.get('expected_response_type')}, slots={list(metadata.get('active_slots', {}).keys())}")

        
        self.chat_memory.save_message(
            user_id=user_id,
            session_id=session_id,
            role="user",
            content=user_message,
            intent=final_state.get("intent"),
            selected_agent=final_state.get("selected_agent"),
            metadata=metadata
        )
        
        self.chat_memory.save_message(
            user_id=user_id,
            session_id=session_id,
            role="bot",
            content=final_state.get("final_response", ""),
            intent=final_state.get("intent"),
            selected_agent=final_state.get("selected_agent"),
            metadata=metadata
        )
        
        # =====================================================================
        # PHASE 2: Complete Turn Logging
        # =====================================================================
        log_turn(
            user_id=user_id,
            session_id=session_id,
            user_message=user_message,
            intent=final_state.get("intent"),
            routing_decision=final_state.get("selected_agent"),
            agent_called=final_state.get("selected_agent"),
            agent_status="success" if not final_state.get("validation_errors") else "error",
            validation_outcome="passed" if final_state.get("validation_passed") else "failed",
            side_effects=[],  # Will be populated by agents in Phase 3
            bot_response=final_state.get("final_response", ""),
            metadata={
                "confidence": final_state.get("confidence", 0.0),
                "active_flow": final_state.get("active_flow"),
                "response_type": response_type
            }
        )
        
        return {
            "type": response_type,
            "agent": final_state.get("selected_agent", "orchestrator"),
            "content": response_content,
            "metadata": {
                "intent": final_state.get("intent"),
                "confidence": final_state.get("confidence", 0.0),
                "mode": mode,
                "active_flow": final_state.get("active_flow"),
                "extracted_slots": final_state.get("extracted_slots", {})
            }
        }
    
    # =========================================================================
    # PUBLIC API: execute_confirmed_action
    # =========================================================================
    
    # Track executed actions to prevent double-execution (session-scoped)
    _executed_actions = set()

    @staticmethod
    def _action_hash(user_id: str, action_data: Dict) -> str:
        """Create a unique hash for an action to detect duplicates."""
        key_parts = [
            user_id,
            action_data.get("action", ""),
            str(action_data.get("preview", {}).get("to", "")),
            str(action_data.get("preview", {}).get("subject", ""))[:50],
            str(action_data.get("ticket_data", {}).get("description", ""))[:50],
        ]
        return hashlib.md5("|".join(key_parts).encode()).hexdigest()

    def execute_confirmed_action(
        self,
        user_id: str,
        session_id: str,
        action_data: Dict,
        student_profile: Optional[Dict] = None
    ) -> Dict:
        """
        Execute a confirmed action with full governance:
        - Rate limit check before execution
        - Double-execution guard
        - Usage counter increment after success
        - Activity logging after success
        
        Args:
            user_id: Student email
            session_id: Session UUID
            action_data: Action parameters from confirmation
            student_profile: Optional student data
            
        Returns:
            Dict with execution result
        """
        print(f"[EXECUTE] Confirmed action: {action_data.get('action', 'unknown')} for {user_id}")
        
        action_type = action_data.get("action", "")
        
        # =====================================================================
        # GUARD 1: Double-execution prevention
        # =====================================================================
        action_id = self._action_hash(user_id, action_data)
        if action_id in self._executed_actions:
            print(f"[EXECUTE] ⛔ DUPLICATE blocked: {action_id}")
            return {
                "success": False,
                "message": "⚠️ This action has already been executed. Please start a new request."
            }
        
        try:
            # EMAIL SEND
            if action_type in ["send_email", "email_preview"]:
                # =============================================================
                # GUARD 2: Rate limit check BEFORE execution
                # =============================================================
                allowed, remaining, max_allowed = LimitsService.check_daily_limit(user_id, 'email')
                if not allowed:
                    print(f"[EXECUTE] ⛔ RATE LIMIT hit for {user_id}: emails {remaining}/{max_allowed}")
                    return {
                        "success": False,
                        "message": f"📧 Daily email limit reached ({max_allowed}/{max_allowed} used).\nPlease try again tomorrow."
                    }
                
                email_data = action_data.get("preview") or action_data
                result = self.email_agent.send_email(
                    to_email=email_data.get("to", ""),
                    subject=email_data.get("subject", ""),
                    body=email_data.get("body", "")
                )
                
                if result.get("success"):
                    # Mark as executed to prevent repeats
                    self._executed_actions.add(action_id)
                    
                    # GOVERNANCE: Increment usage counter
                    try:
                        LimitsService.increment_usage(user_id, 'email')
                        print(f"[EXECUTE] ✅ Usage incremented: {user_id} email")
                    except Exception as ue:
                        print(f"[EXECUTE] ⚠️ Usage increment failed (email sent): {ue}")
                    
                    # GOVERNANCE: Log activity
                    try:
                        to_name = email_data.get('to_name', email_data.get('to', 'recipient'))
                        ActivityService.log_activity(
                            user_id,
                            ActivityType.EMAIL_SENT,
                            f"Email sent to {to_name} — Subject: {email_data.get('subject', 'N/A')[:60]}"
                        )
                        print(f"[EXECUTE] ✅ Activity logged: EMAIL_SENT for {user_id}")
                    except Exception as ae:
                        print(f"[EXECUTE] ⚠️ Activity log failed: {ae}")
                    
                    return {
                        "success": True,
                        "message": f"✅ Email sent successfully to {email_data.get('to_name', email_data.get('to'))}!"
                    }
                else:
                    return {
                        "success": False,
                        "message": f"❌ Failed to send email: {result.get('error', 'Unknown error')}"
                    }
            
            # TICKET CREATE
            elif action_type == "ticket_preview":
                # =============================================================
                # GUARD 2: Rate limit check BEFORE execution
                # =============================================================
                allowed, remaining, max_allowed = LimitsService.check_daily_limit(user_id, 'ticket')
                if not allowed:
                    print(f"[EXECUTE] ⛔ RATE LIMIT hit for {user_id}: tickets {remaining}/{max_allowed}")
                    return {
                        "success": False,
                        "message": f"🎫 Daily ticket limit reached ({max_allowed}/{max_allowed} used).\nPlease try again tomorrow."
                    }
                
                ticket_data = action_data.get("ticket_data", {})
                ticket_data["student_email"] = user_id
                
                # Normalize subcategory
                category = ticket_data.get("category", "Other")
                if category in CATEGORIES:
                    ticket_data["sub_category"] = CATEGORIES[category][0]
                else:
                    ticket_data["sub_category"] = "General Query"
                
                result = self.ticket_agent.create_ticket(ticket_data)
                
                if result.get("success"):
                    ticket_id = result.get("ticket_id")
                    
                    # Mark as executed to prevent repeats
                    self._executed_actions.add(action_id)
                    
                    # GOVERNANCE: Increment usage counter
                    try:
                        LimitsService.increment_usage(user_id, 'ticket')
                        print(f"[EXECUTE] ✅ Usage incremented: {user_id} ticket")
                    except Exception as ue:
                        print(f"[EXECUTE] ⚠️ Usage increment failed (ticket created): {ue}")
                    
                    # GOVERNANCE: Log activity
                    try:
                        ActivityService.log_activity(
                            user_id,
                            ActivityType.TICKET_CREATED,
                            f"Ticket #{ticket_id} created — {category}: {ticket_data.get('description', 'N/A')[:60]}"
                        )
                        print(f"[EXECUTE] ✅ Activity logged: TICKET_CREATED for {user_id}")
                    except Exception as ae:
                        print(f"[EXECUTE] ⚠️ Activity log failed: {ae}")
                    
                    return {
                        "success": True,
                        "message": f"✅ Ticket **#{ticket_id}** created successfully!\n\nYou'll receive updates on your registered email.",
                        "ticket_id": ticket_id
                    }
                else:
                    return {
                        "success": False,
                        "message": f"❌ Failed to create ticket: {result.get('error', 'Unknown error')}"
                    }
            
            else:
                return {
                    "success": False,
                    "message": f"Unknown action type: {action_type}"
                }
                
        except Exception as e:
            print(f"[EXECUTE] Error: {e}")
            return {
                "success": False,
                "message": f"Error executing action: {str(e)}"
            }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_orchestrator_instance = None

def get_orchestrator() -> OrchestratorAgent:
    """Get singleton instance of OrchestratorAgent"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = OrchestratorAgent()
    return _orchestrator_instance


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Testing Orchestrator Agent")
    print("=" * 60 + "\n")
    
    orchestrator = OrchestratorAgent()
    
    # Test 1: Academic query
    result = orchestrator.process_message(
        user_message="What courses are offered?",
        user_id="test@student.com",
        session_id="test-session-1",
        mode="auto"
    )
    print(f"Test 1 - Academic Query:")
    print(f"  Type: {result['type']}")
    print(f"  Agent: {result['agent']}")
    print(f"  Response: {str(result['content'])[:100]}...\n")
