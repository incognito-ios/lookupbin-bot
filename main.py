
import os
import re
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def reply(chat_id, text):
    requests.post(
        f"{API}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=15,
    ).raise_for_status()


def lookup(prefix):
    r = requests.get(
        f"https://lookup.binlist.net/{prefix}",
        headers={"Accept-Version": "3"},
        timeout=15,
    )
    if r.status_code == 404:
        return "No issuer information found."
    if r.status_code == 429:
        return "Lookup limit reached. Try again later."
    r.raise_for_status()
    data = r.json()
    bank = data.get("bank") or {}
    country = data.get("country") or {}
    return (
        "BIN / IIN Lookup\n\n"
        f"Network: {data.get('scheme') or 'Unknown'}\n"
        f"Brand: {data.get('brand') or 'Unknown'}\n"
        f"Type: {data.get('type') or 'Unknown'}\n"
        f"Issuer: {bank.get('name') or 'Unknown'}\n"
        f"Country: {country.get('name') or 'Unknown'}\n\n"
        "Public information only; results may be incomplete."
    )


@app.get("/")
def home():
    return "Lookupbin bot is running!", 200


@app.post("/webhook/<secret>")
def webhook(secret):
    if secret != WEBHOOK_SECRET:
        return "Forbidden", 403

    update = request.get_json(silent=True) or {}
    message = update.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return "OK", 200

    command = text.split()[0].split("@")[0].lower()

    if command in ("/start", "/help"):
        reply(chat_id,
              "Welcome to Lookupbin!\n\n"
              "Use /bin followed by 6–8 digits.\n"
              "Example: /bin 45717360\n\n"
              "Never send a full card number.")

    elif command == "/bin":
        parts = text.split()
        if len(parts) != 2 or not re.fullmatch(r"\d{6,8}", parts[1]):
            reply(chat_id, "Usage: /bin followed by 6–8 digits only.")
        else:
            try:
                reply(chat_id, lookup(parts[1]))
            except requests.RequestException:
                reply(chat_id, "Lookup service unavailable. Try again later.")
    else:
        reply(chat_id, "Type /help for instructions.")

    return "OK", 200
