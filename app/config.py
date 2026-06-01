import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
CSV_FALLBACK_PATH = os.getenv("CSV_FALLBACK_PATH", "data/output/invoices.csv")
HUMAN_REVIEW_LOG_PATH = os.getenv("HUMAN_REVIEW_LOG_PATH", "data/output/human_review.log")
