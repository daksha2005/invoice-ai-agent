import base64
import os
import shutil
from typing import Optional
from pydantic import BaseModel, Field
from app.logger import logger

class AttachmentPayload(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    local_path: Optional[str] = None
    base64_content: Optional[str] = None

class WebhookPayload(BaseModel):
    event_id: str
    received_at: str
    from_email: str = Field(alias="from")
    subject: str
    body_preview: str
    attachment: AttachmentPayload

def save_attachment(attachment: AttachmentPayload, output_dir: str = "data/input") -> str:
    """Save the incoming attachment to the input folder."""
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, attachment.filename)
    
    if attachment.base64_content:
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(attachment.base64_content))
    elif attachment.local_path and os.path.exists(attachment.local_path):
        shutil.copy(attachment.local_path, file_path)
    else:
        # Create a dummy file if testing without real files (so parser can at least throw correct error)
        logger.warning(f"No valid file source found for {attachment.filename}. Creating dummy file.")
        with open(file_path, "w") as f:
            f.write("")
            
    return file_path
