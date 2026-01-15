"""
Responsible for initiating WhatsApp conversations using templates.
This runs OUTSIDE the LangGraph agent.
Phase 1: Now creates template-initiated session BEFORE sending template.
"""

from src.whatsapp.client import WhatsAppClient
from src.whatsapp.session_manager import SessionManager
import logging

logger = logging.getLogger(__name__)


def start_conversation(
    client: WhatsAppClient,
    session_manager: SessionManager,
    phone_number: str
) -> bool:
    """
    Send the initial WhatsApp message to start the conversation.
    
    Steps:
    1. Create template-initiated session
    2. Send template message
    3. If template fails, cleanup session
    
    Returns:
        bool: True if conversation started successfully, False otherwise
    """
    
    # Step 1: Create template-initiated session
    session_created = session_manager.create_template_initiated_session(phone_number)
    
    if not session_created:
        logger.error(f"Failed to create session for {phone_number}")
        return False
    
    # Step 2: Send template message
    template_sent = client.send_template_message(
        to=phone_number,
        template_name="account_notification_1",  # temporary - using approved template
        language_code="en_US"
    )
    
    # Step 3: Cleanup if template send failed
    if not template_sent:
        logger.error(f"Template send failed for {phone_number}, cleaning up session")
        session_manager.end_session(phone_number)
        return False
    
    logger.info(f" Conversation initiated successfully for {phone_number}")
    return True