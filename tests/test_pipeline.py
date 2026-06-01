import json
import requests
import time

def test_webhook():
    with open("webhook_payload.json", "r") as f:
        data = json.load(f)
        
    for event in data["events"]:
        print(f"Sending {event['event_id']}...")
        response = requests.post("http://localhost:3000/webhook/inbound-email", json=event)
        print(f"Response: {response.status_code} - {response.json()}")
        time.sleep(1)

if __name__ == "__main__":
    test_webhook()
