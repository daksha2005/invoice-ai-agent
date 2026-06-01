from pydantic import BaseModel, Field
from typing import List, Optional

class LineItem(BaseModel):
    description: str = ""
    quantity: str = ""
    price: str = ""

class ExtractedInvoice(BaseModel):
    vendor_name: str = ""
    invoice_number: str = ""
    date: str = ""
    line_items: List[LineItem] = Field(default_factory=list)
    total_amount: str = ""
    confidence_score: str = ""
