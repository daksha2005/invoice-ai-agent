import pdfplumber
import pytesseract
from PIL import Image
import os
from app.logger import logger
import fitz  # PyMuPDF

# Configure pytesseract to find Tesseract on Windows
pytesseract.pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def parse_document(file_path: str) -> str:
    """Extract text from PDF or Image."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    ext = file_path.lower().split('.')[-1]
    
    try:
        if ext == 'pdf':
            return parse_pdf(file_path)
        elif ext in ['jpg', 'jpeg', 'png']:
            return parse_image(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
    except Exception as e:
        logger.error(f"Error parsing document {file_path}: {str(e)}")
        raise e

def parse_pdf(file_path: str) -> str:
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\\n"
    except Exception as e:
        logger.warning(f"pdfplumber failed: {str(e)}. Falling back to OCR.")
        
    if not text.strip():
        logger.info(f"No text extracted via pdfplumber for {file_path}, attempting OCR via PyMuPDF.")
        try:
            with fitz.open(file_path) as doc:
                for page_num in range(min(3, len(doc))):  # Only process up to 3 pages to save time
                    page = doc.load_page(page_num)
                    pix = page.get_pixmap()
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    text += pytesseract.image_to_string(img) + "\\n"
        except Exception as e:
            logger.error(f"OCR fallback failed: {str(e)}")
                
    if not text.strip():
        raise ValueError("Could not extract text from document (blank or unreadable).")
        
    return text

def parse_image(file_path: str) -> str:
    try:
        img = Image.open(file_path)
        text = pytesseract.image_to_string(img)
        if not text.strip():
            raise ValueError("Could not extract text from Image (blank or unreadable).")
        return text
    except Exception as e:
        logger.error(f"Error parsing image {file_path}: {str(e)}")
        raise e
