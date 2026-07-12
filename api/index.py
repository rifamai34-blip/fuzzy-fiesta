import os
import asyncio
import requests
from flask import Flask, request, jsonify
from telegram import Update, Bot
from google import genai

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN belum diatur di Environment Variables")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY belum diatur di Environment Variables")


bot = Bot(token=TELEGRAM_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)


async def process_telegram_update(update_dict):
    update = Update.de_json(update_dict, bot)

    if not update.message:
        return

    if not update.message.voice:
        await bot.send_message(
            chat_id=update.message.chat_id,
            text="Kirim voice note ya 🎙️"
        )
        return

    chat_id = update.message.chat_id

    status = await bot.send_message(
        chat_id=chat_id,
        text="🎙️ Sedang memproses voice note..."
    )

    local_filename = None

    try:
        voice_file = await update.message.voice.get_file()

        local_filename = f"/tmp/{voice_file.file_id}.ogg"

        file_url = voice_file.file_path

        audio = requests.get(file_url, timeout=30)

        with open(local_filename, "wb") as f:
            f.write(audio.content)


        uploaded_file = client.files.upload(
        file=local_filename,
        config={
        "mime_type": "audio/ogg"
    }
)
        )


        prompt = """
Dengarkan audio ini.

Buat hasil dengan format:

🗣️ Transkripsi Asli:
(tulis semua ucapan)

ℹ️ Deteksi Bahasa:
(sebutkan bahasa)

🇮🇩 Arti / Terjemahan:
(terjemahkan ke Bahasa Indonesia jika diperlukan)
"""


        result = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                uploaded_file,
                prompt
            ]
        )


        await bot.send_message(
            chat_id=chat_id,
            text=result.text
        )


        await bot.delete_message(
            chat_id=chat_id,
            message_id=status.message_id
        )


    except Exception as e:

        await bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Error:\n{str(e)}"
        )


    finally:

        if local_filename and os.path.exists(local_filename):
            os.remove(local_filename)



@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "running",
        "message": "Telegram Gemini Bot aktif"
    })



@app.route("/", methods=["POST"])
def webhook():

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "No data"
        }), 400


    loop = asyncio.new_event_loop()

    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            process_telegram_update(data)
        )

    finally:
        loop.close()


    return jsonify({
        "status": "ok"
    }), 200



# WAJIB UNTUK VERCEL
handler = app
application = app
