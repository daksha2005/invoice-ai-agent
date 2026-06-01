import json
import re
from typing import Tuple, Dict, List
import google.generativeai as genai
from app.config import GEMINI_API_KEY
from app.validator import ExtractedInvoice
from app.logger import logger
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure Gemini API
if GEMINI_API_KEY and GEMINI_API_KEY != "your_api_key_here":
    genai.configure(api_key=GEMINI_API_KEY)
    MODEL = "gemini-1.5-flash"
    llm_available = True
else:
    logger.warning("GEMINI_API_KEY not set. Using fallback regex extraction.")
    llm_available = False


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def classify_and_extract(text: str) -> Tuple[str, Dict]:
    """
    Classify invoice and extract structured data using Gemini LLM.
    Falls back to regex if LLM unavailable.
    """
    try:
        if llm_available:
            return classify_and_extract_with_llm(text)
        else:
            return classify_and_extract_fallback(text)
    except Exception as e:
        logger.error(f"LLM extraction failed: {str(e)}. Falling back to regex...")
        return classify_and_extract_fallback(text)


def classify_and_extract_with_llm(text: str) -> Tuple[str, Dict]:
    """Use Google Gemini to classify and extract invoice data."""

    prompt = f"""You are an expert at processing vendor invoices and credit notes.

Analyze the following document text and extract the required information.

CLASSIFICATION:
Classify the document as ONE of: "standard_invoice", "credit_note", or "unknown"

EXTRACTION:
Extract these fields (leave blank if not found):
- vendor_name: Name of the company issuing the invoice
- invoice_number: Invoice/bill number
- date: Invoice date (in DD MMM YYYY format if possible)
- line_items: Array of items with description, quantity, price
- total_amount: Final payable amount (for ambiguous cases, use the FINAL PAYABLE amount inclusive of taxes, not subtotal)

IMPORTANT RULES:
1. For ambiguous totals: ALWAYS choose the final payable amount (invoice total), not subtotal or intermediate values
2. For credit notes: extract the actual credited amount (ignore negative signs)
3. Return ONLY valid JSON - no markdown, no extra text
4. If total_amount is ambiguous, explain your choice in a reasoning field

Return EXACTLY this JSON structure:
{{
  "document_type": "standard_invoice|credit_note|unknown",
  "reasoning": "Brief explanation of ambiguous fields if any",
  "extracted_data": {{
    "vendor_name": "string",
    "invoice_number": "string",
    "date": "string",
    "line_items": [
      {{"description": "string", "quantity": "string", "price": "string"}}
    ],
    "total_amount": "string",
    "confidence_score": "0.85"
  }}
}}

DOCUMENT TEXT:
{text}"""

    try:
        model = genai.GenerativeModel(MODEL)
        response = model.generate_content(prompt)

        # Parse LLM response
        response_text = response.text.strip()

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = re.sub(r'^```(?:json)?\n', '', response_text)
            response_text = re.sub(r'\n```$', '', response_text)

        data = json.loads(response_text)

        doc_type = data.get("document_type", "unknown")
        extracted_data = data.get("extracted_data", {})
        reasoning = data.get("reasoning", "")

        if reasoning:
            logger.info(f"LLM Reasoning: {reasoning}")

        # Validate data
        validated = ExtractedInvoice(**extracted_data)
        logger.info(f"✓ LLM extraction successful: {doc_type}")

        return doc_type, validated.model_dump()

    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {str(e)}")
        raise ValueError(f"Malformed JSON from LLM: {str(e)}")
    except Exception as e:
        logger.error(f"LLM extraction failed: {str(e)}")
        raise


def classify_and_extract_fallback(text: str) -> Tuple[str, Dict]:
    """Fallback: regex-based extraction when LLM is unavailable."""
    logger.info("Using fallback regex extraction...")

    doc_type = classify_document_regex(text)
    extracted_data = extract_invoice_data_regex(text)

    validated = ExtractedInvoice(**extracted_data)
    logger.info(f"✓ Fallback extraction successful: {doc_type}")

    return doc_type, validated.model_dump()


# ============= FALLBACK REGEX METHODS =============

def classify_document_regex(text: str) -> str:
    """Fallback: Classify using regex patterns."""
    text_lower = text.lower()

    credit_keywords = ["credit", "refund", "adjustment", "credit note", "return"]
    if any(keyword in text_lower for keyword in credit_keywords):
        return "credit_note"

    invoice_keywords = ["invoice", "bill", "amount due", "total", "payable"]
    if any(keyword in text_lower for keyword in invoice_keywords):
        return "standard_invoice"

    return "unknown"


def extract_invoice_data_regex(text: str) -> Dict:
    """Fallback: Extract using regex patterns."""
    return {
        "vendor_name": extract_vendor_name(text),
        "invoice_number": extract_invoice_number(text),
        "date": extract_date(text),
        "line_items": extract_line_items(text),
        "total_amount": extract_total(text),
        "confidence_score": "0.65"
    }


def extract_vendor_name(text: str) -> str:
    """Extract vendor/company name."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    for line in lines[:15]:
        if (len(line) > 3 and len(line) < 150 and
            not any(x in line.lower() for x in ['invoice', 'bill', 'date:', 'qty', 'price', 'total', 'gstin']) and
            not line[0].isdigit() and
            any(c.isalpha() for c in line)):
            return line

    return "Unknown Vendor"


def extract_invoice_number(text: str) -> str:
    """Extract invoice number."""
    patterns = [
        r"Invoice\s+(?:No|#|Number)?\s*[:\-]*\s*([A-Z0-9/\-\.\s]+?)(?:\s|$|\n)",
        r"Inv\s*[:\-#]*\s*([A-Z0-9/\-\.]+)",
        r"(?:Invoice|Bill)\s+(?:No|#)\s*[:\-]*\s*([^\s\n]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            inv_num = match.group(1).strip().rstrip('.,;:')
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
    lines = text.split('\n')

    for line in lines:
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
    """Extract total amount - prioritize final payable amount."""
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
            for m in matches:
                amount = m.replace(',', '').strip()
                if amount and float(amount) > 0:
                    return amount

    all_amounts = re.findall(r'(?:Rs\.?\s*)?(\d+[\d,\.]*?)(?:\s|$|\n)', text)
    if all_amounts:
        amounts = [float(a.replace(',', '')) for a in all_amounts if a and float(a.replace(',', '')) > 100]
        if amounts:
            return str(int(max(amounts)))

    return "0.00"
