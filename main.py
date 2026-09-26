import os
import re
import uvicorn
import asyncio
from urllib.parse import quote, unquote
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand

# ----------------- Configuration ----------------- #

API_ID = int(os.environ.get("API_ID", "29608422"))
API_HASH = os.environ.get("API_HASH", "3db2f8e109301f02f5d9c8f10dd79244")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8765885559:AAGepuq7edjdkX1dnocii3EfUFiLGX1v9IA")

URL = os.environ.get("URL", "https://sr-video-quality-2.onrender.com").rstrip('/')
PORT = int(os.environ.get("PORT", "8080"))

BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL", "-1004450462812"))
CHANNEL_LINK = "https://t.me/ss_anime_box"

bot = None
user_file_cache = {}

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

# ----------------- Web Player Endpoint ----------------- #

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def root():
    return "<h1>SS Anime Box Web Server Active!</h1>"

@app.get("/watch/{chat_id}/{message_id}/{file_name}", response_class=HTMLResponse)
async def watch_player(
    chat_id: int, 
    message_id: int, 
    file_name: str, 
    q480: str = None, 
    q720: str = None, 
    q1080: str = None
):
    default_stream_url = f"{URL}/stream/{chat_id}/{message_id}/{file_name}"
    
    options_list = []
    if q480 and q480.lower() != "none":
        url_480 = f"{URL}/stream/{BIN_CHANNEL}/{q480}/{file_name}"
        options_list.append(f'<option value="{url_480}">480p</option>')
    
    if q720 and q720.lower() != "none":
        url_720 = f"{URL}/stream/{BIN_CHANNEL}/{q720}/{file_name}"
        options_list.append(f'<option value="{url_720}">720p</option>')

    if q1080 and q1080.lower() != "none":
        url_1080 = f"{URL}/stream/{BIN_CHANNEL}/{q1080}/{file_name}"
        options_list.append(f'<option value="{url_1080}">1080p</option>')

    if not options_list:
        options_list.append(f'<option value="{default_stream_url}">Quality Option</option>')

    quality_options_html = "\n".join(options_list)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="bn">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>SS Anime Box Player</title>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; }}
            html, body {{
                width: 100%;
                height: 100%;
                background-color: #0b0f19;
                color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: flex-start;
                overflow-x: hidden;
            }}
            
            .video-wrapper {{
                position: relative;
                width: 100%;
                max-width: 850px;
                aspect-ratio: 16 / 9;
                background-color: #000;
                overflow: hidden;
            }}

            video {{
                width: 100%;
                height: 100%;
                object-fit: contain;
                display: block;
                outline: none;
            }}

            /* Bottom Embedded Quality Selector Bar */
            .bottom-control-bar {{
                position: absolute;
                bottom: 12px;
                right: 15px;
                z-index: 30;
                display: flex;
                align-items: center;
                gap: 6px;
                background: rgba(0, 0, 0, 0.6);
                padding: 4px 8px;
                border-radius: 6px;
                backdrop-filter: blur(4px);
            }}

            .quality-select {{
                background: rgba(20, 20, 20, 0.9);
                color: #ff9900;
                border: 1px solid #ff9900;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: bold;
                border-radius: 4px;
                outline: none;
                cursor: pointer;
            }}

            .card {{
                margin-top: 15px;
                padding: 14px;
                background: linear-gradient(135deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                text-align: center;
                width: calc(100% - 30px);
                max-width: 450px;
            }}
            .card h2 {{
                font-size: 16px;
                color: #ff9900;
                margin-bottom: 2px;
            }}
            .card p {{
                font-size: 12px;
                color: #9aa0a6;
            }}

            .overlay-indicator {{
                position: absolute;
                top: 50%;
                transform: translateY(-50%);
                padding: 6px 12px;
                background: rgba(0, 0, 0, 0.8);
                color: #fff;
                font-size: 12px;
                border-radius: 6px;
                display: none;
                z-index: 20;
                pointer-events: none;
            }}
            #left-indicator {{ left: 15px; }}
            #right-indicator {{ right: 15px; }}
        </style>
    </head>
    <body>

        <div class="video-wrapper" id="wrapper">
            <video id="player" controls autoplay playsinline preload="metadata">
                <source id="videoSource" src="{default_stream_url}" type="video/mp4">
            </video>

            <div class="bottom-control-bar">
                <span style="font-size: 10px; color: #aaa;">QUAL:</span>
                <select class="quality-select" id="qualitySelector" onchange="changeQuality(this.value)">
                    {quality_options_html}
                </select>
            </div>

            <div id="left-indicator" class="overlay-indicator">Brightness: <span id="b-val">100</span>%</div>
            <div id="right-indicator" class="overlay-indicator">Volume: <span id="v-val">100</span>%</div>
        </div>

        <div class="card">
            <h2>SS ANIME BOX</h2>
            <p>High Quality Player</p>
        </div>

        <script>
            const video = document.getElementById('player');
            const wrapper = document.getElementById('wrapper');
            const leftInd = document.getElementById('left-indicator');
            const rightInd = document.getElementById('right-indicator');
            const bVal = document.getElementById('b-val');
            const vVal = document.getElementById('v-val');

            function changeQuality(newUrl) {{
                if (!newUrl) return;
                const currentTime = video.currentTime;
                const isPaused = video.paused;

                video.src = newUrl;
                video.load();
                
                video.onloadedmetadata = function() {{
                    video.currentTime = currentTime;
                    if (!isPaused) {{
                        video.play().catch(e => console.log(e));
                    }}
                }};
            }}

            let currentBrightness = 100;
            let startY = 0;
            let startVal = 0;
            let isSwipingLeft = false;
            let isSwipingRight = false;

            wrapper.addEventListener('touchstart', (e) => {{
                if (e.target.tagName === 'SELECT' || e.target.tagName === 'OPTION') return;
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
            }}, {{ passive: true }});

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
            }}, {{ passive: true }});

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

# ----------------- Stream & Download Handlers ----------------- #

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
    
    decoded_filename = unquote(file_name)
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
            'Content-Disposition': f'{disposition_type}; filename="{decoded_filename}"'
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
            'Content-Disposition': f'{disposition_type}; filename="{decoded_filename}"'
        }
        return StreamingResponse(fast_full_streamer(), status_code=200, headers=headers)

# ----------------- Telegram Bot Handlers ----------------- #

async def main():
    global bot
    
    bot = Client(
        name="bot_session",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True,
        max_concurrent_transmissions=10
    )

    @bot.on_message(filters.command("start") & filters.private)
    async def start_cmd(client, message: Message):
        start_msg = (
            "🚀 **Start the bot**\n\n"
            "👋 **SS Anime Box Bot এ আপনাকে স্বাগতম!**\n\n"
            "📌 **ব্যবহারের নিয়মাবলী:**\n"
            "১. যেকোনো ফাইল পাঠান, লিংক সাথে সাথে পাবেন।\n"
            "২. **মাল্টি-কোয়ালিটি (2/3 Quality) একত্র করার কমান্ড:**\n"
            "`/combine <480p_ID> <720p_ID> <1080p_ID> <custom_filename>`\n"
            "*(উদাহরন: `/combine 80 81 82 1.mp4`)*\n\n"
            "🗑 **লিংক মুছে ফেলার নিয়ম:**\n"
            "লিংক মেসেজের সাথে থাকা **Delete Link** বোতামে চাপুন।"
        )
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Channel 📢", url=CHANNEL_LINK)]
        ])
        await message.reply_text(start_msg, reply_markup=reply_markup)

    @bot.on_message(filters.command("combine") & filters.private)
    async def combine_qualities(client, message: Message):
        try:
            args = message.text.split(maxsplit=4)
            if len(args) < 5:
                await message.reply_text("❌ ফরম্যাট সঠিক নয়!\nব্যবহার করুন: `/combine <480p_id> <720p_id> <1080p_id> <custom_filename>`")
                return

            id_480 = args[1]
            id_720 = args[2]
            id_1080 = args[3]
            custom_filename = clean_and_encode_filename(args[4])
            display_name = unquote(custom_filename)

            multi_watch_url = f"{URL}/watch/{BIN_CHANNEL}/{id_480}/{custom_filename}?q480={id_480}&q720={id_720}&q1080={id_1080}"
            
            keyboard_buttons = [
                [InlineKeyboardButton("Watch Online 🎬", url=multi_watch_url)]
            ]

            if id_480.lower() != "none":
                dl_480 = f"{URL}/download/{BIN_CHANNEL}/{id_480}/{custom_filename}"
                keyboard_buttons.append([InlineKeyboardButton(f"Direct Download (480p) 📥", url=dl_480)])

            if id_720.lower() != "none":
                dl_720 = f"{URL}/download/{BIN_CHANNEL}/{id_720}/{custom_filename}"
                keyboard_buttons.append([InlineKeyboardButton(f"Direct Download (720p) 📥", url=dl_720)])

            if id_1080.lower() != "none":
                dl_1080 = f"{URL}/download/{BIN_CHANNEL}/{id_1080}/{custom_filename}"
                keyboard_buttons.append([InlineKeyboardButton(f"Direct Download (1080p) 📥", url=dl_1080)])

            keyboard_buttons.append([InlineKeyboardButton("Delete Link 🗑", callback_data="delete_msg")])
            keyboard_buttons.append([InlineKeyboardButton("Join Channel 📢", url=CHANNEL_LINK)])

            await message.reply_text(
                f"📂 **ফাইল নাম:** `{display_name}`\n\n"
                "✅ **মাল্টি-কোয়ালিটি লিংক তৈরি করা হয়েছে!**", 
                reply_markup=InlineKeyboardMarkup(keyboard_buttons)
            )

        except Exception as e:
            await message.reply_text(f"❌ এরর: `{str(e)}`")

    @bot.on_message(filters.private & (filters.document | filters.video | filters.audio))
    async def process_incoming_file(client, message: Message):
        user_file_cache[message.from_user.id] = message
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("480p 🎬", callback_data="qual_480"),
                InlineKeyboardButton("720p 🎬", callback_data="qual_720"),
                InlineKeyboardButton("1080p 🎬", callback_data="qual_1080")
            ]
        ])
        await message.reply_text("📌 **ফাইলটির কোয়ালিটি চয়ন করুন:**", reply_markup=keyboard)

    @bot.on_callback_query(filters.regex("^qual_"))
    async def handle_quality_choice(client, callback: CallbackQuery):
        quality = callback.data.split("_")[1]
        user_id = callback.from_user.id

        if user_id not in user_file_cache:
            await callback.answer("⚠️ ফাইল খুঁজে পাওয়া যায়নি! আবার পাঠান।", show_alert=True)
            return

        message = user_file_cache[user_id]

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

        watch_link = f"{URL}/watch/{target_chat_id}/{target_msg_id}/{safe_name}"
        download_link = f"{URL}/download/{target_chat_id}/{target_msg_id}/{safe_name}"

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Watch Online ({quality}p) 🎬", url=watch_link)],
            [InlineKeyboardButton(f"Direct Download ({quality}p) 📥", url=download_link)],
            [InlineKeyboardButton("Delete Link 🗑", callback_data="delete_msg")],
            [InlineKeyboardButton("Join Channel 📢", url=CHANNEL_LINK)]
        ])

        caption = (
            f"📁 **ফাইল নাম:** `{original_name}`\n"
            f"🏷 **কোয়ালিটি:** `{quality}p` | 📦 **সাইজ:** `{file_size}`\n"
            f"🆔 **Message ID:** `{target_msg_id}`\n\n"
            f"👇 **আপনার লিংক নিচে দেওয়া হলো:**"
        )

        await callback.message.edit_text(caption, reply_markup=reply_markup)

    @bot.on_callback_query(filters.regex("^delete_msg$"))
    async def handle_delete_callback(client, callback: CallbackQuery):
        try:
            await callback.message.delete()
            await callback.answer("🗑 লিংক ও মেসেজ মুছে ফেলা হয়েছে!", show_alert=True)
        except Exception:
            await callback.answer("❌ মুছে ফেলা সম্ভব হয়নি।", show_alert=True)

    await bot.start()

    # --------------- Set Bot Menu Commands --------------- #
    await bot.set_bot_commands([
        BotCommand("start", "🚀 Start the bot"),
        BotCommand("combine", "📂 Combine Multiple Qualities"),
        BotCommand("del", "🗑 Delete Your File"),
        BotCommand("files", "📁 Check Your All Files"),
        BotCommand("help", "🚀 Get Help"),
        BotCommand("about", "⁉️ Why? 😑"),
        BotCommand("ban", "📑 [Admin Only]"),
        BotCommand("unban", "📑 [Admin Only]"),
        BotCommand("status", "📊 [Admin Only]")
    ])

    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
