import os
import re
import uvicorn
import asyncio
from urllib.parse import quote
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

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
    in_memory=True
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length", "Content-Type"]
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

# ----------------- Web Routes & Clean Player ----------------- #

@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h1>SS Anime Box Web Server Active!</h1>"

@app.get("/watch/{chat_id}/{message_id}/{file_name}", response_class=HTMLResponse)
async def watch_player(chat_id: int, message_id: int, file_name: str):
    download_url = f"{URL}/download/{chat_id}/{message_id}/{file_name}"
    
    # Clean Web Player - Video er upore kono name thakbe na
    html_content = f"""
    <!DOCTYPE html>
    <html lang="bn">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SS Anime Box Player</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: sans-serif; }}
            body {{ background-color: #0b0f19; color: #ffffff; display: flex; justify-content: center; }}
            .container {{ width: 100%; max-width: 480px; background-color: #0f1422; min-height: 100vh; padding-bottom: 20px; }}
            .top-bar {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background-color: #0b0f19; }}
            .back-btn {{ background: #1a2030; color: #fff; border: none; padding: 6px 14px; border-radius: 20px; cursor: pointer; font-size: 14px; text-decoration: none; }}
            .brand-tag {{ background: #1a2030; color: #ffffff; padding: 6px 12px; border-radius: 20px; font-size: 12px; display: flex; align-items: center; gap: 6px; }}
            .dot {{ height: 8px; width: 8px; background-color: #ff9800; border-radius: 50%; }}
            .video-container {{ width: 100%; background-color: #000; aspect-ratio: 16 / 9; }}
            video {{ width: 100%; height: 100%; object-fit: contain; }}
            .action-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 16px; }}
            .action-btn {{ background: #ff9800; color: #000; border: none; padding: 12px; border-radius: 12px; font-size: 13px; font-weight: bold; display: flex; align-items: center; justify-content: center; gap: 6px; cursor: pointer; text-decoration: none; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="top-bar">
                <a href="{CHANNEL_LINK}" class="back-btn"><i class="fa-solid fa-arrow-left"></i> Channel</a>
                <div class="brand-tag"><span class="dot"></span> SS ANIME BOX</div>
            </div>
            <div class="video-container">
                <video id="player" controls autoplay preload="metadata" crossorigin="anonymous">
                    <source src="{download_url}" type="video/mp4">
                    <source src="{download_url}" type="video/x-matroska">
                    Your browser does not support HTML5 video streaming.
                </video>
            </div>
            <div class="action-grid">
                <a href="{download_url}" class="action-btn"><i class="fa-solid fa-download"></i> Direct Download</a>
                <a href="vlc://{download_url}" class="action-btn" style="background:#1a2030; color:#fff;"><i class="fa-solid fa-play"></i> VLC Player</a>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

@app.get("/download/{chat_id}/{message_id}/{file_name}")
async def download_file(chat_id: int, message_id: int, file_name: str, request: Request):
    msg = await bot.get_messages(chat_id, message_id)
    media = msg.document or msg.video or msg.audio
    
    async def media_streamer():
        async for chunk in bot.stream_media(msg, limit=0):
            yield chunk

    headers = {
        'Content-Type': 'application/octet-stream',
        'Content-Disposition': f'attachment; filename="{file_name}"',
        'Accept-Ranges': 'bytes',
        'Content-Length': str(media.file_size)
    }
    return StreamingResponse(media_streamer(), headers=headers)

# ----------------- Bot Event Handlers ----------------- #

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    await message.reply_text("👋 **SS Anime Box Streaming Bot Online!**\n\nফাইল পাঠান, স্ট্রিম এবং রিনেম করার লিঙ্ক পাবেন।")

@bot.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_media(client, message: Message):
    try:
        bin_msg = await message.forward(BIN_CHANNEL)
    except Exception:
        bin_msg = message

    media = bin_msg.document or bin_msg.video or bin_msg.audio
    original_name = getattr(media, 'file_name', 'video.mp4')
    safe_name = clean_and_encode_filename(original_name)
    file_size = humanbytes(getattr(media, 'file_size', 0))
    file_ext = original_name.rsplit('.', 1)[-1].upper() if '.' in original_name else "MP4"

    if file_ext in ["MP4", "WEBM"]:
        stream_status = "✅ **ব্রাউজারে সরাসরি চলবে**"
    else:
        stream_status = "⚠️ **ব্রাউজারে সরাসরি চলবে না** (VLC/MX Player ব্যবহার করুন)"

    watch_link = f"{URL}/watch/{BIN_CHANNEL}/{bin_msg.id}/{safe_name}"
    download_link = f"{URL}/download/{BIN_CHANNEL}/{bin_msg.id}/{safe_name}"

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Watch Online 🎬", url=watch_link)],
        [InlineKeyboardButton("Direct Download 📥", url=download_link)],
        [InlineKeyboardButton("Rename File ✏️", callback_data=f"rename_{bin_msg.id}")],
        [InlineKeyboardButton("Our Channel 📢", url=CHANNEL_LINK)]
    ])

    caption = (
        f"📁 **ফাইল নাম:** `{original_name}`\n"
        f"🏷 **টাইপ:** `{file_ext}` | 📦 **সাইজ:** `{file_size}`\n"
        f"📌 **স্ট্যাটাস:** {stream_status}\n\n"
        f"👇 **আপনার লিংক নিচে দেওয়া হলো:**"
    )
    await message.reply_text(caption, reply_markup=reply_markup)

@bot.on_callback_query(filters.regex(r"^rename_"))
async def rename_callback(client, query: CallbackQuery):
    msg_id = int(query.data.split("_")[1])
    rename_state[query.from_user.id] = msg_id
    await query.message.reply_text("✏️ **নতুন ফাইলের নাম পাঠান (যেমন: `Anime_S01E01.mp4`):**")
    await query.answer()

@bot.on_message(filters.private & filters.text & ~filters.command(["start"]))
async def process_rename(client, message: Message):
    user_id = message.from_user.id
    if user_id in rename_state:
        bin_msg_id = rename_state.pop(user_id)
        new_name = message.text.strip()
        
        try:
            bin_msg = await bot.get_messages(BIN_CHANNEL, bin_msg_id)
            media = bin_msg.document or bin_msg.video or bin_msg.audio
            safe_name = clean_and_encode_filename(new_name)
            file_size = humanbytes(getattr(media, 'file_size', 0))
            file_ext = new_name.rsplit('.', 1)[-1].upper() if '.' in new_name else "MP4"
            
            if file_ext in ["MP4", "WEBM"]:
                stream_status = "✅ **ব্রাউজারে সরাসরি চলবে**"
            else:
                stream_status = "⚠️ **ব্রাউজারে সরাসরি চলবে না** (VLC/MX Player ব্যবহার করুন)"

            watch_link = f"{URL}/watch/{BIN_CHANNEL}/{bin_msg_id}/{safe_name}"
            download_link = f"{URL}/download/{BIN_CHANNEL}/{bin_msg_id}/{safe_name}"
            
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("Watch Online 🎬", url=watch_link)],
                [InlineKeyboardButton("Direct Download 📥", url=download_link)],
                [InlineKeyboardButton("Rename File ✏️", callback_data=f"rename_{bin_msg_id}")],
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

# ----------------- Main Runner with Event Loop Fix ----------------- #

async def start_all():
    await bot.start()
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(start_all())
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(bot.stop())
