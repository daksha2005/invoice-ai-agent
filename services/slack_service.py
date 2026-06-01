import requests
from app.config import SLACK_WEBHOOK_URL
from app.logger import logger

def send_slack_notification(vendor_name: str, invoice_number: str, amount: str):
    if not SLACK_WEBHOOK_URL or SLACK_WEBHOOK_URL == "mock_url" or "localhost" in SLACK_WEBHOOK_URL or "mock" in SLACK_WEBHOOK_URL:
        logger.info(f"🔔 [MOCK SLACK] High-value invoice routed to Slack: Vendor={vendor_name}, Inv={invoice_number}, Amount={amount}")
        return True
        
    payload = {
        "text": f"🚨 *High Value Invoice Alert* 🚨\\n*Vendor*: {vendor_name}\\n*Invoice #*: {invoice_number}\\n*Amount*: {amount}"
    }
    
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"✅ Slack notification sent for invoice {invoice_number}.")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send Slack notification: {str(e)}")
        return False
