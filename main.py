import os
import re
import uvicorn
import asyncio
from urllib.parse import quote
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ----------------- Python 3.10+ Event Loop Fix ----------------- #
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# ----------------- Configuration ----------------- #

API_ID = int(os.environ.get("API_ID", "29608422"))
API_HASH = os.environ.get("API_HASH", "3db2f8e109301f02f5d9c8f10dd79244")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8765885559:AAGepuq7edjdkX1dnocii3EfUFiLGX1v9IA")

URL = os.environ.get("URL", "https://sr-video-quality-2.onrender.com").rstrip('/')
PORT = int(os.environ.get("PORT", "8080"))

BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL", "-1004450462812"))
CHANNEL_LINK = "https://t.me/ss_anime_box"

rename_state = {}

# ----------------- Bot & FastAPI Setup ----------------- #

bot = Client(
    name="bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
    max_concurrent_transmissions=10
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length", "Content-Type", "Content-Disposition"]
)

# ----------------- Helper Functions ----------------- #

def clean_and_encode_filename(file_name: str) -> str:
    if not file_name:
        return "video.mp4"
    clean_name = re.sub(r'\[.*?\]|\(.*?\)', '', file_name)
    if '.' in clean_name:
        name_part, ext_part = clean_name.rsplit('.', 1)
        ext = ext_part.lower()
    else:
        name_part = clean_name
        ext = "mp4"
    name_part = re.sub(r'[^a-zA-Z0-9.-]', '_', name_part)
    name_part = re.sub(r'_+', '_', name_part).strip('_')
    return quote(f"{name_part}.{ext}")

def humanbytes(size):
    if not size:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0

# ----------------- Original Clean Video Player Design ----------------- #

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def root():
    return "<h1>SS Anime Box Web Server Active!</h1>"

@app.get("/watch/{chat_id}/{message_id}/{file_name}", response_class=HTMLResponse)
async def watch_player(chat_id: int, message_id: int, file_name: str):
    stream_url = f"{URL}/stream/{chat_id}/{message_id}/{file_name}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="bn">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SS Anime Box Player</title>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
            body {{ background-color: #0b0f19; color: #ffffff; display: flex; justify-content: center; align-items: flex-start; min-height: 100vh; }}
            .container {{ width: 100%; max-width: 500px; background-color: #0f1422; min-height: 100vh; display: flex; flex-direction: column; }}
            .video-container {{ width: 100%; background-color: #000; aspect-ratio: 16 / 9; position: relative; }}
            video {{ width: 100%; height: 100%; object-fit: contain; outline: none; }}
            .brand-card {{ margin: 24px 16px; padding: 18px; background: linear-gradient(135deg, #1a2030, #131826); border-radius: 16px; border: 1px solid #2a344d; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
            .brand-title {{ font-size: 24px; font-weight: 800; color: #ff9800; letter-spacing: 2px; text-transform: uppercase; display: flex; align-items: center; justify-content: center; gap: 10px; }}
            .brand-dot {{ height: 12px; width: 12px; background-color: #ff9800; border-radius: 50%; box-shadow: 0 0 10px #ff9800; }}
            .brand-subtitle {{ font-size: 13px; color: #8a99ad; margin-top: 6px; font-weight: 500; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="video-container">
                <video id="player" controls autoplay playsinline preload="auto" crossorigin="anonymous">
                    <source src="{stream_url}" type="video/mp4">
                    Your browser does not support HTML5 video streaming.
                </video>
            </div>
            
            <div class="brand-card">
                <div class="brand-title">
                    <span class="brand-dot"></span> SS ANIME BOX
                </div>
                <div class="brand-subtitle">High Quality Anime Streaming</div>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

# ----------------- Streaming and Direct Download Handlers ----------------- #

@app.get("/stream/{chat_id}/{message_id}/{file_name}")
async def stream_file(chat_id: int, message_id: int, file_name: str, request: Request):
    return await handle_file_stream(chat_id, message_id, file_name, request, is_download=False)

@app.get("/download/{chat_id}/{message_id}/{file_name}")
async def download_file(chat_id: int, message_id: int, file_name: str, request: Request):
    return await handle_file_stream(chat_id, message_id, file_name, request, is_download=True)

async def handle_file_stream(chat_id: int, message_id: int, file_name: str, request: Request, is_download: bool = False):
    try:
        msg = await bot.get_messages(chat_id, message_id)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found")

    media = msg.document or msg.video or msg.audio
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    file_size = media.file_size
    range_header = request.headers.get('range')
    disposition_type = "attachment" if is_download else "inline"

    if range_header:
        byte_opts = range_header.replace('bytes=', '').split('-')
        start = int(byte_opts[0]) if byte_opts[0] else 0
        end = int(byte_opts[1]) if len(byte_opts) > 1 and byte_opts[1] else file_size - 1
        
        if start >= file_size or end >= file_size:
            headers = {'Content-Range': f'bytes */{file_size}'}
            return StreamingResponse(status_code=416, headers=headers)

        content_length = (end - start) + 1

        async def fast_ranged_streamer():
            current_pos = 0
            async for chunk in bot.stream_media(msg, limit=0):
                chunk_len = len(chunk)
                if current_pos + chunk_len > start:
                    chunk_start = max(0, start - current_pos)
                    chunk_end = min(chunk_len, end - current_pos + 1)
                    yield chunk[chunk_start:chunk_end]
                current_pos += chunk_len
                if current_pos > end:
                    break

        headers = {
            'Content-Range': f'bytes {start}-{end}/{file_size}',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(content_length),
            'Content-Type': 'video/mp4',
            'Content-Disposition': f'{disposition_type}; filename="{file_name}"'
        }
        return StreamingResponse(fast_ranged_streamer(), status_code=206, headers=headers)

    else:
        async def fast_full_streamer():
            async for chunk in bot.stream_media(msg, limit=0):
                yield chunk

        headers = {
            'Accept-Ranges': 'bytes',
            'Content-Length': str(file_size),
            'Content-Type': 'video/mp4',
            'Content-Disposition': f'{disposition_type}; filename="{file_name}"'
        }
        return StreamingResponse(fast_full_streamer(), status_code=200, headers=headers)

# ----------------- Bot Event Handlers ----------------- #

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    await message.reply_text("👋 **SS Anime Box Streaming Bot Online!**\n\nফাইল পাঠান, স্ট্রিম এবং রিনেম করার লিঙ্ক পাবেন।")

@bot.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_media(client, message: Message):
    try:
        try:
            bin_msg = await message.forward(BIN_CHANNEL)
            target_chat_id = BIN_CHANNEL
            target_msg_id = bin_msg.id
        except Exception:
            target_chat_id = message.chat.id
            target_msg_id = message.id

        media = message.document or message.video or message.audio
        
        original_name = getattr(media, 'file_name', None)
        if not original_name:
            original_name = f"video_{message.id}.mp4"
            
        safe_name = clean_and_encode_filename(original_name)
        file_size = humanbytes(getattr(media, 'file_size', 0))
        file_ext = original_name.rsplit('.', 1)[-1].upper() if '.' in original_name else "MP4"

        if file_ext in ["MP4", "WEBM", "MKV"]:
            stream_status = "✅ **ব্রাউজারে সরাসরি চলবে**"
        else:
            stream_status = "⚠️ **ব্রাউজারে সরাসরি চলবে না** (VLC Player ব্যবহার করুন)"

        watch_link = f"{URL}/watch/{target_chat_id}/{target_msg_id}/{safe_name}"
        download_link = f"{URL}/download/{target_chat_id}/{target_msg_id}/{safe_name}"

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Watch Online 🎬", url=watch_link)],
            [InlineKeyboardButton("Direct Download 📥", url=download_link)],
            [InlineKeyboardButton("Rename File ✏️", callback_data=f"rename_{target_chat_id}_{target_msg_id}")],
            [InlineKeyboardButton("Our Channel 📢", url=CHANNEL_LINK)]
        ])

        caption = (
            f"📁 **ফাইল নাম:** `{original_name}`\n"
            f"🏷 **টাইপ:** `{file_ext}` | 📦 **সাইজ:** `{file_size}`\n"
            f"📌 **স্ট্যাটাস:** {stream_status}\n\n"
            f"👇 **আপনার লিংক নিচে দেওয়া হলো:**"
        )
        await message.reply_text(caption, reply_markup=reply_markup)

    except Exception as e:
        await message.reply_text(f"❌ লিংক তৈরিতে সমস্যা হয়েছে: `{str(e)}`")

@bot.on_callback_query(filters.regex(r"^rename_"))
async def rename_callback(client, query: CallbackQuery):
    data_parts = query.data.split("_")
    chat_id = int(data_parts[1])
    msg_id = int(data_parts[2])
    rename_state[query.from_user.id] = (chat_id, msg_id)
    await query.message.reply_text("✏️ **নতুন ফাইলের নাম পাঠান (যেমন: `Anime_S01E01.mp4`):**")
    await query.answer()

@bot.on_message(filters.private & filters.text & ~filters.command(["start"]))
async def process_rename(client, message: Message):
    user_id = message.from_user.id
    if user_id in rename_state:
        chat_id, bin_msg_id = rename_state.pop(user_id)
        new_name = message.text.strip()
        
        try:
            bin_msg = await bot.get_messages(chat_id, bin_msg_id)
            media = bin_msg.document or bin_msg.video or bin_msg.audio
            safe_name = clean_and_encode_filename(new_name)
            file_size = humanbytes(getattr(media, 'file_size', 0))
            file_ext = new_name.rsplit('.', 1)[-1].upper() if '.' in new_name else "MP4"
            
            if file_ext in ["MP4", "WEBM", "MKV"]:
                stream_status = "✅ **ব্রাউজারে সরাসরি চলবে**"
            else:
                stream_status = "⚠️ **ব্রাউজারে সরাসরি চলবে না** (VLC Player ব্যবহার করুন)"

            watch_link = f"{URL}/watch/{chat_id}/{bin_msg_id}/{safe_name}"
            download_link = f"{URL}/download/{chat_id}/{bin_msg_id}/{safe_name}"
            
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("Watch Online 🎬", url=watch_link)],
                [InlineKeyboardButton("Direct Download 📥", url=download_link)],
                [InlineKeyboardButton("Rename File ✏️", callback_data=f"rename_{chat_id}_{bin_msg_id}")],
                [InlineKeyboardButton("Our Channel 📢", url=CHANNEL_LINK)]
            ])
            
            caption = (
                f"📁 **নতুন নাম:** `{new_name}`\n"
                f"🏷 **টাইপ:** `{file_ext}` | 📦 **সাইজ:** `{file_size}`\n"
                f"📌 **স্ট্যাটাস:** {stream_status}\n\n"
                f"👇 **আপনার নতুন লিংক প্রস্তুত:**"
            )
            await message.reply_text(caption, reply_markup=reply_markup)
        except Exception as e:
            await message.reply_text(f"❌ সমস্যা হয়েছে: {str(e)}")

# ----------------- Main Execution ----------------- #

async def start_all():
    await bot.start()
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    try:
        loop.run_until_complete(start_all())
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(bot.stop())
