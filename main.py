import os
import yt_dlp
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ===============================
# Environment Variables (set in Koyeb dashboard)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# ===============================

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global user data storage (in production, use a database)
user_data = {}

# ========= Telegram Bot Handlers =========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name
    greeting = (
        f"👋 Hello, {user_first_name}!\n\n"
        "Send me a TikTok or Instagram link, and I'll download it for you. 📲\n\n"
        "Supported platforms:\n"
        "• TikTok\n"
        "• Instagram (Reels/Posts)\n"
        "• YouTube\n"
        "• Twitter/X"
    )
    await update.message.reply_text(greeting)

def get_available_formats(url: str):
    """Extract available video formats from the URL"""
    ydl_opts = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }
    formats = []
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Get video formats
            for f in info.get("formats", []):
                if (f.get("vcodec") != "none" and 
                    f.get("acodec") != "none" and 
                    f.get("ext") in ["mp4", "webm"]):
                    
                    resolution = f.get("resolution") or f"{f.get('width', '?')}x{f.get('height', '?')}"
                    filesize = f.get("filesize") or f.get("filesize_approx", 0)
                    
                    # Skip if file is too large (Telegram limit is 50MB for bots)
                    if filesize and filesize > 45 * 1024 * 1024:  # 45MB safety margin
                        continue
                        
                    formats.append({
                        "format_id": f["format_id"],
                        "resolution": resolution,
                        "ext": f.get("ext", "mp4"),
                        "filesize": filesize
                    })
            
            # Sort by quality (resolution)
            formats.sort(key=lambda x: int(x["resolution"].split("x")[1]) if "x" in x["resolution"] else 0, reverse=True)
            
            # Limit to top 5 formats to avoid too many buttons
            return formats[:5]
            
    except Exception as e:
        logger.error(f"Error extracting formats: {e}")
        return []

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    # Check if URL is from supported platforms
    supported_sites = [
        "tiktok.com", "instagram.com", "youtube.com", "youtu.be", 
        "twitter.com", "x.com", "facebook.com", "fb.watch"
    ]
    
    if not any(site in url.lower() for site in supported_sites):
        await update.message.reply_text(
            "🚫 Please send a valid link from:\n"
            "• TikTok\n• Instagram\n• YouTube\n• Twitter/X\n• Facebook"
        )
        return
    
    # Show processing message
    processing_msg = await update.message.reply_text("🔍 Analyzing video...")
    
    try:
        formats = get_available_formats(url)
        user_data[update.effective_user.id] = {"url": url, "processing_msg_id": processing_msg.message_id}

        if formats:
            buttons = []
            
            # Add video format buttons
            for f in formats:
                size_text = ""
                if f["filesize"]:
                    size_mb = f["filesize"] / (1024 * 1024)
                    size_text = f" ({size_mb:.1f}MB)"
                
                button_text = f"🎬 {f['resolution']}{size_text}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=f"video_{f['format_id']}")])
            
            # Add audio option
            buttons.append([InlineKeyboardButton("🎧 Audio Only (MP3)", callback_data="audio_mp3")])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await processing_msg.edit_text("📋 Choose download option:", reply_markup=reply_markup)
        else:
            await processing_msg.edit_text("⚠️ No suitable formats found or video is too large (>45MB).")
            
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await processing_msg.edit_text("❌ Error analyzing video. Please try again or check if the link is valid.")

async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_info = user_data.get(user_id)

    if not user_info:
        await query.edit_message_text("❌ Error: Session expired. Please send the link again.")
        return

    url = user_info["url"]
    choice = query.data

    try:
        # Create downloads directory if it doesn't exist
        os.makedirs("downloads", exist_ok=True)

        if choice.startswith("audio_"):
            await query.edit_message_text("⏳ Extracting audio...")
            
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(title)s.%(ext)s",
                "quiet": True,
                "no_warnings": True,
                "postprocessors": [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'audio')
                # yt-dlp changes extension to mp3 after postprocessing
                file_path = f"downloads/{title}.mp3"
                
                # Find the actual file (yt-dlp might change filename)
                for file in os.listdir("downloads"):
                    if file.endswith(".mp3") and title.replace("/", "_") in file:
                        file_path = f"downloads/{file}"
                        break

            await query.edit_message_text("📤 Uploading audio...")
            
            # Check file size
            if os.path.getsize(file_path) > 45 * 1024 * 1024:
                await query.edit_message_text("❌ Audio file too large for Telegram (>45MB)")
                os.remove(file_path)
                return
            
            with open(file_path, "rb") as file:
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=file,
                    title=title
                )
            
            os.remove(file_path)

        elif choice.startswith("video_"):
            format_id = choice.replace("video_", "")
            await query.edit_message_text("⏳ Downloading video...")
            
            ydl_opts = {
                "format": format_id,
                "outtmpl": "downloads/%(title)s.%(ext)s",
                "quiet": True,
                "no_warnings": True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
                title = info.get('title', 'video')

            await query.edit_message_text("📤 Uploading video...")
            
            # Check file size
            if os.path.getsize(file_path) > 45 * 1024 * 1024:
                await query.edit_message_text("❌ Video file too large for Telegram (>45MB)")
                os.remove(file_path)
                return
            
            with open(file_path, "rb") as file:
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=file,
                    caption=f"📹 {title}"
                )
            
            os.remove(file_path)

        await query.edit_message_text("✅ Download completed!")

    except Exception as e:
        logger.error(f"Error in download_handler: {e}")
        await query.edit_message_text(f"❌ Download failed: {str(e)}")
    
    finally:
        # Clean up user data
        if user_id in user_data:
            del user_data[user_id]
        
        # Clean up any remaining files
        try:
            for file in os.listdir("downloads"):
                os.remove(f"downloads/{file}")
        except:
            pass

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
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
    
    # Add error handler
    application.add_error_handler(error_handler)

    logger.info("🤖 Bot is starting...")
    
    # Use webhook for production (Koyeb), polling for development
    if os.getenv("KOYEB_APP"):
        # Production webhook mode
        PORT = int(os.environ.get('PORT', 8000))
        APP_NAME = os.getenv('KOYEB_APP_NAME')
        WEBHOOK_URL = f"https://{APP_NAME}.koyeb.app/"
        
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL,
            url_path="",
        )
    else:
        # Development polling mode
        logger.info("Running in polling mode for development...")
        application.run_polling()

if __name__ == "__main__":
    main()
