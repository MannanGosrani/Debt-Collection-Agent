# src/session_manager.py

from typing import Dict, Optional
from datetime import datetime
import logging
import json
import os

from src.state import CallState, create_initial_state
from src.data import normalize_phone_number

logger = logging.getLogger(__name__)

SESSION_FILE = "whatsapp_sessions.json"

# HARD STOP FLAG
# If True, once state["is_complete"] == True,
# the session will NOT accept any further messages
END_SESSION_ON_COMPLETE = True


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, dict] = {}
        self._load_sessions()

    # --------------------------------------------------
    # Load existing sessions from disk
    # --------------------------------------------------
    def _load_sessions(self):
        if not os.path.exists(SESSION_FILE):
            return

        try:
            with open(SESSION_FILE, "r") as f:
                data = json.load(f)
                for phone, session in data.items():
                    session["session_start_time"] = datetime.fromisoformat(
                        session["session_start_time"]
                    )
                    session["last_activity_time"] = datetime.fromisoformat(
                        session["last_activity_time"]
                    )
                self.sessions = data
                logger.info(f" Loaded {len(self.sessions)} sessions")
        except Exception as e:
            logger.error(f" Failed to load sessions: {e}")

    # --------------------------------------------------
    # Persist sessions to disk
    # --------------------------------------------------
    def _save_sessions(self):
        data = {}
        for phone, session in self.sessions.items():
            data[phone] = {
                "state": session["state"],
                "session_start_time": session["session_start_time"].isoformat(),
                "last_activity_time": session["last_activity_time"].isoformat(),
                "message_count": session["message_count"],
            }

        with open(SESSION_FILE, "w") as f:
            json.dump(data, f, indent=2)

    # --------------------------------------------------
    # Get or create a session
    # --------------------------------------------------
    def get_or_create_session(self, phone_number: str) -> Optional[CallState]:
        normalized = normalize_phone_number(phone_number)

        # ----------------------------------------------
        # Existing session
        # ----------------------------------------------
        if normalized in self.sessions:
            session = self.sessions[normalized]
            state: CallState = session["state"]

            # HARD STOP â€” session already completed
            if END_SESSION_ON_COMPLETE and state.get("is_complete"):
                logger.info(
                    f" Ignoring message for completed session: {normalized}"
                )
                return None  # DO NOT continue conversation

            # Normal session continuation
            session["last_activity_time"] = datetime.now()
            session["message_count"] += 1
            self._save_sessions()
            return state

        # ----------------------------------------------
        # Create new session
        # ----------------------------------------------
        logger.info(f" Creating new session for {normalized}")

        state = create_initial_state(normalized)

        self.sessions[normalized] = {
            "state": state,
            "session_start_time": datetime.now(),
            "last_activity_time": datetime.now(),
            "message_count": 1,
        }

        self._save_sessions()
        return state

    # --------------------------------------------------
    # Update an existing session
    # --------------------------------------------------
    def update_session(self, phone_number: str, state: CallState):
        normalized = normalize_phone_number(phone_number)

        if normalized not in self.sessions:
            return

        self.sessions[normalized]["state"] = state
        self.sessions[normalized]["last_activity_time"] = datetime.now()

        # OPTIONAL: auto-delete completed sessions
        if END_SESSION_ON_COMPLETE and state.get("is_complete"):
            logger.info(f" Auto-ending completed session for {normalized}")
            self.end_session(phone_number)
            return

        self._save_sessions()

    # --------------------------------------------------
    # Explicitly end a session
    # --------------------------------------------------
    def end_session(self, phone_number: str):
        normalized = normalize_phone_number(phone_number)

        if normalized in self.sessions:
            del self.sessions[normalized]
            self._save_sessions()
            logger.info(f" Session ended for {normalized}")