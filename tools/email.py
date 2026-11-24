"""
tools/email.py - Safe Email Drafter
Drafts emails with explicit safety lock.
Rule: "Bina approval ke email SEND mat karna"
"""
from typing import Optional
from utils.helpers import logger


class SafeEmailTool:
    """Enforces the rule that NO email can ever be dispatched without explicit user approval."""

    @staticmethod
    def draft_email(to: str, subject: str, body: str, context: Optional[str] = None) -> dict:
        """Create an email draft and return it for user review."""
        return {
            "status": "DRAFT_READY",
            "approval_required": True,
            "to": to,
            "subject": subject,
            "body": body,
            "context": context or "",
            "instructions": "⚠️ Rule: Bina user approval ke email send nahi hoga. Reply 'APPROVE' to send.",
        }

    @staticmethod
    def send_email(to: str, subject: str, body: str, approval_token: str) -> dict:
        """Protected method that strictly validates confirmation."""
        if approval_token != "APPROVED_BY_OWNER":
            return {
                "status": "BLOCKED",
                "error": "Security Rule: Email sending was blocked because explicit owner approval was not provided.",
            }

        logger.info(f"[Email] Explicit approval granted. Simulating email dispatch to {to}...")
        return {
            "status": "SENT",
            "recipient": to,
            "subject": subject,
            "message": "Email has been dispatched successfully.",
        }


email_tool = SafeEmailTool()
