from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from app.ingestion import WebhookPayload, save_attachment
from app.parser import parse_document
from app.classifier import classify_and_extract
from app.router import process_and_route
from services.email_service import send_acknowledgement_email
from app.logger import logger
from app.utils import ensure_dir_exists
import json
import os
import shutil
from typing import List
import concurrent.futures

app = FastAPI(title="Invoice AI Agent", description="Webhook handler for vendor invoices")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def dashboard():
    html_file = "index.html"
    if os.path.exists(html_file):
        with open(html_file, "r") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Invoice AI Agent Pipeline</h1><p>index.html not found.</p>")

def handle_single_file(file_name: str, file_path: str):
    try:
        logger.info(f"Parsing document: {file_name}")
        raw_text = parse_document(file_path)
        
        logger.info(f"Extracting data: {file_name}")
        doc_type, extracted_data = classify_and_extract(raw_text)
        
        os.makedirs("sample_output/extracted_json", exist_ok=True)
        with open(f"sample_output/extracted_json/{file_name}.json", "w") as f:
            json.dump({"type": doc_type, "data": extracted_data}, f, indent=2)
            
        route = process_and_route(doc_type, extracted_data, file_name)
        
        return {
            "file": file_name,
            "status": "success",
            "data": extracted_data,
            "route": route,
            "classification": doc_type,
            "reason": "Processed successfully."
        }
    except Exception as e:
        logger.error(f"Failed to process {file_name}: {str(e)}")
        return {
            "file": file_name,
            "status": "failed",
            "reason": str(e)
        }

@app.post("/process")
def process_uploaded_files(files: List[UploadFile] = File(...)):
    results = []
    ensure_dir_exists("data/input/dummy.txt")
    
    saved_files = []
    # Save all files sequentially to avoid file I/O conflicts
    for file in files:
        file_name = file.filename
        file_path = os.path.join("data/input", file_name)
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_files.append((file_name, file_path))
        except Exception as e:
            logger.error(f"Failed to save {file_name}: {str(e)}")
            results.append({
                "file": file_name,
                "status": "failed",
                "reason": f"Failed to save uploaded file: {str(e)}"
            })
    
    # Process files concurrently to avoid timeouts
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_file = {executor.submit(handle_single_file, fname, fpath): fname for fname, fpath in saved_files}
        for future in concurrent.futures.as_completed(future_to_file):
            results.append(future.result())
            
    return {"results": results}

def process_pipeline(payload: WebhookPayload):
    file_name = payload.attachment.filename
    vendor_email = payload.from_email
    
    try:
        file_path = save_attachment(payload.attachment)
        logger.info(f"Parsing document: {file_name}")
        raw_text = parse_document(file_path)
        logger.info(f"Extracting data: {file_name}")
        doc_type, extracted_data = classify_and_extract(raw_text)
        process_and_route(doc_type, extracted_data, file_name)
        send_acknowledgement_email(vendor_email, "success", file_name, "Document processed and routed successfully.")
    except Exception as e:
        logger.error(f"Failed to process {file_name}: {str(e)}")
        send_acknowledgement_email(vendor_email, "failed", file_name, f"Processing error: {str(e)}")

@app.post("/webhook/inbound-email")
def handle_inbound_email(payload: WebhookPayload, background_tasks: BackgroundTasks):
    logger.info(f"📥 Received webhook for event: {payload.event_id}")
    background_tasks.add_task(process_pipeline, payload)
    return {"status": "accepted", "message": "Email queued for processing"}

