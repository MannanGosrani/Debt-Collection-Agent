import requests
import logging
import os

logger = logging.getLogger(__name__)


class WhatsAppClient:
    def __init__(self, token: str, phone_number_id: str):
        self.token = token
        self.phone_number_id = phone_number_id
        self.base_url = f"https://graph.facebook.com/v19.0/{phone_number_id}"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def send_text_message(self, to: str, message: str) -> bool:
        """
        Send a plain text WhatsApp message.
        Used AFTER the user replies (24-hour session window).
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "body": message
            }
        }

        try:
            response = requests.post(
                f"{self.base_url}/messages",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info(f"Text message sent successfully to {to}")
            return True
        except Exception as e:
            logger.error(f"Failed to send text message to {to}: {e}")
            return False

    def send_template_message(
        self,
        to: str,
        template_name: str,
        language_code: str = "en_US"
    ) -> bool:
        """
        Send a WhatsApp template message.
        Used to INITIATE the conversation (agent-initiated flow).
        """
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code
                }
            }
        }

        try:
            response = requests.post(
                f"{self.base_url}/messages",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info(
                f"Template message '{template_name}' sent successfully to {to}"
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to send template message '{template_name}' to {to}: {e}"
            )
            return False

    def mark_as_read(self, message_id: str) -> bool:
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }

        try:
            response = requests.post(
                f"{self.base_url}/messages",
                headers=self.headers,
                json=payload,
                timeout=10
            )

            if response.status_code != 200:
                logger.error(
                    f"Mark as read failed | "
                    f"Status: {response.status_code} | "
                    f"Response: {response.text}"
                )
                return False

            logger.info(f"Message {message_id} marked as read")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Mark as read request exception: {e}")
            return False