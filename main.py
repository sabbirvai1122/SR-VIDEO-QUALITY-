import os
import re
import asyncio
from urllib.parse import quote
from aiohttp import web
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

# ----------------- User Rename State Storage ----------------- #
rename_state = {}

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
        
        display_name = getattr(media, 'file_name', 'Video Stream')
        clean_filename = clean_and_encode_filename(display_name)
        download_url = f"/download/{chat_id}/{message_id}/{clean_filename}"
        
        # 2nd Photo Style Fullscreen/Clean Player
        html_content = f"""
        <!DOCTYPE html>
        <html lang="bn">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{display_name}</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body, html {{ width: 100%; height: 100%; background-color: #000; color: #fff; font-family: sans-serif; overflow: hidden; display: flex; flex-direction: column; justify-content: center; align-items: center; }}
                .video-container {{ width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; position: relative; }}
                video {{ width: 100%; height: 100%; max-height: 100vh; object-fit: contain; background: #000; }}
                .title-overlay {{ position: absolute; top: 15px; left: 15px; z-index: 10; background: rgba(0, 0, 0, 0.6); padding: 8px 15px; border-radius: 5px; font-size: 14px; max-width: 90%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
            </style>
        </head>
        <body>
            <div class="video-container">
                <div class="title-overlay">📁 {display_name}</div>
                <video controls autoplay name="media" playsinline>
                    <source src="{download_url}" type="video/mp4">
                    <source src="{download_url}" type="video/x-matroska">
                    Your browser does not support video playback.
                </video>
            </div>
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
            "আমাকে যেকোনো ভিডিও বা ফাইল পাঠান, আমি লিংক বানিয়ে দেব।",
            reply_markup=reply_markup
        )

    @app.on_message(filters.private & (filters.document | filters.video | filters.audio))
    async def media_handler(bot, message: Message):
        # Forward file to BIN Channel
        try:
            bin_msg = await message.forward(BIN_CHANNEL)
        except Exception:
            bin_msg = message

        media = bin_msg.document or bin_msg.video or bin_msg.audio
        original_name = getattr(media, 'file_name', 'video.mp4')
        safe_name = clean_and_encode_filename(original_name)
        file_size = humanbytes(getattr(media, 'file_size', 0))
        
        file_ext = original_name.rsplit('.', 1)[-1].upper() if '.' in original_name else "MP4"
        
        # Compatibility Check
        if file_ext in ["MP4", "WEBM"]:
            stream_status = "✅ **ব্রাউজারে সরাসরি চলবে**"
        else:
            stream_status = "⚠️ **ব্রাউজারে সরাসরি চলবে না** (ডাউনলোড অথবা VLC/MX Player এ প্লে করুন)"

        watch_link = f"{URL}/watch/{BIN_CHANNEL}/{bin_msg.id}/{safe_name}"
        download_link = f"{URL}/download/{BIN_CHANNEL}/{bin_msg.id}/{safe_name}"
        
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Watch Online 🎬", url=watch_link)],
            [InlineKeyboardButton("Direct Download 📥", url=download_link)],
            [InlineKeyboardButton("Rename File ✏️", callback_data=f"rename_{bin_msg.id}")],
            [InlineKeyboardButton("Our Channel 📢", url=CHANNEL_LINK)]
        ])
        
        caption_text = (
            f"📁 **ফাইল নাম:** `{original_name}`\n"
            f"🏷 **ফাইল টাইপ:** `{file_ext}`\n"
            f"📦 **ফাইল সাইজ:** `{file_size}`\n"
            f"📌 **স্ট্রিমিং স্ট্যাটাস:** {stream_status}\n\n"
            f"👇 **আপনার ভিডিও দেখার ও ডাউনলোডের লিংক নিচে দেওয়া হলো:**"
        )
        
        await message.reply_text(caption_text, reply_markup=reply_markup)

    @app.on_callback_query(filters.regex(r"^rename_"))
    async def rename_callback(bot, query: CallbackQuery):
        msg_id = int(query.data.split("_")[1])
        rename_state[query.from_user.id] = msg_id
        await query.message.reply_text("✏️ **নতুন ফাইলের নাম পাঠান (এক্সটেনশন সহ, যেমন: `Anime_S01E01.mp4`):**")
        await query.answer()

    @app.on_message(filters.private & filters.text & ~filters.command(["start"]))
    async def process_rename(bot, message: Message):
        user_id = message.from_user.id
        if user_id in rename_state:
            bin_msg_id = rename_state.pop(user_id)
            new_name = message.text.strip()
            
            try:
                bin_msg = await app.get_messages(BIN_CHANNEL, bin_msg_id)
                media = bin_msg.document or bin_msg.video or bin_msg.audio
                safe_name = clean_and_encode_filename(new_name)
                file_size = humanbytes(getattr(media, 'file_size', 0))
                
                file_ext = new_name.rsplit('.', 1)[-1].upper() if '.' in new_name else "MP4"
                
                if file_ext in ["MP4", "WEBM"]:
                    stream_status = "✅ **ব্রাউজারে সরাসরি চলবে**"
                else:
                    stream_status = "⚠️ **ব্রাউজারে সরাসরি চলবে না** (ডাউনলোড অথবা VLC/MX Player এ প্লে করুন)"

                watch_link = f"{URL}/watch/{BIN_CHANNEL}/{bin_msg_id}/{safe_name}"
                download_link = f"{URL}/download/{BIN_CHANNEL}/{bin_msg_id}/{safe_name}"
                
                reply_markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Watch Online 🎬", url=watch_link)],
                    [InlineKeyboardButton("Direct Download 📥", url=download_link)],
                    [InlineKeyboardButton("Rename File ✏️", callback_data=f"rename_{bin_msg_id}")],
                    [InlineKeyboardButton("Our Channel 📢", url=CHANNEL_LINK)]
                ])
                
                caption_text = (
                    f"📁 **নতুন ফাইল নাম:** `{new_name}`\n"
                    f"🏷 **ফাইল টাইপ:** `{file_ext}`\n"
                    f"📦 **ফাইল সাইজ:** `{file_size}`\n"
                    f"📌 **স্ট্রিমিং স্ট্যাটাস:** {stream_status}\n\n"
                    f"👇 **আপনার ভিডিও দেখার ও ডাউনলোডের নতুন লিংক নিচে দেওয়া হলো:**"
                )
                
                await message.reply_text(caption_text, reply_markup=reply_markup)
            except Exception as e:
                await message.reply_text(f"❌ নাম পরিবর্তন করতে সমস্যা হয়েছে: {str(e)}")

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
