"""
Orchestrator Agent v2 — Single Controller
==========================================
Clean classify -> route -> validate -> respond loop.
The orchestrator NEVER generates answers itself — it routes to specialized agents.

Pipeline:
1. Load dialogue state from session
2. If active flow (email/ticket in progress) -> route to flow handler
3. Else -> LLM intent classification with dialogue history
4. Route to agent (FAQ / Email / Ticket)
5. Validate agent output (intent match + constraints)
6. Save state & respond
"""
import json
import re
import hashlib
import os
import traceback
from typing import Dict, Optional, List, Any
from enum import Enum
from datetime import datetime

from langchain_groq import ChatGroq
from config import GROQ_API_KEY, DEFAULT_FACULTY_EMAIL

# --- Agent & Service Imports ---
try:
    # Relative imports for agents (when imported as agents.orchestrator_agent)
    from .faq_agent import FAQAgent
    from .email_agent import EmailAgent
    from .ticket_agent import TicketAgent
    from .faculty_db import FacultyDatabase
    from .chat_memory import get_chat_memory
    from .flow_pause import (
        pause_flow, resume_flow, has_paused_flow, clear_flow,
        update_session_activity, check_session_timeout
    )
    from .agent_protocol import AgentResponse
    from .ticket_config import CATEGORIES, PRIORITY_LEVELS
    from .turn_logging import log_turn
    from .history_rag_service import get_history_rag_service
    
    # absolute imports for services (project root is in generic path)
    from services.limits_service import LimitsService
    from services.activity_service import ActivityService, ActivityType

except ImportError:
    # Fallback for direct execution or different path structure
    import sys
    import os
    # Add project root to path if needed
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    
    from agents.faq_agent import FAQAgent
    from agents.email_agent import EmailAgent
    from agents.ticket_agent import TicketAgent
    from agents.faculty_db import FacultyDatabase
    from agents.chat_memory import get_chat_memory
    from agents.flow_pause import (
        pause_flow, resume_flow, has_paused_flow, clear_flow,
        update_session_activity, check_session_timeout
    )
    from agents.agent_protocol import AgentResponse
    from agents.ticket_config import CATEGORIES, PRIORITY_LEVELS
    from agents.turn_logging import log_turn
    from agents.history_rag_service import get_history_rag_service
    
    from services.limits_service import LimitsService
    from services.activity_service import ActivityService, ActivityType



# =============================================================================
# CONSTANTS
# =============================================================================
MAX_SESSION_MESSAGES = 50

# Per-intent confidence thresholds (actions are stricter)
CONFIDENCE_THRESHOLDS = {
    "FAQ": 0.45,
    "EMAIL": 0.65,
    "TICKET": 0.65,
    "TICKET_STATUS": 0.50,
    "GREETING": 0.30,
}

CANCEL_KEYWORDS = frozenset([
    "cancel", "never mind", "nevermind", "stop", "abort", "forget it", "quit"
])
CONFIRM_KEYWORDS = frozenset([
    "yes", "confirm", "send", "send it", "go ahead", "ok", "okay",
    "sure", "looks good", "correct", "do it"
])
EDIT_KEYWORDS = frozenset([
    "edit", "change", "modify", "update", "fix", "redo",
    "regenerate", "try again", "rewrite"
])


class IntentType(str, Enum):
    FAQ = "FAQ"
    EMAIL = "EMAIL"
    TICKET = "TICKET"
    TICKET_STATUS = "TICKET_STATUS"
    GREETING = "GREETING"
    UNKNOWN = "UNKNOWN"


# =============================================================================
# ORCHESTRATOR AGENT
# =============================================================================
class OrchestratorAgent:
    """
    Single-controller orchestrator: classify -> route -> validate -> respond.
    Never generates final answers — always routes to specialized agents.
    """

    def __init__(self):
        self.llm = ChatGroq(
            api_key=GROQ_API_KEY,
            model_name="llama-3.1-8b-instant",
            temperature=0.1
        )
        self.faq_agent = FAQAgent(llm=self.llm)
        self.email_agent = EmailAgent()
        self.ticket_agent = TicketAgent()
        self.faculty_db = FacultyDatabase()
        self.chat_memory = get_chat_memory()
        self.history_rag = get_history_rag_service()
        self._executed_actions = set()
        print("[OK] Orchestrator v2 initialized (classify -> route -> validate -> respond)")

    # =========================================================================
    # HELPERS
    # =========================================================================
    def _get_history_text(self, session_id: str, user_id: str, limit: int = 10) -> str:
        try:
            history = self.chat_memory.get_session_history(session_id, user_id, limit=limit)
            if not history:
                return ""
            lines = []
            for msg in history[-limit:]:
                role = "Student" if msg.get("role") == "user" else "Assistant"
                lines.append(f"{role}: {msg.get('content', '')[:200]}")
            return "\n".join(lines)
        except Exception:
            return ""

    def _save_flow(self, session_id, flow, step, slots, entities=None, extra=None):
        state = {
            "active_flow": flow, "step": step, "slots": slots,
            "entities": entities or {}
        }
        if extra:
            state.update(extra)
        pause_flow(session_id, "active", state)

    def _save_turn(self, session_id, user_id, user_message, bot_response,
                   intent="", agent="orchestrator", confidence=0.0,
                   active_flow=None, slots=None):
        meta = {
            "intent": intent, "agent": agent, "confidence": confidence,
            "active_flow": active_flow, "active_slots": slots or {}
        }
        try:
            self.chat_memory.save_message(
                user_id=user_id, session_id=session_id,
                role="user", content=user_message, intent=intent,
                selected_agent=agent, metadata=meta
            )
            self.chat_memory.save_message(
                user_id=user_id, session_id=session_id,
                role="bot", content=bot_response, intent=intent,
                selected_agent=agent, metadata=meta
            )
        except Exception as e:
            print(f"[WARN] Failed to save turn: {e}")
        try:
            log_turn(
                user_id=user_id, session_id=session_id,
                user_message=user_message, intent=intent,
                routing_decision=agent, agent_called=agent,
                agent_status="success", validation_outcome="passed",
                side_effects=[], bot_response=bot_response,
                metadata={"confidence": confidence}
            )
        except Exception:
            pass

    def _make_response(self, message, response_type="information",
                       session_id="", user_id="", user_message="",
                       intent="", agent="orchestrator", confidence=0.0,
                       student_profile=None, agent_output=None,
                       confirmation_data=None, active_flow=None, slots=None):
        self._save_turn(session_id, user_id, user_message, message,
                        intent, agent, confidence, active_flow, slots)
        resp = {
            "type": response_type,
            "agent": agent,
            "content": confirmation_data if confirmation_data else message,
            "metadata": {
                "intent": intent,
                "confidence": confidence,
                "active_flow": active_flow,
                "extracted_slots": slots or {}
            }
        }
        if agent_output:
            resp["agent_output"] = agent_output
        return resp

    # =========================================================================
    # INTENT CLASSIFICATION (single LLM call)
    # =========================================================================
    def _classify_intent(self, message: str, history_text: str) -> Dict:
        prompt = f"""You are an intent classifier for a college student support chatbot.

INTENT TYPES:
- FAQ: Asking about college policies, rules, courses, fees, attendance, placements, hostel, library
- EMAIL: Wants to compose/send an email to faculty or external contact
- TICKET: Wants to raise a NEW support ticket or complaint
- TICKET_STATUS: Check status of existing tickets, close tickets, view history
- GREETING: Hello, hi, thanks, bye, "what can you do", capability questions
- UNKNOWN: Cannot determine

RULES:
- Questions about college info -> FAQ
- "send email", "write email", "email to", "contact professor" -> EMAIL
- "raise ticket", "create ticket", "report issue", "complaint" -> TICKET
- "check ticket", "ticket status", "close ticket" -> TICKET_STATUS
- Capability questions like "can you send emails?" -> GREETING (NOT EMAIL)
- If message is just a greeting/thanks/bye -> GREETING

ENTITY EXTRACTION RULES (CRITICAL):
- faculty_name: The name of the faculty/professor/teacher mentioned. Strip "Dr.", "Prof.", etc.
- email_address: Any email address (user@domain.com)
- purpose: MUST extract the reason/topic/subject if mentioned. Look for phrases after "about", "regarding", "for", "asking", "to discuss", "to request", "to inquire". NEVER return null for purpose if the user mentions a reason.
  Examples:
  - "email Dr. Kumar about internship" → purpose: "internship"
  - "send email to test@email.com regarding exam schedule" → purpose: "exam schedule"
  - "contact faculty for notes" → purpose: "notes"
- ticket_description: Description of the issue/complaint

CONVERSATION HISTORY:
{history_text if history_text else "(none)"}

STUDENT MESSAGE: "{message}"

Return ONLY valid JSON:
{{"intent":"FAQ|EMAIL|TICKET|TICKET_STATUS|GREETING|UNKNOWN","confidence":0.85,"entities":{{"faculty_name":null,"email_address":null,"purpose":null,"ticket_description":null}},"reasoning":"brief"}}"""

        try:
            response = self.llm.invoke(prompt)
            text = response.content.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            result = json.loads(text)

            intent_str = result.get("intent", "UNKNOWN").upper()
            valid = [e.value for e in IntentType]
            if intent_str not in valid:
                intent_str = "UNKNOWN"

            confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
            entities = result.get("entities", {})

            # Extract email from message if LLM missed it
            email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', message)
            if email_match and not entities.get("email_address"):
                entities["email_address"] = email_match.group()

            print(f"[INTENT] {intent_str} (conf={confidence:.2f}) — {result.get('reasoning', '')[:80]}")
            return {"intent": intent_str, "confidence": confidence,
                    "entities": entities, "reasoning": result.get("reasoning", "")}
        except Exception as e:
            print(f"[INTENT] Classification error: {e}")
            return {"intent": "UNKNOWN", "confidence": 0.0,
                    "entities": {}, "reasoning": str(e)}

    # =========================================================================
    # MAIN ENTRY POINT
    # =========================================================================
    def process_message(self, user_message: str, user_id: str, session_id: str,
                        mode: str = "auto", student_profile: Optional[Dict] = None) -> Dict:
        print(f"[ORCHESTRATOR] '{user_message[:80]}' (user={user_id})")

        update_session_activity(session_id)
        if check_session_timeout(session_id):
            print("[SESSION] Timed out")

        msg_lower = user_message.lower().strip()

        # --- Load active flow ---
        state = resume_flow(session_id, "active") or {}
        active_flow = state.get("active_flow")

        # --- Cancel check ---
        if msg_lower in CANCEL_KEYWORDS and active_flow:
            clear_flow(session_id, "active")
            return self._make_response(
                "Cancelled. How can I help you?",
                session_id=session_id, user_id=user_id,
                user_message=user_message, intent="GREETING",
                student_profile=student_profile)

        # --- Active flow -> route to handler ---
        if active_flow:
            print(f"[FLOW] Active: {active_flow}, step: {state.get('step')}")
            if active_flow == "email":
                return self._handle_email_flow(
                    user_message, user_id, session_id, student_profile,
                    state.get("entities", {}), state)
            elif active_flow == "ticket":
                return self._handle_ticket_flow(
                    user_message, user_id, session_id, student_profile,
                    state.get("entities", {}), state)
            else:
                clear_flow(session_id, "active")

        # --- Classify intent via LLM ---
        history_text = self._get_history_text(session_id, user_id)
        cls = self._classify_intent(user_message, history_text)
        intent = cls["intent"]
        confidence = cls["confidence"]
        entities = cls["entities"]
        threshold = CONFIDENCE_THRESHOLDS.get(intent, 0.5)

        # --- Confidence check with entity fallback ---
        if confidence < threshold:
            has_entities = any(v for v in entities.values() if v)
            if has_entities and intent in ("EMAIL", "TICKET"):
                print(f"[INTENT] Low conf ({confidence:.2f}<{threshold}) but entities present — proceeding")
            else:
                print(f"[INTENT] Low conf ({confidence:.2f}<{threshold}) — clarifying")
                return self._make_response(
                    "Could you please clarify what you'd like help with?\n\n"
                    "• **Ask about college policies/fees**\n"
                    "• **Send an email** to faculty or contacts\n"
                    "• **Raise a ticket** for issues\n"
                    "• **Check ticket status**",
                    response_type="clarification_request",
                    session_id=session_id, user_id=user_id,
                    user_message=user_message, intent=intent,
                    confidence=confidence, student_profile=student_profile)

        # --- Route ---
        print(f"[ROUTE] {intent}")
        if intent == "FAQ":
            return self._handle_faq(user_message, user_id, session_id, student_profile, entities)
        elif intent == "EMAIL":
            clear_flow(session_id, "active")  # Prevent stale state from old flows
            return self._handle_email_flow(
                user_message, user_id, session_id, student_profile, entities, {})
        elif intent == "TICKET":
            clear_flow(session_id, "active")  # Prevent stale state from old flows
            return self._handle_ticket_flow(
                user_message, user_id, session_id, student_profile, entities, {})
        elif intent == "TICKET_STATUS":
            return self._handle_ticket_status(user_message, user_id, session_id, student_profile, entities)
        elif intent == "GREETING":
            return self._handle_greeting(user_message, user_id, session_id, student_profile)
        else:
            return self._make_response(
                "I'm not sure I understand. Could you clarify?\n\n"
                "• **Ask a question** about college policies\n"
                "• **Send an email** to faculty or contacts\n"
                "• **Raise a ticket**\n• **Check tickets**",
                response_type="clarification_request",
                session_id=session_id, user_id=user_id,
                user_message=user_message, intent="UNKNOWN",
                student_profile=student_profile)

    # =========================================================================
    # GREETING
    # =========================================================================
    def _handle_greeting(self, message, user_id, session_id, student_profile):
        name = student_profile.get("name", "there") if student_profile else "there"
        ml = message.lower()
        if any(w in ml for w in ["can you", "what can", "help", "features"]):
            r = (f"Hi {name}! 👋 Here's what I can do:\n\n"
                 "📚 **Answer questions** about college policies, courses, fees\n"
                 "📧 **Send emails** to faculty or any contact\n"
                 "🎫 **Raise tickets** for issues or complaints\n"
                 "📋 **Check ticket status**\n\nWhat would you like help with?")
        elif any(w in ml for w in ["bye", "goodbye"]):
            r = f"Goodbye {name}! Feel free to come back anytime. 👋"
        elif any(w in ml for w in ["thank", "thanks"]):
            r = f"You're welcome, {name}! Let me know if you need anything else. 😊"
        else:
            r = (f"Hello {name}! 👋 How can I help you today?\n\n"
                 "You can ask about college policies, send emails, or raise tickets.")
        return self._make_response(
            r, session_id=session_id, user_id=user_id,
            user_message=message, intent="GREETING", agent="orchestrator",
            student_profile=student_profile)

    # =========================================================================
    # FAQ HANDLER
    # =========================================================================
    def _handle_faq(self, message, user_id, session_id, student_profile, entities):
        try:
            msg_lower = message.lower().strip()

            # --- Faculty data queries (e.g. "is Dr. X in CSM?", "faculty in CSE") ---
            faculty_keywords = ['faculty', 'professor', 'teacher', 'sir', 'madam', 'ma\'am', 'hod', 'dean']
            dept_keywords = ['department', 'dept', 'cse', 'csm', 'ece', 'eee', 'mech', 'civil', 'it', 'aiml', 'aids']
            is_faculty_query = any(kw in msg_lower for kw in faculty_keywords) and any(kw in msg_lower for kw in dept_keywords)
            # Also match "is <name> in <dept>" patterns
            if not is_faculty_query and ('in ' in msg_lower or 'from ' in msg_lower) and any(kw in msg_lower for kw in faculty_keywords):
                is_faculty_query = True

            if is_faculty_query:
                # Try to extract a faculty name or department from the message
                try:
                    # Search by department keywords found in message
                    dept_found = None
                    for dkw in dept_keywords:
                        if dkw in msg_lower and dkw not in ['department', 'dept']:
                            dept_found = dkw.upper()
                            break

                    # Search for specific faculty name
                    search_result = self.faculty_db.search_faculty(
                        name=message if not dept_found else None,
                        department=dept_found,
                        limit=10
                    )
                    # search_faculty returns {"status", "faculty", "matches", "message"}
                    faculty_list = []
                    if isinstance(search_result, dict):
                        # Single exact match
                        if search_result.get('faculty'):
                            faculty_list = [search_result['faculty']]
                        # Multiple matches
                        elif search_result.get('matches'):
                            faculty_list = search_result['matches']

                    if faculty_list:
                        lines = []
                        for f in faculty_list[:10]:
                            name = f.get('name', 'Unknown')
                            desig = f.get('designation', '')
                            dept = f.get('department', '')
                            lines.append(f"• **{name}** — {desig}, {dept}")
                        text = f"Here are the faculty members I found:\n\n" + "\n".join(lines)
                        if dept_found:
                            text = f"📋 **Faculty in {dept_found} department:**\n\n" + "\n".join(lines)
                    else:
                        # Try get_faculty_by_department as fallback for department queries
                        if dept_found:
                            all_faculty = self.faculty_db.get_faculty_by_department(dept_found)
                            if all_faculty:
                                lines = []
                                for f in all_faculty[:10]:
                                    name = f.get('name', 'Unknown')
                                    desig = f.get('designation', '')
                                    lines.append(f"• **{name}** — {desig}")
                                text = f"📋 **Faculty in {dept_found} department:**\n\n" + "\n".join(lines)
                            else:
                                text = f"I couldn't find any faculty in the **{dept_found}** department. Please check the department name."
                        else:
                            text = search_result.get('message', '') if isinstance(search_result, dict) else ''
                            if not text:
                                text = "I couldn't find matching faculty. Try asking with a specific department name (e.g. CSE, CSM, ECE)."

                    return self._make_response(
                        text, session_id=session_id, user_id=user_id,
                        user_message=message, intent="FAQ", agent="faq_agent",
                        confidence=0.9, student_profile=student_profile)
                except Exception as e:
                    print(f"[WARN] Faculty query failed, falling through to FAQ: {e}")

            # --- Email history queries ---
            email_history_keywords = ['email history', 'emails sent', 'emails i sent', 'email log',
                                       'sent emails', 'what emails', 'which emails', 'show emails',
                                       'my emails', 'email records', 'how many emails sent',
                                       'emails have i sent', 'list emails', 'previous emails']
            is_email_history = any(kw in msg_lower for kw in email_history_keywords)

            if is_email_history:
                try:
                    history = self.faculty_db.get_student_email_history(user_id)
                    if history:
                        lines = []
                        for h in history[:10]:
                            name = h.get('faculty_name', 'Unknown')
                            subj = h.get('subject', 'No subject')
                            status = h.get('status', 'Unknown')
                            ts = h.get('timestamp', '')
                            lines.append(f"• **To: {name}** — \"{subj}\" [{status}] ({ts})")
                        text = f"📬 **Your Email History** ({len(history)} total):\n\n" + "\n".join(lines)
                        if len(history) > 10:
                            text += f"\n\n...and {len(history) - 10} more. Check the **Email History** page for the full list."
                    else:
                        text = "📭 You haven't sent any emails yet. You can email faculty from **Contact Faculty** or use **Send Email** in chat."

                    return self._make_response(
                        text, session_id=session_id, user_id=user_id,
                        user_message=message, intent="FAQ", agent="faq_agent",
                        confidence=0.9, student_profile=student_profile)
                except Exception as e:
                    print(f"[WARN] Email history query failed, falling through to FAQ: {e}")

            # --- Email quota queries ---
            quota_keywords = ['emails left', 'email left', 'email limit', 'email quota',
                              'how many emails can', 'remaining emails', 'emails remaining',
                              'can i send email', 'email count', 'daily email', 'daily limit']
            is_quota_query = any(kw in msg_lower for kw in quota_keywords)

            if is_quota_query:
                try:
                    allowed, remaining, mx = LimitsService.check_daily_limit(user_id, 'email')
                    used = mx - remaining
                    if allowed:
                        text = f"📧 **Email Quota:**\n\n• Sent today: **{used}** / {mx}\n• Remaining: **{remaining}**\n\nYou can send {remaining} more email(s) today."
                    else:
                        text = f"📧 **Email Quota:**\n\n• Sent today: **{used}** / {mx}\n• Remaining: **0**\n\n⚠️ Daily email limit reached. Please try again tomorrow."

                    return self._make_response(
                        text, session_id=session_id, user_id=user_id,
                        user_message=message, intent="FAQ", agent="faq_agent",
                        confidence=0.9, student_profile=student_profile)
                except Exception as e:
                    print(f"[WARN] Quota query failed, falling through to FAQ: {e}")

            # --- Default: route to FAQ agent ---
            result = self.faq_agent.process(
                user_query=message, session_id=session_id, user_id=user_id)
            if isinstance(result, dict):
                text = result.get("message", "")
                conf = result.get("metadata", {}).get("confidence", 0.5)
                cites = result.get("metadata", {}).get("citations", [])
            elif isinstance(result, str):
                text, conf, cites = result, 0.5, []
            else:
                text, conf, cites = str(result) if result else "", 0.3, []

            if not text:
                text = ("I couldn't find specific information about that. "
                        "Try rephrasing, or:\n• 🎫 **Raise a ticket** for help\n"
                        "• 📧 **Email faculty** for detailed answers")

            print(f"[VALIDATE] FAQ conf={conf:.2f}, citations={len(cites)}")
            ao = {"agent_name": "faq_agent", "detected_intent": "FAQ",
                  "confidence": conf, "required_slots": {},
                  "action_type": "answer", "preview_or_final": "final",
                  "message_to_user": text, "citations": cites}
            return self._make_response(
                text, session_id=session_id, user_id=user_id,
                user_message=message, intent="FAQ", agent="faq_agent",
                confidence=conf, student_profile=student_profile, agent_output=ao)
        except Exception as e:
            print(f"[ERROR] FAQ: {e}")
            traceback.print_exc()
            return self._make_response(
                "I encountered an error retrieving that information. Please try rephrasing.",
                session_id=session_id, user_id=user_id,
                user_message=message, intent="FAQ", agent="faq_agent",
                student_profile=student_profile)

    # =========================================================================
    # EMAIL FLOW (multi-step)
    # =========================================================================
    def _handle_email_flow(self, message, user_id, session_id,
                           student_profile, entities, state):
        step = state.get("step", "start")
        slots = state.get("slots", {})
        msg_lower = message.lower().strip()

        # Cancel check
        if msg_lower in CANCEL_KEYWORDS:
            clear_flow(session_id, "active")
            return self._make_response(
                "Email cancelled. How can I help you?",
                session_id=session_id, user_id=user_id,
                user_message=message, intent="EMAIL",
                student_profile=student_profile)

        # Merge entities into slots
        for key in ["faculty_name", "email_address", "purpose"]:
            val = entities.get(key)
            if val and not slots.get(key.replace("email_address", "recipient_email")):
                slots[key.replace("email_address", "recipient_email")] = val

        # Extract email from message
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', message)
        if email_match and not slots.get("recipient_email"):
            slots["recipient_email"] = email_match.group()

        # Regex fallback: extract purpose from message text if LLM missed it
        if not slots.get("purpose"):
            purpose_match = re.search(
                r'(?:about|for|regarding|asking|to discuss|to ask about|to inquire about)\s+(.+?)(?:\s*$)',
                message, re.IGNORECASE)
            if purpose_match and len(purpose_match.group(1).strip()) > 3:
                slots["purpose"] = purpose_match.group(1).strip()

        # ---------- STEP: START ----------
        if step == "start":
            if slots.get("recipient_email"):
                if not slots.get("purpose"):
                    self._save_flow(session_id, "email", "collect_purpose", slots, entities)
                    return self._make_response(
                        f"📧 I'll send an email to **{slots['recipient_email']}**.\n\n"
                        "What would you like to say?",
                        response_type="clarification_request",
                        session_id=session_id, user_id=user_id,
                        user_message=message, intent="EMAIL", agent="email_agent",
                        student_profile=student_profile, active_flow="email", slots=slots)
                else:
                    return self._generate_email_preview(
                        message, user_id, session_id, student_profile, slots, entities)
            elif slots.get("faculty_name"):
                return self._search_faculty(
                    slots["faculty_name"], message, user_id, session_id,
                    student_profile, slots, entities)
            else:
                # Try extracting faculty name AND purpose from message
                # Pattern: "email/contact Dr. X about Y"
                nm_with_purpose = re.search(
                    r'(?:to|email|contact|write\s+to|send\s+(?:an?\s+)?email\s+to)\s+'
                    r'(?:dr\.?\s*|prof\.?\s*|professor\s+|mr\.?\s*|mrs?\.?\s*|ms\.?\s*)?'
                    r'(\w[\w\s]{1,30}?)\s+(?:about|regarding|for|asking|to discuss)\s+(.+?)\s*$',
                    message, re.IGNORECASE)
                if nm_with_purpose and len(nm_with_purpose.group(1).strip()) > 1:
                    faculty_name = nm_with_purpose.group(1).strip()
                    if not slots.get("purpose"):
                        slots["purpose"] = nm_with_purpose.group(2).strip()
                    return self._search_faculty(
                        faculty_name, message, user_id, session_id,
                        student_profile, slots, entities)

                # Fallback: extract just the faculty name (no purpose in message)
                nm = re.search(
                    r'(?:to|email|contact|write\s+to|send\s+(?:an?\s+)?email\s+to)\s+'
                    r'(?:dr\.?\s*|prof\.?\s*|professor\s+|mr\.?\s*|mrs?\.?\s*|ms\.?\s*)?'
                    r'(\w[\w\s]{1,30}?)\s*$',
                    message, re.IGNORECASE)
                if nm and len(nm.group(1).strip()) > 1:
                    return self._search_faculty(
                        nm.group(1).strip(), message, user_id, session_id,
                        student_profile, slots, entities)
                self._save_flow(session_id, "email", "collect_recipient", slots, entities)
                return self._make_response(
                    "📧 Sure! Who would you like to email?\n"
                    "• A **faculty member** (tell me their name)\n"
                    "• An **external contact** (provide their email address)",
                    response_type="clarification_request",
                    session_id=session_id, user_id=user_id,
                    user_message=message, intent="EMAIL", agent="email_agent",
                    student_profile=student_profile, active_flow="email", slots=slots)

        # ---------- STEP: COLLECT_RECIPIENT ----------
        if step == "collect_recipient":
            # Detect unrelated intents and break out of email flow
            escape_patterns = [
                r'\b(raise|create|open|file)\s+(a\s+)?ticket\b',
                r'\b(check|view|close)\s+ticket\b',
                r'\bticket\s+status\b',
                r'\b(what|how|when|where|tell me about|explain)\b.*\b(attendance|placement|fee|hostel|library|admission)\b'
            ]
            for pattern in escape_patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    clear_flow(session_id, "active")
                    return self.process_message(message, user_id, session_id,
                                                student_profile=student_profile)

            if email_match:
                slots["recipient_email"] = email_match.group()
                slots["recipient_name"] = email_match.group().split("@")[0]
                self._save_flow(session_id, "email", "collect_purpose", slots, entities)
                return self._make_response(
                    f"📧 Got it! I'll email **{slots['recipient_email']}**.\n\nWhat would you like to say?",
                    response_type="clarification_request",
                    session_id=session_id, user_id=user_id,
                    user_message=message, intent="EMAIL", agent="email_agent",
                    student_profile=student_profile, active_flow="email", slots=slots)
            else:
                # Extract faculty name from message — not the raw message
                faculty_name = message.strip()
                # Try to extract just the name part using regex
                nm_extract = re.search(
                    r'(?:to|email|contact|send\s+(?:an?\s+)?email\s+to|write\s+to)?\s*'
                    r'(?:dr\.?\s*|prof\.?\s*|professor\s+|mr\.?\s*|mrs?\.?\s*|ms\.?\s*)?'
                    r'([a-zA-Z][a-zA-Z\s]{1,30}?)'
                    r'(?:\s+(?:about|regarding|for|asking|referring|requesting|to discuss)\s+(.+?))?\s*$',
                    message, re.IGNORECASE)
                if nm_extract and len(nm_extract.group(1).strip()) > 1:
                    faculty_name = nm_extract.group(1).strip()
                    # Also capture purpose if present
                    if nm_extract.group(2) and not slots.get("purpose"):
                        slots["purpose"] = nm_extract.group(2).strip()
                slots["faculty_name"] = faculty_name
                return self._search_faculty(
                    faculty_name, message, user_id, session_id,
                    student_profile, slots, entities)

        # ---------- STEP: FACULTY_SELECT ----------
        if step == "faculty_select":
            matches = state.get("faculty_matches", [])
            try:
                idx = int(msg_lower.strip()) - 1
                if 0 <= idx < len(matches):
                    f = matches[idx]
                    slots["recipient_email"] = f.get("email", "")
                    slots["recipient_name"] = f.get("name", "")
                    slots["faculty_id"] = f.get("id", "")
                    if not slots.get("purpose"):
                        self._save_flow(session_id, "email", "collect_purpose", slots, entities)
                        return self._make_response(
                            f"📧 I'll email **{slots['recipient_name']}**.\n\nWhat would you like to say?",
                            response_type="clarification_request",
                            session_id=session_id, user_id=user_id,
                            user_message=message, intent="EMAIL", agent="email_agent",
                            student_profile=student_profile, active_flow="email", slots=slots)
                    return self._generate_email_preview(
                        message, user_id, session_id, student_profile, slots, entities)
                return self._make_response(
                    f"Please pick a number between 1 and {len(matches)}.",
                    response_type="clarification_request",
                    session_id=session_id, user_id=user_id,
                    user_message=message, intent="EMAIL", agent="email_agent",
                    student_profile=student_profile, active_flow="email", slots=slots)
            except ValueError:
                return self._search_faculty(
                    message.strip(), message, user_id, session_id,
                    student_profile, slots, entities)

        # ---------- STEP: COLLECT_PURPOSE ----------
        if step == "collect_purpose":
            slots["purpose"] = message.strip()
            return self._generate_email_preview(
                message, user_id, session_id, student_profile, slots, entities)

        # ---------- STEP: PREVIEW ----------
        if step == "preview":
            draft = state.get("email_draft", {})
            if msg_lower in CONFIRM_KEYWORDS or "send" in msg_lower:
                return self._execute_email_send(
                    draft, user_id, session_id, student_profile, message, slots)
            elif any(k in msg_lower for k in EDIT_KEYWORDS):
                # Mark as regenerate if user asked to regenerate
                is_regen = any(k in msg_lower for k in ["regenerate", "regen", "try again", "rewrite", "redo"])
                if is_regen:
                    slots["_regenerate"] = True
                return self._generate_email_preview(
                    message, user_id, session_id, student_profile, slots, entities)
            else:
                clear_flow(session_id, "active")
                return self._make_response(
                    "Email cancelled. How can I help you?",
                    session_id=session_id, user_id=user_id,
                    user_message=message, intent="EMAIL",
                    student_profile=student_profile)

        clear_flow(session_id, "active")
        return self.process_message(user_message, user_id, session_id,
                                    student_profile=student_profile)

    def _search_faculty(self, name, message, user_id, session_id,
                        student_profile, slots, entities):
        try:
            result = self.faculty_db.search_faculty(name=name)
            # CRITICAL: Use 'matches' key (list), NOT 'faculty' (can be None or dict)
            matches = result.get("matches", [])
            if matches is None:
                matches = []
            print(f"[INFO] Faculty Search Result: Found {len(matches)} matches")

            if len(matches) == 1:
                f = matches[0]
                slots["recipient_email"] = f.get("email", "")
                slots["recipient_name"] = f.get("name", "")
                slots["faculty_id"] = f.get("id", f.get("faculty_id", ""))
                if not slots.get("purpose"):
                    self._save_flow(session_id, "email", "collect_purpose", slots, entities)
                    return self._make_response(
                        f"📧 Found **{f['name']}** ({f.get('department','N/A')}).\n\n"
                        "What would you like to say?",
                        response_type="clarification_request",
                        session_id=session_id, user_id=user_id,
                        user_message=message, intent="EMAIL", agent="email_agent",
                        student_profile=student_profile, active_flow="email", slots=slots)
                return self._generate_email_preview(
                    message, user_id, session_id, student_profile, slots, entities)
            elif len(matches) > 1:
                display_matches = matches[:5]
                lines = [f"I found {len(matches)} matches for \"{name}\":\n"]
                for i, fac in enumerate(display_matches, 1):
                    lines.append(f"{i}. **{fac['name']}** — {fac.get('department','N/A')}")
                lines.append("\nReply with the number.")
                self._save_flow(session_id, "email", "faculty_select", slots, entities,
                               extra={"faculty_matches": display_matches})
                return self._make_response(
                    "\n".join(lines), response_type="clarification_request",
                    session_id=session_id, user_id=user_id,
                    user_message=message, intent="EMAIL", agent="email_agent",
                    student_profile=student_profile, active_flow="email", slots=slots)
            else:
                self._save_flow(session_id, "email", "collect_recipient", slots, entities)
                return self._make_response(
                    f"No faculty found for \"{name}\".\n\nTry a different name or provide their email address.",
                    response_type="clarification_request",
                    session_id=session_id, user_id=user_id,
                    user_message=message, intent="EMAIL", agent="email_agent",
                    student_profile=student_profile, active_flow="email", slots=slots)
        except Exception as e:
            print(f"[ERROR] Faculty search: {e}")
            traceback.print_exc()
            self._save_flow(session_id, "email", "collect_recipient", slots, entities)
            return self._make_response(
                "Trouble searching faculty. Please provide the email address directly.",
                response_type="clarification_request",
                session_id=session_id, user_id=user_id,
                user_message=message, intent="EMAIL", agent="email_agent",
                student_profile=student_profile, active_flow="email", slots=slots)

    def _generate_email_preview(self, message, user_id, session_id,
                                student_profile, slots, entities):
        purpose = slots.get("purpose", message)
        recipient_name = slots.get("recipient_name", slots.get("recipient_email", ""))
        recipient_email = slots.get("recipient_email", "")
        student_name = student_profile.get("name", "") if student_profile else ""
        is_regen = slots.pop("_regenerate", False)
        try:
            subject = self.email_agent.generate_email_subject(purpose)
            body = self.email_agent.generate_email_body(
                purpose=purpose, recipient_name=recipient_name,
                student_name=student_name, length="medium",
                regenerate=is_regen)
            draft = {
                "to": recipient_email,
                "to_name": recipient_name,
                "subject": subject, "body": body,
                "action": "email_preview"
            }
            self._save_flow(session_id, "email", "preview", slots, entities,
                           extra={"email_draft": draft})

            # Build the confirmation_data in the format the frontend expects:
            # ConfirmationCard checks: action === 'email_preview' && preview
            # preview must have {to, subject, body}
            confirmation_payload = {
                "action": "email_preview",
                "summary": f"Email to {recipient_email}",
                "preview": {
                    "to": recipient_email,
                    "subject": subject,
                    "body": body
                }
            }
            preview_text = (f"📧 **Email Preview**\n\n"
                       f"**To:** {recipient_email}\n"
                       f"**Subject:** {subject}\n\n---\n{body}\n---\n\n"
                       "Reply **confirm** to send, **edit** to change, or **cancel**.")
            ao = {"agent_name": "email_agent", "detected_intent": "EMAIL",
                  "confidence": 0.95, "action_type": "email_send",
                  "preview_or_final": "preview", "message_to_user": preview_text,
                  "required_slots": slots, "citations": []}
            return self._make_response(
                preview_text, response_type="email_preview",
                session_id=session_id, user_id=user_id,
                user_message=message, intent="EMAIL", agent="email_agent",
                confidence=0.95, student_profile=student_profile,
                agent_output=ao, confirmation_data=confirmation_payload,
                active_flow="email", slots=slots)
        except Exception as e:
            print(f"[ERROR] Email draft: {e}")
            traceback.print_exc()
            clear_flow(session_id, "active")
            return self._make_response(
                "Error generating email draft. Please try again.",
                session_id=session_id, user_id=user_id,
                user_message=message, intent="EMAIL", agent="email_agent",
                student_profile=student_profile)

    def _execute_email_send(self, draft, user_id, session_id,
                            student_profile, message, slots):
        clear_flow(session_id, "active")
        if not draft or not draft.get("to"):
            return self._make_response(
                "No email draft found. Please start over.",
                session_id=session_id, user_id=user_id,
                user_message=message, intent="EMAIL",
                student_profile=student_profile)
        action_data = {"action": "send_email", "preview": draft}
        result = self.execute_confirmed_action(
            user_id, session_id, action_data, student_profile)
        return self._make_response(
            result.get("message", "Email processed."),
            session_id=session_id, user_id=user_id,
            user_message=message, intent="EMAIL", agent="email_agent",
            student_profile=student_profile)

    # =========================================================================
    # TICKET FLOW (multi-step)
    # =========================================================================
    def _handle_ticket_flow(self, message, user_id, session_id,
                            student_profile, entities, state):
        step = state.get("step", "start")
        slots = state.get("slots", {})
        msg_lower = message.lower().strip()

        if msg_lower in CANCEL_KEYWORDS:
            clear_flow(session_id, "active")
            return self._make_response(
                "Ticket creation cancelled. How can I help you?",
                session_id=session_id, user_id=user_id,
                user_message=message, intent="TICKET",
                student_profile=student_profile)

        if entities.get("ticket_description") and not slots.get("description"):
            slots["description"] = entities["ticket_description"]

        # ---------- STEP: START ----------
        if step == "start":
            if slots.get("description"):
                return self._generate_ticket_preview(
                    message, user_id, session_id, student_profile, slots, entities)
            # Try to extract description from message
            desc = message.strip()
            # Remove trigger phrases
            for phrase in ["raise a ticket", "create a ticket", "raise ticket",
                           "create ticket", "i want to", "i need to",
                           "please", "about", "for", "regarding"]:
                desc = re.sub(r'\b' + phrase + r'\b', '', desc, flags=re.IGNORECASE).strip()
            if len(desc) > 5:
                slots["description"] = desc
                return self._generate_ticket_preview(
                    message, user_id, session_id, student_profile, slots, entities)
            self._save_flow(session_id, "ticket", "collect_description", slots, entities)
            return self._make_response(
                "🎫 Sure, I can help you raise a ticket!\n\n"
                "Please describe your issue in detail.",
                response_type="clarification_request",
                session_id=session_id, user_id=user_id,
                user_message=message, intent="TICKET", agent="ticket_agent",
                student_profile=student_profile, active_flow="ticket", slots=slots)

        # ---------- STEP: COLLECT_DESCRIPTION ----------
        if step == "collect_description":
            slots["description"] = message.strip()
            return self._generate_ticket_preview(
                message, user_id, session_id, student_profile, slots, entities)

        # ---------- STEP: PREVIEW ----------
        if step == "preview":
            ticket_data = state.get("ticket_data", {})
            # Detect ticket status or close requests — escape from flow
            status_patterns = [
                r'\b(show|view|list|check|see)\s+(all\s+)?(my\s+)?(raised\s+|open\s+)?tickets\b',
                r'\bticket\s+(status|history)\b',
                r'\bclose\s+(all\s+)?ticket'
            ]
            for pattern in status_patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    clear_flow(session_id, "active")
                    return self._handle_ticket_status(
                        message, user_id, session_id, student_profile, entities)
            if msg_lower in CONFIRM_KEYWORDS:
                return self._execute_ticket_create(
                    ticket_data, user_id, session_id, student_profile, message, slots)
            else:
                clear_flow(session_id, "active")
                return self._make_response(
                    "Ticket creation cancelled. How can I help you?",
                    session_id=session_id, user_id=user_id,
                    user_message=message, intent="TICKET",
                    student_profile=student_profile)

        clear_flow(session_id, "active")
        return self.process_message(user_message, user_id, session_id,
                                    student_profile=student_profile)

    def _generate_ticket_preview(self, message, user_id, session_id,
                                 student_profile, slots, entities):
        description = slots.get("description", message)
        # Auto-classify category, generate title, priority, and formal description
        try:
            cat_prompt = f"""You are a student support system. Classify this student complaint and rewrite it formally.

Categories: {', '.join(CATEGORIES.keys())}
Priority levels: Low, Medium, High, Urgent

Student's complaint: "{description}"

Return ONLY valid JSON (no markdown):
{{"category":"one of the categories above","title":"concise 5-10 word ticket title","priority":"Low|Medium|High|Urgent","professional_description":"formal 2-3 sentence rewrite of the complaint"}}"""
            resp = self.llm.invoke(cat_prompt)
            text = resp.content.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            cat_result = json.loads(text)
            category = cat_result.get("category", "Other")
            title = cat_result.get("title", description[:80])
            priority = cat_result.get("priority", "Medium")
            prof_desc = cat_result.get("professional_description", description)
            if category not in CATEGORIES:
                category = "Other"
            if priority not in PRIORITY_LEVELS:
                priority = "Medium"
        except Exception as e:
            print(f"[TICKET] LLM classification error: {e}")
            category = "Other"
            title = description[:80]
            priority = "Medium"
            prof_desc = description

        student_email = student_profile.get("email", user_id) if student_profile else user_id
        sub_cat = CATEGORIES.get(category, ["General Query"])[0]
        ticket_data = {
            "student_email": student_email,
            "category": category, "sub_category": sub_cat,
            "priority": priority,
            "description": prof_desc, "attachments": []
        }
        self._save_flow(session_id, "ticket", "preview", slots, entities,
                       extra={"ticket_data": ticket_data})

        # Build confirmation payload matching ConfirmationCard.jsx expectations:
        # ConfirmationCard checks: action === 'ticket_preview' && preview
        # preview must have {category, sub_category, priority, title, description, editable}
        confirmation_payload = {
            "action": "ticket_preview",
            "summary": f"Ticket: {title}",
            "preview": {
                "category": category,
                "sub_category": sub_cat,
                "priority": priority,
                "title": title,
                "description": prof_desc,
                "editable": True
            },
            "ticket_data": ticket_data
        }
        preview_text = (f"🎫 **Ticket Preview**\n\n"
                   f"**Category:** {category}\n"
                   f"**Priority:** {priority}\n"
                   f"**Title:** {title}\n"
                   f"**Description:** {prof_desc}\n\n"
                   "Reply **confirm** to create or **cancel** to discard.")
        ao = {"agent_name": "ticket_agent", "detected_intent": "TICKET",
              "confidence": 0.9, "action_type": "ticket_create",
              "preview_or_final": "preview", "message_to_user": preview_text,
              "required_slots": {"description": prof_desc, "category": category},
              "citations": []}
        return self._make_response(
            preview_text, response_type="ticket_preview",
            session_id=session_id, user_id=user_id,
            user_message=message, intent="TICKET", agent="ticket_agent",
            confidence=0.9, student_profile=student_profile,
            agent_output=ao, confirmation_data=confirmation_payload,
            active_flow="ticket", slots=slots)

    def _execute_ticket_create(self, ticket_data, user_id, session_id,
                               student_profile, message, slots):
        clear_flow(session_id, "active")
        if not ticket_data:
            return self._make_response(
                "No ticket data found. Please start over.",
                session_id=session_id, user_id=user_id,
                user_message=message, intent="TICKET",
                student_profile=student_profile)
        action_data = {"action": "ticket_preview", "ticket_data": ticket_data}
        result = self.execute_confirmed_action(
            user_id, session_id, action_data, student_profile)
        return self._make_response(
            result.get("message", "Ticket processed."),
            session_id=session_id, user_id=user_id,
            user_message=message, intent="TICKET", agent="ticket_agent",
            student_profile=student_profile)

    # =========================================================================
    # TICKET STATUS
    # =========================================================================
    def _handle_ticket_status(self, message, user_id, session_id,
                              student_profile, entities):
        try:
            email = student_profile.get("email", user_id) if student_profile else user_id
            msg_lower = message.lower().strip()

            # --- Handle close ticket requests ---
            close_match = re.search(r'close\s+(?:ticket\s*#?\s*)(\S+)', message, re.IGNORECASE)
            close_all = bool(re.search(r'close\s+all\s+ticket', message, re.IGNORECASE))

            if close_all:
                result = self.ticket_agent.close_all_tickets(email)
                text = result.get("message", "Could not close tickets.")
                return self._make_response(
                    text, session_id=session_id, user_id=user_id,
                    user_message=message, intent="TICKET_STATUS", agent="ticket_agent",
                    student_profile=student_profile)
            elif close_match:
                ticket_id = close_match.group(1)
                result = self.ticket_agent.close_ticket(ticket_id, email)
                text = result.get("message", result.get("error", "Could not close ticket."))
                return self._make_response(
                    text, session_id=session_id, user_id=user_id,
                    user_message=message, intent="TICKET_STATUS", agent="ticket_agent",
                    student_profile=student_profile)

            # --- Show all tickets ---
            result = self.ticket_agent.get_student_tickets(email)
            ticket_list = result.get("tickets", []) if isinstance(result, dict) else []
            if not ticket_list:
                text = "You don't have any tickets. Would you like to raise one?"
            else:
                open_tickets = [t for t in ticket_list if t.get("status", "").lower() in ("open", "assigned", "in progress")]
                closed_tickets = [t for t in ticket_list if t.get("status", "").lower() in ("closed", "resolved", "cancelled")]
                lines = [f"📋 **Your Tickets** ({len(ticket_list)} total, {len(open_tickets)} open):\n"]
                for t in ticket_list[:10]:
                    status = t.get("status", "unknown").lower()
                    if status in ("open", "assigned", "in progress"):
                        status_icon = "🟢"
                    elif status in ("resolved", "closed"):
                        status_icon = "🔴"
                    else:
                        status_icon = "⚪"
                    priority = t.get("priority", "")
                    priority_badge = f" [{priority}]" if priority else ""
                    lines.append(f"{status_icon} **#{t.get('ticket_id','')}**{priority_badge} — "
                                f"{t.get('category','N/A')}: {t.get('description','')[:60]}")
                if open_tickets:
                    lines.append("\n💡 To close a ticket, say **close ticket #ID**")
                text = "\n".join(lines)
            ao = {"agent_name": "ticket_agent", "detected_intent": "TICKET_STATUS",
                  "confidence": 0.9, "action_type": "answer",
                  "preview_or_final": "final", "message_to_user": text,
                  "required_slots": {}, "citations": []}
            return self._make_response(
                text, session_id=session_id, user_id=user_id,
                user_message=message, intent="TICKET_STATUS", agent="ticket_agent",
                student_profile=student_profile, agent_output=ao)
        except Exception as e:
            print(f"[ERROR] Ticket status: {e}")
            traceback.print_exc()
            return self._make_response(
                "Error fetching tickets. Please try again.",
                session_id=session_id, user_id=user_id,
                user_message=message, intent="TICKET_STATUS",
                student_profile=student_profile)

    # =========================================================================
    # CONFIRMED ACTION EXECUTION (rate-limited, deduplicated)
    # =========================================================================
    @staticmethod
    def _action_hash(user_id: str, action_data: Dict) -> str:
        parts = [user_id, action_data.get("action", ""),
                 str(action_data.get("preview", {}).get("to", "")),
                 str(action_data.get("preview", {}).get("subject", ""))[:50],
                 str(action_data.get("ticket_data", {}).get("description", ""))[:50]]
        return hashlib.md5("|".join(parts).encode()).hexdigest()

    def execute_confirmed_action(self, user_id, session_id, action_data,
                                 student_profile=None) -> Dict:
        action_type = action_data.get("action", "")
        action_id = self._action_hash(user_id, action_data)

        # Guard: double execution
        if action_id in self._executed_actions:
            return {"success": False,
                    "message": "⚠️ This action was already executed."}

        try:
            if action_type in ["send_email", "email_preview"]:
                allowed, remaining, mx = LimitsService.check_daily_limit(user_id, 'email')
                if not allowed:
                    return {"success": False,
                            "message": f"📧 Daily email limit reached ({mx}/{mx})."}
                email = action_data.get("preview") or action_data
                result = self.email_agent.send_email(
                    to_email=email.get("to", ""),
                    subject=email.get("subject", ""),
                    body=email.get("body", ""))
                if result.get("success"):
                    self._executed_actions.add(action_id)
                    try:
                        LimitsService.increment_usage(user_id, 'email')
                    except Exception:
                        pass
                    try:
                        ActivityService.log_activity(
                            user_id, ActivityType.EMAIL_SENT,
                            f"Email to {email.get('to_name', email.get('to',''))} — {email.get('subject','')[:60]}")
                    except Exception:
                        pass
                    # Log to email_requests table so it appears in Email History
                    try:
                        sp = student_profile or {}
                        recipient_name = email.get('to_name', email.get('to', ''))
                        faculty_id = email.get('faculty_id', 'N/A')
                        self.faculty_db.log_email_request(
                            student_email=user_id,
                            student_name=sp.get('full_name', sp.get('name', 'Unknown')),
                            student_roll_no=sp.get('roll_number', sp.get('roll_no', 'N/A')),
                            student_department=sp.get('department', 'N/A'),
                            student_year=sp.get('year', 'N/A'),
                            faculty_id=faculty_id,
                            faculty_name=recipient_name if recipient_name else 'Unknown',
                            subject=email.get('subject', 'No Subject'),
                            message=email.get('body', ''),
                            attachment_name=None,
                            status='Sent'
                        )
                    except Exception as e:
                        print(f"[WARN] Failed to log email to history: {e}")
                    # Clear the email flow state so next message isn't trapped
                    clear_flow(session_id, "active")
                    return {"success": True,
                            "message": f"✅ Email sent to {email.get('to_name', email.get('to',''))}!"}
                return {"success": False,
                        "message": f"❌ Failed: {result.get('error', 'Unknown')}"}

            elif action_type == "ticket_preview":
                allowed, remaining, mx = LimitsService.check_daily_limit(user_id, 'ticket')
                if not allowed:
                    return {"success": False,
                            "message": f"🎫 Daily ticket limit reached ({mx}/{mx})."}
                td = action_data.get("ticket_data", {})
                td["student_email"] = user_id
                # Merge edited fields from frontend if present
                edited = action_data.get("edited_draft", {})
                if edited:
                    if edited.get("description"):
                        td["description"] = edited["description"]
                    if edited.get("title"):
                        td["description"] = f"{edited['title']}\n\n{td.get('description', '')}"
                    if edited.get("category"):
                        td["category"] = edited["category"]
                    if edited.get("priority"):
                        td["priority"] = edited["priority"]
                cat = td.get("category", "Other")
                if cat in CATEGORIES:
                    td["sub_category"] = CATEGORIES[cat][0]
                else:
                    td["sub_category"] = "General Query"
                # Ensure priority is set
                if not td.get("priority"):
                    td["priority"] = "Medium"
                result = self.ticket_agent.create_ticket(td)
                if result.get("success"):
                    tid = result.get("ticket_id")
                    self._executed_actions.add(action_id)
                    try:
                        LimitsService.increment_usage(user_id, 'ticket')
                    except Exception:
                        pass
                    try:
                        ActivityService.log_activity(
                            user_id, ActivityType.TICKET_CREATED,
                            f"Ticket #{tid} — {cat}: {td.get('description','')[:60]}")
                    except Exception:
                        pass
                    # Clear the ticket flow state so next message isn't trapped
                    clear_flow(session_id, "active")
                    return {"success": True, "ticket_id": tid,
                            "message": f"✅ Ticket **#{tid}** created!"}
                return {"success": False,
                        "message": f"❌ Failed: {result.get('error', 'Unknown')}"}
            else:
                return {"success": False, "message": f"Unknown action: {action_type}"}
        except Exception as e:
            print(f"[ERROR] Action execution: {e}")
            return {"success": False, "message": f"Error: {str(e)}"}


# =============================================================================
# SINGLETON
# =============================================================================
_orchestrator_instance = None

def get_orchestrator() -> OrchestratorAgent:
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = OrchestratorAgent()
    return _orchestrator_instance


if __name__ == "__main__":
    o = OrchestratorAgent()
    r = o.process_message("What courses are offered?", "test@test.com", "test-1")
    print(f"Result: {r}")
