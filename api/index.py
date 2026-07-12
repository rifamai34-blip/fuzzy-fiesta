import os
import requests
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Ambil token dari Environment Variables Vercel
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Konfigurasi Google Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def send_telegram_message(chat_id, text, reply_to_message_id=None):
    """Fungsi sederhana untuk mengirim pesan ke Telegram"""
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
    """Endpoint Webhook Utama untuk menerima pesan Telegram"""
    try:
        update = request.get_json(force=True)
        
        # Pastikan data berupa pesan teks atau media yang masuk
        if "message" in update:
            message = update["message"]
            chat_id = message["chat"]["id"]
            message_id = message["message_id"]
            
            # Cek apakah pengguna mengirimkan Voice Note (Pesan Suara)
            if "voice" in message:
                voice = message["voice"]
                file_id = voice["file_id"]
                
                # 1. Dapatkan jalur file suara dari server Telegram
                get_file_url = f"https://telegram.org{TELEGRAM_TOKEN}/getFile?file_id={file_id}"
                file_info = requests.get(get_file_url).json()
                
                if file_info.get("ok"):
                    file_path = file_info["result"]["file_path"]
                    download_url = f"https://telegram.org{TELEGRAM_TOKEN}/{file_path}"
                    
                    # 2. Unduh file suara langsung ke RAM berupa bytes data
                    audio_data = requests.get(download_url).content
                    
                    # 3. Prompt instruksi pintar untuk deteksi Sunda / Indonesia otomatis
                    prompt = (
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
                    
                    # 4. Kirim data suara langsung secara inline ke Gemini AI
                    response = model.generate_content([
                        {
                            'mime_type': 'audio/ogg',
                            'data': audio_data
                        },
                        prompt
                    ])
                    
                    # 5. Kirimkan hasil akhir transkripsi ke user Telegram
                    send_telegram_message(chat_id, response.text, reply_to_message_id=message_id)
            
            # Cek jika pengguna hanya mengirimkan teks biasa seperti /start
            elif "text" in message and message["text"] == "/start":
                welcome_text = "👋 Halo! Kirimkan pesan suara (*voice note*) dalam Bahasa Sunda atau Bahasa Indonesia ke sini, saya akan mentranskrip dan mengartikannya secara otomatis!"
                send_telegram_message(chat_id, welcome_text)
                
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        # Jika terjadi eror internal, tetap kirim status 200 agar Telegram tidak melakukan loop kirim ulang
        return jsonify({"status": "error", "message": str(e)}), 200

@app.route('/health', methods=['GET'])
def health():
    return "OK", 200
