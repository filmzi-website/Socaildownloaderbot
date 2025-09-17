import os
import asyncio
import logging
from urllib.parse import urlparse
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from pyrogram import Client
import aiohttp
import json

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

# Initialize bot
bot = Bot(token=TOKEN)

# Dictionary to keep track of user data
user_data = {}

# Create downloads directory if it doesn't exist
os.makedirs('downloads', exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name
    welcome_image_url = "https://ar-hosting.pages.dev/1753585583429.jpg"
    
    welcome_message = f"""**ʜᴇʏ {user_first_name}, ɢᴏᴏᴅ ᴇᴠᴇɴɪɴɢ 🌘

ɪ ᴀᴍ ᴛʜᴇ ᴍᴏsᴛ ᴘᴏᴡᴇʀғᴜʟ ᴀᴜᴛᴏ ғɪʟᴛᴇʀ ʙᴏᴛ ᴡɪᴛʜ ᴘʀᴇᴍɪᴜᴍ ғᴇᴀᴛᴜʀᴇs 🚀

✨ **ᴡʜᴀᴛ ɪ ᴄᴀɴ ᴅᴏ:**
🎬 ᴛɪᴋᴛᴏᴋ ᴠɪᴅᴇᴏ ᴅᴏᴡɴʟᴏᴀᴅs (ʜᴅ ǫᴜᴀʟɪᴛʏ)
📸 ɪɴsᴛᴀɢʀᴀᴍ ᴘᴏsᴛs & sᴛᴏʀɪᴇs
🎵 ᴀᴜᴅɪᴏ ᴇxᴛʀᴀᴄᴛɪᴏɴ (ᴍᴘ3)
🔍 ᴀᴜᴛᴏ ғɪʟᴛᴇʀ sᴇᴀʀᴄʜ

**sɪᴍᴘʟʏ sᴇɴᴅ ᴀɴʏ ᴜʀʟ ᴀɴᴅ ɪ'ʟʟ ʜᴀɴᴅʟᴇ ᴛʜᴇ ʀᴇsᴛ! ⚡**

ᴍᴀᴅᴇ ᴡɪᴛʜ ❤️ ʙʏ [ᴢᴇʀᴏ ᴄʀᴇᴀᴛɪᴏɴs](https://t.me/zerocreations)**"""
    
    # Create inline keyboard
    keyboard = [
        [InlineKeyboardButton("🚀 ɢᴇᴛ sᴛᴀʀᴛᴇᴅ", callback_data="get_started")],
        [InlineKeyboardButton("📞 sᴜᴘᴘᴏʀᴛ", url="https://t.me/zerocreations")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # Send photo with caption
        await update.message.reply_photo(
            photo=welcome_image_url,
            caption=welcome_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        # If image fails, send text message
        await update.message.reply_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

def is_supported_url(url: str) -> str:
    """Check if URL is from supported platforms"""
    if "tiktok.com" in url or "vm.tiktok.com" in url:
        return "tiktok"
    elif "instagram.com" in url:
        return "instagram"
    return None

def get_high_quality_formats(url: str, platform: str):
    """Get available high-quality formats for the URL"""
    if platform == "tiktok":
        ydl_opts = {
            'format': 'best[height<=1080]',
            'noplaylist': True,
            'quiet': True,
        }
    elif platform == "instagram":
        ydl_opts = {
            'format': 'best',
            'noplaylist': True,
            'quiet': True,
        }
    else:
        return []

    formats = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get('formats'):
                for f in info['formats']:
                    if f.get('vcodec') != 'none' and f.get('height'):
                        formats.append({
                            'format_id': f['format_id'],
                            'resolution': f"{f.get('height')}p",
                            'ext': f.get('ext', 'mp4')
                        })
                # Sort by quality (highest first)
                formats.sort(key=lambda x: int(x['resolution'].replace('p', '')), reverse=True)
            
            # Always include audio option
            formats.append({
                'format_id': 'audio',
                'resolution': 'Audio Only',
                'ext': 'mp3'
            })
    except Exception as e:
        logger.error(f"Error extracting formats: {e}")
    
    return formats

async def handle_get_started(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle get started button"""
    query = update.callback_query
    await query.answer()
    
    help_text = """🎯 **ʜᴏᴡ ᴛᴏ ᴜsᴇ:**

1️⃣ ᴄᴏᴘʏ ᴀɴʏ ᴛɪᴋᴛᴏᴋ ᴏʀ ɪɴsᴛᴀɢʀᴀᴍ ʟɪɴᴋ
2️⃣ ᴘᴀsᴛᴇ ɪᴛ ʜᴇʀᴇ
3️⃣ ᴄʜᴏᴏsᴇ ʏᴏᴜʀ ᴘʀᴇғᴇʀʀᴇᴅ ǫᴜᴀʟɪᴛʏ
4️⃣ ᴅᴏᴡɴʟᴏᴀᴅ & ᴇɴᴊᴏʏ! 🎉

**sᴜᴘᴘᴏʀᴛᴇᴅ ᴘʟᴀᴛғᴏʀᴍs:**
• ᴛɪᴋᴛᴏᴋ (ʜᴅ ǫᴜᴀʟɪᴛʏ)
• ɪɴsᴛᴀɢʀᴀᴍ (ᴘᴏsᴛs & sᴛᴏʀɪᴇs)"""
    
    await query.edit_message_caption(
        caption=help_text,
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    url = update.message.text.strip()
    platform = is_supported_url(url)
    
    if platform:
        # Show processing message
        processing_msg = await update.message.reply_text(
            "🔄 **ᴘʀᴏᴄᴇssɪɴɢ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ...**",
            parse_mode='Markdown'
        )
        
        try:
            formats = get_high_quality_formats(url, platform)
            user_data[update.effective_user.id] = {
                'url': url,
                'platform': platform,
                'formats': formats
            }

            if formats:
                # Create quality selection buttons
                buttons = []
                for f in formats[:5]:  # Limit to top 5 qualities
                    if f['format_id'] == 'audio':
                        buttons.append([InlineKeyboardButton(f"🎵 {f['resolution']}", callback_data=f"download_{f['format_id']}")])
                    else:
                        buttons.append([InlineKeyboardButton(f"📹 {f['resolution']} {f['ext'].upper()}", callback_data=f"download_{f['format_id']}")])
                
                reply_markup = InlineKeyboardMarkup(buttons)
                
                platform_emoji = "🎬" if platform == "tiktok" else "📸"
                await processing_msg.edit_text(
                    f"{platform_emoji} **sᴇʟᴇᴄᴛ ǫᴜᴀʟɪᴛʏ ғᴏʀ {platform.upper()} ᴅᴏᴡɴʟᴏᴀᴅ:**",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await processing_msg.edit_text(
                    "❌ **sᴏʀʀʏ, ɴᴏ ғᴏʀᴍᴀᴛs ᴀᴠᴀɪʟᴀʙʟᴇ ғᴏʀ ᴛʜɪs ʟɪɴᴋ**",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error processing URL: {e}")
            await processing_msg.edit_text(
                "❌ **ᴇʀʀᴏʀ ᴘʀᴏᴄᴇssɪɴɢ ᴛʜᴇ ʟɪɴᴋ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.**",
                parse_mode='Markdown'
            )
    else:
        # Auto-filter search functionality
        search_query = url
        await handle_auto_filter_search(update, context, search_query)

async def handle_auto_filter_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Handle auto-filter search functionality"""
    search_msg = await update.message.reply_text(
        f"🔍 **sᴇᴀʀᴄʜɪɴɢ ғᴏʀ:** `{query}`\n\n⚡ **ᴀᴜᴛᴏ ғɪʟᴛᴇʀ ʀᴇsᴜʟᴛs:**",
        parse_mode='Markdown'
    )
    
    # Simulate search results (replace with your actual search logic)
    await asyncio.sleep(1)
    
    # Create sample results buttons
    buttons = [
        [InlineKeyboardButton(f"📁 {query} - Result 1", callback_data="search_result_1")],
        [InlineKeyboardButton(f"📁 {query} - Result 2", callback_data="search_result_2")],
        [InlineKeyboardButton(f"📁 {query} - Result 3", callback_data="search_result_3")],
        [InlineKeyboardButton("🔄 ᴍᴏʀᴇ ʀᴇsᴜʟᴛs", callback_data="more_results")]
    ]
    
    reply_markup = InlineKeyboardMarkup(buttons)
    
    await search_msg.edit_text(
        f"🎯 **ғᴏᴜɴᴅ ʀᴇsᴜʟᴛs ғᴏʀ:** `{query}`\n\n**ᴄʟɪᴄᴋ ᴏɴ ᴀɴʏ ʀᴇsᴜʟᴛ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ:**",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def download_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle content download"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "get_started":
        await handle_get_started(update, context)
        return
    
    if query.data.startswith("search_result_"):
        await query.edit_message_text(
            "📁 **ᴀᴜᴛᴏ ғɪʟᴛᴇʀ ғᴇᴀᴛᴜʀᴇ ᴄᴏᴍɪɴɢ sᴏᴏɴ!**\n\nғᴏʀ ɴᴏᴡ, sᴇɴᴅ ᴛɪᴋᴛᴏᴋ ᴏʀ ɪɴsᴛᴀɢʀᴀᴍ ʟɪɴᴋs ғᴏʀ ᴅᴏᴡɴʟᴏᴀᴅ! 🚀",
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
            "❌ **sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ. ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ʟɪɴᴋ ᴀɢᴀɪɴ.**",
            parse_mode='Markdown'
        )
        return

    url = user_info['url']
    platform = user_info['platform']
    
    await query.edit_message_text(
        "⏳ **ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ...**\n\n🚀 **ʜɪɢʜ ǫᴜᴀʟɪᴛʏ ᴘʀᴏᴄᴇssɪɴɢ ɪɴ ᴘʀᴏɢʀᴇss**",
        parse_mode='Markdown'
    )

    try:
        if format_id == 'audio':
            # Download audio
            ydl_opts = {
                'format': 'bestaudio/best',
                'extractaudio': True,
                'audioformat': 'mp3',
                'audioquality': 1,
                'outtmpl': 'downloads/%(title)s.%(ext)s',
                'quiet': True,
            }
        else:
            # Download video
            ydl_opts = {
                'format': format_id,
                'outtmpl': 'downloads/%(title)s.%(ext)s',
                'quiet': True,
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            title = info.get('title', 'Downloaded Content')

        # Upload to Telegram
        await query.edit_message_text(
            "📤 **ᴜᴘʟᴏᴀᴅɪɴɢ ʏᴏᴜʀ ᴄᴏɴᴛᴇɴᴛ...**",
            parse_mode='Markdown'
        )

        file_size = os.path.getsize(file_path)
        if file_size > 50 * 1024 * 1024:  # 50MB limit
            await query.edit_message_text(
                "❌ **ғɪʟᴇ ᴛᴏᴏ ʟᴀʀɢᴇ (>50ᴍʙ). ᴄᴏᴍɪɴɢ sᴏᴏɴ: ᴄʟᴏᴜᴅ ᴜᴘʟᴏᴀᴅ!**",
                parse_mode='Markdown'
            )
        else:
            # Send file based on type
            with open(file_path, 'rb') as file:
                if format_id == 'audio':
                    await query.message.reply_audio(
                        file, 
                        title=title,
                        caption=f"🎵 **{title}**\n\n✨ ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ ᴡɪᴛʜ ❤️ ʙʏ [ᴢᴇʀᴏ ᴄʀᴇᴀᴛɪᴏɴs](https://t.me/zerocreations)",
                        parse_mode='Markdown'
                    )
                else:
                    await query.message.reply_video(
                        file, 
                        caption=f"🎬 **{title}**\n\n✨ ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ ᴡɪᴛʜ ❤️ ʙʏ [ᴢᴇʀᴏ ᴄʀᴇᴀᴛɪᴏɴs](https://t.me/zerocreations)",
                        parse_mode='Markdown'
                    )
            
            await query.edit_message_text(
                f"✅ **sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ!**\n\n🎯 **{title}**\n\n🚀 sᴇɴᴅ ᴀɴᴏᴛʜᴇʀ ʟɪɴᴋ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ!",
                parse_mode='Markdown'
            )

        # Clean up
        if os.path.exists(file_path):
            os.remove(file_path)
        if user_id in user_data:
            del user_data[user_id]
            
    except Exception as e:
        logger.error(f"Download error: {e}")
        await query.edit_message_text(
            "❌ **ᴅᴏᴡɴʟᴏᴀᴅ ғᴀɪʟᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ᴏʀ ᴄᴏɴᴛᴀᴄᴛ sᴜᴘᴘᴏʀᴛ.**",
            parse_mode='Markdown'
        )

async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Health check endpoint"""
    await update.message.reply_text(
        "✅ **ʙᴏᴛ ɪs ʜᴇᴀʟᴛʜʏ ᴀɴᴅ ʀᴜɴɴɪɴɢ!**\n\n🚀 **sᴛᴀᴛᴜs:** ᴀᴄᴛɪᴠᴇ\n📡 **ᴘᴏʀᴛ:** 8000\n💾 **ᴀᴄᴛɪᴠᴇ sᴇssɪᴏɴs:** " + str(len(user_data)),
        parse_mode='Markdown'
    )

def main():
    """Main function to run the bot"""
    logger.info("Starting Professional TikTok Instagram Downloader Bot...")
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("health", health_check))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(download_content))
    
    logger.info(f"Bot is running on port {PORT}")
    
    # Run the bot with webhook for production
    # For development, use run_polling()
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            timeout=30
        )
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")

if __name__ == '__main__':
    main()
