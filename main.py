import os
import asyncio
import logging
import re
from urllib.parse import urlparse
import yt_dlp
import nest_asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from pyrogram import Client
import json

# Enable nested asyncio for compatibility
nest_asyncio.apply()

# Bot Configuration
TOKEN = '8373569170:AAGLJ00dxy8kQQGoWqSUIVlt2v0yT1Uu4SY'  # Add your bot token here
API_ID = 20288994
API_HASH = "d702614912f1ad370a0d18786002adbf"
PORT = 8000

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Dictionary to keep track of user data
user_data = {}

# Create downloads directory
os.makedirs('downloads', exist_ok=True)

# Auto-filter database (mock data for demo)
movies_db = {
    "avengers": ["Avengers Endgame 2019", "Avengers Infinity War 2018", "The Avengers 2012"],
    "spider": ["Spider-Man No Way Home 2021", "Spider-Man Far From Home 2019", "Spider-Man Homecoming 2017"],
    "batman": ["The Batman 2022", "Batman Begins 2005", "The Dark Knight 2008"],
    "action": ["John Wick 2014", "Fast Five 2011", "Mission Impossible 2018"],
    "comedy": ["The Hangover 2009", "Superbad 2007", "Pineapple Express 2008"]
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command with compact welcome message"""
    user_first_name = update.effective_user.first_name
    welcome_image_url = "https://ar-hosting.pages.dev/1753585583429.jpg"
    
    welcome_message = f"""**ʜᴇʏ {user_first_name}, ɢᴏᴏᴅ ᴇᴠᴇɴɪɴɢ 🌘

ɪ ᴀᴍ ᴛʜᴇ ᴍᴏsᴛ ᴘᴏᴡᴇʀғᴜʟ ᴀᴜᴛᴏ ғɪʟᴛᴇʀ ʙᴏᴛ

🎬 TikTok Videos, Posts, Stories
📸 Instagram Videos, Reels, Posts, Stories  
🎵 Audio Downloads (MP3)
🔍 Auto Filter Search

Just send URL or search query!

Made by [Zero Creations](https://t.me/zerocreations)**"""
    
    keyboard = [
        [InlineKeyboardButton("🚀 Start", callback_data="get_started")],
        [InlineKeyboardButton("📞 Support", url="https://t.me/zerocreations")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.message.reply_photo(
            photo=welcome_image_url,
            caption=welcome_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception:
        await update.message.reply_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

def is_supported_url(url: str) -> str:
    """Check if URL is from supported platforms"""
    url = url.lower()
    if any(x in url for x in ["tiktok.com", "vm.tiktok.com", "vt.tiktok.com"]):
        return "tiktok"
    elif any(x in url for x in ["instagram.com", "instagr.am"]):
        return "instagram"
    return None

def get_yt_dlp_extractors():
    """Get updated yt-dlp options for TikTok and Instagram"""
    return {
        'tiktok': {
            'format': 'best[height<=1080]/best',
            'noplaylist': True,
            'extract_flat': False,
            'writethumbnail': False,
            'writeinfojson': False,
            'quiet': True,
            'no_warnings': True,
            'extractaudio': False,
            'outtmpl': 'downloads/%(title)s.%(ext)s',
        },
        'instagram': {
            'format': 'best[height<=1080]/best',
            'noplaylist': True,
            'extract_flat': False,
            'writethumbnail': False,
            'writeinfojson': False,
            'quiet': True,
            'no_warnings': True,
            'extractaudio': False,
            'outtmpl': 'downloads/%(title)s.%(ext)s',
        }
    }

async def get_video_info(url: str, platform: str):
    """Extract video information and available formats"""
    ydl_opts = get_yt_dlp_extractors()[platform]
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info without downloading
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return None, []
                
            # Get available formats
            formats = []
            
            # Add video formats
            if info.get('formats'):
                video_formats = [f for f in info['formats'] if f.get('vcodec') != 'none']
                if video_formats:
                    # Get best quality
                    best_format = max(video_formats, key=lambda x: x.get('height', 0) or 0)
                    formats.append({
                        'format_id': 'best',
                        'resolution': f"{best_format.get('height', 'Unknown')}p",
                        'ext': best_format.get('ext', 'mp4'),
                        'type': 'video'
                    })
            
            # Always add audio option
            formats.append({
                'format_id': 'audio',
                'resolution': 'Audio Only',
                'ext': 'mp3',
                'type': 'audio'
            })
            
            return info, formats
            
    except Exception as e:
        logger.error(f"Error extracting info from {url}: {str(e)}")
        return None, []

async def handle_get_started(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle get started button"""
    query = update.callback_query
    await query.answer()
    
    help_text = """🎯 **How to use:**

📱 **For Downloads:**
• Send TikTok/Instagram URL
• Choose quality and download

🔍 **For Auto Filter:**
• Type movie/series name
• Get instant results

**Supported:**
• TikTok (Videos, Posts, Stories)
• Instagram (Videos, Reels, Posts, Stories)"""
    
    await query.edit_message_caption(
        caption=help_text,
        parse_mode='Markdown'
    )

def search_movies(query: str):
    """Search for movies in database"""
    query = query.lower()
    results = []
    
    for key, movies in movies_db.items():
        if query in key or any(query in movie.lower() for movie in movies):
            results.extend(movies)
    
    # Remove duplicates and limit results
    results = list(set(results))[:10]
    return results

async def handle_auto_filter_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Handle auto-filter search functionality"""
    search_msg = await update.message.reply_text(
        f"🔍 **Searching for:** `{query}`",
        parse_mode='Markdown'
    )
    
    # Search in database
    results = search_movies(query)
    
    if results:
        buttons = []
        for i, movie in enumerate(results[:8]):  # Limit to 8 results
            buttons.append([InlineKeyboardButton(f"📁 {movie}", callback_data=f"movie_{i}")])
        
        if len(results) > 8:
            buttons.append([InlineKeyboardButton("🔄 More Results", callback_data="more_results")])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        
        await search_msg.edit_text(
            f"🎯 **Found {len(results)} results for:** `{query}`\n\n**Select any movie to get download links:**",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await search_msg.edit_text(
            f"❌ **No results found for:** `{query}`\n\nTry searching with different keywords like:\n• Movie name\n• Actor name\n• Genre (action, comedy, etc.)",
            parse_mode='Markdown'
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    text = update.message.text.strip()
    platform = is_supported_url(text)
    
    if platform:
        # Handle URL downloads
        processing_msg = await update.message.reply_text(
            "🔄 **Processing your request...**",
            parse_mode='Markdown'
        )
        
        try:
            info, formats = await get_video_info(text, platform)
            
            if info and formats:
                user_data[update.effective_user.id] = {
                    'url': text,
                    'platform': platform,
                    'info': info,
                    'formats': formats
                }
                
                # Create quality selection buttons
                buttons = []
                for f in formats:
                    if f['type'] == 'audio':
                        buttons.append([InlineKeyboardButton(f"🎵 {f['resolution']}", callback_data=f"download_{f['format_id']}")])
                    else:
                        buttons.append([InlineKeyboardButton(f"📹 {f['resolution']} {f['ext'].upper()}", callback_data=f"download_{f['format_id']}")])
                
                reply_markup = InlineKeyboardMarkup(buttons)
                
                platform_emoji = "🎬" if platform == "tiktok" else "📸"
                title = info.get('title', 'Unknown')[:50] + "..." if len(info.get('title', '')) > 50 else info.get('title', 'Unknown')
                
                await processing_msg.edit_text(
                    f"{platform_emoji} **{title}**\n\n**Select quality:**",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await processing_msg.edit_text(
                    "❌ **Unable to process this link**\n\nPlease try:\n• Check if link is valid\n• Try a different link\n• Contact support",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error processing URL: {e}")
            await processing_msg.edit_text(
                "❌ **Error processing link**\n\nThis might be due to:\n• Private/restricted content\n• Network issues\n• Unsupported format",
                parse_mode='Markdown'
            )
    else:
        # Handle auto-filter search
        await handle_auto_filter_search(update, context, text)

async def download_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle content download"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "get_started":
        await handle_get_started(update, context)
        return
    
    if query.data.startswith("movie_"):
        movie_index = int(query.data.split("_")[1])
        keyboard = [
            [InlineKeyboardButton("📥 Download HD", callback_data="download_hd")],
            [InlineKeyboardButton("📥 Download 720p", callback_data="download_720p")],
            [InlineKeyboardButton("🔙 Back to Search", callback_data="back_search")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🎬 **Movie Selected**\n\n📁 Quality options available:\n\n**Select preferred quality:**",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    if query.data in ["download_hd", "download_720p", "more_results", "back_search"]:
        await query.edit_message_text(
            "🚧 **Auto Filter Downloads Coming Soon!**\n\nFor now, send TikTok or Instagram links for instant downloads! 🚀",
            parse_mode='Markdown'
        )
        return
    
    if not query.data.startswith("download_"):
        return
        
    format_id = query.data.replace("download_", "")
    user_id = query.from_user.id
    user_info = user_data.get(user_id)

    if not user_info:
        await query.edit_message_text(
            "❌ **Session expired**\n\nPlease send the link again.",
            parse_mode='Markdown'
        )
        return

    url = user_info['url']
    platform = user_info['platform']
    info = user_info['info']
    
    await query.edit_message_text(
        "⏳ **Downloading...**\n\n🚀 **High quality processing**",
        parse_mode='Markdown'
    )

    try:
        ydl_opts = get_yt_dlp_extractors()[platform].copy()
        
        if format_id == 'audio':
            # Download audio
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            # Download video with best quality
            ydl_opts.update({
                'format': 'best[height<=1080]/best',
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find downloaded file
        title = info.get('title', 'download').replace('/', '_').replace('\\', '_')
        possible_extensions = ['mp4', 'webm', 'mp3', 'wav', 'm4a'] if format_id == 'audio' else ['mp4', 'webm', 'avi', 'mkv']
        
        file_path = None
        for ext in possible_extensions:
            test_path = f"downloads/{title}.{ext}"
            if os.path.exists(test_path):
                file_path = test_path
                break
        
        # If exact match not found, find any file in downloads folder
        if not file_path:
            downloads = [f for f in os.listdir('downloads') if f.endswith(tuple(possible_extensions))]
            if downloads:
                # Get the most recently created file
                downloads.sort(key=lambda x: os.path.getctime(f"downloads/{x}"), reverse=True)
                file_path = f"downloads/{downloads[0]}"

        if file_path and os.path.exists(file_path):
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > 50 * 1024 * 1024:  # 50MB limit
                await query.edit_message_text(
                    "❌ **File too large (>50MB)**\n\nTry downloading audio version or contact support for large files.",
                    parse_mode='Markdown'
                )
            else:
                # Upload to Telegram
                await query.edit_message_text(
                    "📤 **Uploading...**",
                    parse_mode='Markdown'
                )

                with open(file_path, 'rb') as file:
                    caption = f"✨ **Downloaded from {platform.upper()}**\n\n🎯 **{info.get('title', 'Unknown')}**\n\n💝 By [Zero Creations](https://t.me/zerocreations)"
                    
                    if format_id == 'audio':
                        await query.message.reply_audio(
                            file, 
                            caption=caption,
                            parse_mode='Markdown'
                        )
                    else:
                        await query.message.reply_video(
                            file, 
                            caption=caption,
                            parse_mode='Markdown'
                        )
                
                await query.edit_message_text(
                    f"✅ **Successfully downloaded!**\n\n🚀 Send another link to continue!",
                    parse_mode='Markdown'
                )

            # Clean up
            try:
                os.remove(file_path)
            except:
                pass
        else:
            await query.edit_message_text(
                "❌ **Download failed**\n\nFile could not be processed. Please try again or contact support.",
                parse_mode='Markdown'
            )

        # Clean up user data
        if user_id in user_data:
            del user_data[user_id]
            
    except Exception as e:
        logger.error(f"Download error: {e}")
        await query.edit_message_text(
            "❌ **Download failed**\n\nPlease try again or contact support if the issue persists.",
            parse_mode='Markdown'
        )

async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Health check endpoint"""
    await update.message.reply_text(
        f"✅ **Bot Status: Healthy**\n\n🚀 **Port:** {PORT}\n📊 **Active Sessions:** {len(user_data)}\n🔧 **Version:** 2.0",
        parse_mode='Markdown'
    )

def main():
    """Main function to run the bot"""
    if not TOKEN:
        logger.error("Please add your bot token!")
        return
        
    logger.info("🚀 Starting TikTok Instagram Downloader Bot...")
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("health", health_check))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(download_content))
    
    logger.info(f"✅ Bot is running on port {PORT}")
    logger.info("🎬 TikTok and Instagram downloads ready!")
    logger.info("🔍 Auto-filter search enabled!")
    
    # Run the bot
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            timeout=30,
            pool_timeout=30
        )
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Bot crashed: {e}")

if __name__ == '__main__':
    main()
