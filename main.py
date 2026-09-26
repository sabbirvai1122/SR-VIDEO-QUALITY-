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
user_rename_state = {}

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
    return quote(file_name)

def humanbytes(size):
    if not size:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0

def check_streamable(file_name: str, mime_type: str = ""):
    ext = os.path.splitext(file_name)[1].lower() if file_name else ""
    if ext in [".mp4", ".m4v"]:
        return True, "✅ আপনি এই ভিডিওটি সরাসরি দেখতে এবং ডাউনলোড করতে পারবেন।"
    elif ext in [".mkv", ".avi", ".flv", ".wmv", ".webm"]:
        return False, f"⚠️ আপনি এই ভিডিওটি প্লেয়ারে সরাসরি দেখতে পারবেন না (কারণ: {ext.upper()} ফরম্যাট ব্রাউজারে স্ট্রিম সাপোর্ট করে না)। তবে আপনি এটি ডাউনলোড করে দেখতে পারবেন।"
    else:
        return True, "✅ আপনি এই ভিডিওটি দেখতে এবং ডাউনলোড করতে পারবেন।"

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
        options_list.append(f'<option value="{default_stream_url}">Quality</option>')

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
                background-color: #000000;
                color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: flex-start;
                overflow: hidden;
            }}
            
            .video-wrapper {{
                position: relative;
                width: 100%;
                max-width: 900px;
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

            .center-play-btn {{
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 60px;
                height: 60px;
                background: rgba(0, 0, 0, 0.6);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                z-index: 30;
                opacity: 0;
                transition: opacity 0.2s ease;
                pointer-events: auto;
            }}
            .center-play-btn svg {{
                width: 30px;
                height: 30px;
                fill: #ffffff;
            }}
            .video-wrapper:hover .center-play-btn, .video-wrapper:active .center-play-btn {{
                opacity: 1;
            }}

            .hud-overlay {{
                position: absolute;
                top: 15%;
                left: 50%;
                transform: translateX(-50%);
                display: none;
                align-items: center;
                gap: 12px;
                width: 240px;
                height: 42px;
                background: rgba(20, 20, 20, 0.85);
                border-radius: 20px;
                padding: 0 16px;
                backdrop-filter: blur(10px);
                z-index: 50;
                pointer-events: none;
                box-shadow: 0 4px 15px rgba(0,0,0,0.6);
            }}

            .hud-icon {{
                font-size: 18px;
                display: flex;
                align-items: center;
                justify-content: center;
            }}

            .hud-bar-container {{
                flex: 1;
                height: 10px;
                background: rgba(255, 255, 255, 0.25);
                border-radius: 5px;
                overflow: hidden;
            }}

            .hud-bar-fill {{
                height: 100%;
                width: 50%;
                border-radius: 5px;
                transition: width 0.05s ease-out;
            }}

            #volume-hud .hud-bar-fill {{
                background: #34c759;
            }}

            #brightness-hud .hud-bar-fill {{
                background: #e5e5ea;
            }}

            .custom-quality-box {{
                position: absolute;
                bottom: 12px;
                right: 15px;
                z-index: 40;
                display: flex;
                align-items: center;
                gap: 4px;
                background: rgba(0, 0, 0, 0.75);
                padding: 4px 6px;
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }}

            .gear-icon {{
                width: 18px;
                height: 18px;
            }}

            .quality-select {{
                background: transparent;
                color: #fff;
                border: none;
                font-size: 13px;
                font-weight: 600;
                outline: none;
                cursor: pointer;
            }}

            .card {{
                margin-top: 15px;
                padding: 12px;
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                text-align: center;
                width: calc(100% - 30px);
                max-width: 450px;
            }}
            .card h2 {{
                font-size: 15px;
                color: #ff9900;
            }}
            .card p {{
                font-size: 11px;
                color: #aaa;
            }}
        </style>
    </head>
    <body>

        <div class="video-wrapper" id="wrapper">
            <video id="player" controls autoplay playsinline preload="metadata">
                <source id="videoSource" src="{default_stream_url}" type="video/mp4">
            </video>

            <div class="center-play-btn" id="centerPlayBtn" onclick="togglePlayPause()">
                <svg id="playIcon" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
            </div>

            <div id="volume-hud" class="hud-overlay">
                <div class="hud-icon">🔊</div>
                <div class="hud-bar-container">
                    <div id="volume-fill" class="hud-bar-fill"></div>
                </div>
            </div>

            <div id="brightness-hud" class="hud-overlay">
                <div class="hud-icon">☀️</div>
                <div class="hud-bar-container">
                    <div id="brightness-fill" class="hud-bar-fill"></div>
                </div>
            </div>

            <div class="custom-quality-box">
                <svg class="gear-icon" viewBox="0 0 24 24" fill="#ffffff">
                    <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
                </svg>
                <select class="quality-select" id="qualitySelector" onchange="changeQuality(this.value)">
                    {quality_options_html}
                </select>
            </div>
        </div>

        <div class="card">
            <h2>SS ANIME BOX</h2>
            <p>High Quality Video Player</p>
        </div>

        <script>
            const video = document.getElementById('player');
            const wrapper = document.getElementById('wrapper');
            const playIcon = document.getElementById('playIcon');
            
            const volumeHud = document.getElementById('volume-hud');
            const volumeFill = document.getElementById('volume-fill');
            
            const brightnessHud = document.getElementById('brightness-hud');
            const brightnessFill = document.getElementById('brightness-fill');

            function togglePlayPause() {{
                if (video.paused) {{
                    video.play();
                }} else {{
                    video.pause();
                }}
            }}

            video.addEventListener('play', () => {{
                playIcon.innerHTML = '<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>';
            }});

            video.addEventListener('pause', () => {{
                playIcon.innerHTML = '<path d="M8 5v14l11-7z"/>';
            }});

            function changeQuality(newUrl) {{
                if (!newUrl) return;
                const currentTime = video.currentTime;
                const isPlaying = !video.paused;

                const source = document.getElementById('videoSource');
                source.src = newUrl;
                video.load();

                video.onloadeddata = function() {{
                    video.currentTime = currentTime;
                    if (isPlaying) {{
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
                if (e.target.tagName === 'SELECT' || e.target.tagName === 'OPTION' || e.target.id === 'centerPlayBtn' || e.target.closest('#centerPlayBtn')) return;
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
                    
                    let percentage = (newB / 200) * 100;
                    brightnessFill.style.width = percentage + '%';
                    brightnessHud.style.display = 'flex';
                }} else if (isSwipingRight) {{
                    let newV = Math.min(Math.max(startVal + change, 0), 100);
                    video.volume = newV / 100;
                    
                    volumeFill.style.width = newV + '%';
                    volumeHud.style.display = 'flex';
                }}
            }}, {{ passive: true }});

            wrapper.addEventListener('touchend', () => {{
                isSwipingLeft = false;
                isSwipingRight = false;
                brightnessHud.style.display = 'none';
                volumeHud.style.display = 'none';
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
        range_value = range_header.strip().lower().replace('bytes=', '')
        byte_opts = range_value.split('-')
        
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
            "*(উদাহরন: `/combine 80 81 82 Episode_01.mp4`)*\n\n"
            "🗑 **লিংক বা ফাইল ডিলিট করার নিয়ম:**\n"
            "চ্যাটে `/del <Message_ID>` লিখে পাঠাল লিংক রিমুভ হয়ে যাবে।"
        )
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Channel 📢", url=CHANNEL_LINK)]
        ])
        await message.reply_text(start_msg, reply_markup=reply_markup)

    @bot.on_message(filters.command("del") & filters.private)
    async def delete_file_cmd(client, message: Message):
        try:
            args = message.text.split()
            if len(args) < 2:
                await message.reply_text("❌ ফাইল ডিলিট করতে মেসেজ আইডি দিন!\nউদাহরণ: `/del 86`")
                return
            
            target_msg_id = int(args[1])
            await bot.delete_messages(BIN_CHANNEL, target_msg_id)
            await message.reply_text(f"🗑 Message ID `{target_msg_id}` এর ভিডিও ও লিংক সফলভাবে মুছে ফেলা হয়েছে!")
        except Exception as e:
            await message.reply_text(f"❌ ডিলিট করা যায়নি বা আইডি খুঁজে পাওয়া যায়নি: `{str(e)}`")

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
        mime_type = getattr(media, 'mime_type', '')
            
        safe_name = clean_and_encode_filename(original_name)
        file_size = humanbytes(getattr(media, 'file_size', 0))

        watch_link = f"{URL}/watch/{target_chat_id}/{target_msg_id}/{safe_name}"
        download_link = f"{URL}/download/{target_chat_id}/{target_msg_id}/{safe_name}"

        _, status_note = check_streamable(original_name, mime_type)

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Watch Online ({quality}p) 🎬", url=watch_link)],
            [InlineKeyboardButton(f"Direct Download ({quality}p) 📥", url=download_link)],
            [InlineKeyboardButton("Rename File ✏️", callback_data=f"rename_{target_chat_id}_{target_msg_id}_{quality}")],
            [InlineKeyboardButton("Delete Link 🗑", callback_data="delete_msg")],
            [InlineKeyboardButton("Join Channel 📢", url=CHANNEL_LINK)]
        ])

        caption = (
            f"📁 **ফাইল নাম:** `{original_name}`\n"
            f"🏷 **কোয়ালিটি:** `{quality}p` | 📦 **সাইজ:** `{file_size}`\n"
            f"🆔 **Message ID:** `{target_msg_id}`\n\n"
            f"ℹ️ {status_note}\n\n"
            f"👇 **আপনার লিংক নিচে দেওয়া হলো:**"
        )

        await callback.message.edit_text(caption, reply_markup=reply_markup)

    @bot.on_callback_query(filters.regex("^rename_"))
    async def handle_rename_click(client, callback: CallbackQuery):
        data = callback.data.split("_")
        chat_id = data[1]
        msg_id = data[2]
        quality = data[3]
        
        user_id = callback.from_user.id
        user_rename_state[user_id] = {
            "chat_id": chat_id,
            "msg_id": msg_id,
            "quality": quality,
            "bot_msg_id": callback.message.id
        }

        await callback.message.reply_text("✏️ **অনুগ্রহ করে নতুন ফাইল নামটি টাইপ করে পাঠান:**\n*(যেমন: Episode_01.mp4)*")
        await callback.answer()

    @bot.on_message(filters.private & filters.text & ~filters.command(["start", "combine", "del"]))
    async def process_rename_input(client, message: Message):
        user_id = message.from_user.id
        if user_id in user_rename_state:
            state = user_rename_state.pop(user_id)
            new_name = message.text.strip()

            target_chat_id = state["chat_id"]
            target_msg_id = state["msg_id"]
            quality = state["quality"]

            safe_name = clean_and_encode_filename(new_name)
            
            try:
                msg = await bot.get_messages(int(target_chat_id), int(target_msg_id))
                media = msg.document or msg.video or msg.audio
                file_size = humanbytes(getattr(media, 'file_size', 0))
                mime_type = getattr(media, 'mime_type', '')
            except Exception:
                file_size = "N/A"
                mime_type = ""

            watch_link = f"{URL}/watch/{target_chat_id}/{target_msg_id}/{safe_name}"
            download_link = f"{URL}/download/{target_chat_id}/{target_msg_id}/{safe_name}"

            _, status_note = check_streamable(new_name, mime_type)

            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Watch Online ({quality}p) 🎬", url=watch_link)],
                [InlineKeyboardButton(f"Direct Download ({quality}p) 📥", url=download_link)],
                [InlineKeyboardButton("Rename File ✏️", callback_data=f"rename_{target_chat_id}_{target_msg_id}_{quality}")],
                [InlineKeyboardButton("Delete Link 🗑", callback_data="delete_msg")],
                [InlineKeyboardButton("Join Channel 📢", url=CHANNEL_LINK)]
            ])

            caption = (
                f"📁 **ফাইল নাম:** `{new_name}`\n"
                f"🏷 **কোয়ালিটি:** `{quality}p` | 📦 **সাইজ:** `{file_size}`\n"
                f"🆔 **Message ID:** `{target_msg_id}`\n\n"
                f"ℹ️ {status_note}\n\n"
                f"👇 **আপনার লিংক নিচে দেওয়া হলো:**"
            )

            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=state["bot_msg_id"],
                text=caption,
                reply_markup=reply_markup
            )
            await message.reply_text("✅ ফাইলের নাম সফলভাবে আপডেট করা হয়েছে!")

    @bot.on_callback_query(filters.regex("^delete_msg$"))
    async def handle_delete_callback(client, callback: CallbackQuery):
        try:
            await callback.message.delete()
            await callback.answer("🗑 লিংক ও মেসেজ মুছে ফেলা হয়েছে!", show_alert=True)
        except Exception:
            await callback.answer("❌ মুছে ফেলা সম্ভব হয়নি।", show_alert=True)

    await bot.start()

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
