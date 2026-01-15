import sys
import os
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.whatsapp.client import WhatsAppClient
from src.whatsapp.session_manager import SessionManager
from src.whatsapp.conversation_starter import start_conversation

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
    raise RuntimeError("WhatsApp credentials not found in .env")

# Initialize client and session manager
client = WhatsAppClient(
    token=WHATSAPP_TOKEN,
    phone_number_id=PHONE_NUMBER_ID
)

session_manager = SessionManager()

# 👇 Replace with the recipient number you want to test
TEST_PHONE_NUMBER = "+917506319945"

# Start conversation (sends template + creates session)
success = start_conversation(client, session_manager, TEST_PHONE_NUMBER)

if success:
    print("✅ WhatsApp conversation initiated")
    print(f"✅ Session created for {TEST_PHONE_NUMBER}")
    print("📱 User can now reply and agent will respond")
else:
    print("❌ Failed to initiate conversation")