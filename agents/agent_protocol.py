"""
Agent Response Protocol & Validation
Defines structured output format for all agents and validation utilities
"""
from typing import Dict, Any, Optional, List, Literal
from enum import Enum
from datetime import datetime
import json


class AgentResponse:
    """
    Standardized response format for all agents.
    
    Schema:
        status: "success" | "error" | "needs_input" | "needs_confirmation"
        message: User-facing text (agent-generated, not orchestrator)
        resolved_entities: Dict of confirmed entities (e.g., {"faculty": {...}, "purpose": "..."})
        artifacts: Dict of generated content (e.g., {"email_draft": {...}})
        next_expected: What input is needed next (e.g., "email_confirmation")
        side_effects: List of actions taken (e.g., ["email_sent", "ticket_created"])
        metadata: Agent-specific data
    """
    
    VALID_STATUSES = {"success", "error", "needs_input", "needs_confirmation"}
    
    @staticmethod
    def create(
        status: Literal["success", "error", "needs_input", "needs_confirmation"],
        message: str,
        resolved_entities: Optional[Dict[str, Any]] = None,
        artifacts: Optional[Dict[str, Any]] = None,
        next_expected: Optional[str] = None,
        side_effects: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        # --- New structured output fields ---
        agent_name: Optional[str] = None,
        detected_intent: Optional[str] = None,
        confidence: Optional[float] = None,
        required_slots: Optional[Dict[str, Any]] = None,
        action_type: Optional[str] = None,        # "answer", "email_send", "ticket_create", "clarify"
        preview_or_final: Optional[str] = None,   # "preview" or "final"
        citations: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a valid agent response with structured output fields."""
        return {
            "status": status,
            "message": message,
            "resolved_entities": resolved_entities or {},
            "artifacts": artifacts or {},
            "next_expected": next_expected,
            "side_effects": side_effects or [],
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
            # Structured output fields
            "agent_name": agent_name,
            "detected_intent": detected_intent,
            "confidence": confidence,
            "required_slots": required_slots or {},
            "action_type": action_type,
            "preview_or_final": preview_or_final,
            "citations": citations or []
        }
    
    @staticmethod
    def validate(response: Any) -> tuple[bool, Optional[str]]:
        """
        Validate agent response schema
        
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(response, dict):
            return False, f"Response must be dict, got {type(response)}"
        
        # Required fields
        required = ["status", "message"]
        for field in required:
            if field not in response:
                return False, f"Missing required field: {field}"
        
        # Validate status
        if response["status"] not in AgentResponse.VALID_STATUSES:
            return False, f"Invalid status: {response['status']}, must be one of {AgentResponse.VALID_STATUSES}"
        
        # Validate message is string
        if not isinstance(response["message"], str):
            return False, f"Message must be string, got {type(response['message'])}"
        
        # Validate optional fields types
        if "resolved_entities" in response and not isinstance(response["resolved_entities"], dict):
            return False, "resolved_entities must be dict"
        
        if "artifacts" in response and not isinstance(response["artifacts"], dict):
            return False, "artifacts must be dict"
        
        if "side_effects" in response and not isinstance(response["side_effects"], list):
            return False, "side_effects must be list"
        
        return True, None
    
    @staticmethod
    def wrap_legacy_string(text: str, status: str = "success") -> Dict[str, Any]:
        """
        Compatibility wrapper for old agents that return plain strings
        """
        return AgentResponse.create(
            status=status,
            message=text,
            resolved_entities={},
            artifacts={},
            metadata={"legacy_wrapper": True}
        )
    
    @staticmethod
    def error(message: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Create error response"""
        return AgentResponse.create(
            status="error",
            message=f"❌ {message}",
            metadata=metadata or {}
        )
    
    @staticmethod
    def success(message: str, side_effects: Optional[List[str]] = None, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Create success response"""
        return AgentResponse.create(
            status="success",
            message=f"✅ {message}",
            side_effects=side_effects or [],
            metadata=metadata or {}
        )


def safe_agent_call(agent_func, *args, **kwargs) -> Dict[str, Any]:
    """
    Safely call agent function with automatic validation and error handling
    
    Usage:
        result = safe_agent_call(faq_agent.process, user_query, session_id)
    """
    try:
        response = agent_func(*args, **kwargs)
        
        # If agent returns plain string (legacy), wrap it
        if isinstance(response, str):
            print(f"[WARN] Agent {agent_func.__name__} returned string, wrapping in protocol")
            return AgentResponse.wrap_legacy_string(response)
        
        # Validate structured response
        is_valid, error = AgentResponse.validate(response)
        if not is_valid:
            print(f"[ERROR] Agent {agent_func.__name__} returned invalid response: {error}")
            print(f"[ERROR] Raw response: {response}")
            return AgentResponse.error(
                "An internal error occurred. Please try again.",
                metadata={"validation_error": error, "agent": agent_func.__name__}
            )
        
        return response
    
    except Exception as e:
        print(f"[ERROR] Agent {agent_func.__name__} crashed: {str(e)}")
        import traceback
        traceback.print_exc()
        return AgentResponse.error(
            "An internal error occurred. Please try again.",
            metadata={"exception": str(e), "agent": agent_func.__name__}
        )


def compact_state_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    """Create a lightweight summary of the state for storage"""
    # Helper to serialize enums
    def serialize(obj):
        if isinstance(obj, Enum):
            return obj.value
        return obj

    return {
        "intent": serialize(state.get("intent_enum")),
        "active_flow": state.get("active_flow"),
        "active_slots": state.get("extracted_slots", {}),
        "expected_response_type": state.get("expected_response_type"),
        "start_time": state.get("start_time")
    }
