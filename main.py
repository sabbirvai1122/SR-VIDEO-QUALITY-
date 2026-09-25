import os
import re
import asyncio
from urllib.parse import quote
from aiohttp import web
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# ----------------- Configuration ----------------- #

API_ID = int(os.environ.get("API_ID", "29608422"))
API_HASH = os.environ.get("API_HASH", "3db2f8e109301f02f5d9c8f10dd79244")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8765885559:AAGepuq7edjdkX1dnocii3EfUFiLGX1v9IA")

URL = os.environ.get("URL", "https://sr-video-quality-2.onrender.com").rstrip('/')
PORT = int(os.environ.get("PORT", "8080"))

CHANNEL_LINK = "https://t.me/ss_anime_box"

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
    
    full_name = f"{name_part}.{ext}"
    return quote(full_name)

def humanbytes(size):
    if not size:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0

# ----------------- Web Server Routes ----------------- #

routes = web.RouteTableDef()

@routes.get("/")
async def root_route(request):
    return web.Response(text="Bot is Live and Running!", status=200)

@routes.get("/watch/{chat_id}/{message_id}/{file_name}")
async def stream_handler(request):
    app = request.app['bot_client']
    chat_id = int(request.match_info['chat_id'])
    message_id = int(request.match_info['message_id'])
    
    try:
        msg = await app.get_messages(chat_id, message_id)
        media = msg.document or msg.video or msg.audio
        if not media:
            return web.Response(text="File Not Found", status=404)
        
        clean_filename = clean_and_encode_filename(getattr(media, 'file_name', 'video.mp4'))
        download_url = f"/download/{chat_id}/{message_id}/{clean_filename}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Stream Video</title>
            <link href="https://vjs.zencdn.net/7.20.3/video-js.css" rel="stylesheet" />
            <style>
                body {{ background-color: #0f0f0f; color: #fff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; margin: 0; padding: 15px; }}
                .container {{ max-width: 800px; margin: 0 auto; }}
                .video-js {{ width: 100% !important; height: auto !important; aspect-ratio: 16/9; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }}
                .btn-group {{ margin-top: 20px; }}
                .btn {{ display: block; width: 100%; padding: 14px; margin: 10px 0; background: #1e1e1e; color: #fff; text-decoration: none; border-radius: 8px; font-weight: bold; border: 1px solid #333; box-sizing: border-box; transition: 0.3s; }}
                .btn:hover {{ background: #007bff; border-color: #007bff; }}
                .note {{ color: #aaa; font-size: 13px; margin-top: 8px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <video id="my-video" class="video-js vjs-default-skin vjs-big-play-centered" controls preload="auto" data-setup='{{}}'>
                    <source src="{download_url}" type="video/mp4">
                    <source src="{download_url}" type="video/webm">
                    <source src="{download_url}" type="video/x-matroska">
                    Your browser does not support video playback.
                </video>

                <div class="btn-group">
                    <a class="btn" href="{download_url}">📥 DIRECT DOWNLOAD</a>
                    <a class="btn" href="vlc://{URL}{download_url}">🎬 WATCH IN VLC PLAYER</a>
                    <a class="btn" href="intent://{URL.replace('https://', '').replace('http://', '')}{download_url}#Intent;package=com.mxtech.videoplayer.ad;type=video/*;end">▶ WATCH IN MX PLAYER</a>
                </div>
                <p class="note">💡 ব্রাউজারে সমস্য হলে "WATCH IN VLC" অথবা "MX PLAYER" এ ক্লিক করুন।</p>
            </div>
            <script src="https://vjs.zencdn.net/7.20.3/video.min.js"></script>
        </body>
        </html>
        """
        return web.Response(text=html_content, content_type='text/html')
    except Exception as e:
        return web.Response(text=str(e), status=500)

@routes.get("/download/{chat_id}/{message_id}/{file_name}")
async def download_handler(request):
    app = request.app['bot_client']
    chat_id = int(request.match_info['chat_id'])
    message_id = int(request.match_info['message_id'])
    
    msg = await app.get_messages(chat_id, message_id)
    media = msg.document or msg.video or msg.audio
    
    clean_filename = clean_and_encode_filename(getattr(media, 'file_name', 'video.mp4'))
    
    # attachment হেডারের কারণে লিংকে চাপ দিলেই ফাইলটি সরাসরি ডাউনলোড হওয়া শুরু করবে
    response = web.StreamResponse(
        status=200,
        headers={
            'Content-Type': 'application/octet-stream',
            'Content-Disposition': f'attachment; filename="{clean_filename}"',
            'Content-Length': str(media.file_size),
            'Accept-Ranges': 'bytes'
        }
    )
    await response.prepare(request)
    
    async for chunk in app.stream_media(msg, limit=0):
        await response.write(chunk)
        
    return response

# ----------------- Main Execution ----------------- #

async def main():
    app = Client(
        name="bot_session",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True
    )

    @app.on_message(filters.command("start") & filters.private)
    async def start_handler(bot, message: Message):
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Channel 📢", url=CHANNEL_LINK)]
        ])
        await message.reply_text(
            "👋 **হ্যালো! আমি আপনার স্ট্রিমিং বট।**\n\n"
            "আমাকে যেকোনো ফাইল পাঠান, আমি সরাসরি লিংক বানিয়ে দেব।",
            reply_markup=reply_markup
        )

    @app.on_message(filters.private & (filters.document | filters.video | filters.audio))
    async def media_handler(bot, message: Message):
        media = message.document or message.video or message.audio
        original_name = getattr(media, 'file_name', 'video.mp4')
        safe_name = clean_and_encode_filename(original_name)
        file_size = humanbytes(getattr(media, 'file_size', 0))
        
        # ফাইল এক্সটেনশন/টাইপ বের করা
        if '.' in original_name:
            file_ext = original_name.rsplit('.', 1)[-1].upper()
        else:
            file_ext = "MP4"

        watch_link = f"{URL}/watch/{message.chat.id}/{message.id}/{safe_name}"
        download_link = f"{URL}/download/{message.chat.id}/{message.id}/{safe_name}"
        
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Watch Online 🎬", url=watch_link)],
            [InlineKeyboardButton("Direct Download 📥", url=download_link)],
            [InlineKeyboardButton("Our Channel 📢", url=CHANNEL_LINK)]
        ])
        
        caption_text = (
            f"📁 **ফাইল নাম:** `{original_name}`\n"
            f"🏷 **ফাইল টাইপ:** `{file_ext}`\n"
            f"📦 **ফাইল সাইজ:** `{file_size}`\n\n"
            f"👇 **আপনার ভিডিও দেখার ও ডাউনলোডের লিংক নিচে দেওয়া হলো:**"
        )
        
        await message.reply_text(caption_text, reply_markup=reply_markup)

    await app.start()
    
    web_app = web.Application()
    web_app['bot_client'] = app
    web_app.add_routes(routes)
    
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    print("Bot & Web Server Started Successfully!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
