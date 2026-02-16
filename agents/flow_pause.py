"""
Flow Pausing & Session Management
Manages paused flows with session-based expiration
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import time


class FlowPauseManager:
    """
    Manages paused conversation flows
    Flows expire at session end (30-minute inactivity or explicit logout)
    """
    
    def __init__(self, inactivity_timeout_minutes: int = 30):
        # {session_id: {flow_name: {state, paused_at, expires_at}}}
        self.paused_flows: Dict[str, Dict[str, Dict]] = {}
        self.session_activity: Dict[str, float] = {}  # {session_id: last_activity_timestamp}
        self.timeout_seconds = inactivity_timeout_minutes * 60
    
    def pause_flow(self, session_id: str, flow_name: str, state: Dict[str, Any]):
        """Pause a flow for later resumption"""
        if session_id not in self.paused_flows:
            self.paused_flows[session_id] = {}
        
        expires_at = time.time() + self.timeout_seconds
        
        self.paused_flows[session_id][flow_name] = {
            "state": state.copy(),
            "paused_at": time.time(),
            "expires_at": expires_at
        }
        
        print(f"[FLOW_PAUSE] Paused '{flow_name}' for session {session_id[:8]}, expires in {self.timeout_seconds/60:.0f} min")
    
    def resume_flow(self, session_id: str, flow_name: str) -> Optional[Dict[str, Any]]:
        """
        Resume a paused flow
        
        Returns:
            State dict if flow exists and not expired, None otherwise
        """
        # Clean expired flows first
        self._clean_expired_flows(session_id)
        
        if session_id not in self.paused_flows:
            return None
        
        if flow_name not in self.paused_flows[session_id]:
            return None
        
        flow_data = self.paused_flows[session_id][flow_name]
        
        # Check expiry
        if time.time() >= flow_data["expires_at"]:
            print(f"[FLOW_PAUSE] Flow '{flow_name}' expired, cannot resume")
            del self.paused_flows[session_id][flow_name]
            return None
        
        # Resume: return state and remove from paused
        state = flow_data["state"]
        del self.paused_flows[session_id][flow_name]
        
        print(f"[FLOW_PAUSE] Resumed '{flow_name}' for session {session_id[:8]}")
        return state
    
    def has_paused_flow(self, session_id: str, flow_name: str) -> bool:
        """Check if a specific flow is paused and not expired"""
        self._clean_expired_flows(session_id)
        
        if session_id not in self.paused_flows:
            return False
        
        if flow_name not in self.paused_flows[session_id]:
            return False
        
        # Check if expired
        flow_data = self.paused_flows[session_id][flow_name]
        if time.time() >= flow_data["expires_at"]:
            return False
        
        return True
    
    def clear_flow(self, session_id: str, flow_name: str):
        """Explicitly clear a paused flow"""
        if session_id in self.paused_flows and flow_name in self.paused_flows[session_id]:
            del self.paused_flows[session_id][flow_name]
            print(f"[FLOW_PAUSE] Cleared paused flow '{flow_name}'")
    
    def update_activity(self, session_id: str):
        """Update last activity timestamp for session"""
        self.session_activity[session_id] = time.time()
    
    def end_session(self, session_id: str):
        """Explicitly end session and clear all paused flows"""
        if session_id in self.paused_flows:
            flow_count = len(self.paused_flows[session_id])
            del self.paused_flows[session_id]
            print(f"[FLOW_PAUSE] Session {session_id[:8]} ended, cleared {flow_count} paused flows")
        
        if session_id in self.session_activity:
            del self.session_activity[session_id]
    
    def check_session_timeout(self, session_id: str) -> bool:
        """
        Check if session has timed out due to inactivity
        
        Returns:
            True if session timed out, False otherwise
        """
        if session_id not in self.session_activity:
            return False
        
        last_activity = self.session_activity[session_id]
        if time.time() - last_activity > self.timeout_seconds:
            print(f"[FLOW_PAUSE] Session {session_id[:8]} timed out (inactive for {self.timeout_seconds/60:.0f} min)")
            self.end_session(session_id)
            return True
        
        return False
    
    def _clean_expired_flows(self, session_id: str):
        """Remove expired flows for a session"""
        if session_id not in self.paused_flows:
            return
        
        current_time = time.time()
        expired = []
        
        for flow_name, flow_data in self.paused_flows[session_id].items():
            if current_time >= flow_data["expires_at"]:
                expired.append(flow_name)
        
        for flow_name in expired:
            del self.paused_flows[session_id][flow_name]
        
        if expired:
            print(f"[FLOW_PAUSE] Cleaned {len(expired)} expired flows")
        
        # Clean session if no flows left
        if not self.paused_flows[session_id]:
            del self.paused_flows[session_id]


# Global instance
_flow_manager = FlowPauseManager(inactivity_timeout_minutes=30)


def pause_flow(session_id: str, flow_name: str, state: Dict[str, Any]):
    """Pause a flow (module-level convenience function)"""
    _flow_manager.update_activity(session_id)
    _flow_manager.pause_flow(session_id, flow_name, state)


def resume_flow(session_id: str, flow_name: str) -> Optional[Dict[str, Any]]:
    """Resume a paused flow"""
    _flow_manager.update_activity(session_id)
    return _flow_manager.resume_flow(session_id, flow_name)


def has_paused_flow(session_id: str, flow_name: str) -> bool:
    """Check if flow is paused"""
    return _flow_manager.has_paused_flow(session_id, flow_name)


def clear_flow(session_id: str, flow_name: str):
    """Clear a paused flow"""
    _flow_manager.clear_flow(session_id, flow_name)


def update_session_activity(session_id: str):
    """Update session activity timestamp"""
    _flow_manager.update_activity(session_id)


def end_session(session_id: str):
    """End session and clear all paused flows"""
    _flow_manager.end_session(session_id)


def check_session_timeout(session_id: str) -> bool:
    """Check if session timed out"""
    return _flow_manager.check_session_timeout(session_id)
