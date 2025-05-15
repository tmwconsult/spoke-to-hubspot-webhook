from pathlib import Path

# Re-create the secure webhook script after kernel reset
secured_webhook_code = '''
import os
import requests
import time
import hashlib
import hmac
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

HUBSPOT_TOKEN = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")
HUBSPOT_BASE_URL = "https://api.hubapi.com"
SPOKE_SIGNING_SECRET = os.getenv("SPOKE_SIGNING_SECRET", "").encode()

def find_contact_by_phone(phone_number):
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts/search"
    headers = {
        "Authorization": f"Bearer {HUBSPOT_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "phone",
                "operator": "EQ",
                "value": phone_number
            }]
        }],
        "properties": ["firstname", "lastname", "phone"],
        "limit": 1
    }
    res = requests.post(url, headers=headers, json=data)
    res.raise_for_status()
    results = res.json().get("results", [])
    return results[0] if results else None

def create_note_for_contact(contact_id, message_body):
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/notes"
    headers = {
        "Authorization": f"Bearer {HUBSPOT_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "properties": {
            "hs_note_body": f"Inbound SMS: {message_body}",
            "hs_timestamp": int(time.time() * 1000)
        }
    }
    res = requests.post(url, headers=headers, json=payload)
    res.raise_for_status()
    note = res.json()

    note_id = note["id"]
    assoc_url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/notes/{note_id}/associations/contacts/{contact_id}/note_to_contact"
    assoc_res = requests.put(assoc_url, headers=headers)
    assoc_res.raise_for_status()

    return note

@app.route("/inbound-sms", methods=["POST"])
def handle_inbound_sms():
    signature = request.headers.get("Spoke-Signature")
    raw_body = request.get_data()
    expected_signature = hmac.new(SPOKE_SIGNING_SECRET, raw_body, hashlib.sha256).hexdigest()
    if signature != expected_signature:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    from_number = data.get("from")
    message = data.get("message")

    if not from_number or not message:
        return jsonify({"error": "Missing required fields"}), 400

    contact = find_contact_by_phone(from_number)
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    contact_id = contact["id"]
    note = create_note_for_contact(contact_id, message)
    return jsonify({"status": "note created", "noteId": note.get("id")})

if __name__ == "__main__":
    app.run(debug=True)
'''

# Save the file
file_path = "spoke_to_hubspot_webhook.py"
Path(file_path).write_text(secured_webhook_code.strip())
file_path
