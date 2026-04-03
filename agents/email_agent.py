"""
Email Agent - Sends emails using SendGrid API with LLM-powered body generation
Now supports image attachments!
"""
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
    SENDGRID_AVAILABLE = True
except Exception:
    SendGridAPIClient = None
    Mail = None
    Attachment = None
    SENDGRID_AVAILABLE = False

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except Exception:
    Groq = None
    GROQ_AVAILABLE = False

import sys
import base64
import os
import mimetypes
import requests
sys.path.append('..')
from core.config import SENDGRID_API_KEY, NOTIFICATION_EMAIL_FROM, GROQ_API_KEY


class EmailAgent:
    """Agent for sending emails via SendGrid with LLM-powered body generation and image support"""
    
    def __init__(self):
        self.api_key = SENDGRID_API_KEY
        self.from_email = NOTIFICATION_EMAIL_FROM
        
        # Initialize SendGrid client with debug logging
        print("[EMAIL_AGENT] Initializing EmailAgent...")
        print(f"[EMAIL_AGENT] SendGrid available: {SENDGRID_AVAILABLE}")
        print(f"[EMAIL_AGENT] API key present: {bool(self.api_key)}")
        print(f"[EMAIL_AGENT] From email: {self.from_email}")
        
        if SENDGRID_AVAILABLE and self.api_key:
            try:
                self.client = SendGridAPIClient(self.api_key)
                print("[EMAIL_AGENT] ✓ SendGrid client initialized successfully")
            except Exception as e:
                self.client = None
                print(f"[EMAIL_AGENT] ✗ SendGrid client initialization failed: {e}")
        else:
            self.client = None
            if not SENDGRID_AVAILABLE:
                print("[EMAIL_AGENT] ✗ SendGrid package not available")
            if not self.api_key:
                print("[EMAIL_AGENT] ✗ SendGrid API key not set")
        
        # Initialize Groq client for email body generation
        if GROQ_AVAILABLE and GROQ_API_KEY:
            try:
                self.llm_client = Groq(api_key=GROQ_API_KEY)
            except Exception:
                self.llm_client = None
        else:
            self.llm_client = None
        
        self.model = "llama-3.1-8b-instant"

    def generate_email_subject(self, purpose: str, regenerate: bool = False) -> str:
        """
        Generate a concise, professional email subject line (6-10 words).
        
        CRITICAL RULES:
        - Subject must directly match the user's purpose (NO creativity, NO paraphrasing)
        - At least one noun phrase from purpose must appear VERBATIM in subject
        - NEVER change the intent or topic of the email
        
        Args:
            purpose: The main purpose/topic of the email
            regenerate: If True, vary the phrasing for regeneration
            
        Returns:
            str: Generated email subject line
        """
        if not GROQ_AVAILABLE or self.llm_client is None:
            # Fallback: Extract first 8 words from purpose
            words = purpose.split()[:8]
            return " ".join(words).capitalize()
        
        try:
            temperature = 0.3 if regenerate else 0.2  # Lower temp for strict purpose preservation
            
            prompt = f"""Generate a concise email subject line based STRICTLY on this purpose:

Purpose: {purpose}

CRITICAL RULES (DO NOT VIOLATE):
1. Subject MUST directly reflect the purpose - NO creativity, NO topic changes
2. At least one noun phrase from the purpose MUST appear VERBATIM in the subject
3. Subject must be 6-10 words maximum
4. Use professional, clear language
5. DO NOT add information not in the purpose
6. DO NOT paraphrase the core topic (keep key nouns/verbs unchanged)

VALIDATION CHECK:
- Does the subject match the user's intended purpose? (If NO → regenerate)
- Does the subject contain verbatim words from the purpose? (If NO → regenerate)

Generate ONLY the subject line, nothing else."""

            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a strict email subject line generator. Your ONLY job is to preserve the user's purpose exactly. NEVER change topics, NEVER add creativity. Use verbatim phrases from the purpose."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=30
            )
            
            subject = response.choices[0].message.content.strip()
            # Remove quotes if present
            subject = subject.strip('"').strip("'")
            
            return subject
            
        except Exception as e:
            # Fallback: Extract first 8 words
            words = purpose.split()[:8]
            return " ".join(words).capitalize()
    
    def generate_email_body(self, purpose: str, recipient_name: str = "", tone: str = "semi-formal", 
                           length: str = "medium", image_count: int = 0, student_name: str = "", 
                           regenerate: bool = False, sender_role: str = "student") -> str:
        """
        Generate a professional email body using LLM with strict rules.
        
        Args:
            purpose: The main purpose/topic of the email
            recipient_name: Optional recipient name for personalization  
            tone: Email tone - "formal", "semi-formal", "friendly", "urgent", or "strict"
            length: Email length - "short" (~3-4 lines), "medium" (~5-7 lines), "detailed" (~10-12 lines)
            image_count: Number of images attached (0 if none)
            student_name: Sender's name for signature
            regenerate: If True, vary the phrasing for regeneration
            sender_role: "student" or "faculty" — controls voice and persona
            
        Returns:
            str: Generated professional email body with signature
        """
        is_faculty = sender_role == "faculty"
        default_sig = student_name if student_name else ("Faculty" if is_faculty else "Student")
        default_greeting_target = recipient_name or ("Student" if is_faculty else "Sir/Madam")

        if not GROQ_AVAILABLE or self.llm_client is None:
            body = f"Dear {default_greeting_target},\n\nI am writing to you regarding: {purpose}"
            if image_count > 0:
                body += "\n\nPlease refer to the attached images for reference."
            signature = f"\n\nBest regards,\n{default_sig}"
            return body + signature
        
        try:
            # Tone descriptions
            tone_guidance = {
                "formal": "Use formal, respectful language. Be direct and professional.",
                "semi-formal": "Use professional but approachable language. Be polite and clear.",
                "friendly": "Use warm, conversational language while maintaining professionalism.",
                "urgent": "Use direct, action-oriented language. Convey urgency while remaining professional.",
                "strict": "Use firm, authoritative language. Be direct and unambiguous. The email should sound commanding but still professional — NOT rude, but clearly leaving no room for negotiation or delay."
            }
            
            # Length guidance - Professional & Detailed
            length_guidance = {
                "short": "At least 3-4 professional sentences. Be concise but clear.",
                "medium": "At least 5-7 professional sentences (roughly 4-6 lines). Provide sufficient context and detail.",
                "detailed": "At least 10-12 professional sentences. Include thorough explanations and next steps."
            }
            
            # Image reference instruction
            image_instruction = ""
            if image_count > 0:
                image_instruction = f"\n- Include ONE brief sentence referencing the {image_count} attached image(s)."
            
            temperature = 0.5 if regenerate else 0.4

            # Build voice rules based on sender role
            if is_faculty:
                voice_rules = (
                    "2. FIRST-PERSON VOICE (MANDATORY):\n"
                    "   - ALWAYS use: \"I am writing\", \"I need\", \"I would like\", \"I expect\"\n"
                    "   - NEVER use: \"we\", \"our college\", \"the institution\"\n"
                    "   - The sender is a FACULTY MEMBER addressing a student\n"
                    "   - Maintain authority appropriate for a teacher/professor"
                )
                system_msg = (
                    f"You are a professional university faculty member. You MUST preserve the user's exact purpose. "
                    f"You MUST write as a FACULTY MEMBER using 'I'. "
                    f"Write a polished, professional email of {length} length with an appropriate '{tone}' tone. "
                    f"Expand on the provided purpose with professional phrasing while staying strictly grounded in the facts."
                )
            else:
                voice_rules = (
                    "2. FIRST-PERSON VOICE (MANDATORY):\n"
                    "   - ALWAYS use: \"I am writing\", \"I need\", \"I would like\", \"my request\"\n"
                    "   - NEVER use: \"we\", \"our college\", \"the institution\", \"our students\", \"the college\"\n"
                    "   - The sender is an INDIVIDUAL STUDENT, NOT an institution"
                )
                system_msg = (
                    f"You are a professional student assistant. You MUST preserve the user's exact purpose. "
                    f"You MUST write using 'I', never as an institution. "
                    f"Write a polished, professional email of {length} length. "
                    f"Expand on the provided purpose with professional phrasing while staying strictly grounded in the facts."
                )
            
            prompt = f"""Generate a professional email body for this EXACT purpose:

Purpose: {purpose}
Recipient Name: {recipient_name or default_greeting_target}
Tone: {tone}
Length: {length}

Tone Guidance: {tone_guidance.get(tone, tone_guidance['semi-formal'])}
Length Guidance: {length_guidance.get(length, length_guidance['medium'])}

⚠️ CRITICAL RULES - VIOLATION WILL CAUSE FAILURE:

1. PURPOSE PRESERVATION (ABSOLUTE PRIORITY):
   - Write ONLY about the stated purpose: "{purpose}"
   - Use the provided details to construct a professional narrative. 
   - Ensure the email explains the context clearly—do not just state the purpose in one line.
   - If the purpose mentions specific Dates, Times, Locations, or Items, you MUST include them.
   - NEVER add hallucinated details (like room numbers or documents) that weren't in the purpose.
   - If the purpose is a STATEMENT, treat it as a confirmed fact or action.

{voice_rules}

3. NO GENERIC FILLER:
   - DO NOT use generic placeholders like "[Your Name]" or "[Date]".
   - DO NOT add pleasantries like "I hope this email finds you well" unless the purpose includes it.
   - Use the specific details from the purpose to make the email sound grounded and authentic.

4. LENGTH REQUIREMENT:
   - {length_guidance.get(length, length_guidance['medium'])}
   - The user expects a reasonable, professional email body of at least 5 sentences.
   - DO NOT provide a 1-2 sentence response.

5. GREETING CONSTRAINT:
   - Use ONLY this line as the greeting: "Dear {recipient_name or default_greeting_target},"
   - Use the recipient's name if provided, otherwise use the default.{image_instruction}

6. PLAIN TEXT FORMAT:
   - NO HTML tags. Use standard punctuation and line breaks ONLY.

Generate ONLY the email body (greeting + content), NO signature."""
            
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=500 if length == "detailed" else (300 if length == "medium" else 150)
            )
            
            body = response.choices[0].message.content.strip()
            
            # Add signature
            signature = f"\n\nBest regards,\n{default_sig}"
            
            return body + signature
            
        except Exception as e:
            # Fallback
            body = f"Dear {default_greeting_target},\n\nI am writing to you regarding: {purpose}"
            if image_count > 0:
                body += "\n\nPlease refer to the attached images for reference."
            signature = f"\n\nBest regards,\n{default_sig}"
            return body + signature

    def _prepare_image_attachment(self, image_url: str) -> dict:
        """
        Download and prepare image for attachment.
        
        Args:
            image_url: URL or local file path of the image
            
        Returns:
            dict with attachment data or None if failed
        """
        try:
            # Check if it's a local file or URL
            if os.path.exists(image_url):
                # Local file
                with open(image_url, 'rb') as f:
                    file_data = f.read()
                filename = os.path.basename(image_url)
            else:
                # URL - download the image
                response = requests.get(image_url, timeout=10)
                response.raise_for_status()
                file_data = response.content
                filename = os.path.basename(image_url.split('?')[0]) or 'image.jpg'
            
            # Encode to base64
            encoded = base64.b64encode(file_data).decode()
            
            # Get MIME type
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                mime_type = 'image/jpeg'
            
            return {
                'content': encoded,
                'filename': filename,
                'type': mime_type
            }
            
        except Exception as e:
            print(f"⚠ Error preparing image {image_url}: {e}")
            return None
    
    def draft_email(self, to_email: str, subject: str, body: str) -> dict:
        """
        Create a draft email for preview before sending.
        
        Args:
            to_email: Recipient email address
            subject: Email subject line
            body: Email body content
            
        Returns:
            dict with email details for preview
        """
        return {
            "from": self.from_email,
            "to": to_email,
            "subject": subject,
            "body": body
        }
    
    def send_email(self, to_email: str, subject: str, body: str, image_urls: list = None, 
                   from_email_override: str = None) -> dict:
        """
        Send an email using SendGrid with optional image attachments.
        
        SAFETY GUARDS:
        - Validates recipient email is not None/empty
        - Validates recipient is not the sender (no fallback to self)
        - Requires subject and body
        - Logs all operations for debugging
        
        Args:
            to_email: Recipient email address
            subject: Email subject line
            body: Email body content
            image_urls: Optional list of image URLs or file paths to attach
            from_email_override: Optional override for sender (for logging only)
            
        Returns:
            dict with status and message
        """
        # SAFETY GUARD 1: Validate recipient email
        if not to_email or not isinstance(to_email, str):
            print(f"⛔ EMAIL_SAFETY: Blocked - recipient email is None or invalid")
            return {
                "success": False,
                "error": "missing_recipient",
                "message": "Cannot send email: No recipient email address provided."
            }
        
        to_email = to_email.strip()
        if not to_email or "@" not in to_email:
            print(f"⛔ EMAIL_SAFETY: Blocked - invalid recipient email format: '{to_email}'")
            return {
                "success": False,
                "error": "invalid_recipient",
                "message": "Cannot send email: Invalid recipient email address."
            }
        
        # SAFETY GUARD 2: Prevent sending to self (fallback protection)
        sender_email = from_email_override or self.from_email
        if to_email.lower() == sender_email.lower():
            print(f"⛔ EMAIL_SAFETY: Blocked - recipient same as sender: '{to_email}'")
            return {
                "success": False,
                "error": "self_send_blocked",
                "message": "Cannot send email to yourself. Please specify a different recipient."
            }
        
        # SAFETY GUARD 3: Validate subject
        if not subject or not isinstance(subject, str) or len(subject.strip()) < 3:
            print(f"⛔ EMAIL_SAFETY: Blocked - missing or invalid subject")
            return {
                "success": False,
                "error": "missing_subject",
                "message": "Cannot send email: Subject line is required."
            }
        
        # SAFETY GUARD 4: Validate body
        if not body or not isinstance(body, str) or len(body.strip()) < 10:
            print(f"⛔ EMAIL_SAFETY: Blocked - missing or too short body")
            return {
                "success": False,
                "error": "missing_body",
                "message": "Cannot send email: Email body is required."
            }
        
        # Log email operation with debug info
        print(f"\n{'='*60}")
        print(f"[EMAIL_AGENT] Preparing email payload")
        print(f"[EMAIL_SEND] To: {to_email}")
        print(f"[EMAIL_SEND] From: {self.from_email}")
        print(f"[EMAIL_SEND] Subject: {subject}")
        print(f"[EMAIL_SEND] Body length: {len(body)} chars")
        print(f"[EMAIL_SEND] SendGrid client status: {'OK' if self.client else 'NOT INITIALIZED'}")
        print(f"{'='*60}")
        
        if not SENDGRID_AVAILABLE or self.client is None:
            print(f"[EMAIL_SEND] ✗ BLOCKED: SendGrid not available or client not initialized")
            return {
                "success": False,
                "error": "sendgrid package not available or client not initialized",
                "message": "SendGrid not configured. Install the `sendgrid` package and set `SENDGRID_API_KEY` to enable email sending."
            }

        try:
            # Convert plain text to HTML for better email rendering
            # Replace newlines with <br> and wrap in <p> tags
            html_body = body.replace('\n\n', '</p><p>').replace('\n', '<br>')
            html_body = f'<p>{html_body}</p>'
            
            message = Mail(
                from_email=self.from_email,
                to_emails=to_email,
                subject=subject,
                html_content=html_body
            )
            
            # Add image attachments if provided
            if image_urls:
                attached_count = 0
                for img_url in image_urls:
                    if not img_url or not img_url.strip():
                        continue
                        
                    attachment_data = self._prepare_image_attachment(img_url.strip())
                    if attachment_data:
                        attachment = Attachment(
                            FileContent(attachment_data['content']),
                            FileName(attachment_data['filename']),
                            FileType(attachment_data['type']),
                            Disposition('attachment')
                        )
                        message.add_attachment(attachment)
                        attached_count += 1
                        print(f"✓ Attached image: {attachment_data['filename']}")

            print(f"[EMAIL_SEND] Calling SendGrid API")
            response = self.client.send(message)
            
            print(f"[EMAIL_SEND] Response status={response.status_code}")
            print(f"[EMAIL_SEND] Response headers: {dict(response.headers) if response.headers else 'None'}")
            
            success_msg = f"Email sent successfully to {to_email}"
            if image_urls and attached_count > 0:
                success_msg += f" with {attached_count} image(s) attached"
            
            print(f"[EMAIL_SEND] ✓ SUCCESS: {success_msg}")
            print(f"{'='*60}\n")

            return {
                "success": True,
                "status_code": response.status_code,
                "message": success_msg,
                "images_attached": attached_count if image_urls else 0
            }

        except Exception as e:
            error_str = str(e)
            print(f"[EMAIL_SEND] ✗ EXCEPTION: {type(e).__name__}: {e}")
            print(f"[EMAIL_SEND] Full error details: {repr(e)}")
            print(f"{'='*60}\n")
            
            # Parse common SendGrid errors for user-friendly messages
            user_message = f"Failed to send email to {to_email}"
            if "401" in error_str or "Unauthorized" in error_str:
                user_message = "Email service authentication failed. Please check SendGrid configuration."
            elif "403" in error_str or "Forbidden" in error_str:
                user_message = "Email sending is not authorized for this sender. Please verify sender domain."
            elif "400" in error_str:
                user_message = "Invalid email request. Please check recipient address and email content."
            elif "500" in error_str:
                user_message = "Email service temporarily unavailable. Please try again later."
            elif "timeout" in error_str.lower():
                user_message = "Email service timed out. Please try again."
            
            return {
                "success": False,
                "error": error_str,
                "error_type": type(e).__name__,
                "message": user_message
            }
    
    def process(self, to_email: str, subject: str, body: str, image_urls: list = None, confirm: bool = True) -> dict:
        """
        Process an email request with optional confirmation and image attachments.
        
        Args:
            to_email: Recipient email address
            subject: Email subject line
            body: Email body content
            image_urls: Optional list of image URLs or file paths
            confirm: If True, show draft first
            
        Returns:
            dict with result
        """
        if confirm:
            draft = self.draft_email(to_email, subject, body)
            print("\n--- Email Draft Preview ---")
            print(f"From: {draft['from']}")
            print(f"To: {draft['to']}")
            print(f"Subject: {draft['subject']}")
            print(f"Body:\n{draft['body']}")
            if image_urls:
                print(f"\nImages to attach: {len(image_urls)}")
                for img in image_urls:
                    print(f"  - {img}")
            print("---------------------------\n")
            
            user_confirm = input("Send this email? (yes/no): ").strip().lower()
            if user_confirm != 'yes':
                return {"success": False, "message": "Email cancelled by user"}
        
        return self.send_email(to_email, subject, body, image_urls)

    def send_test_email(self, recipient: str = "test@example.com") -> None:
        """Run a self-test of the email system"""
        print("\n[EMAIL_AGENT] Running self-test...")
        result = self.send_email(
            to_email=recipient,
            subject="ACE Email Agent Self-Test",
            body="This is an automated test of the ACE College email system. If you received this, the SendGrid integration is working correctly."
        )
        if result["success"]:
            print("[EMAIL_AGENT] ✓ Self-test passed")
        else:
            print(f"[EMAIL_AGENT] ✗ Self-test failed: {result.get('message')}")
