import os
import re
import uvicorn
import asyncio
from urllib.parse import quote
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ----------------- Configurations ----------------- #

API_ID = int(os.environ.get("API_ID", "29608422"))
API_HASH = os.environ.get("API_HASH", "3db2f8e109301f02f5d9c8f10dd79244")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8765885559:AAGepuq7edjdkX1dnocii3EfUFiLGX1v9IA")

URL = os.environ.get("URL", "https://sr-video-quality-2.onrender.com").rstrip('/')
PORT = int(os.environ.get("PORT", "8080"))

BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL", "-1004450462812"))
CHANNEL_LINK = "https://t.me/ss_anime_box"

rename_state = {}

# ----------------- Hydrogram Bot Client ----------------- #

bot = Client(
    name="bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# ----------------- FastAPI App Setup ----------------- #

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

# ----------------- Web Routes ----------------- #

@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h1>SS Anime Box Web Server Active!</h1>"

@app.get("/watch/{chat_id}/{message_id}/{file_name}", response_class=HTMLResponse)
async def watch_player(chat_id: int, message_id: int, file_name: str):
    download_url = f"{URL}/download/{chat_id}/{message_id}/{file_name}"
    
    # HTML UI Template
    html_content = f"""
    <!DOCTYPE html>
    <html lang="bn">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{file_name} - SS Anime Box</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
            body {{ background-color: #0b0f19; color: #ffffff; display: flex; justify-content: center; }}
            .container {{ width: 100%; max-width: 480px; background-color: #0f1422; min-height: 100vh; padding-bottom: 20px; }}
            .top-bar {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background-color: #0b0f19; }}
            .back-btn {{ background: #1a2030; color: #fff; border: none; padding: 6px 14px; border-radius: 20px; cursor: pointer; font-size: 14px; text-decoration: none; }}
            .brand-tag {{ background: #1a2030; color: #ffffff; padding: 6px 12px; border-radius: 20px; font-size: 12px; display: flex; align-items: center; gap: 6px; }}
            .dot {{ height: 8px; width: 8px; background-color: #ff9800; border-radius: 50%; }}
            .video-container {{ width: 100%; background-color: #000; aspect-ratio: 16 / 9; }}
            video {{ width: 100%; height: 100%; object-fit: contain; }}
            .controls-section {{ padding: 12px 16px; display: flex; flex-direction: column; gap: 10px; }}
            .action-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 16px; }}
            .action-btn {{ background: #ff9800; color: #000; border: none; padding: 12px; border-radius: 12px; font-size: 14px; font-weight: bold; display: flex; align-items: center; justify-content: center; gap: 6px; cursor: pointer; text-decoration: none; }}
            .info-section {{ padding: 16px; border-top: 1px solid #1a2030; }}
            .title-header h2 {{ font-size: 15px; font-weight: 600; color: #ff9800; word-break: break-all; }}
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
                <a href="vlc://{download_url}" class="action-btn" style="background:#1a2030; color:#fff;"><i class="fa-solid fa-play"></i> Open in VLC</a>
            </div>
            <div class="info-section">
                <div class="title-header">
                    <h2>📁 {file_name}</h2>
                </div>
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
        'Content-Type': 'video/mp4',
        'Content-Disposition': f'inline; filename="{file_name}"',
        'Accept-Ranges': 'bytes',
        'Content-Length': str(media.file_size)
    }
    return StreamingResponse(media_streamer(), headers=headers)

# ----------------- Bot Event Handlers ----------------- #

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    await message.reply_text("👋 **SS Anime Box Streaming Bot is Online!**\n\nযেকোনো ভিডিও বা ফাইল পাঠান।")

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
        stream_status = "⚠️ **ব্রাউজারে সরাসরি চলবে না** (VLC Player ব্যবহার করুন)"

    watch_link = f"{URL}/watch/{BIN_CHANNEL}/{bin_msg.id}/{safe_name}"
    download_link = f"{URL}/download/{BIN_CHANNEL}/{bin_msg.id}/{safe_name}"

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Watch Online 🎬", url=watch_link)],
        [InlineKeyboardButton("Direct Download 📥", url=download_link)],
        [InlineKeyboardButton("Our Channel 📢", url=CHANNEL_LINK)]
    ])

    caption = (
        f"📁 **ফাইল নাম:** `{original_name}`\n"
        f"🏷 **টাইপ:** `{file_ext}` | 📦 **সাইজ:** `{file_size}`\n"
        f"📌 **স্ট্যাটাস:** {stream_status}\n\n"
        f"👇 **আপনার লিংক নিচে তৈরি তৈরি হয়ে গেছে:**"
    )
    await message.reply_text(caption, reply_markup=reply_markup)

# ----------------- Server Lifecycle ----------------- #

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(bot.start())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
