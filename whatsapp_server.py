import logging
from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse
from src.whatsapp.agent_handler import WhatsAppAgentHandler
from src.whatsapp.client import WhatsAppClient
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

# Debug logging
logger.info("=" * 60)
logger.info("🔑 Environment Variables:")
logger.info(f"   VERIFY_TOKEN: {VERIFY_TOKEN}")
logger.info(f"   WHATSAPP_TOKEN: {'✅ SET' if WHATSAPP_TOKEN else '❌ NOT SET'}")
logger.info(f"   PHONE_NUMBER_ID: {PHONE_NUMBER_ID}")
logger.info("=" * 60)

app = FastAPI()

whatsapp_client = WhatsAppClient(
    token=WHATSAPP_TOKEN,
    phone_number_id=PHONE_NUMBER_ID
)
agent_handler = WhatsAppAgentHandler(whatsapp_client)


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token")
):
    """
    Webhook verification endpoint.
    Meta sends parameters with dots (hub.mode) but we use underscores internally.
    """
    logger.info("🔍 Webhook verification attempt:")
    logger.info(f"   Mode: {hub_mode}")
    logger.info(f"   Received token: {hub_verify_token}")
    logger.info(f"   Expected token: {VERIFY_TOKEN}")
    logger.info(f"   Match: {hub_verify_token == VERIFY_TOKEN}")
    
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        logger.info("✅ Webhook verified successfully!")
        return PlainTextResponse(content=hub_challenge)
    
    logger.warning("❌ Webhook verification FAILED")
    return PlainTextResponse(content="Verification failed", status_code=403)


@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()

    logger.info("🔔 WEBHOOK POST RECEIVED")
    logger.info(f"Full payload: {payload}")

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})

            # ✅ INBOUND USER MESSAGE
            if "messages" in value:
                for msg in value["messages"]:
                    from_number = msg["from"]
                    message_id = msg["id"]
                    text = msg.get("text", {}).get("body", "")

                    logger.info("📱 Message extracted:")
                    logger.info(f"   From: {from_number}")
                    logger.info(f"   Text: {text}")
                    logger.info(f"   ID: {message_id}")

                    await agent_handler.process_message(
                        from_number=from_number,
                        message_text=text,
                        message_id=message_id
                    )

            # ✅ STATUS UPDATE (read/delivered/sent)
            elif "statuses" in value:
                logger.info("ℹ️ Status update received — ignored")

            else:
                logger.info("ℹ️ Unknown webhook payload — ignored")

    return {"status": "ok"}