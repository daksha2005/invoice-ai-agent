import json
import re
from typing import Tuple, Dict, List
from app.config import GEMINI_API_KEY
from app.validator import ExtractedInvoice
from app.logger import logger
from tenacity import retry, stop_after_attempt, wait_exponential

logger.warning("Using fallback invoice extraction. For production, set up Google Generative AI API.")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def classify_and_extract(text: str) -> Tuple[str, Dict]:
    """Classify and extract invoice data from text."""
    try:
        doc_type = classify_document(text)
        extracted_data = extract_invoice_data(text)
        validated = ExtractedInvoice(**extracted_data)
        return doc_type, validated.model_dump()
    except Exception as e:
        logger.error(f"Extraction error: {str(e)}")
        raise e

def classify_document(text: str) -> str:
    """Classify document type."""
    text_lower = text.lower()
    credit_keywords = ["credit", "refund", "adjustment", "credit note", "return"]
    if any(keyword in text_lower for keyword in credit_keywords):
        return "credit_note"
    invoice_keywords = ["invoice", "bill", "amount due", "total", "payable"]
    if any(keyword in text_lower for keyword in invoice_keywords):
        return "standard_invoice"
    return "unknown"

def extract_invoice_data(text: str) -> Dict:
    """Extract all invoice fields."""
    return {
        "vendor_name": extract_vendor_name(text),
        "invoice_number": extract_invoice_number(text),
        "date": extract_date(text),
        "line_items": extract_line_items(text),
        "total_amount": extract_total(text),
        "confidence_score": "0.75"
    }

def extract_vendor_name(text: str) -> str:
    """Extract vendor/company name - usually the first substantial line."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    for line in lines[:15]:
        # Skip lines that are clearly not company names
        if (len(line) > 3 and len(line) < 150 and
            not any(x in line.lower() for x in ['invoice', 'bill', 'date:', 'qty', 'price', 'total', 'gstin', 'gst', '©', 'http']) and
            not line[0].isdigit() and
            any(c.isalpha() for c in line)):
            return line

    return "Unknown Vendor"

def extract_invoice_number(text: str) -> str:
    """Extract invoice number with improved pattern matching."""
    # More specific pattern for invoice numbers
    patterns = [
        r"Invoice\s+(?:No|#|Number)?\s*[:\-]*\s*([A-Z0-9/\-\.\s]+?)(?:\s|$|\n)",
        r"Inv\s*[:\-#]*\s*([A-Z0-9/\-\.]+)",
        r"(?:Invoice|Bill)\s+(?:No|#)\s*[:\-]*\s*([^\s\n]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            inv_num = match.group(1).strip().rstrip('.,;:')
            # Validate it looks like an invoice number
            if inv_num and len(inv_num) < 50 and (any(c.isdigit() for c in inv_num) or '/' in inv_num):
                return inv_num

    return "N/A"

def extract_date(text: str) -> str:
    """Extract invoice date."""
    patterns = [
        r"Date\s*[:\-]*\s*(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})",
        r"Dated\s*[:\-]*\s*(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})",
        r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b",
        r"Date\s*[:\-]*\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
        r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return "N/A"

def extract_line_items(text: str) -> List[Dict]:
    """Extract line items from invoice table."""
    items = []
    # Pattern for: number, description, qty, unit price, amount
    # Looking for table rows with columns
    lines = text.split('\n')
    in_table = False

    for line in lines:
        # Simple pattern: digit + space + text + digit + number + number
        match = re.match(r'^\s*(\d+)\s+(.+?)\s+(\d+)\s+([\d,\.]+)\s+([\d,\.]+)', line)
        if match:
            try:
                item = {
                    "description": match.group(2).strip()[:100],
                    "quantity": match.group(3).strip(),
                    "price": match.group(5).strip().replace(',', '')
                }
                items.append(item)
            except:
                pass

    return items[:10]

def extract_total(text: str) -> str:
    """Extract invoice total amount."""
    # Look for the largest amount which is usually the total
    patterns = [
        r"Invoice\s+Total\s*[:\-]*\s*(?:Rs\.?\s*)?(\d+[\d,\.]*)",
        r"Grand\s+Total\s*[:\-]*\s*(?:Rs\.?\s*)?(\d+[\d,\.]*)",
        r"Total\s+Amount\s*[:\-]*\s*(?:Rs\.?\s*)?(\d+[\d,\.]*)",
        r"Amount\s+Due\s*[:\-]*\s*(?:Rs\.?\s*)?(\d+[\d,\.]*)",
        r"(?:^|\n)TOTAL\s*[:\-]*\s*(?:Rs\.?\s*)?(\d+[\d,\.]*)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        if matches:
            # Get the first valid amount
            for m in matches:
                amount = m.replace(',', '').strip()
                if amount and float(amount) > 0:
                    return amount

    # Fallback: find all numbers that could be amounts
    all_amounts = re.findall(r'(?:Rs\.?\s*)?(\d+[\d,\.]*?)(?:\s|$|\n)', text)
    if all_amounts:
        # Get the largest amount
        amounts = [float(a.replace(',', '')) for a in all_amounts if a and float(a.replace(',', '')) > 100]
        if amounts:
            return str(int(max(amounts)))

    return "0.00"
