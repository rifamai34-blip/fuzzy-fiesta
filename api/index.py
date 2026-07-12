import os
from flask import Flask, request, jsonify
from telegram import Update, Bot
import google.generativeai as genai
import requests
import asyncio

app = Flask(__name__)

# Mengambil token aman dari Environment Variables Vercel
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Inisialisasi Bot Telegram dan Google Gemini
bot = Bot(token=TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

async def process_telegram_update(update_dict):
    """Fungsi utama untuk memproses kiriman pesan dari Telegram"""
    update = Update.de_json(update_dict, bot)
    
    # Pastikan ada pesan masuk dan pesan tersebut berupa Voice Note
    if update.message and update.message.voice:
        chat_id = update.message.chat_id
        
        # Kirim status loading agar pengguna tahu bot sedang bekerja
        status_msg = await bot.send_message(chat_id=chat_id, text="🎙️ Sedang mengunduh suara dan memproses transkripsi...")
        
        try:
            # 1. Ambil informasi file dari Telegram
            voice_file = await update.message.voice.get_file()
            file_url = voice_file.file_path
            
            # 2. Unduh file suara langsung ke folder memori sementara /tmp (Vercel bersifat read-only)
            local_filename = f"/tmp/{voice_file.file_id}.ogg"
            response_audio = requests.get(file_url)
            with open(local_filename, 'wb') as f:
                f.write(response_audio.content)
            
            # 3. Unggah file audio ogg tersebut ke server API Gemini
            uploaded_file = genai.upload_file(path=local_filename)
            
            # 4. Prompt pintar untuk mendeteksi Bahasa Sunda atau Bahasa Indonesia otomatis
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
            
            # 5. Jalankan proses AI
            gemini_response = model.generate_content([uploaded_file, prompt])
            
            # 6. Kirim balik teks hasil akhir ke user, lalu hapus pesan loading tadi
            await bot.send_message(chat_id=chat_id, text=gemini_response.text, parse_mode="Markdown")
            await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
            
            # Hapus file sampah audio di folder /tmp agar kapasitas tidak penuh
            if os.path.exists(local_filename):
                os.remove(local_filename)
                
        except Exception as e:
            await bot.send_message(chat_id=chat_id, text=f"⚠️ Terjadi kesalahan teknis: {str(e)}")

@app.route('/', methods=['POST'])
def webhook():
    """Endpoint Webhook yang akan dipanggil oleh Telegram"""
    if request.method == "POST":
        update_dict = request.get_json(force=True)
        # Menjalankan fungsi async di dalam routing Flask sync
        asyncio.run(process_telegram_update(update_dict))
        return jsonify({"status": "success"}), 200
    return "OK", 200
# Struktur Handler wajib agar file Python dikenali sebagai Serverless Endpoint oleh Vercel
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Menangkap data POST Webhook yang dikirim oleh server Telegram"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            update_dict = json.loads(post_data.decode('utf-8'))
            
            # Menjalankan fungsi async di dalam class sync menggunakan asyncio
            import asyncio
            asyncio.run(process_telegram_update(update_dict))
            
            # Beri respons status 200 OK ke Telegram agar Telegram tidak mengirim ulang data yang sama
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
