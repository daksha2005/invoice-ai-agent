import os
from app.logger import logger
from services.slack_service import send_slack_notification
from services.sheet_service import append_to_csv
from app.config import HUMAN_REVIEW_LOG_PATH
from app.utils import ensure_dir_exists
import re

def process_and_route(doc_type: str, extracted_data: dict, file_name: str) -> str:
    logger.info(f"Routing document {file_name}. Type: {doc_type}")
    
    if doc_type == "unknown":
        _log_human_review(file_name, "Document classified as unknown.")
        return "HUMAN_REVIEW"
        
    # Extract numerical value from total_amount
    amount_str = extracted_data.get("total_amount", "0")
    # Clean string: remove commas, currency symbols, handle parentheses as negative
    clean_amount = re.sub(r'[^\d.-]', '', amount_str.replace(',', ''))
    
    try:
        amount_val = float(clean_amount)
        # Handle negative values for credit notes (turn them into absolute numbers for magnitude check if needed, but routing rule is based on value > 50000)
        amount_val = abs(amount_val)
    except ValueError:
        logger.warning(f"Could not parse amount '{amount_str}'. Routing to manual review.")
        _log_human_review(file_name, f"Unparseable amount: {amount_str}")
        return "HUMAN_REVIEW"

    if amount_val > 50000:
        logger.info(f"💰 Amount {amount_val} > 50000. Routing to Slack.")
        send_slack_notification(
            vendor_name=extracted_data.get("vendor_name", "Unknown"),
            invoice_number=extracted_data.get("invoice_number", "Unknown"),
            amount=amount_str
        )
        return "SLACK"
    else:
        logger.info(f"🧾 Amount {amount_val} <= 50000. Logging to CSV.")
        append_to_csv(extracted_data)
        return "CSV_SHEET"

def _log_human_review(file_name: str, reason: str):
    ensure_dir_exists(HUMAN_REVIEW_LOG_PATH)
    with open(HUMAN_REVIEW_LOG_PATH, "a") as f:
        f.write(f"FILE: {file_name} | REASON: {reason}\\n")
    logger.info(f"⚠️ Document {file_name} flagged for human review: {reason}")
