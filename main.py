
import os
import re
import logging
import requests
from flask import Flask, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def reply(chat_id, text):
    try:
        response = requests.post(
            f"{API}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException:
        logging.exception("Could not send Telegram message")


def lookup(prefix):
    try:
        response = requests.get(
            f"https://lookup.binlist.net/{prefix}",
            headers={"Accept-Version": "3"},
            timeout=10,
        )

        if response.status_code == 404:
            return "❌ No issuer information found for that BIN/IIN."

        if response.status_code == 429:
            return "⏳ Too many lookups. Please try again later."

        response.raise_for_status()
        data = response.json()

    except requests.Timeout:
        return "⏳ The lookup took too long. Please try again."
    except requests.RequestException:
        return "⚠️ The lookup service is temporarily unavailable."
    except ValueError:
        return "⚠️ The lookup service returned an unreadable response."

    bank = data.get("bank") or {}
    country = data.get("country") or {}

    scheme = data.get("scheme") or "Unknown"
    brand = data.get("brand") or "Unknown"
    card_type = data.get("type") or "Unknown"
    issuer = bank.get("name") or "Unknown"
    country_name = country.get("name") or "Unknown"
    country_code = country.get("alpha2") or ""

    if country_code:
        country_name = f"{country_name} ({country_code})"

    return (
        "💳 BIN / IIN LOOKUP\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🌐 Network: {scheme.upper()}\n"
        f"🏷️ Brand: {brand}\n"
        f"💰 Card type: {card_type.title()}\n"
        f"🏦 Issuer: {issuer}\n"
        f"🌍 Country: {country_name}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "ℹ️ Public issuer information only.\n"
        "Results may be incomplete or outdated."
    )


@app.get("/")
def home():
    return "Lookupbin bot is running!", 200


@app.post("/webhook/<secret>")
def webhook(secret):
    if secret != WEBHOOK_SECRET:
        return "Forbidden", 403

    
                update = request.get_json(silent=True) or {}
    logging.info("Telegram update keys: %s", list(update.keys()))
    logging.info("Telegram message chat type: %s", (update.get("message") or {}).get("chat", {}).get("type"))
    message = update.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return "OK", 200

    command = text.split()[0].split("@")[0].lower()

    if command == "/start":
        reply(
            chat_id,
            "💗 Welcome to Lookupbin!\n\n"
            "Your simple BIN / IIN lookup bot.\n\n"
            "🔎 Check publicly available card issuer details.\n\n"
            "📌 How to use:\n"
            "Send /bin followed by 6–8 digits.\n\n"
            "Example:\n"
            "/bin 457173\n\n"
            "Type /help to see the instructions.\n\n"
            "🔒 Never send a full card number, "
            "expiration date, or CVV."
        )

    elif command == "/help":
        reply(
            chat_id,
            "📖 LOOKUPBIN HELP\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "🔎 Lookup command:\n"
            "/bin 457173\n\n"
            "Enter only 6–8 digits after /bin.\n\n"
            "✅ Shows available network, brand, "
            "card type, issuer, and country details.\n\n"
            "⚠️ Information may be incomplete. "
            "This bot does not verify balances, "
            "card validity, or transactions.\n\n"
            "🔒 Never enter a full card number or CVV."
        )

    
    elif command == "/about":
        reply(
            chat_id,
            "💗 ABOUT LOOKUPBIN\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "🔎 Lookupbin provides public BIN / IIN "
            "issuer information.\n\n"
            "📋 Results may include the network, "
            "brand, card type, issuing bank, and country.\n\n"
            "⚠️ Information may be incomplete or outdated. "
            "This bot does not verify card validity, "
            "balances, or transactions.\n\n"
            "🔒 Never send a full card number or CVV."
        )
    elif command == "/bin":
        parts = text.split()

        if len(parts) != 2 or not re.fullmatch(r"\d{6,8}", parts[1]):
            reply(
                chat_id,
                "⚠️ Incorrect format.\n\n"
                "Use /bin followed by 6–8 digits.\n"
                "Example: /bin 457173\n\n"
                "Never enter a full card number."
            )
        else:
            result = lookup(parts[1])
            reply(chat_id, result)

    else:
        reply(chat_id, "I don't recognize that command. Type /help.")

    return "OK", 200
