from app.logger import logger

def send_acknowledgement_email(vendor_email: str, status: str, file_name: str, reason: str = ""):
    """Mock email service to send acknowledgement back to vendor."""
    subject = f"Re: Your Invoice {file_name} - Status: {status.upper()}"
    body = f"Hello,\\n\\nWe received your file: {file_name}.\\nStatus: {status.upper()}\\n"
    
    if reason:
        body += f"Message: {reason}\\n"
        
    body += "\\nThank you,\\nAccounts Payable Team"
    
    logger.info("--------------------------------------------------")
    logger.info(f"📧 [MOCK EMAIL SENT TO: {vendor_email}]")
    logger.info(f"Subject: {subject}")
    logger.info(f"Body:\\n{body}")
    logger.info("--------------------------------------------------")
