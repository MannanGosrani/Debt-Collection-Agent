import logging
from src.graph import app
from src.whatsapp.session_manager import SessionManager
from src.whatsapp.client import WhatsAppClient
from src.whatsapp.message_formatter import format_for_whatsapp
from src.state import validate_state

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
                    f" Ignoring message from {from_number}  session already closed"
                )
                return {"status": "ignored"}

            # Append user message
            state["messages"].append(
                {"role": "user", "content": message_text}
            )
            state["last_user_input"] = message_text
            state["awaiting_user"] = False

            logger.info(f" Processing message from {from_number}")
            
            validate_state(state)

            # Run LangGraph
            updated_state = app.invoke(
                state,
                config={"recursion_limit": 25}
            )

            # Send assistant response if present
            if updated_state.get("messages"):
                last_msg = updated_state["messages"][-1]
                if last_msg.get("role") == "assistant":
                    reply = format_for_whatsapp(last_msg["content"])
                    self.client.send_text_message(from_number, reply)

            # End or update session
            if updated_state.get("is_complete"):
                logger.info(
                    f" Ending session for {from_number} (conversation complete)"
                )
                self.session_manager.end_session(from_number)
            else:
                self.session_manager.update_session(from_number, updated_state)

            return {"status": "success"}

        except Exception as e:
            logger.error(
                f"[FATAL] Agent execution failed for {from_number}: {e}",
                exc_info=True
            )

            # Attempt to persist failure context
            try:
                if state:
                    self._record_failure(state, e)
                    self.session_manager.update_session(from_number, state)
            except Exception as persist_error:  
                logger.error(
                    f"[FATAL] Failed to persist error state: {persist_error}",
                    exc_info=True
                )

            # User-safe response
            self.client.send_text_message(
                from_number,
                "We’re facing a technical issue right now. "
                "Your request has been logged and we’ll follow up shortly."
            )

            return {"status": "error"}

        
    def _record_failure(self, state: dict, error: Exception):
        """
        Persist failure details into state for debugging and audit.
        Does NOT expose internal details to the user.
        """
        state["call_outcome"] = "system_error"
        state["call_summary"] = f"Unhandled exception: {type(error).__name__}"
        state["is_complete"] = True
