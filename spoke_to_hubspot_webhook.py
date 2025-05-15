
import os
from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

HUBSPOT_TOKEN = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")
HUBSPOT_BASE_URL = "https://api.hubapi.com"

def find_contact_by_phone(phone_number):
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts/search"
    headers = {
        "Authorization": f"Bearer {HUBSPOT_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "phone",
                "operator": "EQ",
                "value": phone_number
            }]
        }],
        "properties": ["firstname", "lastname", "email"]
    }

    res = requests.post(url, headers=headers, json=payload)
    res.raise_for_status()
    results = res.json().get("results", [])
    return results[0] if results else None

import time

def create_note_for_contact(contact_id, message_body):
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/notes"
    headers = {
        "Authorization": f"Bearer {HUBSPOT_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "properties": {
            "hs_note_body": f"Inbound SMS: {message_body}",
            "hs_timestamp": int(time.time() * 1000)  # required in some setups
        }
    }

    res = requests.post(url, headers=headers, json=payload)

    try:
        res.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print("HubSpot responded with error:", res.text)
        raise

    note = res.json()

    # Associate the note to the contact (v3-style)
    note_id = note["id"]
    assoc_url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/notes/{note_id}/associations/contacts/{contact_id}/note_to_contact"
    assoc_res = requests.put(assoc_url, headers=headers)
    assoc_res.raise_for_status()

    return note

@app.route("/inbound-sms", methods=["POST"])
def handle_inbound_sms():
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
