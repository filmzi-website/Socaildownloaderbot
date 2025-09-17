import os
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Your bot token
TOKEN = '8373569170:AAGLJ00dxy8kQQGoWqSUIVlt2v0yT1Uu4SY'

# Initialize bot
bot = Bot(token=TOKEN)

# Dictionary to keep track of user-selected URLs and formats
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name
    greeting = f"👋 Hello, {user_first_name}! 🎉\n\nSend me a link from YouTube, Instagram, TikTok, Facebook, or Pinterest, and I'll download it for you. 📲"
    await update.message.reply_text(greeting)

def get_available_formats(url: str):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',  # Prefer best video + best audio
        'noplaylist': True,  # Do not download playlists
    }
    formats = []

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        for f in info['formats']:
            # Filter video formats only
            if f.get('vcodec') != 'none':
                formats.append({
                    'format_id': f['format_id'],
                    'resolution': f.get('resolution', 'Unknown')
                })
    return formats

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if any(platform in url for platform in ["youtube.com", "instagram.com", "tiktok.com", "facebook.com", "pinterest.com"]):
        formats = get_available_formats(url)
        user_data[update.effective_user.id] = url

        if formats:
            buttons = [
                [InlineKeyboardButton(f"🎬 {f['resolution']}", callback_data=f"{f['format_id']}")]
                for f in formats
            ]
            buttons.append([InlineKeyboardButton("🎧 Download as MP3", callback_data="mp3")])
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text("Select a resolution or download as MP3:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("⚠️ No video formats available for this link.")
    else:
        await update.message.reply_text("🚫 Please send a valid link from YouTube, Instagram, TikTok, Facebook, or Pinterest.")

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    format_id = query.data
    user_id = query.from_user.id
    url = user_data.get(user_id)

    if url and format_id != 'mp3':
        await query.edit_message_text("⏳ Downloading... Please wait a moment!")

        # Download video with selected format
        ydl_opts = {
            'format': format_id,
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        # Send video to Telegram
        await query.edit_message_text("📤 Uploading your video...")
        with open(file_path, 'rb') as file:
            await query.message.reply_video(file)
        os.remove(file_path)
        del user_data[user_id]
    elif format_id == 'mp3':
        await download_mp3(update, context)
    else:
        await query.edit_message_text("❌ Error: Link not found. Please try sending it again.")

async def download_mp3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    url = user_data.get(user_id)

    if url:
        await query.edit_message_text("⏳ Converting to MP3... Please wait a moment!")

        # Download audio and convert to MP3
        ydl_opts = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioquality': 1,
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        # Send MP3 file to Telegram
        await query.edit_message_text("📤 Uploading your MP3 file...")
        with open(file_path, 'rb') as file:
            await query.message.reply_audio(file)
        os.remove(file_path)
        del user_data[user_id]
    else:
        await query.edit_message_text("❌ Error: Link not found. Please try sending it again.")

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(download_video))
    application.add_handler(CallbackQueryHandler(download_mp3, pattern='^mp3$'))

    application.run_polling()

if __name__ == '__main__':
    main()
