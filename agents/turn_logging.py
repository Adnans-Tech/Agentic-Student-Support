"""
Structured Logging Service
Logs each turn with intent, routing, agent status, validation, and side effects
"""
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
import os


class TurnLogger:
    """
    Logs each conversation turn in structured format
    Enables traceability and debugging
    """
    
    def __init__(self, log_file: str = "data/turn_logs.jsonl"):
        self.log_file = log_file
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    def log_turn(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
        intent: Optional[str] = None,
        routing_decision: Optional[str] = None,
        agent_called: Optional[str] = None,
        agent_status: Optional[str] = None,
        validation_outcome: Optional[str] = None,
        side_effects: Optional[List[str]] = None,
        bot_response: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log a complete turn
        
        Args:
            user_id: User email
            session_id: Session UUID
            user_message: User's input
            intent: Detected intent
            routing_decision: Which agent to call
            agent_called: Agent that was invoked
            agent_status: success/error/needs_input/needs_confirmation
            validation_outcome: passed/failed/skipped
            side_effects: List of actions (email_sent, ticket_created, etc.)
            bot_response: Final message shown to user
            metadata: Additional context
        """
        log_entry = {
            "turn_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "session_id": session_id,
            "user_message": user_message[:200],  # Truncate for storage
            "intent": intent,
            "routing_decision": routing_decision,
            "agent_called": agent_called,
            "agent_status": agent_status,
            "validation_outcome": validation_outcome,
            "side_effects": side_effects or [],
            "bot_response": bot_response[:200] if bot_response else None,  # Truncate
            "metadata": metadata or {}
        }
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[TURN_LOG] Failed to write log: {e}")
    
    def get_recent_turns(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve recent turns for a session"""
        if not os.path.exists(self.log_file):
            return []
        
        turns = []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get("session_id") == session_id:
                            turns.append(entry)
                    except:
                        continue
        except Exception as e:
            print(f"[TURN_LOG] Failed to read logs: {e}")
        
        # Return most recent
        return turns[-limit:]


# Global instance
_turn_logger = TurnLogger()


def log_turn(
    user_id: str,
    session_id: str,
    user_message: str,
    intent: Optional[str] = None,
    routing_decision: Optional[str] = None,
    agent_called: Optional[str] = None,
    agent_status: Optional[str] = None,
    validation_outcome: Optional[str] = None,
    side_effects: Optional[List[str]] = None,
    bot_response: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Log a turn (module-level convenience function)"""
    _turn_logger.log_turn(
        user_id=user_id,
        session_id=session_id,
        user_message=user_message,
        intent=intent,
        routing_decision=routing_decision,
        agent_called=agent_called,
        agent_status=agent_status,
        validation_outcome=validation_outcome,
        side_effects=side_effects,
        bot_response=bot_response,
        metadata=metadata
    )
