import os
import re
from urllib.parse import quote
from aiohttp import web
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# ----------------- Configurations ----------------- #

API_ID = int(os.environ.get("API_ID", "29608422"))
API_HASH = os.environ.get("API_HASH", "3db2f8e109301f02f5d9c8f10dd79244")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8227731967:AAEmgSiywxmGfe1GYhj9RSqaOtMvaAgS99k")

URL = os.environ.get("URL", "https://sr-video-quality-2.onrender.com").rstrip('/')
PORT = int(os.environ.get("PORT", "8080"))

bot = Client("StreamBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ----------------- Clean Filename ----------------- #

def clean_and_encode_filename(file_name: str) -> str:
    if not file_name:
        return "video.mp4"
    clean_name = re.sub(r'\[.*?\]|\(.*?\)', '', file_name)
    clean_name = re.sub(r'[^a-zA-Z0-9.-]', '_', clean_name)
    clean_name = re.sub(r'_+', '_', clean_name).strip('_')
    
    if '.' in clean_name:
        name_part, ext_part = clean_name.rsplit('.', 1)
        clean_name = f"{name_part}.{ext_part.lower()}"
    else:
        clean_name += ".mp4"
        
    return quote(clean_name)

# ----------------- Web Routes ----------------- #

routes = web.RouteTableDef()

@routes.get("/")
async def root_route(request):
    return web.Response(text="Bot is Live and Running!", status=200)

@routes.get("/watch/{chat_id}/{message_id}/{file_name}")
async def stream_handler(request):
    chat_id = int(request.match_info['chat_id'])
    message_id = int(request.match_info['message_id'])
    
    try:
        msg = await bot.get_messages(chat_id, message_id)
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
            <style>
                body {{ background-color: #121212; color: #fff; font-family: sans-serif; text-align: center; margin: 0; padding: 20px; }}
                .container {{ max-width: 700px; margin: 0 auto; }}
                video {{ width: 100%; max-height: 450px; background: #000; border-radius: 8px; margin-bottom: 15px; }}
                .btn {{ display: block; width: 100%; padding: 12px; margin: 10px 0; background: #222; color: #fff; text-decoration: none; border-radius: 5px; font-weight: bold; border: 1px solid #444; box-sizing: border-box; }}
                .btn:hover {{ background: #333; }}
            </style>
        </head>
        <body>
            <div class="container">
                <video controls autoplay name="media">
                    <source src="{download_url}" type="video/mp4">
                    Your browser does not support HTML5 video.
                </video>
                <a class="btn" href="{download_url}">DOWNLOAD VIDEO</a>
                <a class="btn" href="vlc://{URL}{download_url}">WATCH IN VLC PLAYER</a>
                <a class="btn" href="intent://{URL.replace('https://', '').replace('http://', '')}{download_url}#Intent;package=com.mxtech.videoplayer.ad;type=video/*;end">WATCH IN MX PLAYER</a>
            </div>
        </body>
        </html>
        """
        return web.Response(text=html_content, content_type='text/html')
    except Exception as e:
        return web.Response(text=str(e), status=500)

@routes.get("/download/{chat_id}/{message_id}/{file_name}")
async def download_handler(request):
    chat_id = int(request.match_info['chat_id'])
    message_id = int(request.match_info['message_id'])
    
    msg = await bot.get_messages(chat_id, message_id)
    media = msg.document or msg.video or msg.audio
    
    clean_filename = clean_and_encode_filename(getattr(media, 'file_name', 'video.mp4'))
    
    response = web.StreamResponse(
        status=200,
        headers={
            'Content-Type': 'video/mp4',
            'Content-Disposition': f'inline; filename="{clean_filename}"',
            'Content-Length': str(media.file_size)
        }
    )
    await response.prepare(request)
    
    async for chunk in bot.stream_media(msg, limit=0):
        await response.write(chunk)
        
    return response

# ----------------- Telegram Bot Handlers ----------------- #

@bot.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def media_handler(cli, message: Message):
    media = message.document or message.video or message.audio
    original_name = getattr(media, 'file_name', 'video.mp4')
    safe_name = clean_and_encode_filename(original_name)
    
    watch_link = f"{URL}/watch/{message.chat.id}/{message.id}/{safe_name}"
    download_link = f"{URL}/download/{message.chat.id}/{message.id}/{safe_name}"
    
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Watch Online 🎬", url=watch_link)],
        [InlineKeyboardButton("Direct Download 📥", url=download_link)]
    ])
    
    await message.reply_text(f"**File Name:** `{original_name}`\n\nলিংক তৈরি হয়েছে:", reply_markup=reply_markup)

# ----------------- Start Services ----------------- #

async def web_app():
    app = web.Application()
    app.add_routes(routes)
    return app

if __name__ == "__main__":
    bot.start()
    web.run_app(web_app(), host="0.0.0.0", port=PORT)
