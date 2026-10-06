import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_IDS, ADMIN_USERNAME
from database import (
    AsyncSessionLocal, get_or_create_user, update_user_city,
    toggle_user_setting, Content, Reminder, ContentRequest
)
from categories import get_category_keyboard
from smart_conv import check_smart_reply
from ai_engine import get_ai_response
from search_engine import search_media
from reminder import reload_reminders
from ad_system import attach_ad_to_keyboard

UPLOAD_TITLE, UPLOAD_CATEGORY = range(2)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.first_name, user.last_name)

    keyboard = [
        [InlineKeyboardButton("🤖 AI Chat", callback_data="btn_ai_help"), InlineKeyboardButton("🎬 Content", callback_data="btn_content_help")],
        [InlineKeyboardButton("⏰ Reminder", callback_data="btn_reminder_menu"), InlineKeyboardButton("🕌 Prayer Time", callback_data="btn_prayer")],
        [InlineKeyboardButton("🌦️ Weather", callback_data="btn_weather"), InlineKeyboardButton("🔔 Notifications", callback_data="btn_notifications")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="btn_help")]
    ]
    reply_markup = attach_ad_to_keyboard(InlineKeyboardMarkup(keyboard))
    welcome_text = (
        f"👋 আসসালামু আলাইকুম, {user.first_name}!\n\n"
        f"আমি আপনার অল-ইন-ওয়ান AI অ্যাসিস্ট্যান্ট।\n"
        f"যেকোনো প্রশ্ন করুন কিংবা গান/ভিডিও/নাটক খুঁজতে নাম লিখুন।\n\n"
        f"নিচের মেনু থেকেও সুবিধা বেছে নিতে পারেন: 👇"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *বটের ব্যবহার নির্দেশিকা:*\n\n"
        "• যেকোনো কথা লিখলে সরাসরি মানুষের মতো উত্তর দেব।\n"
        "• ভিডিও বা নাটক পেতে লিখুন: যেমন `ব্যাচেলর পয়েন্ট ভিডিও দেও`\n"
        "• `/notifications` দিয়ে নোটিফিকেশন সেটিংস পরিবর্তন করুন।"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# --- মিডিয়া আপলোড (Admin Only) ---
async def media_upload_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return ConversationHandler.END

    message = update.message
    file_id = None
    media_type = None

    if message.video:
        file_id = message.video.file_id
        media_type = "video"
    elif message.audio:
        file_id = message.audio.file_id
        media_type = "audio"
    elif message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.document:
        file_id = message.document.file_id
        media_type = "document"

    if not file_id:
        return ConversationHandler.END

    context.user_data["upload_file_id"] = file_id
    context.user_data["upload_media_type"] = media_type

    await message.reply_text("🎬 এই কন্টেন্টের নাম কী? নাম লিখে পাঠান:")
    return UPLOAD_TITLE

async def media_title_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()
    context.user_data["upload_title"] = title

    keyboard = get_category_keyboard(page=0, callback_prefix="admin_cat")
    await update.message.reply_text(
        f"✅ কন্টেন্টের নাম: *{title}*\n\n📂 ক্যাটাগরি নির্বাচন করুন:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return UPLOAD_CATEGORY

async def category_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("admin_cat_page:"):
        page = int(data.split(":")[1])
        await query.edit_message_reply_markup(reply_markup=get_category_keyboard(page=page, callback_prefix="admin_cat"))
        return UPLOAD_CATEGORY

    if data.startswith("admin_cat:"):
        category = data.split(":")[1]
        file_id = context.user_data.get("upload_file_id")
        media_type = context.user_data.get("upload_media_type")
        title = context.user_data.get("upload_title")
        uploader_id = query.from_user.id

        async with AsyncSessionLocal() as session:
            new_content = Content(
                title=title,
                category=category,
                file_id=file_id,
                media_type=media_type,
                keywords=f"{title.lower()}, {category.lower()}",
                uploader_id=uploader_id
            )
            session.add(new_content)
            await session.commit()

        success_text = (
            "✅ *Content Successfully Added!*\n\n"
            f"🎬 *Name:* {title}\n"
            f"📂 *Category:* {category}\n"
            f"💾 *Database:* Saved Successfully"
        )
        await query.edit_message_text(success_text, parse_mode="Markdown")
        context.user_data.clear()
        return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ অপারেশন বাতিল করা হয়েছে।")
    return ConversationHandler.END

# --- প্রধান মেসেজ হ্যান্ডলার ---
async def handle_user_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type

    # গ্রুপ মেসেজ হ্যান্ডলিং
    if chat_type in ["group", "supergroup"]:
        bot_user = await context.bot.get_me()
        bot_username = bot_user.username
        if not (f"@{bot_username}" in text or (update.message.reply_to_message and update.message.reply_to_message.from_user.id == bot_user.id)):
            return
        text = text.replace(f"@{bot_username}", "").strip()

    # ১. দ্রুত রিপ্লাই চেক (Smart Conversation Engine)
    smart_reply = check_smart_reply(text)
    if smart_reply:
        await update.message.reply_text(smart_reply)
        return

    t_lower = text.lower()

    # ২. কন্টেন্ট সার্চ (দাও, দেও, দে, দেন, পাঠান, dao, deo, pathan সব ধরবে)
    ask_words = ["দাও", "দেও", "দে", "দেন", "পাঠান", "পাঠাও", "চাই", "খুঁজছি", "খুজছি", "dao", "deo", "de", "den", "pathao", "pathan", "chai"]
    media_words = ["ভিডিও", "নাটক", "গান", "মুভি", "সিনেমা", "ওয়াজ", "video", "natok", "gan", "movie", "waz"]

    has_ask = any(w in t_lower for w in ask_words)
    has_media = any(w in t_lower for w in media_words)

    # যদি ইউজার কোনো কন্টেন্ট খোঁজে
    if (has_ask and has_media) or (has_media and len(text.split()) >= 2):
        wait_msg = await update.message.reply_text("অবশ্যই 😎\nএকটু অপেক্ষা করুন, দিচ্ছি..... ⏳")
        content_item = await search_media(text)

        if content_item:
            caption = f"🎬 *{content_item.title}*\n📂 ক্যাটাগরি: {content_item.category}"
            keyboard = attach_ad_to_keyboard()
            try:
                if content_item.media_type == "video":
                    await context.bot.send_video(chat_id=user_id, video=content_item.file_id, caption=caption, reply_markup=keyboard, parse_mode="Markdown")
                elif content_item.media_type == "audio":
                    await context.bot.send_audio(chat_id=user_id, audio=content_item.file_id, caption=caption, reply_markup=keyboard, parse_mode="Markdown")
                elif content_item.media_type == "photo":
                    await context.bot.send_photo(chat_id=user_id, photo=content_item.file_id, caption=caption, reply_markup=keyboard, parse_mode="Markdown")
                else:
                    await context.bot.send_document(chat_id=user_id, document=content_item.file_id, caption=caption, reply_markup=keyboard, parse_mode="Markdown")
                
                await wait_msg.delete()
                return
            except Exception:
                pass

        # ডাটাবেসে না থাকলে
        await wait_msg.delete()
        async with AsyncSessionLocal() as session:
            req = ContentRequest(user_id=user_id, username=update.effective_user.username, query=text)
            session.add(req)
            await session.commit()

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🔔 *Content Request*\n\n👤 User: @{update.effective_user.username or user_id}\n🔎 Requested: `{text}`\n❌ Status: Not Found",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        not_found_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📂 Available Content", callback_data="btn_categories_list")],
            [InlineKeyboardButton("🔎 Search Again", callback_data="btn_search_prompt")]
        ])
        await update.message.reply_text(
            f"😔 Sorry! আপনার চাওয়া অনুযায়ী এই content এখনো আমার database-এ যোগ করা হয়নি।\n\n"
            f"আমি বিষয়টি আমার বস @{ADMIN_USERNAME}-কে জানিয়ে দিয়েছি। 👑\n"
            f"তবে আপনি চাইলে আমাদের available content দেখতে পারেন। 👇",
            reply_markup=not_found_markup
        )
        return

    # ৩. ন্যাচারাল রিমাইন্ডার হ্যান্ডলিং
    time_match = re.search(r"(\d{1,2})[^\d]*([০-৯]{0,2})?\s*(টায়|টা|am|pm|ঘন্টায়)", text, re.IGNORECASE)
    if ("মনে করিয়ে" in text or "রিমাইন্ডার" in text or "remind" in text.lower()) and time_match:
        hour = int(time_match.group(1))
        if any(w in text for w in ["সন্ধ্যা", "রাত", "বিকাল", "দুপুর"]) and hour < 12:
            hour += 12
        elif "সকাল" in text and hour == 12:
            hour = 0
            
        rem_type = "custom"
        if any(w in text.lower() for w in ["পড়া", "study"]): rem_type = "study"
        elif any(w in text.lower() for w in ["খেলা", "play"]): rem_type = "play"
        elif any(w in text.lower() for w in ["কাজ", "work"]): rem_type = "work"
        elif any(w in text.lower() for w in ["ঘুমা", "sleep"]): rem_type = "sleep"
        elif any(w in text.lower() for w in ["খাবার", "food"]): rem_type = "food"

        schedule_str = f"{hour:02d}:00"
        async with AsyncSessionLocal() as session:
            new_rem = Reminder(user_id=user_id, reminder_type=rem_type, message=text, schedule_time=schedule_str, is_recurring=True)
            session.add(new_rem)
            await session.commit()
        
        await reload_reminders(context.bot)
        await update.message.reply_text(f"✅ ঠিক আছে! প্রতিদিন {schedule_str}-এ আপনাকে মনে করিয়ে দেওয়া হবে। ⏰")
        return

    # ৪. বাকি সব ক্ষেত্রে স্মার্ট AI চ্যাট
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    ai_reply = await get_ai_response(text)
    await update.message.reply_text(ai_reply)

# --- নোটিফিকেশন সেটিংস ---
async def notifications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.user_id == user_id))).scalars().first()

    def get_status_icon(val):
        return "✅ ON" if val else "❌ OFF"

    keyboard = [
        [InlineKeyboardButton(f"🕌 Prayer: {get_status_icon(user.prayer_notify)}", callback_data="toggle_prayer_notify")],
        [InlineKeyboardButton(f"🕐 Hourly: {get_status_icon(user.hourly_notify)}", callback_data="toggle_hourly_notify")],
        [InlineKeyboardButton(f"📚 Study: {get_status_icon(user.study_notify)}", callback_data="toggle_study_notify")],
        [InlineKeyboardButton(f"💼 Work: {get_status_icon(user.work_notify)}", callback_data="toggle_work_notify")],
        [InlineKeyboardButton(f"😴 Sleep: {get_status_icon(user.sleep_notify)}", callback_data="toggle_sleep_notify")],
        [InlineKeyboardButton(f"🌅 Wake-up: {get_status_icon(user.wake_notify)}", callback_data="toggle_wake_notify")]
    ]
    await update.message.reply_text("⚙️ *আপনার নোটিফিকেশন সেটিংস:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def toggle_notification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field_map = {
        "toggle_prayer_notify": "prayer_notify",
        "toggle_hourly_notify": "hourly_notify",
        "toggle_study_notify": "study_notify",
        "toggle_work_notify": "work_notify",
        "toggle_sleep_notify": "sleep_notify",
        "toggle_wake_notify": "wake_notify"
    }
    field = field_map.get(query.data)
    if field:
        await toggle_user_setting(query.from_user.id, field)
        await notifications_menu(update, context)
