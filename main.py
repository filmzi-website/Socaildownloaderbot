import os
import yt_dlp
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from pyrogram import Client
import time

# ===============================
# Environment Variables (set in Koyeb dashboard)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "20288994"))
API_HASH = os.getenv("API_HASH", "d702614912f1ad370a0d18786002adbf")
# ===============================

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Pyrogram client for large file uploads
pyrogram_client = None

# Global user data storage
user_data = {}

async def init_pyrogram():
    """Initialize Pyrogram client"""
    global pyrogram_client
    try:
        pyrogram_client = Client(
            "bot_session",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=TOKEN,
            in_memory=True
        )
        await pyrogram_client.start()
        logger.info("✅ Pyrogram client started successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to start Pyrogram client: {e}")
        return False

# ========= Telegram Bot Handlers =========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name
    greeting = (
        f"👋 Hello, {user_first_name}!\n\n"
        "Send me a video link, and I'll download it for you. 📲\n\n"
        "✨ **Features:**\n"
        "• Support for large files (up to 2GB)\n"
        "• High quality downloads\n"
        "• Fast processing\n\n"
        "📱 **Supported platforms:**\n"
        "• TikTok • Instagram • YouTube\n"
        "• Twitter/X • Facebook • And more!"
    )
    await update.message.reply_text(greeting, parse_mode='Markdown')

def get_best_formats(url: str):
    """Get the best available formats optimized for speed"""
    ydl_opts = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }
    
    formats = {
        'video': [],
        'audio': None,
        'title': 'Unknown'
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats['title'] = info.get('title', 'Unknown')[:50]  # Limit title length
            
            # Get video formats
            video_formats = []
            for f in info.get("formats", []):
                if (f.get("vcodec") != "none" and 
                    f.get("ext") in ["mp4", "webm", "mkv"]):
                    
                    height = f.get('height', 0)
                    width = f.get('width', 0)
                    resolution = f"{width}x{height}" if width and height else "Unknown"
                    filesize = f.get("filesize") or f.get("filesize_approx", 0)
                    
                    video_formats.append({
                        "format_id": f["format_id"],
                        "resolution": resolution,
                        "height": height,
                        "ext": f.get("ext", "mp4"),
                        "filesize": filesize,
                        "quality": f.get("quality", 0)
                    })
            
            # Sort by height (quality) and get best formats
            video_formats.sort(key=lambda x: x["height"], reverse=True)
            
            # Select best formats: 1080p, 720p, 480p, 360p, best available
            selected_heights = [1080, 720, 480, 360]
            for target_height in selected_heights:
                for fmt in video_formats:
                    if fmt["height"] == target_height:
                        formats['video'].append(fmt)
                        break
            
            # If no standard resolutions found, add the best one
            if not formats['video'] and video_formats:
                formats['video'].append(video_formats[0])
            
            # Limit to 4 video options max
            formats['video'] = formats['video'][:4]
            
            # Get best audio format
            for f in info.get("formats", []):
                if (f.get("acodec") != "none" and f.get("vcodec") == "none" and
                    f.get("ext") in ["m4a", "mp3", "webm", "ogg"]):
                    formats['audio'] = {
                        "format_id": f["format_id"],
                        "ext": f.get("ext", "m4a"),
                        "filesize": f.get("filesize") or f.get("filesize_approx", 0)
                    }
                    break
            
    except Exception as e:
        logger.error(f"Error extracting formats: {e}")
        return None
        
    return formats

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    # Check if URL contains common video site patterns
    video_patterns = [
        "tiktok.com", "instagram.com", "youtube.com", "youtu.be", 
        "twitter.com", "x.com", "facebook.com", "fb.watch",
        "reddit.com", "streamable.com", "vimeo.com", "dailymotion.com"
    ]
    
    if not any(pattern in url.lower() for pattern in video_patterns):
        await update.message.reply_text(
            "🚫 Please send a valid video link from supported platforms:\n"
            "TikTok, Instagram, YouTube, Twitter/X, Facebook, Reddit, etc."
        )
        return
    
    # Show quick processing message
    processing_msg = await update.message.reply_text("⚡ Processing... (This will be quick!)")
    
    try:
        start_time = time.time()
        formats = get_best_formats(url)
        process_time = time.time() - start_time
        
        if not formats or not formats['video']:
            await processing_msg.edit_text(
                "❌ Could not extract video information. Please check if:\n"
                "• The link is valid and public\n"
                "• The video is not private/restricted\n"
                "• The platform is supported"
            )
            return
        
        user_data[update.effective_user.id] = {
            "url": url, 
            "formats": formats,
            "processing_msg_id": processing_msg.message_id
        }

        buttons = []
        
        # Add video format buttons
        for fmt in formats['video']:
            size_text = ""
            if fmt["filesize"] and fmt["filesize"] > 0:
                size_mb = fmt["filesize"] / (1024 * 1024)
                if size_mb > 1024:
                    size_text = f" ({size_mb/1024:.1f}GB)"
                else:
                    size_text = f" ({size_mb:.0f}MB)"
            
            quality_text = f"📺 {fmt['height']}p" if fmt['height'] > 0 else f"📺 {fmt['resolution']}"
            button_text = f"{quality_text}{size_text}"
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"video_{fmt['format_id']}")])
        
        # Add audio option
        if formats['audio']:
            buttons.append([InlineKeyboardButton("🎵 Audio Only (Best Quality)", callback_data="audio_best")])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        
        title_preview = formats['title'][:30] + "..." if len(formats['title']) > 30 else formats['title']
        message_text = (
            f"🎬 **{title_preview}**\n\n"
            f"⚡ Analyzed in {process_time:.1f}s\n"
            f"📊 Choose your preferred quality:\n\n"
            f"💡 *Large files supported (up to 2GB)*"
        )
        
        await processing_msg.edit_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await processing_msg.edit_text(
            f"❌ Error processing video: {str(e)[:100]}\n\n"
            "Please try again or check if the link is valid."
        )

async def upload_with_pyrogram(file_path: str, chat_id: int, caption: str = "", is_video: bool = True):
    """Upload large files using Pyrogram client"""
    global pyrogram_client
    try:
        if not pyrogram_client or not pyrogram_client.is_connected:
            if not await init_pyrogram():
                return False
        
        if is_video:
            message = await pyrogram_client.send_video(
                chat_id=chat_id,
                video=file_path,
                caption=caption,
                supports_streaming=True
            )
        else:
            message = await pyrogram_client.send_audio(
                chat_id=chat_id,
                audio=file_path,
                caption=caption
            )
        
        return True
        
    except Exception as e:
        logger.error(f"Error uploading with Pyrogram: {e}")
        return False

async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_info = user_data.get(user_id)

    if not user_info:
        await query.edit_message_text("❌ Session expired. Please send the link again.")
        return

    url = user_info["url"]
    formats = user_info["formats"]
    choice = query.data

    try:
        # Create downloads directory
        os.makedirs("downloads", exist_ok=True)
        
        start_time = time.time()

        if choice == "audio_best":
            await query.edit_message_text("🎵 Downloading audio... ⚡")
            
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(title)s.%(ext)s",
                "quiet": True,
                "no_warnings": True,
                "postprocessors": [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',  # High quality
                }],
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'audio').replace('/', '_')
                
                # Find the downloaded file
                file_path = None
                for file in os.listdir("downloads"):
                    if file.endswith(".mp3") and any(word in file.lower() for word in title.lower().split()[:3]):
                        file_path = f"downloads/{file}"
                        break
                
                if not file_path:
                    # Fallback: find any mp3 file
                    for file in os.listdir("downloads"):
                        if file.endswith(".mp3"):
                            file_path = f"downloads/{file}"
                            break

            if not file_path or not os.path.exists(file_path):
                await query.edit_message_text("❌ Audio extraction failed.")
                return

            download_time = time.time() - start_time
            file_size = os.path.getsize(file_path) / (1024 * 1024)
            
            await query.edit_message_text(f"📤 Uploading audio... ({file_size:.1f}MB)")
            
            # Use appropriate upload method based on file size
            chat_id = query.message.chat_id
            caption = f"🎵 {title}\n⚡ Downloaded in {download_time:.1f}s"
            
            if file_size > 45:  # Use Pyrogram for large files
                upload_success = await upload_with_pyrogram(file_path, chat_id, caption, is_video=False)
                if not upload_success:
                    await query.edit_message_text("❌ Upload failed. File might be too large or corrupted.")
                    return
            else:  # Use regular bot API for smaller files
                with open(file_path, "rb") as file:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=file,
                        caption=caption
                    )

        elif choice.startswith("video_"):
            format_id = choice.replace("video_", "")
            await query.edit_message_text("📹 Downloading video... ⚡")
            
            ydl_opts = {
                "format": format_id,
                "outtmpl": "downloads/%(title)s.%(ext)s",
                "quiet": True,
                "no_warnings": True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
                title = info.get('title', 'video').replace('/', '_')

            download_time = time.time() - start_time
            file_size = os.path.getsize(file_path) / (1024 * 1024)
            
            await query.edit_message_text(f"📤 Uploading video... ({file_size:.1f}MB)")
            
            # Use appropriate upload method
            chat_id = query.message.chat_id
            caption = f"🎬 {title}\n⚡ Downloaded in {download_time:.1f}s"
            
            if file_size > 45:  # Use Pyrogram for large files
                upload_success = await upload_with_pyrogram(file_path, chat_id, caption, is_video=True)
                if not upload_success:
                    await query.edit_message_text("❌ Upload failed. Please try a different quality.")
                    return
            else:  # Use regular bot API
                with open(file_path, "rb") as file:
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=file,
                        caption=caption
                    )

        total_time = time.time() - start_time
        await query.edit_message_text(f"✅ Completed in {total_time:.1f}s! 🚀")

    except Exception as e:
        logger.error(f"Error in download_handler: {e}")
        await query.edit_message_text(f"❌ Download failed: {str(e)[:100]}")
    
    finally:
        # Clean up
        if user_id in user_data:
            del user_data[user_id]
        
        # Remove downloaded files
        try:
            for file in os.listdir("downloads"):
                file_path = f"downloads/{file}"
                if os.path.exists(file_path):
                    os.remove(file_path)
        except:
            pass

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enhanced error handler"""
    logger.error("Exception while handling an update:", exc_info=context.error)

# ========= Main =========

def main():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set!")
        return
    
    # Create application
    application = Application.builder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(download_handler))
    application.add_error_handler(error_handler)

    logger.info("🚀 Bot is starting with enhanced features...")
    
    # Check environment and run accordingly
    if os.getenv("KOYEB_APP") or os.getenv("PORT"):
        # Production webhook mode
        PORT = int(os.environ.get('PORT', 8000))
        
        # For Koyeb, the URL format is: https://app-name.koyeb.app
        app_name = os.getenv('KOYEB_APP_NAME', 'your-app')
        WEBHOOK_URL = f"https://{app_name}.koyeb.app/"
        
        logger.info(f"Starting webhook mode on port {PORT}")
        logger.info(f"Webhook URL: {WEBHOOK_URL}")
        
        # Initialize Pyrogram in a separate task
        async def init_and_run():
            await init_pyrogram()
            
        # Run webhook
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL,
            url_path="",
            close_loop=False
        )
        
    else:
        # Development polling mode
        logger.info("Starting polling mode for development...")
        
        # Initialize Pyrogram and run polling
        async def run_polling():
            await init_pyrogram()
            await application.initialize()
            await application.start()
            await application.updater.start_polling()
            
            try:
                # Keep running
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Stopping bot...")
            finally:
                await application.updater.stop()
                await application.stop()
                await application.shutdown()
                if pyrogram_client and pyrogram_client.is_connected:
                    await pyrogram_client.stop()
        
        # Run with proper event loop handling
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, create a task
                asyncio.create_task(run_polling())
            else:
                # Start new loop
                asyncio.run(run_polling())
        except RuntimeError:
            # Fallback for environments with existing event loops
            import nest_asyncio
            nest_asyncio.apply()
            asyncio.run(run_polling())

if __name__ == "__main__":
    main()
