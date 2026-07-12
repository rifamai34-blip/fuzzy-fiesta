import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Ambil token dari Environment Variables Vercel
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def send_telegram_message(chat_id, text, reply_to_message_id=None):
    """Fungsi mengirim pesan teks balasan ke Telegram"""
    url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    requests.post(url, json=payload)

@app.route('/', methods=['POST'])
def webhook():
    """Endpoint Webhook Utama"""
    try:
        update = request.get_json(force=True)
        
        if "message" in update:
            message = update["message"]
            chat_id = message["chat"]["id"]
            message_id = message["message_id"]
            
            # Jika user mengirim Voice Note
            if "voice" in message:
                voice = message["voice"]
                file_id = voice["file_id"]
                
                # 1. Ambil file path suara dari Telegram
                get_file_url = f"https://telegram.org{TELEGRAM_TOKEN}/getFile?file_id={file_id}"
                file_info = requests.get(get_file_url).json()
                
                if file_info.get("ok"):
                    file_path = file_info["result"]["file_path"]
                    download_url = f"https://telegram.org{TELEGRAM_TOKEN}/{file_path}"
                    
                    # 2. Unduh file audio (.ogg) langsung ke memori RAM
                    audio_data = requests.get(download_url).content
                    
                    # Konversi data audio ke format standar struktur Google API
                    import base64
                    audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                    
                    # 3. Prompt instruksi pintar deteksi otomatis Sunda / Indonesia
                    prompt_text = (
                        "Dengarkan rekaman audio ini dengan sangat teliti, lalu analisis bahasanya.\n"
                        "Berikan output dengan format rapi seperti di bawah ini:\n\n"
                        "🗣️ **Transkripsi Asli:**\n"
                        "[Tuliskan teks kata-per-kata yang diucapkan secara akurat sesuai bahasa aslinya beserta tanda baca yang rapi]\n\n"
                        "ℹ️ **Deteksi Bahasa:**\n"
                        "[Sebutkan bahasa apa yang digunakan, contoh: 'Bahasa Sunda' atau 'Bahasa Indonesia']\n\n"
                        "🇮🇩 **Arti / Terjemahan:**\n"
                        "[Jika audio menggunakan Bahasa Sunda, terjemahkan ke Bahasa Indonesia yang baik dan santun. "
                        "TETAPI jika audio dari awal sudah menggunakan Bahasa Indonesia, cukup tulis: 'Ucapan sudah dalam Bahasa Indonesia']"
                    )
                    
                    # 4. Tembak API Gemini menggunakan metode HTTP POST murni
                    gemini_url = f"https://googleapis.com{GEMINI_API_KEY}"
                    headers = {"Content-Type": "application/json"}
                    payload_gemini = {
                        "contents": [{
                            "parts": [
                                {"inline_data": {"mime_type": "audio/ogg", "data": audio_b64}},
                                {"text": prompt_text}
                            ]
                        }]
                    }
                    
                    gemini_response = requests.post(gemini_url, headers=headers, json=payload_gemini).json()
                    
                    # Ambil hasil teks respon dari susunan JSON Gemini
                    try:
                        result_text = gemini_response['candidates'][0]['content']['parts'][0]['text']
                    except Exception:
                        result_text = "⚠️ Gagal memproses teks dari AI Gemini. Coba kirim ulang suara Anda."
                    
                    # 5. Kirim teks hasil transkripsi asli + terjemahan ke user Telegram
                    send_telegram_message(chat_id, result_text, reply_to_message_id=message_id)
            
            # Jika user mengirim perintah teks biasa /start
            elif "text" in message and message["text"] == "/start":
                welcome_text = "👋 Halo! Kirimkan pesan suara (*voice note*) dalam Bahasa Sunda atau Bahasa Indonesia ke sini, saya akan mentranskrip dan mengartikannya secara otomatis!"
                send_telegram_message(chat_id, welcome_text)
                
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 200

@app.route('/health', methods=['GET'])
def health():
    return "Aplikasi Berjalan Lancar!", 200
