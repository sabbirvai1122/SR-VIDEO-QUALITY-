import os
import re
import uvicorn
import asyncio
from urllib.parse import quote
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# ----------------- Configuration ----------------- #

API_ID = int(os.environ.get("API_ID", "29608422"))
API_HASH = os.environ.get("API_HASH", "3db2f8e109301f02f5d9c8f10dd79244")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8765885559:AAGepuq7edjdkX1dnocii3EfUFiLGX1v9IA")

URL = os.environ.get("URL", "https://sr-video-quality-2.onrender.com").rstrip('/')
PORT = int(os.environ.get("PORT", "8080"))

BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL", "-1004450462812"))
CHANNEL_LINK = "https://t.me/ss_anime_box"

# Global Client Placeholder
bot = None

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

# ----------------- Web Player ----------------- #

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def root():
    return "<h1>SS Anime Box Web Server Active!</h1>"

@app.get("/watch/{chat_id}/{message_id}/{file_name}", response_class=HTMLResponse)
async def watch_player(chat_id: int, message_id: int, file_name: str):
    stream_url = f"{URL}/stream/{chat_id}/{message_id}/{file_name}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>SS Anime Box Player</title>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; }}
            body {{
                background-color: #0b0f19;
                color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: flex-start;
                min-height: 100vh;
            }}
            .video-container {{
                position: relative;
                width: 100%;
                background-color: #000;
                display: flex;
                justify-content: center;
                align-items: center;
                filter: brightness(100%);
            }}
            video {{
                width: 100%;
                max-height: 70vh;
                outline: none;
            }}
            
            .card {{
                margin: 20px 15px;
                padding: 16px;
                background: linear-gradient(135deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 16px;
                text-align: center;
                width: calc(100% - 30px);
                max-width: 500px;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            }}
            .card h2 {{
                font-size: 20px;
                color: #ff9900;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                font-weight: 700;
                margin-bottom: 4px;
            }}
            .card h2::before {{
                content: "●";
                color: #ff9900;
                font-size: 14px;
            }}
            .card p {{
                font-size: 13px;
                color: #9aa0a6;
            }}

            .overlay-indicator {{
                position: absolute;
                top: 50%;
                transform: translateY(-50%);
                padding: 10px 18px;
                background: rgba(0, 0, 0, 0.75);
                color: #fff;
                font-size: 14px;
                border-radius: 8px;
                display: none;
                z-index: 10;
                pointer-events: none;
            }}
            #left-indicator {{ left: 15px; }}
            #right-indicator {{ right: 15px; }}
        </style>
    </head>
    <body>
        <div class="video-container" id="wrapper">
            <video id="player" controls autoplay playsinline preload="metadata" crossorigin="anonymous">
                <source src="{stream_url}" type="video/mp4">
            </video>
            <div id="left-indicator" class="overlay-indicator">Brightness: <span id="b-val">100</span>%</div>
            <div id="right-indicator" class="overlay-indicator">Volume: <span id="v-val">100</span>%</div>
        </div>

        <div class="card">
            <h2>SS ANIME BOX</h2>
            <p>High Quality Anime Streaming</p>
        </div>

        <script>
            const video = document.getElementById('player');
            const wrapper = document.getElementById('wrapper');
            const leftInd = document.getElementById('left-indicator');
            const rightInd = document.getElementById('right-indicator');
            const bVal = document.getElementById('b-val');
            const vVal = document.getElementById('v-val');

            let currentBrightness = 100;
            let startY = 0;
            let startVal = 0;
            let isSwipingLeft = false;
            let isSwipingRight = false;

            wrapper.addEventListener('touchstart', (e) => {{
                if (e.touches.length === 1) {{
                    startY = e.touches[0].clientY;
                    const screenWidth = window.innerWidth;
                    if (e.touches[0].clientX < screenWidth / 2) {{
                        isSwipingLeft = true;
                        isSwipingRight = false;
                        startVal = currentBrightness;
                    }} else {{
                        isSwipingRight = true;
                        isSwipingLeft = false;
                        startVal = video.volume * 100;
                    }}
                }}
            }});

            wrapper.addEventListener('touchmove', (e) => {{
                if (!isSwipingLeft && !isSwipingRight) return;
                let deltaY = startY - e.touches[0].clientY;
                let change = (deltaY / window.innerHeight) * 150;

                if (isSwipingLeft) {{
                    let newB = Math.min(Math.max(startVal + change, 10), 200);
                    currentBrightness = newB;
                    wrapper.style.filter = `brightness(${{newB}}%)`;
                    bVal.innerText = Math.round((newB / 200) * 100);
                    leftInd.style.display = 'block';
                }} else if (isSwipingRight) {{
                    let newV = Math.min(Math.max(startVal + change, 0), 100);
                    video.volume = newV / 100;
                    vVal.innerText = Math.round(newV);
                    rightInd.style.display = 'block';
                }}
            }});

            wrapper.addEventListener('touchend', () => {{
                isSwipingLeft = false;
                isSwipingRight = false;
                leftInd.style.display = 'none';
                rightInd.style.display = 'none';
            }});
        </script>
    </body>
    </html>
    """
    return html_content

# ----------------- Fast Streaming Handler ----------------- #

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
            async for chunk in bot.stream_media(msg, offset=start, limit=content_length):
                yield chunk

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
            async for chunk in bot.stream_media(msg):
                yield chunk

        headers = {
            'Accept-Ranges': 'bytes',
            'Content-Length': str(file_size),
            'Content-Type': 'video/mp4',
            'Content-Disposition': f'{disposition_type}; filename="{file_name}"'
        }
        return StreamingResponse(fast_full_streamer(), status_code=200, headers=headers)

# ----------------- Main Async Entry Point ----------------- #

async def main():
    global bot
    
    # Create the asyncio event loop first
    loop = asyncio.get_running_loop()
    
    # Initialize client inside active event loop
    bot = Client(
        name="bot_session",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True,
        max_concurrent_transmissions=10
    )

    # Attach Handlers
    @bot.on_message(filters.command("start") & filters.private)
    async def start_cmd(client, message: Message):
        await message.reply_text("👋 **SS Anime Box Bot Active!**\n\nফাইল পাঠান, দ্রুত স্ট্রিম লিংক পেয়ে যাবেন।")

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
            original_name = getattr(media, 'file_name', None) or f"video_{message.id}.mp4"
                
            safe_name = clean_and_encode_filename(original_name)
            file_size = humanbytes(getattr(media, 'file_size', 0))
            
            ext = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else "mp4"
            file_ext = ext.upper()

            if ext == "mp4":
                status_msg = "✅ ব্রাউজারে সরাসরি চলবে"
            else:
                status_msg = "⚠️ MKV/অন্যান্য ফাইল; ব্রাউজারে না চললে Direct Download করুন"

            watch_link = f"{URL}/watch/{target_chat_id}/{target_msg_id}/{safe_name}"
            download_link = f"{URL}/download/{target_chat_id}/{target_msg_id}/{safe_name}"

            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("Watch Online 🎬", url=watch_link)],
                [InlineKeyboardButton("Direct Download 📥", url=download_link)],
                [InlineKeyboardButton("Our Channel 📢", url=CHANNEL_LINK)]
            ])

            caption = (
                f"📁 **ফাইল নাম:** `{original_name}`\n"
                f"🏷 **টাইপ:** `{file_ext}` | 📦 **সাইজ:** `{file_size}`\n"
                f"📌 **স্ট্যাটাস:** {status_msg}\n\n"
                f"👇 **আপনার লিংক নিচে দেওয়া হলো:**"
            )
            await message.reply_text(caption, reply_markup=reply_markup)

        except Exception as e:
            await message.reply_text(f"❌ লিংক তৈরিতে সমস্যা হয়েছে: `{str(e)}`")

    # Start Telegram Bot Client
    await bot.start()
    
    # Configure and run Uvicorn FastAPI Server concurrently
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
