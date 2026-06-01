import pandas as pd
import os
from app.config import CSV_FALLBACK_PATH
from app.utils import ensure_dir_exists
from app.logger import logger

def append_to_csv(data: dict):
    ensure_dir_exists(CSV_FALLBACK_PATH)
    
    # Flatten line items for simple CSV
    flat_data = {
        "vendor_name": data.get("vendor_name"),
        "invoice_number": data.get("invoice_number"),
        "date": data.get("date"),
        "total_amount": data.get("total_amount"),
        "line_items_count": len(data.get("line_items", []))
    }
    
    df = pd.DataFrame([flat_data])
    
    try:
        # Append if exists, else write new
        if os.path.exists(CSV_FALLBACK_PATH):
            df.to_csv(CSV_FALLBACK_PATH, mode='a', header=False, index=False)
        else:
            df.to_csv(CSV_FALLBACK_PATH, mode='w', header=True, index=False)
        logger.info(f"📝 Appended document {flat_data['invoice_number']} to CSV sheet at {CSV_FALLBACK_PATH}")
    except Exception as e:
        logger.error(f"❌ Failed to append to CSV: {str(e)}")
