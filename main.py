
import os
import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor

import requests
from flask import Flask, request

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Process several Telegram updates concurrently.
executor = ThreadPoolExecutor(max_workers=4)


def telegram_request(method, payload):
    response = requests.post(
        f"{API}/{method}",
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    if not data.get("ok"):
        raise RuntimeError("Telegram API returned an unsuccessful response")

    return data.get("result")


def reply(chat_id, text):
    started = time.monotonic()

    try:
        telegram_request(
            "sendMessage",
            {"chat_id": chat_id, "text": text},
        )
        logging.info(
            "sendMessage completed in %.2f seconds",
            time.monotonic() - started,
        )
    except Exception:
        logging.exception(
            "sendMessage failed after %.2f seconds",
            time.monotonic() - started,
        )


def lookup(prefix):
    started = time.monotonic()

    try:
        response = requests.get(
            f"https://lookup.binlist.net/{prefix}",
            headers={"Accept-Version": "3"},
            timeout=8,
        )

        if response.status_code == 404:
            return "No issuer information found for that BIN/IIN."

        if response.status_code == 429:
            return "Too many lookups. Please try again later."

        response.raise_for_status()
        data = response.json()

    except requests.Timeout:
        return "The lookup took too long. Please try again."

    except requests.RequestException:
        return "The lookup service is temporarily unavailable."

    except ValueError:
        return "The lookup service returned an unreadable response."

    finally:
        logging.info(
            "BIN lookup completed in %.2f seconds",
            time.monotonic() - started,
        )

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


def process_update(update):
    started = time.monotonic()

    try:
        message = (
            update.get("message")
            or update.get("channel_post")
            or {}
        )

        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = (message.get("text") or "").strip()

        if not chat_id or not text:
            return

        parts = text.split()
        command = parts[0].split("@")[0].lower()

        if command == "/start":
            reply(
                chat_id,
                "🤓 Welcome to Lookupbin!\n\n"
                "Your simple BIN / IIN lookup bot.\n\n"
                "🔎 Look up publicly available card issuer details.\n\n"
                "📌 How to use:\n"
                "Send /bin followed by 6–8 digits.\n\n"
                "Example: /bin 457173\n\n"
                "Type /help for instructions.\n\n"
                "🔒 Never send a full card number, expiration date, or CVV."
            )

        elif command == "/help":
            reply(
                chat_id,
                "📖 LOOKUPBIN HELP\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "🔎 Lookup command:\n"
                "/bin 457173\n\n"
                "Enter only 6–8 digits after /bin.\n\n"
                "Results may include network, brand, card type, "
                "issuer, and country.\n\n"
                "This bot does not verify card validity, balances, "
                "or transactions.\n\n"
                "🔒 Never enter a full card number or CVV."
            )

        elif command == "/about":
            reply(
                chat_id,
                "🧐 ABOUT LOOKUPBIN\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "Lookupbin provides public BIN / IIN issuer information.\n\n"
                "Results may be incomplete or outdated.\n\n"
                "This bot does not verify card validity, balances, "
                "or transactions."
            )

        elif command == "/bin":
            if len(parts) != 2 or not re.fullmatch(
                r"\d{6,8}", parts[1]
            ):
                reply(
                    chat_id,
                    "⚠️ Incorrect format.\n\n"
                    "Use /bin followed by 6–8 digits.\n"
                    "Example: /bin 457173\n\n"
                    "Never enter a full card number."
                )
            else:
                # Give the user immediate feedback.
                result = telegram_request(
                    "sendMessage",
                    {
                        "chat_id": chat_id,
                        "text": "🔎 Looking up public issuer information...",
                    },
                )

                message_id = result["message_id"]
                result_text = lookup(parts[1])

                telegram_request(
                    "editMessageText",
                    {
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": result_text,
                    },
                )

        else:
            reply(
                chat_id,
                "I don't recognize that command. Type /help."
            )

    except Exception:
        logging.exception("Failed to process Telegram update")

    finally:
        logging.info(
            "Update processing completed in %.2f seconds",
            time.monotonic() - started,
        )


@app.get("/")
def home():
    return "Lookupbin bot is running!", 200


@app.post("/webhook/<secret>")
def webhook(secret):
    if secret != WEBHOOK_SECRET:
        return "Forbidden", 403

    update = request.get_json(silent=True) or {}

    try:
        executor.submit(process_update, update)
    except RuntimeError:
        logging.exception("Could not queue Telegram update")
        return "Temporarily unavailable", 503

    # Acknowledge Telegram without waiting for processing.
    return "OK", 200
