import uvicorn
from app.utils import ensure_dir_exists

if __name__ == "__main__":
    ensure_dir_exists("data/input/dummy.txt")
    ensure_dir_exists("data/output/dummy.txt")
    ensure_dir_exists("sample_output/extracted_json/dummy.txt")
    ensure_dir_exists("sample_output/routing_logs/dummy.txt")
    uvicorn.run("app.main:app", host="0.0.0.0", port=3000)
