# src/whatsapp/agent_handler.py

import logging
from src.graph import app
from src.whatsapp.session_manager import SessionManager
from src.whatsapp.client import WhatsAppClient
from src.whatsapp.message_formatter import format_for_whatsapp

logger = logging.getLogger(__name__)


class WhatsAppAgentHandler:
    def __init__(self, whatsapp_client: WhatsAppClient):
        self.client = whatsapp_client
        self.session_manager = SessionManager()

    async def process_message(
        self,
        from_number: str,
        message_text: str,
        message_id: str
    ):
        try:
            # Mark message as read
            self.client.mark_as_read(message_id)

            # Get session (may return None if session is completed)
            state = self.session_manager.get_or_create_session(from_number)

            # HARD STOP: Session already completed
            if state is None:
                logger.info(
                    f"🚫 Ignoring message from {from_number} — session already closed"
                )
                return {"status": "ignored"}

            # Append user message
            state["messages"].append(
                {"role": "user", "content": message_text}
            )
            state["last_user_input"] = message_text
            state["awaiting_user"] = False

            logger.info(f"🤖 Processing message from {from_number}")
            logger.info(f"📊 Stage: {state.get('stage')}, Has greeted: {state.get('has_greeted')}")

            # Run LangGraph
            updated_state = app.invoke(
                state,
                config={"recursion_limit": 25}
            )

            logger.info(f"✅ Graph completed. New stage: {updated_state.get('stage')}")

            # Send assistant response if present
            if updated_state.get("messages"):
                last_msg = updated_state["messages"][-1]
                logger.info(f"📤 Last message role: {last_msg.get('role')}")
                
                if last_msg.get("role") == "assistant":
                    reply = format_for_whatsapp(last_msg["content"])
                    logger.info(f"📨 Sending reply: {reply[:100]}...")
                    self.client.send_text_message(from_number, reply)
                else:
                    logger.warning(f"⚠️ Last message was not from assistant: {last_msg.get('role')}")

            # End or update session
            if updated_state.get("is_complete"):
                logger.info(
                    f"🔒 Ending session for {from_number} (conversation complete)"
                )
                self.session_manager.end_session(from_number)
            else:
                self.session_manager.update_session(from_number, updated_state)

            return {"status": "success"}

        except Exception as e:
            logger.error(f"❌ Agent error: {e}", exc_info=True)
            self.client.send_text_message(
                from_number,
                "Something went wrong. Please try again later."
            )
            return {"status": "error"}